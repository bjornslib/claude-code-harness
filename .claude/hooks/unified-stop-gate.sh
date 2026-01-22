#!/bin/bash
# unified-stop-gate.sh
# Stop hook that enforces completion promise checking
#
# This hook:
# 1. Runs the unified_stop_gate Python package
# 2. Blocks if in_progress promises exist (especially when CLAUDE_SESSION_ID not set)
# 3. Provides actionable feedback on how to proceed
#
# Usage: Called by Claude Code as a Stop hook

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Read JSON from stdin (Claude Code passes context)
INPUT=$(cat)

# Run the unified stop gate as a Python package
# We need to set PYTHONPATH so the relative imports work
cd "$PROJECT_ROOT"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run the evaluator
echo "$INPUT" | python3 << 'PYTHON_SCRIPT'
import json
import sys
import os
import subprocess
from pathlib import Path

# Setup paths
project_root = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
hooks_dir = project_root / '.claude' / 'hooks' / 'unified_stop_gate'

# Add hooks dir to path for imports
sys.path.insert(0, str(hooks_dir.parent))

# Import from unified_stop_gate
from unified_stop_gate.checkers import SessionInfo, CompletionPromiseChecker
from unified_stop_gate.config import EnvironmentConfig, PathResolver, CheckResult


def get_beads_ready_work():
    """Run bd ready to find unblocked P0-P2 work."""
    try:
        result = subprocess.run(
            ["bd", "ready", "--limit=5"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None


def has_high_priority_work(ready_output: str) -> bool:
    """Check if ready work contains P0, P1, or P2 items."""
    if not ready_output:
        return False
    # Check for priority markers in the output
    return "[P0]" in ready_output or "[P1]" in ready_output or "[P2]" in ready_output


def get_fallback_session_id() -> str:
    """Generate a fallback session ID based on project dir when CLAUDE_SESSION_ID is not set."""
    import hashlib
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    # Use project dir hash + date for session isolation
    from datetime import datetime
    date_str = datetime.now().strftime('%Y%m%d')
    return f"fallback-{hashlib.md5(f'{project_dir}-{date_str}'.encode()).hexdigest()[:12]}"


def get_stop_marker_path(session_id: str) -> Path:
    """Get path to stop attempt marker file."""
    return Path(f"/tmp/claude-stop-momentum-{session_id}")


def get_stop_attempt_count(session_id: str) -> int:
    """Get the number of stop attempts within the last 5 minutes."""
    if not session_id:
        session_id = get_fallback_session_id()
    marker = get_stop_marker_path(session_id)
    if marker.exists():
        import time
        age_seconds = time.time() - marker.stat().st_mtime
        if age_seconds < 300:  # 5 minutes
            # Read the count from the file
            try:
                count = int(marker.read_text().strip())
                return count
            except (ValueError, OSError):
                return 1
        # Old marker, remove it
        marker.unlink()
    return 0


def should_allow_stop(session_id: str) -> bool:
    """Check if stop should be allowed (after 2 blocked attempts)."""
    if not session_id:
        session_id = get_fallback_session_id()
    return get_stop_attempt_count(session_id) >= 2


def mark_stop_attempt(session_id: str):
    """Mark that a stop attempt was blocked. Increments counter."""
    if not session_id:
        session_id = get_fallback_session_id()
    marker = get_stop_marker_path(session_id)
    current_count = get_stop_attempt_count(session_id)
    marker.write_text(str(current_count + 1))


def build_momentum_message(promise_message: str):
    """Build momentum check message with beads ready work."""
    ready_work = get_beads_ready_work()

    message_parts = [f"✅ {promise_message}"]

    if ready_work:
        message_parts.append("")
        message_parts.append("## 🚀 Momentum Check: Unblocked Work Available")
        message_parts.append("")
        message_parts.append("```")
        message_parts.append(ready_work)
        message_parts.append("```")
        message_parts.append("")
        message_parts.append("**Decision Framework:**")
        message_parts.append("- **Continue** if: P0-P2 beads ready, clear implementation path")
        message_parts.append("- **Stop** if: Only P3-P4 work, blocked on external factors, user feedback required")
        message_parts.append("IMPORTANT: If you are seriously blocked from progressing without user input, submit user option questions so that they can provide you with the necessary feedback")
        message_parts.append("If continuing: Add specific todos and proceed autonomously.")

    return "\n".join(message_parts)


def build_momentum_block_message(ready_work: str, attempt_num: int = 1):
    """Build message for blocking due to available high-priority work."""
    remaining = 2 - attempt_num + 1
    bypass_hint = f"*Attempt {attempt_num}/2. Stop {remaining} more time(s) to bypass.*" if remaining > 0 else ""

    return (
        "## 🚀 High-Priority Work Available - Continue Working!\n\n"
        f"```\n{ready_work}\n```\n\n"
        "**P0-P2 work is unblocked.** You should continue autonomously.\n\n"
        "Actions:\n"
        "1. Pick a task from the list above\n"
        "2. Add todos and proceed with implementation\n"
        "3. Only stop if genuinely blocked or user input required\n\n"
        "IMPORTANT: If you are seriously blocked from progressing without user input, "
        "submit user option questions so that they can provide you with the necessary feedback.\n\n"
        f"{bypass_hint}"
    )


def main():
    # Parse input
    try:
        input_text = sys.stdin.read()
        hook_input = json.loads(input_text) if input_text.strip() else {}
    except json.JSONDecodeError:
        hook_input = {}

    # Load configuration
    config = EnvironmentConfig.from_env()
    paths = PathResolver(config=config)
    session = SessionInfo.from_hook_input(hook_input)

    # Get session ID for stop attempt tracking
    session_id = os.environ.get('CLAUDE_SESSION_ID', '')

    # Run completion promise check
    checker = CompletionPromiseChecker(config, paths)
    result = checker.check()

    # Build output
    if not result.passed:
        # Block stop due to incomplete promises
        output = {
            "decision": "block",
            "reason": f"🚫 COMPLETION CRITERIA NOT MET\n\n{result.message}\n\n" +
                      "To proceed:\n" +
                      "1. Complete or verify your promises: cs-promise --mine\n" +
                      "2. Or adopt/cancel orphaned promises\n" +
                      "3. Session ID is auto-generated by ccsystem3"
        }
    else:
        # Promises passed - check for momentum block
        ready_work = get_beads_ready_work()

        if ready_work and has_high_priority_work(ready_work):
            # High-priority work exists
            if should_allow_stop(session_id):
                # Third attempt (after 2 blocks) - allow through with reminder
                output = {
                    "decision": "approve",
                    "systemMessage": f"✅ {result.message}\n\n(Momentum check bypassed after 2 blocked attempts)"
                }
            else:
                # First or second attempt - block and encourage continuation
                attempt_num = get_stop_attempt_count(session_id) + 1
                mark_stop_attempt(session_id)
                output = {
                    "decision": "block",
                    "reason": build_momentum_block_message(ready_work, attempt_num)
                }
        else:
            # No high-priority work - allow stop
            output = {
                "decision": "approve",
                "systemMessage": build_momentum_message(result.message)
            }

    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
PYTHON_SCRIPT
