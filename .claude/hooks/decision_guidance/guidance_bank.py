"""Guidance bank: Short, situational micro-prompts.

These are the actual guidance messages injected at decision time.
Each guidance is:
- Short and focused on ONE decision
- Actionable with specific suggestions
- Ephemeral (doesn't persist in context)
"""

from typing import Optional


class GuidanceBank:
    """Bank of micro-prompts for decision-time injection."""

    # Maximum number of guidance to inject at once
    # (Replit found diminishing returns after 2-3)
    MAX_CONCURRENT_GUIDANCE = 2

    GUIDANCE = {
        "error_recovery": {
            "priority": 1,
            "template": """
## Decision-Time Guidance: Error Pattern Detected

{error_count} errors in the last {window_minutes} minutes.

**Recent errors:**
{error_messages}

**Before continuing, consider:**
1. Read the error messages carefully - they often contain the solution
2. Check your assumptions - is the file/path/command correct?
3. Try a different approach if the same one keeps failing

*If you've tried 3+ different approaches without success, consider consulting System3 for guidance.*
""",
        },
        "doom_loop": {
            "priority": 2,
            "template": """
## Decision-Time Guidance: Potential Doom Loop

Same file(s) edited multiple times without progress:
{file_details}

**This pattern suggests:**
- The underlying approach may be wrong
- There may be a missing dependency or prerequisite
- The problem might need a different solution

**Recommended actions:**
1. Step back and reconsider the approach
2. Check if tests are failing for a different reason than you think
3. Consider asking System3 for a fresh perspective

*Don't keep editing the same file - try something different.*
""",
        },
        "consult_system3": {
            "priority": 3,
            "template": """
## Decision-Time Guidance: Consultation Recommended

{reason}

**Escalate to System3 via beads:**
```bash
bd update <id> --status=impl_complete
```

**Why consult?**
- A fresh perspective from a different model often recognizes solutions the stuck agent cannot
- System3 can provide strategic guidance without the failed attempts polluting its context

*Update the bead status and wait for System3 to pick it up.*
""",
        },
        "delegation_reminder": {
            "priority": 4,
            "template": """
## Decision-Time Guidance: Delegation Check

You're about to use {tool_name} as an orchestrator.

**STOP and verify:**
- Is this INVESTIGATION (Read/Grep/Glob)? -> Proceed
- Is this IMPLEMENTATION (Edit/Write)? -> Delegate via tmux

**If implementation is needed:**
```bash
tmux new-session -d -s worker-{task_id}
tmux send-keys -t worker-{task_id} "claude" Enter
# Delegate task via native Agent Teams
```

*Orchestrators coordinate, workers implement. No exceptions.*
""",
        },
        "not_found_reminder": {
            "priority": 5,
            "template": """
## Decision-Time Guidance: Resource Not Found

The tool reported a file or resource was not found.

**Common causes:**
1. Path is incorrect (typo, wrong directory)
2. File was moved or renamed
3. File hasn't been created yet

**Actions:**
1. Use Glob to search for similar filenames
2. Check if you're in the right directory
3. Re-read the original context to verify the path

*Don't assume paths are correct - verify them.*
""",
        },
        "worker_failure": {
            "priority": 2,
            "template": """
## Decision-Time Guidance: Worker Failed

Worker {worker_id} failed on task {task_id}.

**Failure details:**
{failure_details}

**Before retrying with the same approach:**
1. Check if the worker's approach was correct
2. Consider if prerequisites are missing
3. Consult System3 for alternative strategies

**To consult System3:**
```bash
bd update <id> --status=impl_complete
```

*A fresh perspective often recognizes solutions the stuck agent cannot generate.*
""",
        },
        "orchestrator_blocker": {
            "priority": 1,
            "template": """
## Decision-Time Guidance: Unescalated Blocker

You have blockers that should be escalated before stopping:

{blocker_list}

**Required action:**
1. Escalate to System3 via beads:
   ```bash
   bd update <id> --status=impl_complete
   ```
2. Or mark as external dependency if truly external

*Orchestrators should escalate blockers, not silently stop.*
""",
        },
    }

    @classmethod
    def get_guidance(
        cls,
        key: str,
        **kwargs,
    ) -> Optional[str]:
        """Get formatted guidance message.

        Args:
            key: Guidance key (e.g., "error_recovery")
            **kwargs: Template variables

        Returns:
            Formatted guidance string, or None if key not found.
        """
        guidance = cls.GUIDANCE.get(key)
        if not guidance:
            return None

        template = guidance["template"]
        try:
            return template.format(**kwargs)
        except KeyError:
            # Return template with unfilled placeholders visible
            return template

    @classmethod
    def get_priority(cls, key: str) -> int:
        """Get priority of a guidance (lower = higher priority)."""
        guidance = cls.GUIDANCE.get(key)
        return guidance["priority"] if guidance else 999

    @classmethod
    def select_guidance(
        cls,
        candidates: list[tuple[str, dict]],
        max_count: int = None,
    ) -> list[str]:
        """Select guidance to inject from candidates.

        Respects priority ordering and max concurrent limit.

        Args:
            candidates: List of (key, kwargs) tuples
            max_count: Maximum guidance to return (default: MAX_CONCURRENT_GUIDANCE)

        Returns:
            List of formatted guidance strings.
        """
        if max_count is None:
            max_count = cls.MAX_CONCURRENT_GUIDANCE

        # Sort by priority
        sorted_candidates = sorted(
            candidates,
            key=lambda x: cls.get_priority(x[0])
        )

        results = []
        for key, kwargs in sorted_candidates[:max_count]:
            guidance = cls.get_guidance(key, **kwargs)
            if guidance:
                results.append(guidance)

        return results
