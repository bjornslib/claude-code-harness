# Completion Promise CLI Reference

> Extracted from `system3-meta-orchestrator.md` to reduce output style context size.
> This is lookup/reference material for the Completion Promise Protocol.

---

### Session Initialization (MANDATORY for goal-oriented work)

At session start, when user provides a goal or PRD:

```bash
# CLAUDE_SESSION_ID is already set by ccsystem3 - no cs-init needed!

# 1. Create promise from user's goal
cs-promise --create "Complete the user authentication feature with tests"

# 2. Start work immediately (pending -> in_progress)
cs-promise --start <promise-id>

# 3. (Optional) Check for orphaned promises from crashed sessions
cs-status --orphans
```

### During Work

```bash
# View your active promises
cs-promise --mine

# Show promise details
cs-promise --show <promise-id>

# Check overall status
cs-status

# Verify when work is complete
cs-verify --promise <promise-id> --type test --proof "All acceptance criteria met, tests passing"
```

### Ownership Management

```bash
# Release ownership (orphan the promise) if you need to hand off
cs-promise --release <promise-id>

# Adopt an orphaned promise from another session
cs-promise --adopt <promise-id>

# Cancel a promise that's no longer needed
cs-promise --cancel <promise-id>
```

### Stop Hook Integration

The `CompletionPromiseChecker` in `unified_stop_gate/checkers.py` evaluates promise status:

- **Exit 0**: No owned promises OR all owned promises verified -> session can end
- **Exit 2**: Owned promises have `pending` or `in_progress` status -> blocks stop

When blocked, you'll see:
```
COMPLETION CRITERIA NOT MET

Session: 20260110T142532Z-a7f3b9e1

IN_PROGRESS PROMISES (1):
  promise-b1afb394: "Complete user authentication..."

NEXT ACTION:
  Complete and verify: cs-verify --promise promise-b1afb394 --proof "..."
```

**Orphan Warnings**: The checker warns about orphaned in_progress promises but doesn't block on them.

### Checking Status

```bash
# Full status overview (all sessions)
cs-status

# Only my promises
cs-status --mine

# Check for orphaned promises
cs-status --orphans

# View history (verified/cancelled)
cs-status --history

# JSON output for programmatic access
cs-status --json

# Check if session can end (for scripts)
cs-verify --check
```

### Verification Sub-Agent

For thorough verification, spawn a dedicated agent:

```python
Task(
    subagent_type="general-purpose",
    model="sonnet",
    description="Verify completion criteria",
    prompt="""
    List promises owned by this session: cs-status --mine

    For each in_progress promise:
    1. Verify the acceptance criteria are actually met
    2. Run relevant tests to confirm
    3. Collect evidence/proof

    Then verify each promise:
    cs-verify --promise <id> --type test --proof "Evidence of completion"

    Report what was verified and any gaps found.
    """
)
```

### Integration with Orchestrators

When spawning orchestrators, inject completion context:

```python
# Include in wisdom injection
completion_context = Bash("cs-status --json")

wisdom = f"""
## Active Completion Promises
{completion_context}

Report completion with:
  cs-verify --promise <id> --type test --proof "Evidence..."

If blocked, use:
  cs-promise --release <id>  # To hand off to another session
"""
```

### Promise JSON Schema

```json
{
    "id": "promise-{8hex_chars}",
    "summary": "Description of the promise",
    "ownership": {
        "created_by": "session-id",
        "created_at": "timestamp",
        "owned_by": "session-id",
        "owned_since": "timestamp"
    },
    "status": "pending|in_progress|verified|cancelled",
    "verification": {
        "verified_at": null,
        "verified_by": null,
        "type": null,
        "proof": null
    },
    "structure": {
        "epics": [],
        "goals": []
    }
}
```

### CLI Reference

**Note**: `CLAUDE_SESSION_ID` is auto-set by `ccsystem3`. Only orchestrators in tmux need manual setup.

| Command | Purpose |
|---------|---------|
| `cs-promise --create "..."` | Create new promise owned by current session |
| `cs-promise --list` | List all promises with ownership |
| `cs-promise --mine` | List only my promises |
| `cs-promise --show <id>` | Show promise details |
| `cs-promise --start <id>` | Set status to in_progress |
| `cs-promise --adopt <id>` | Adopt an orphaned promise |
| `cs-promise --release <id>` | Release ownership (orphan) |
| `cs-promise --cancel <id>` | Cancel promise |
| `cs-verify --promise <id> --proof "..."` | Verify and complete promise |
| `cs-verify --check` | Check if session can end |
| `cs-status` | Show completion state overview |

**Scripts location**: `.claude/scripts/completion-state/`
