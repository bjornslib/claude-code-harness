"""Identity Registry — Agent liveness and identity tracking.

Provides atomic file-based identity records for all agents (orchestrator, runner,
guardian). Each agent writes its own identity on startup and updates heartbeat
timestamps during execution.

Identity files are JSON documents written atomically using the write-then-rename
pattern (same as signal_protocol.py). They are stored per-agent in
{state_dir}/{role}-{name}.json.

Identity File Schema:
    {
        "agent_id": "{role}-{name}-{timestamp}",
        "role": "orchestrator",
        "name": "impl_auth",
        "session_id": "orch-impl_auth",
        "worktree": ".claude/worktrees/impl_auth",
        "status": "active",
        "created_at": "2026-02-26T12:00:00Z",
        "last_heartbeat": "2026-02-26T12:05:00Z",
        "crashed_at": null,
        "terminated_at": null,
        "predecessor_id": null,
        "metadata": {}
    }

Directory Resolution (in order of precedence):
    1. Explicit ``state_dir`` argument
    2. ``ATTRACTOR_STATE_DIR`` environment variable (identities/ subdirectory)
    3. ``{git_root}/.claude/state/identities/`` (found via .git walk)
    4. ``~/.claude/state/identities/`` (fallback)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------

def _find_git_root(start: str) -> Optional[str]:
    """Walk up directory tree to find .git root. Returns None if not found."""
    current = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _identity_dir(state_dir: Optional[str] = None) -> str:
    """Resolve the identities state directory.

    Resolution order:
    1. Explicit ``state_dir`` argument (used as-is)
    2. ``ATTRACTOR_STATE_DIR`` env var + /identities/ subdirectory
    3. ``{git_root}/.claude/state/identities/``
    4. ``~/.claude/state/identities/`` (fallback)

    Args:
        state_dir: Explicit state directory override.

    Returns:
        Absolute path to the identities directory.
    """
    if state_dir is not None:
        return state_dir

    env_dir = os.environ.get("ATTRACTOR_STATE_DIR")
    if env_dir:
        return os.path.join(env_dir, "identities")

    git_root = _find_git_root(os.getcwd())
    if git_root:
        return os.path.join(git_root, ".claude", "state", "identities")

    return os.path.join(os.path.expanduser("~"), ".claude", "state", "identities")


def _identity_path(role: str, name: str, state_dir: Optional[str] = None) -> str:
    """Return the path for an identity file."""
    return os.path.join(_identity_dir(state_dir), f"{role}-{name}.json")


def _now_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_agent_id(role: str, name: str) -> str:
    """Generate a unique agent ID from role, name, and current timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{role}-{name}-{ts}"


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def _write_identity(data: dict, path: str) -> None:
    """Write identity data to path atomically (write to .tmp, then rename).

    Args:
        data: Identity dict to serialise.
        path: Destination path for the identity JSON file.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp_path, path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_identity(
    role: str,
    name: str,
    session_id: str,
    worktree: str,
    predecessor_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    state_dir: Optional[str] = None,
) -> dict:
    """Create a new identity record for an agent.

    Writes a new identity file at ``{state_dir}/{role}-{name}.json``.
    Overwrites any existing identity with the same role+name.

    Args:
        role: Agent role (e.g., "orchestrator", "runner", "guardian").
        name: Agent name / node identifier (e.g., "impl_auth").
        session_id: Session identifier (e.g., "orch-impl_auth").
        worktree: Worktree path (e.g., ".claude/worktrees/impl_auth").
        predecessor_id: agent_id of the previous instance (for respawn tracking).
        metadata: Arbitrary extra data to embed in the identity.
        state_dir: Override the default identities directory.

    Returns:
        The created identity dict.
    """
    now = _now_iso()
    data = {
        "agent_id": _make_agent_id(role, name),
        "role": role,
        "name": name,
        "session_id": session_id,
        "worktree": worktree,
        "status": "active",
        "created_at": now,
        "last_heartbeat": now,
        "crashed_at": None,
        "terminated_at": None,
        "predecessor_id": predecessor_id,
        "metadata": metadata or {},
    }
    path = _identity_path(role, name, state_dir)
    _write_identity(data, path)
    return data


def read_identity(
    role: str,
    name: str,
    state_dir: Optional[str] = None,
) -> Optional[dict]:
    """Read an existing identity record.

    Args:
        role: Agent role.
        name: Agent name.
        state_dir: Override the default identities directory.

    Returns:
        Identity dict, or None if the file does not exist.
    """
    path = _identity_path(role, name, state_dir)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def update_liveness(
    role: str,
    name: str,
    state_dir: Optional[str] = None,
) -> dict:
    """Update the last_heartbeat timestamp of an active identity.

    Reads the current identity, updates last_heartbeat, and writes atomically.
    Creates a new identity if none exists (idempotent for re-registration).

    Args:
        role: Agent role.
        name: Agent name.
        state_dir: Override the default identities directory.

    Returns:
        Updated identity dict.

    Raises:
        FileNotFoundError: If no identity file exists for this role+name.
    """
    path = _identity_path(role, name, state_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No identity found for {role}/{name}. Call create_identity() first."
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["last_heartbeat"] = _now_iso()
    _write_identity(data, path)
    return data


def mark_crashed(
    role: str,
    name: str,
    state_dir: Optional[str] = None,
) -> dict:
    """Mark an agent as crashed.

    Sets status to "crashed" and records crashed_at timestamp.

    Args:
        role: Agent role.
        name: Agent name.
        state_dir: Override the default identities directory.

    Returns:
        Updated identity dict.

    Raises:
        FileNotFoundError: If no identity file exists for this role+name.
    """
    path = _identity_path(role, name, state_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No identity found for {role}/{name}. Call create_identity() first."
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["status"] = "crashed"
    data["crashed_at"] = _now_iso()
    _write_identity(data, path)
    return data


def mark_terminated(
    role: str,
    name: str,
    state_dir: Optional[str] = None,
) -> dict:
    """Mark an agent as cleanly terminated.

    Sets status to "terminated" and records terminated_at timestamp.

    Args:
        role: Agent role.
        name: Agent name.
        state_dir: Override the default identities directory.

    Returns:
        Updated identity dict.

    Raises:
        FileNotFoundError: If no identity file exists for this role+name.
    """
    path = _identity_path(role, name, state_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No identity found for {role}/{name}. Call create_identity() first."
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["status"] = "terminated"
    data["terminated_at"] = _now_iso()
    _write_identity(data, path)
    return data


def list_all(state_dir: Optional[str] = None) -> list[dict]:
    """List all identity records in the identities directory.

    Args:
        state_dir: Override the default identities directory.

    Returns:
        List of identity dicts, sorted by agent_id (creation order).
        Returns empty list if the directory does not exist.
    """
    directory = _identity_dir(state_dir)
    if not os.path.isdir(directory):
        return []

    results = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return []

    for fname in sorted(entries):
        if not fname.endswith(".json"):
            continue
        if fname.endswith(".tmp"):
            continue
        full_path = os.path.join(directory, fname)
        try:
            with open(full_path, encoding="utf-8") as fh:
                data = json.load(fh)
            results.append(data)
        except (json.JSONDecodeError, OSError):
            # Skip unreadable files
            continue

    return results


def find_stale(
    timeout_seconds: int = 300,
    state_dir: Optional[str] = None,
) -> list[dict]:
    """Find active agents whose last_heartbeat is older than timeout_seconds.

    Only considers agents with status "active" — crashed/terminated agents are
    not considered stale.

    Args:
        timeout_seconds: How many seconds since last_heartbeat before stale.
        state_dir: Override the default identities directory.

    Returns:
        List of stale identity dicts.
    """
    now = datetime.now(timezone.utc)
    stale = []

    for identity in list_all(state_dir):
        if identity.get("status") != "active":
            continue

        last_hb_str = identity.get("last_heartbeat")
        if not last_hb_str:
            continue

        try:
            # Parse ISO 8601 with Z suffix
            last_hb = datetime.strptime(last_hb_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

        age_seconds = (now - last_hb).total_seconds()
        if age_seconds > timeout_seconds:
            stale.append(identity)

    return stale
