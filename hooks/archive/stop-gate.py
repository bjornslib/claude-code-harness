#!/usr/bin/env python3
"""
LLM-Powered Stop Gate Hook

This hook acts as a true stage gate for session close, gathering objective
context and conversation history to make the blocking decision.

Architecture:
1. Extract transcript_path from hook input (conversation history)
2. Gather objective data (git status, todo list, beads status)
3. Analyze conversation context for session completeness
4. Return JSON decision to block or approve

Exit codes:
- 0 with JSON {"decision": "approve"} = Allow stop
- 0 with JSON {"decision": "block", "reason": "..."} = Block stop, force continuation

Hook Input (via stdin):
{
    "transcript_path": "~/.claude/projects/<project>/<session_id>.jsonl",
    "event": "Stop",
    ...
}
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_transcript_context(transcript_path: Optional[str]) -> dict:
    """
    Read the session transcript to understand conversation context.

    The transcript is a JSONL file containing the full message history,
    including any summaries from /compact or auto-compaction.
    """
    if not transcript_path:
        return {"available": False, "error": "No transcript_path provided"}

    try:
        path = Path(transcript_path).expanduser()
        if not path.exists():
            return {"available": False, "error": f"Transcript not found: {path}"}

        # Read last N lines of the JSONL file for recent context
        messages = []
        with open(path, "r") as f:
            lines = f.readlines()
            # Get last 2000 messages for broader context window
            recent_lines = lines[-2000:] if len(lines) > 2000 else lines

            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue

        # Extract key information from messages
        # Claude Code transcript format:
        # - Human messages: {"type": "user", "message": {"role": "user", "content": "text string"}}
        # - Tool results: {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", ...}]}}
        # - Assistant: {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", ...}]}}
        user_requests = []
        assistant_messages = []
        completion_indicators = []
        summaries = []

        for entry in messages:
            entry_type = entry.get("type", "")
            msg = entry.get("message", entry)
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Handle different content formats
            text = ""
            is_human_message = False

            if isinstance(content, str):
                # Direct string content = actual human message
                text = content
                is_human_message = True
            elif isinstance(content, list):
                # Array content - check for text blocks vs tool results
                texts = []
                has_tool_result = False
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            has_tool_result = True
                            # Skip tool results for user message extraction
                text = " ".join(texts)
                is_human_message = len(texts) > 0 and not has_tool_result

            # Categorize messages
            if entry_type == "user" and is_human_message and text:
                # This is actual human input, not tool results
                user_requests.append(text[:300])  # Truncate for context
            elif entry_type == "assistant" and text:
                # Collect all assistant messages for context
                assistant_messages.append(text[:400])  # Slightly longer for assistant context
                # Also track completion indicators separately
                if any(kw in text.lower() for kw in ["complete", "done", "finished", "pushed", "committed"]):
                    completion_indicators.append(text[:200])

            # Look for summary/compact markers
            if "summary" in text.lower() or "compact" in text.lower():
                summaries.append(text[:500])

        return {
            "available": True,
            "message_count": len(messages),
            "recent_user_requests": user_requests[-10:],  # Last 10 user requests
            "recent_assistant_messages": assistant_messages[-5:],  # Last 5 assistant messages
            "completion_indicators": completion_indicators[-5:],  # Last 5 completion mentions
            "has_summaries": len(summaries) > 0,
            "transcript_path": str(path),
        }

    except Exception as e:
        return {"available": False, "error": str(e)}


def get_git_status() -> dict:
    """Get git status information."""
    try:
        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=os.environ.get("CLAUDE_PROJECT_DIR", "."),
        )
        changes = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Filter for code files
        code_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".sql", ".md"}
        code_changes = []
        other_changes = []

        for change in changes:
            if not change:
                continue
            # Parse git status format: "XY filename"
            parts = change.split(maxsplit=1)
            if len(parts) >= 2:
                filename = parts[1].strip()
                ext = Path(filename).suffix
                if ext in code_extensions:
                    code_changes.append(change)
                else:
                    other_changes.append(change)

        return {
            "has_uncommitted_code": len(code_changes) > 0,
            "code_changes": code_changes[:10],  # Limit to first 10
            "code_change_count": len(code_changes),
            "other_changes": other_changes[:5],
            "other_change_count": len(other_changes),
        }
    except Exception as e:
        return {"error": str(e), "has_uncommitted_code": False}


def get_todo_status() -> dict:
    """Get todo list status from the todo file."""
    try:
        # Claude Code stores todos in ~/.claude/todos/
        todos_dir = Path.home() / ".claude" / "todos"
        if not todos_dir.exists():
            return {"has_todos": False, "has_continuation": False, "items": []}

        # Find the most recent todo file for this session
        todo_files = list(todos_dir.glob("*.json"))
        if not todo_files:
            return {"has_todos": False, "has_continuation": False, "items": []}

        # Sort by modification time (most recent first)
        sorted_files = sorted(todo_files, key=lambda p: p.stat().st_mtime, reverse=True)

        # Find first non-empty todo file (handles race with agent empty files)
        todos = []
        for todo_file in sorted_files[:10]:  # Check recent 10 files
            try:
                with open(todo_file) as f:
                    content = json.load(f)
                    if content:  # Non-empty
                        todos = content
                        break
            except (json.JSONDecodeError, IOError):
                continue

        if not todos:
            return {"has_todos": False, "has_continuation": False, "items": []}

        # Check for continuation items
        pending_or_in_progress = [
            t for t in todos if t.get("status") in ("pending", "in_progress")
        ]
        completed = [t for t in todos if t.get("status") == "completed"]

        # A continuation item is one that suggests future work
        # Includes "blocked" and "external" for external dependency cases
        continuation_keywords = [
            "check",
            "verify",
            "next",
            "continue",
            "follow",
            "await",
            "monitor",
            "blocked",
            "external",
        ]
        has_continuation = any(
            any(kw in t.get("content", "").lower() for kw in continuation_keywords)
            for t in pending_or_in_progress
        )

        return {
            "has_todos": True,
            "total_count": len(todos),
            "pending_count": len(pending_or_in_progress),
            "completed_count": len(completed),
            "has_continuation": has_continuation or len(pending_or_in_progress) > 0,
            "pending_items": [t.get("content", "") for t in pending_or_in_progress[:5]],
        }
    except Exception as e:
        return {"error": str(e), "has_todos": False, "has_continuation": False}


def get_beads_status() -> dict:
    """Check if beads needs syncing."""
    try:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
        beads_dir = Path(project_dir) / ".beads"

        if not beads_dir.exists():
            return {"has_beads": False, "needs_sync": False}

        # Check git status for .beads directory
        result = subprocess.run(
            ["git", "status", "--porcelain", ".beads/"],
            capture_output=True,
            text=True,
            cwd=project_dir,
        )

        changes = result.stdout.strip().split("\n") if result.stdout.strip() else []
        modified_files = [c for c in changes if c.strip()]

        return {
            "has_beads": True,
            "needs_sync": len(modified_files) > 0,
            "modified_files": modified_files[:5],
        }
    except Exception as e:
        return {"error": str(e), "has_beads": False, "needs_sync": False}


def get_business_outcome_status() -> dict:
    """
    Check business outcome context: ready work, Key Results, Business Epics.

    This enables System 3's OKR-Driven Development pattern - the stop hook
    should consider whether there's high-priority work that advances
    business outcomes before allowing a session to close.
    """
    try:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")

        # Check for ready P0/P1 work via bd ready
        result = subprocess.run(
            ["bd", "ready", "--priority=1"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=5,
        )

        ready_lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        ready_p1_work = []

        for line in ready_lines[:5]:  # First 5 ready items
            # Filter out non-task lines (headers, "No ready work" messages)
            # Task lines contain [P0], [P1], [P2] priority indicators
            if line and "[P" in line and "]" in line:
                ready_p1_work.append(line.strip())

        # Check for Business Epics (tag=bo)
        bo_result = subprocess.run(
            ["bd", "list", "--status=open"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=5,
        )

        bo_lines = [l for l in bo_result.stdout.strip().split("\n") if "[bo]" in l]
        business_epics = [l.strip() for l in bo_lines[:3]]

        # Check for Key Results (tag=kr)
        kr_lines = [l for l in bo_result.stdout.strip().split("\n") if "[kr]" in l]
        key_results = [l.strip() for l in kr_lines[:5]]

        return {
            "has_ready_p1_work": len(ready_p1_work) > 0,
            "ready_p1_work": ready_p1_work,
            "ready_p1_count": len(ready_p1_work),
            "business_epics": business_epics,
            "key_results": key_results,
            "key_result_count": len(key_results),
        }
    except subprocess.TimeoutExpired:
        return {"error": "bd command timed out", "has_ready_p1_work": False}
    except FileNotFoundError:
        return {"error": "bd command not found", "has_ready_p1_work": False}
    except Exception as e:
        return {"error": str(e), "has_ready_p1_work": False}


def make_decision(git_status: dict, todo_status: dict, beads_status: dict, business_outcome_status: dict = None) -> dict:
    """Make blocking decision based on gathered context."""
    required_actions = []
    business_outcome_status = business_outcome_status or {}
    checklist = {
        "todo_continuation": "pass",
        "git_status": "pass",
        "beads_sync": "pass",
        "business_outcomes": "pass",
        "session_learnings": "warn",  # Can't objectively check this
    }

    # Check 1: Todo continuation
    if not todo_status.get("has_continuation", False):
        checklist["todo_continuation"] = "fail"
        required_actions.append(
            "Add a continuation todo item (e.g., 'Check bd ready for next task')"
        )

    # Check 2: Git status - Warning only (not blocking)
    if git_status.get("has_uncommitted_code", False):
        checklist["git_status"] = "warn"
        required_actions.append(
            f"Consider committing {git_status.get('code_change_count', 0)} uncommitted code changes"
        )

    # Check 3: Beads sync
    if beads_status.get("needs_sync", False):
        checklist["beads_sync"] = "fail"
        required_actions.append("Run 'bd sync' to sync beads changes")

    # Check 4: Business Outcomes (OKR-Driven Development)
    # Environment variable controls enforcement level:
    # - CLAUDE_ENFORCE_BO=true  -> Block session if P1 work available (focused work mode)
    # - CLAUDE_ENFORCE_BO=false or unset -> Warn only (exploratory mode)
    enforce_bo = os.environ.get("CLAUDE_ENFORCE_BO", "").lower() in ("true", "1", "yes")

    if business_outcome_status.get("has_ready_p1_work", False):
        bo_count = len(business_outcome_status.get("business_epics", []))
        kr_count = business_outcome_status.get("key_result_count", 0)
        p1_count = business_outcome_status.get("ready_p1_count", 0)

        if enforce_bo:
            # Focused work mode: block until P1 work is addressed
            checklist["business_outcomes"] = "fail"
            required_actions.append(
                f"ENFORCED: {p1_count} ready P1 tasks must be progressed to advance {bo_count} Business Epic(s) with {kr_count} open Key Result(s)"
            )
        else:
            # Exploratory mode: warn only
            checklist["business_outcomes"] = "warn"
            required_actions.append(
                f"Consider: {p1_count} ready P1 tasks could advance {bo_count} Business Epic(s) with {kr_count} open Key Result(s)"
            )

    # Make decision
    failures = [k for k, v in checklist.items() if v == "fail"]

    if failures:
        return {
            "decision": "block",
            "reason": f"Session close blocked: {', '.join(failures)} checks failed",
            "checklist": checklist,
            "required_actions": required_actions,
            "context": {
                "git": git_status,
                "todos": todo_status,
                "beads": beads_status,
            },
        }
    else:
        return {
            "decision": "approve",
            "reason": "All mandatory checks passed. Session may close.",
            "checklist": checklist,
            "required_actions": [],
        }


def main():
    """Main entry point."""
    # Read hook input from stdin (Claude Code passes context including transcript_path)
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Extract transcript path from hook input
    transcript_path = hook_input.get("transcript_path")

    # Gather all context
    transcript_context = get_transcript_context(transcript_path)
    git_status = get_git_status()
    todo_status = get_todo_status()
    beads_status = get_beads_status()
    business_outcome_status = get_business_outcome_status()

    # Make decision (rule-based checks for mandatory items)
    decision = make_decision(git_status, todo_status, beads_status, business_outcome_status)

    # Add transcript context to output for visibility
    decision["transcript_context"] = {
        "available": transcript_context.get("available", False),
        "message_count": transcript_context.get("message_count", 0),
        "recent_user_requests": transcript_context.get("recent_user_requests", []),
        "recent_assistant_messages": transcript_context.get("recent_assistant_messages", []),
        "has_completion_indicators": len(transcript_context.get("completion_indicators", [])) > 0,
    }

    # Add business outcome context for LLM reasoning
    # This enables System 3's OKR-Driven Development - the LLM can reason about
    # whether there's high-priority work that advances business outcomes
    enforce_bo = os.environ.get("CLAUDE_ENFORCE_BO", "").lower() in ("true", "1", "yes")
    decision["business_outcome_context"] = {
        "enforcement_mode": "focused_work" if enforce_bo else "exploratory",
        "enforce_bo_env_var": enforce_bo,
        "has_ready_p1_work": business_outcome_status.get("has_ready_p1_work", False),
        "ready_p1_count": business_outcome_status.get("ready_p1_count", 0),
        "ready_p1_work": business_outcome_status.get("ready_p1_work", []),
        "business_epics": business_outcome_status.get("business_epics", []),
        "key_results": business_outcome_status.get("key_results", []),
        "key_result_count": business_outcome_status.get("key_result_count", 0),
    }

    # Add LLM reasoning prompt for business outcomes
    if business_outcome_status.get("has_ready_p1_work", False):
        decision["llm_reasoning_prompt"] = (
            f"IMPORTANT: There are {business_outcome_status.get('ready_p1_count', 0)} ready P0/P1 tasks "
            f"that could advance business outcomes. Before closing this session, consider: "
            f"Should you continue working on these high-priority items? "
            f"Ready work: {business_outcome_status.get('ready_p1_work', [])}"
        )

    # Add hook input info for debugging
    decision["hook_input_keys"] = list(hook_input.keys())

    # Output JSON decision
    print(json.dumps(decision, indent=2))

    # Exit 0 - the decision JSON controls blocking, not exit code
    sys.exit(0)


if __name__ == "__main__":
    main()
