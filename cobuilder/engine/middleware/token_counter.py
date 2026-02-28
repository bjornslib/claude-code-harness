"""TokenCountingMiddleware — extracts token usage from Outcome.raw_messages.

After the handler returns, this middleware inspects Outcome.raw_messages for
SDK ResultMessage objects that carry usage data.  It accumulates:
  - context["$node_tokens"]:  tokens used by the most recently completed node.
  - context["$total_tokens"]: running sum across all completed nodes.

Then it emits a context.updated event if tokens changed.

SDK ResultMessage detection: checks hasattr(msg, 'usage') and
hasattr(msg.usage, 'input_tokens').  This avoids a hard import dependency on
the claude_code_sdk package.

This is a no-op when Outcome.raw_messages is empty.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, TYPE_CHECKING

from cobuilder.engine.middleware.chain import HandlerRequest

if TYPE_CHECKING:
    from cobuilder.engine.outcome import Outcome

logger = logging.getLogger(__name__)


class TokenCountingMiddleware:
    """Accumulates token usage from SDK messages into PipelineContext.

    Reads usage.input_tokens and usage.output_tokens from any message in
    Outcome.raw_messages that has a ``usage`` attribute.  Updates
    context["$node_tokens"] and context["$total_tokens"] accordingly.

    Emits a context.updated event when tokens are accumulated.
    """

    async def __call__(
        self,
        request: HandlerRequest,
        next: Callable[[HandlerRequest], Awaitable["Outcome"]],
    ) -> "Outcome":
        """Pass through to next; extract tokens from outcome.raw_messages."""
        from cobuilder.engine.events.types import EventBuilder

        outcome = await next(request)

        if not outcome.raw_messages:
            return outcome

        # Extract token counts from SDK ResultMessage objects.
        node_tokens = 0
        for msg in outcome.raw_messages:
            if hasattr(msg, "usage") and msg.usage is not None:
                usage = msg.usage
                input_tok = getattr(usage, "input_tokens", 0) or 0
                output_tok = getattr(usage, "output_tokens", 0) or 0
                node_tokens += int(input_tok) + int(output_tok)

        if node_tokens == 0:
            return outcome

        # Update context accumulators.
        prev_total = int(request.context.get("$total_tokens", 0) or 0)
        new_total = prev_total + node_tokens

        request.context.update({
            "$node_tokens": node_tokens,
            "$total_tokens": new_total,
        })

        # Emit context.updated event.
        emitter = request.emitter
        if emitter is not None:
            try:
                await emitter.emit(EventBuilder.context_updated(
                    pipeline_id=request.pipeline_id,
                    node_id=request.node.id,
                    keys_added=[],
                    keys_modified=["$node_tokens", "$total_tokens"],
                ))
            except Exception as exc:
                logger.warning(
                    "Failed to emit context.updated after token counting for %s: %s",
                    request.node.id,
                    exc,
                )

        return outcome
