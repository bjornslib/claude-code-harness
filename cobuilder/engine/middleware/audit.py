"""AuditMiddleware — writes tamper-evident audit entries before and after execution.

This middleware wraps ChainedAuditWriter from the anti_gaming subsystem.
The writer is injected via constructor to enable test injection.

Before calling next:
    Writes AuditEntry(from_status="pending", to_status="active").

After calling next:
    Writes AuditEntry(from_status="active", to_status=<outcome.status.value>).

ChainedAuditWriter failures are caught and logged — audit failure is non-fatal.
agent_id is read from context["$session_id"] if present.

AuditEntryProtocol / AuditWriterProtocol:
    When ChainedAuditWriter is not available (e.g. the pipeline package is not
    yet installed), the middleware accepts any writer that implements:
        writer.write(entry) -> None
    and any entry that has the required fields.  The built-in _StubAuditWriter
    is used when no writer is injected.
"""
from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol, TYPE_CHECKING

from cobuilder.engine.middleware.chain import HandlerRequest

if TYPE_CHECKING:
    from cobuilder.engine.outcome import Outcome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols — define the interface the middleware depends on
# ---------------------------------------------------------------------------

class AuditEntryProtocol(Protocol):
    """Minimal protocol for an audit entry object."""
    node_id: str
    from_status: str
    to_status: str
    agent_id: str
    prev_hash: str


class AuditWriterProtocol(Protocol):
    """Minimal protocol for an audit writer object."""

    def write(self, entry: Any) -> None:
        """Append entry to the audit trail."""
        ...


# ---------------------------------------------------------------------------
# _StubAuditWriter — no-op used when no writer is injected
# ---------------------------------------------------------------------------

class _StubAuditWriter:
    """No-op writer used when AuditMiddleware is constructed without a writer."""

    def write(self, entry: Any) -> None:
        return


# ---------------------------------------------------------------------------
# AuditEntry builder — produces a Pydantic model if available, else a dict
# ---------------------------------------------------------------------------

def _make_audit_entry(
    node_id: str,
    from_status: str,
    to_status: str,
    agent_id: str,
) -> Any:
    """Return an AuditEntry model or a simple namespace object.

    Tries to import AuditEntry from cobuilder.orchestration.runner_models.
    Falls back to a simple object if the import fails.
    """
    try:
        from cobuilder.orchestration.runner_models import AuditEntry
        return AuditEntry(
            node_id=node_id,
            from_status=from_status,
            to_status=to_status,
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        # Fallback: simple namespace.
        class _SimpleEntry:
            def __init__(self) -> None:
                self.node_id = node_id
                self.from_status = from_status
                self.to_status = to_status
                self.agent_id = agent_id
                self.prev_hash = ""
                self.timestamp = datetime.now(timezone.utc).isoformat()

            def model_dump_json(self) -> str:
                import json
                return json.dumps({
                    "node_id": self.node_id,
                    "from_status": self.from_status,
                    "to_status": self.to_status,
                    "agent_id": self.agent_id,
                    "prev_hash": self.prev_hash,
                    "timestamp": self.timestamp,
                })

        return _SimpleEntry()


# ---------------------------------------------------------------------------
# AuditMiddleware
# ---------------------------------------------------------------------------

class AuditMiddleware:
    """Writes two AuditEntry records per handler invocation.

    Record 1 (before execution): from_status="pending", to_status="active"
    Record 2 (after execution):  from_status="active",  to_status=<outcome status>

    ChainedAuditWriter is injected via constructor.  When None is provided a
    no-op stub writer is used.

    Args:
        writer: An object implementing write(entry) -> None.  Typically a
                ChainedAuditWriter from anti_gaming.  Defaults to _StubAuditWriter.
    """

    def __init__(self, writer: AuditWriterProtocol | None = None) -> None:
        self._writer: AuditWriterProtocol = writer if writer is not None else _StubAuditWriter()

    async def __call__(
        self,
        request: HandlerRequest,
        next: Callable[[HandlerRequest], Awaitable["Outcome"]],
    ) -> "Outcome":
        """Write before/after audit entries around the handler call."""
        node_id = request.node.id
        agent_id = str(request.context.get("$session_id", "unknown") or "unknown")

        # --- Pre-execution entry: pending → active ---
        pre_entry = _make_audit_entry(
            node_id=node_id,
            from_status="pending",
            to_status="active",
            agent_id=agent_id,
        )
        try:
            self._writer.write(pre_entry)
        except OSError as exc:
            logger.warning(
                "AuditMiddleware: pre-execution write failed for node '%s': %s",
                node_id, exc,
            )
        except Exception as exc:
            logger.warning(
                "AuditMiddleware: pre-execution write error for node '%s': %s",
                node_id, exc,
            )

        # --- Execute handler ---
        outcome = await next(request)

        # --- Post-execution entry: active → <outcome status> ---
        post_entry = _make_audit_entry(
            node_id=node_id,
            from_status="active",
            to_status=outcome.status.value,
            agent_id=agent_id,
        )
        try:
            self._writer.write(post_entry)
        except OSError as exc:
            logger.warning(
                "AuditMiddleware: post-execution write failed for node '%s': %s",
                node_id, exc,
            )
        except Exception as exc:
            logger.warning(
                "AuditMiddleware: post-execution write error for node '%s': %s",
                node_id, exc,
            )

        return outcome
