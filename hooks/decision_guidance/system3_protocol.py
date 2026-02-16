"""System3 guidance protocol for orchestrator consultation.

When orchestrators are blocked or stuck, they can request guidance from System3.
This module provides:
1. Guidance request formatting
2. State tracking for pending requests
3. Response processing

The protocol uses the message bus for communication:
- Orchestrator sends: mb-send system3 '{"type": "guidance_request", ...}'
- System3 responds via: mb-send <orch-id> '{"type": "guidance_response", ...}'
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class GuidanceRequest:
    """A request for guidance from System3."""

    request_id: str
    session_id: str
    context: str  # "error_pattern", "worker_failure", "doom_loop", "blocked"
    details: dict
    timestamp: float
    status: str = "pending"  # pending, sent, received, applied

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GuidanceRequest":
        return cls(**data)

    def to_message_bus_payload(self) -> str:
        """Format as message bus payload."""
        return json.dumps({
            "type": "guidance_request",
            "request_id": self.request_id,
            "session_id": self.session_id,
            "context": self.context,
            "details": self.details,
            "timestamp": self.timestamp,
        })


@dataclass
class GuidanceResponse:
    """A response from System3 with guidance."""

    request_id: str
    guidance: str
    suggested_actions: list[str]
    priority: str  # "urgent", "normal", "advisory"
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GuidanceResponse":
        return cls(**data)


class GuidanceProtocol:
    """Manage guidance requests and responses between orchestrators and System3."""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"

        self.state_dir = state_dir
        self.requests_file = state_dir / "guidance-requests.json"
        self.responses_file = state_dir / "guidance-responses.json"
        self.session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    def _load_requests(self) -> list[GuidanceRequest]:
        """Load pending guidance requests."""
        if self.requests_file.exists():
            try:
                with open(self.requests_file, "r") as f:
                    data = json.load(f)
                    return [GuidanceRequest.from_dict(r) for r in data.get("requests", [])]
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_requests(self, requests: list[GuidanceRequest]) -> None:
        """Save guidance requests."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.requests_file, "w") as f:
            json.dump({"requests": [r.to_dict() for r in requests]}, f, indent=2)

    def _load_responses(self) -> list[GuidanceResponse]:
        """Load guidance responses."""
        if self.responses_file.exists():
            try:
                with open(self.responses_file, "r") as f:
                    data = json.load(f)
                    return [GuidanceResponse.from_dict(r) for r in data.get("responses", [])]
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_responses(self, responses: list[GuidanceResponse]) -> None:
        """Save guidance responses."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.responses_file, "w") as f:
            json.dump({"responses": [r.to_dict() for r in responses]}, f, indent=2)

    def create_request(
        self,
        context: str,
        details: dict,
    ) -> GuidanceRequest:
        """Create a new guidance request.

        Args:
            context: The type of situation ("error_pattern", "worker_failure", etc.)
            details: Additional context about the situation

        Returns:
            GuidanceRequest ready to be sent via message bus.
        """
        import uuid

        request = GuidanceRequest(
            request_id=str(uuid.uuid4())[:8],
            session_id=self.session_id,
            context=context,
            details=details,
            timestamp=time.time(),
            status="pending",
        )

        # Save request
        requests = self._load_requests()
        requests.append(request)
        self._save_requests(requests)

        return request

    def mark_request_sent(self, request_id: str) -> None:
        """Mark a request as sent."""
        requests = self._load_requests()
        for r in requests:
            if r.request_id == request_id:
                r.status = "sent"
                break
        self._save_requests(requests)

    def record_response(self, response: GuidanceResponse) -> None:
        """Record a response from System3."""
        responses = self._load_responses()
        responses.append(response)
        self._save_responses(responses)

        # Update corresponding request status
        requests = self._load_requests()
        for r in requests:
            if r.request_id == response.request_id:
                r.status = "received"
                break
        self._save_requests(requests)

    def get_pending_requests(self) -> list[GuidanceRequest]:
        """Get requests that haven't received responses yet."""
        requests = self._load_requests()
        return [r for r in requests if r.status in ("pending", "sent")]

    def get_unread_responses(self) -> list[GuidanceResponse]:
        """Get responses that haven't been applied yet."""
        responses = self._load_responses()
        requests = self._load_requests()
        applied_ids = {r.request_id for r in requests if r.status == "applied"}
        return [r for r in responses if r.request_id not in applied_ids]

    def mark_response_applied(self, request_id: str) -> None:
        """Mark a response as applied."""
        requests = self._load_requests()
        for r in requests:
            if r.request_id == request_id:
                r.status = "applied"
                break
        self._save_requests(requests)

    def generate_guidance_command(self, request: GuidanceRequest) -> str:
        """Generate the mb-send command for a guidance request."""
        payload = request.to_message_bus_payload()
        return f"mb-send system3 '{payload}'"

    def format_response_for_injection(self, response: GuidanceResponse) -> str:
        """Format a guidance response for context injection."""
        actions = "\n".join(f"- {a}" for a in response.suggested_actions)

        priority_emoji = {
            "urgent": "🚨",
            "normal": "💡",
            "advisory": "ℹ️",
        }.get(response.priority, "💡")

        return f"""
## {priority_emoji} Guidance from System3

{response.guidance}

**Suggested Actions:**
{actions}

*Response to request {response.request_id}. Consider these suggestions before continuing.*
"""


def create_worker_failure_request(
    worker_id: str,
    task_id: str,
    failure_details: str,
) -> str:
    """Helper to create a worker failure guidance request.

    Returns the mb-send command to run.
    """
    protocol = GuidanceProtocol()
    request = protocol.create_request(
        context="worker_failure",
        details={
            "worker_id": worker_id,
            "task_id": task_id,
            "failure_details": failure_details,
        },
    )
    return protocol.generate_guidance_command(request)


def create_error_pattern_request(
    error_count: int,
    error_types: list[str],
    recent_messages: list[str],
) -> str:
    """Helper to create an error pattern guidance request.

    Returns the mb-send command to run.
    """
    protocol = GuidanceProtocol()
    request = protocol.create_request(
        context="error_pattern",
        details={
            "error_count": error_count,
            "error_types": error_types,
            "recent_messages": recent_messages,
        },
    )
    return protocol.generate_guidance_command(request)


def create_blocked_request(
    blockers: list[str],
    attempted_solutions: list[str],
) -> str:
    """Helper to create a blocked/stuck guidance request.

    Returns the mb-send command to run.
    """
    protocol = GuidanceProtocol()
    request = protocol.create_request(
        context="blocked",
        details={
            "blockers": blockers,
            "attempted_solutions": attempted_solutions,
        },
    )
    return protocol.generate_guidance_command(request)
