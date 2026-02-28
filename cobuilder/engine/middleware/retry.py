"""RetryMiddleware — retries FAILURE outcomes with exponential back-off.

On each call:
1. Calls next(request) and checks Outcome.status.
2. If FAILURE and attempts < max_attempts:
   - Emits retry.triggered event.
   - Sleeps for exponential back-off: base_delay_s * 2^attempt seconds.
   - Increments request.attempt_number and retries.
3. After exhausting retries: returns the final FAILURE Outcome.
4. If next() raises an Exception (not a FAILURE outcome): propagates unless
   retry_on_exception=True is set.

max_attempts is resolved from:
  node.attrs.get("max_retries") → RetryMiddleware.default_max_retries (3).

Note: attempt_number in HandlerRequest is a frozen dataclass field, so we
create a new HandlerRequest with the updated attempt_number on each retry.
The middleware replaces HandlerRequest.attempt_number by reconstructing it.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Awaitable, Callable, TYPE_CHECKING

from cobuilder.engine.middleware.chain import HandlerRequest
from cobuilder.engine.outcome import OutcomeStatus

if TYPE_CHECKING:
    from cobuilder.engine.outcome import Outcome

logger = logging.getLogger(__name__)


class RetryMiddleware:
    """Retries FAILURE outcomes up to max_retries times with exponential back-off.

    Args:
        default_max_retries: Fallback max attempts when node has no max_retries
                             attribute.  Defaults to 3.
        base_delay_s:        Base back-off delay in seconds (doubles each attempt).
                             Defaults to 1.0.
        retry_on_exception:  If True, also retry when next() raises an Exception.
                             Defaults to False (exceptions propagate immediately).
    """

    default_max_retries: int = 3

    def __init__(
        self,
        default_max_retries: int = 3,
        base_delay_s: float = 1.0,
        retry_on_exception: bool = False,
    ) -> None:
        self.default_max_retries = default_max_retries
        self._base_delay_s = base_delay_s
        self._retry_on_exception = retry_on_exception

    async def __call__(
        self,
        request: HandlerRequest,
        next: Callable[[HandlerRequest], Awaitable["Outcome"]],
    ) -> "Outcome":
        """Execute with retry logic on FAILURE outcomes."""
        from cobuilder.engine.events.types import EventBuilder

        # Resolve max_attempts from node attribute or instance default.
        try:
            max_attempts = int(request.node.attrs.get("max_retries", self.default_max_retries))
        except (ValueError, TypeError, AttributeError):
            max_attempts = self.default_max_retries

        attempt = 0
        current_request = request

        while True:
            try:
                outcome = await next(current_request)
            except Exception as exc:
                if not self._retry_on_exception or attempt >= max_attempts:
                    raise
                # Retry on exception path.
                delay_s = self._base_delay_s * (2 ** attempt)
                emitter = request.emitter
                if emitter is not None:
                    try:
                        await emitter.emit(EventBuilder.retry_triggered(
                            pipeline_id=request.pipeline_id,
                            node_id=request.node.id,
                            attempt_number=attempt + 1,
                            backoff_ms=delay_s * 1000.0,
                            error_type=type(exc).__name__,
                        ))
                    except Exception as emit_exc:
                        logger.warning(
                            "Failed to emit retry.triggered for %s: %s",
                            request.node.id, emit_exc,
                        )
                await asyncio.sleep(delay_s)
                attempt += 1
                current_request = dataclasses.replace(current_request, attempt_number=attempt)
                continue

            # Outcome returned — check if it's a failure.
            if outcome.status != OutcomeStatus.FAILURE:
                return outcome

            # It's a FAILURE.  Check if we have retries left.
            if attempt >= max_attempts:
                return outcome

            # Emit retry.triggered and sleep.
            delay_s = self._base_delay_s * (2 ** attempt)
            emitter = request.emitter
            if emitter is not None:
                try:
                    await emitter.emit(EventBuilder.retry_triggered(
                        pipeline_id=request.pipeline_id,
                        node_id=request.node.id,
                        attempt_number=attempt + 1,
                        backoff_ms=delay_s * 1000.0,
                        error_type="FAILURE",
                    ))
                except Exception as emit_exc:
                    logger.warning(
                        "Failed to emit retry.triggered for %s: %s",
                        request.node.id, emit_exc,
                    )

            logger.info(
                "RetryMiddleware: node '%s' attempt %d/%d failed; "
                "retrying in %.1fs",
                request.node.id,
                attempt + 1,
                max_attempts,
                delay_s,
            )
            await asyncio.sleep(delay_s)
            attempt += 1
            current_request = dataclasses.replace(current_request, attempt_number=attempt)
