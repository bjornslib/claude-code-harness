"""Communicator active checker for the unified stop gate hook.

P1.5: Prevents System 3 from stopping while an active S3 Communicator
teammate is running in the s3-live team. The communicator is a heartbeat
agent that monitors orchestrators — System 3 must shut it down gracefully
before ending its session.

Only applies to System 3 sessions (session ID starts with 'system3-').
Non-System 3 sessions always pass this check.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .config import CheckResult, EnvironmentConfig, Priority


# Default team name where the S3 communicator lives
S3_LIVE_TEAM_NAME = "s3-live"

# Member name to look for in the team config
S3_COMMUNICATOR_MEMBER_NAME = "s3-communicator"


class CommunicatorActiveChecker:
    """P1.5: Check if an active S3 Communicator is running.

    Prevents System 3 from stopping while it has an active communicator
    teammate that should be gracefully shut down first. The communicator
    runs a heartbeat loop monitoring orchestrators — abandoning it leaves
    a zombie agent consuming resources.

    Only applies to System 3 sessions. All other session types pass immediately.

    Detection logic:
        1. Read ~/.claude/teams/s3-live/config.json
        2. Search members array for name == 's3-communicator'
        3. Check if isActive == true
        4. If active → BLOCK (must shut down communicator first)
        5. If not active / not found / no config → PASS
    """

    def __init__(self, config: EnvironmentConfig):
        """Initialize the checker.

        Args:
            config: Environment configuration (provides is_system3 check).
        """
        self.config = config

    def _get_team_config_path(self) -> Path:
        """Get the path to the s3-live team config file.

        Returns:
            Path to ~/.claude/teams/s3-live/config.json
        """
        return Path.home() / ".claude" / "teams" / S3_LIVE_TEAM_NAME / "config.json"

    def _find_communicator_member(self, team_config: dict) -> Optional[dict]:
        """Find the s3-communicator member in the team config.

        Args:
            team_config: Parsed team config JSON dictionary.

        Returns:
            The member dictionary if found, None otherwise.
        """
        members = team_config.get("members", [])
        for member in members:
            if member.get("name") == S3_COMMUNICATOR_MEMBER_NAME:
                return member
        return None

    def check(self) -> CheckResult:
        """Check if an active S3 Communicator is running.

        Returns:
            CheckResult with:
            - passed=True if not System 3, no config, no communicator, or communicator inactive
            - passed=False if System 3 AND communicator is active (BLOCK)
        """
        # Only applies to System 3 sessions
        if not self.config.is_system3:
            return CheckResult(
                priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
                passed=True,
                message="Not a System 3 session - communicator check skipped",
                blocking=False,
            )

        config_path = self._get_team_config_path()

        # No team config = no communicator running
        if not config_path.exists():
            return CheckResult(
                priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
                passed=True,
                message=f"No s3-live team config found at {config_path}",
                blocking=True,
            )

        # Read and parse team config
        try:
            with open(config_path, "r") as f:
                team_config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Fail-open: if we can't read the config, don't block
            return CheckResult(
                priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
                passed=True,
                message=f"Error reading s3-live team config (fail-open): {e}",
                blocking=True,
            )

        # Find the communicator member
        communicator = self._find_communicator_member(team_config)

        if communicator is None:
            return CheckResult(
                priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
                passed=True,
                message=f"No '{S3_COMMUNICATOR_MEMBER_NAME}' member found in s3-live team",
                blocking=True,
            )

        # Check if communicator is active
        is_active = communicator.get("isActive", False)

        if not is_active:
            return CheckResult(
                priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
                passed=True,
                message=f"S3 Communicator exists but is not active (isActive=False)",
                blocking=True,
            )

        # Communicator IS active — BLOCK System 3 from stopping
        agent_id = communicator.get("agentId", "unknown")
        agent_type = communicator.get("agentType", "unknown")

        return CheckResult(
            priority=Priority.P1_5_COMMUNICATOR_ACTIVE,
            passed=False,
            message=self._format_block_message(agent_id, agent_type),
            blocking=True,
        )

    def _format_block_message(self, agent_id: str, agent_type: str) -> str:
        """Format the blocking message with shutdown instructions.

        Args:
            agent_id: The communicator's agent ID.
            agent_type: The communicator's agent type.

        Returns:
            Formatted message with shutdown guidance.
        """
        return f"""S3 Communicator is ACTIVE - cannot stop session

An active S3 Communicator teammate is running:
  - Member: {S3_COMMUNICATOR_MEMBER_NAME}
  - Agent ID: {agent_id}
  - Type: {agent_type}
  - Team: {S3_LIVE_TEAM_NAME}

The communicator runs a heartbeat loop monitoring orchestrators.
Stopping System 3 without shutting it down leaves a zombie agent.

REQUIRED ACTIONS before stopping:

1. **Graceful shutdown** (preferred):
   ```python
   SendMessage(
       type="shutdown_request",
       recipient="{S3_COMMUNICATOR_MEMBER_NAME}",
       content="Session ending, please shut down gracefully"
   )
   ```

2. **Force shutdown** (if communicator is unresponsive):
   - Remove the member from s3-live team config
   - Kill the tmux pane if applicable

3. **Override**: If you've already initiated shutdown and are waiting
   for confirmation, try stopping again — this check will pass once
   the communicator's isActive flag is set to false."""
