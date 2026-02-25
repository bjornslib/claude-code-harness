---
title: "Decision_Time_Guidance"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# Decision-Time Guidance Architecture

Adapting Replit's decision-time guidance approach to the Claude Code harness for selective, situational instruction injection.

## Background: The Problem

From Replit's research:
- **Static front-loaded rules**: Influence fades over time due to recency bias
- **Interleaved generic reminders**: Token cost grows, earlier reminders lose relevance
- **Solution**: Inject short, situational instructions exactly when they matter

Key insight: A lightweight classifier decides WHICH guidance to inject, not WHETHER to inject everything.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Decision-Time Guidance System                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ Event Hooks  │───▶│ Signal Tracker   │───▶│ Guidance Bank    │  │
│  │              │    │ (Classifier)     │    │ (Micro-prompts)  │  │
│  │ - PostToolUse│    │                  │    │                  │  │
│  │ - Stop       │    │ Analyzes:        │    │ - Error recovery │  │
│  │ - PreCompact │    │ - Error patterns │    │ - Doom loops     │  │
│  │ - SessionStrt│    │ - Doom loops     │    │ - Delegation     │  │
│  └──────────────┘    │ - Worker status  │    │ - Consult System3│  │
│                      │ - Stop attempts  │    │ - Re-read context│  │
│                      └──────────────────┘    └──────────────────┘  │
│                                                                      │
│  State Storage:                                                      │
│  .claude/state/decision-guidance/                                   │
│    ├── error-tracker.json    # Rolling 5-min error window           │
│    ├── doom-loop-detector.json  # Repeated failures                 │
│    └── worker-status.json    # Worker completion tracking           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### 1. Context Preservation After Compression (PreCompact Hook)

**Problem**: System3 instructions are lost after context compression.

**Solution**: Before compaction, extract and persist key instructions to be selectively re-injected.

```python
# Hook: PreCompact
# Trigger: Before context compression

def extract_key_instructions():
    """Extract critical instructions from System3 to persist across compaction."""

    # 1. Read current transcript
    # 2. Extract System3 directives (tagged with specific markers)
    # 3. Store in .claude/state/decision-guidance/preserved-context.json

    preserved = {
        "timestamp": now(),
        "session_id": os.environ.get("CLAUDE_SESSION_ID"),
        "instructions": [
            # Only preserve what's RELEVANT to current work
            {
                "type": "goal",
                "content": "Complete feature X with validation",
                "priority": "P0"
            },
            {
                "type": "constraint",
                "content": "Do not modify shared database schema",
                "priority": "P1"
            }
        ],
        "current_task": {
            "id": "TASK-123",
            "context": "Working on authentication flow"
        }
    }
```

**Re-injection Logic** (SessionStart with source="compact"):

```python
# Only inject if:
# 1. Session ID matches (same orchestrator)
# 2. Instructions are < 24 hours old
# 3. Current work aligns with preserved context

def should_inject_preserved_context(preserved, current_context):
    if preserved["session_id"] != current_session_id:
        return False
    if age(preserved["timestamp"]) > 24 * 3600:
        return False
    return True
```

### 2. Error Tracking Hook (PostToolUse)

**Problem**: Repeated errors indicate the agent is stuck, but current setup doesn't detect patterns.

**Solution**: Rolling window error tracker with configurable threshold.

```python
# Hook: PostToolUse
# File: .claude/hooks/decision-time-error-tracker.py

ERROR_WINDOW_SECONDS = 300  # 5 minutes
ERROR_THRESHOLD = 4

def track_tool_result(hook_input):
    """Track tool execution results and detect failure patterns."""

    tool_name = hook_input.get("tool_name")
    tool_result = hook_input.get("result", {})

    # Detect various error signals
    is_error = (
        tool_result.get("error") or
        tool_result.get("exit_code", 0) != 0 or
        "error" in str(tool_result.get("output", "")).lower()[:200]
    )

    if is_error:
        record_error(tool_name, tool_result)

    # Check rolling window
    recent_errors = get_errors_in_window(ERROR_WINDOW_SECONDS)

    if len(recent_errors) >= ERROR_THRESHOLD:
        return inject_error_guidance(recent_errors)

    return {"continue": True}  # No guidance needed
```

**Guidance Injection**:

```python
def inject_error_guidance(recent_errors):
    """Inject situational guidance when error threshold is reached."""

    # Classify error pattern
    error_types = classify_errors(recent_errors)

    guidance = """
## ⚠️ Error Pattern Detected

{error_count} errors in the last 5 minutes. Consider:

1. **Read the error messages carefully** - don't repeat the same approach
2. **Check assumptions** - is the file/path/command correct?
3. **Try a different approach** - if X didn't work 3 times, try Y

Recent errors:
{error_summary}

*This is a decision-time guidance injection. Take a moment to reassess.*
"""

    return {
        "continue": True,
        "systemMessage": guidance.format(
            error_count=len(recent_errors),
            error_summary=format_error_summary(recent_errors)
        )
    }
```

### 3. Worker Failure → System3 Guidance Protocol

**Problem**: When workers fail, orchestrators often retry the same failing approach.

**Solution**: Detect worker failure patterns and trigger System3 consultation.

**Detection Mechanism**:

```python
# File: .claude/hooks/worker-failure-detector.py
# Hook: PostToolUse (for tmux commands that check worker status)

def detect_worker_failure(hook_input):
    """Detect when a tmux worker has failed its assigned task."""

    # Check if this was a tmux status check
    if not is_tmux_status_check(hook_input):
        return None

    result = parse_tmux_output(hook_input["result"]["output"])

    # Detect failure indicators
    failure_signals = [
        "Error:" in result,
        "failed" in result.lower(),
        "could not" in result.lower(),
        worker_exited_with_error(result),
    ]

    if any(failure_signals):
        return record_worker_failure(result)

    return None
```

**System3 Consultation Trigger**:

```python
def should_consult_system3(worker_failures):
    """Determine if orchestrator should pause and consult System3."""

    # Triggers:
    # 1. Same worker failed 2+ times on same task
    # 2. Multiple workers failed on related tasks
    # 3. Worker reported "blocked" or "need guidance"

    if len(worker_failures) >= 2:
        return True

    for failure in worker_failures:
        if "blocked" in failure.get("reason", "").lower():
            return True

    return False

def inject_consultation_guidance():
    """Guide orchestrator to consult System3."""

    return {
        "continue": True,
        "systemMessage": """
## 🔄 Consultation Recommended

Worker execution failed multiple times. Before retrying:

1. **Update bead status to signal need for guidance**:
   ```bash
   bd update <id> --status=impl_complete
   ```

2. **Wait for System3 response** - System3 monitors bead status changes

3. **Alternative**: Create a fresh plan from first principles instead of retrying

*This exploits the generator-discriminator gap: a fresh perspective often recognizes solutions the stuck agent cannot generate.*
"""
    }
```

### 4. Orchestrator Stop-Gate with Guidance Request

**Problem**: Orchestrators may stop without properly escalating blockers.

**Solution**: Detect orchestrator sessions (session ID prefix) and modify stop behavior.

**Session ID Convention**:

```bash
# In launchorchestrator script:
export CLAUDE_SESSION_ID="orch-${epic_name}-$(date +%s)"

# Examples:
# orch-auth-feature-1706054400
# orch-payment-refactor-1706054500
```

**Modified Stop-Gate**:

```python
# File: unified-stop-gate.sh (modified)

def is_orchestrator_session(session_id):
    """Check if this is an orchestrator session."""
    return session_id and session_id.startswith("orch-")

def orchestrator_stop_gate(session_id, context):
    """Enhanced stop gate for orchestrators."""

    # Standard checks first
    standard_result = run_standard_checks(context)

    if not standard_result.passed:
        return standard_result

    # Additional orchestrator check: Blockers should be escalated
    if is_orchestrator_session(session_id):
        blockers = detect_unescalated_blockers(context)

        if blockers:
            return {
                "decision": "block",
                "reason": f"""
## 🚫 Orchestrator Stop Gate: Unescalated Blockers

You have {len(blockers)} blocker(s) that should be escalated to System3 before stopping:

{format_blockers(blockers)}

**Required Action**:
1. Update bead status to signal System3:
   ```bash
   bd update <id> --status=impl_complete
   ```

2. Or explicitly mark blockers as "external dependency" if truly external

*Orchestrators should escalate blockers, not silently stop.*
"""
            }

    return standard_result
```

## Guidance Bank: Micro-Prompts

Following Replit's approach, we maintain a bank of short, focused guidance:

```yaml
# .claude/config/guidance-bank.yaml

error_recovery:
  trigger: "4+ errors in 5 minutes"
  message: |
    ⚠️ Error pattern detected. Stop and read the errors carefully.
    Don't repeat the same approach - try something different.

doom_loop:
  trigger: "Same file edited 3+ times in 10 minutes without test pass"
  message: |
    🔄 Potential doom loop. Step back and reconsider the approach.
    Consider: Is the underlying assumption wrong?

consult_external:
  trigger: "Worker failure on same task 2+ times"
  message: |
    💡 Consider consulting System3 for a fresh perspective.
    Use: bd update <id> --status=impl_complete

delegation_reminder:
  trigger: "Orchestrator used Edit/Write after compaction"
  message: |
    ⚠️ DELEGATION CHECK: Orchestrators coordinate, workers implement.
    Use tmux to delegate this change.

re_read_context:
  trigger: "Tool result mentions 'not found' or 'does not exist'"
  message: |
    📖 Path/file not found. Re-read the relevant context or search again.
```

## Signal Tracker (Lightweight Classifier)

```python
# .claude/hooks/decision_guidance/classifier.py

class SignalTracker:
    """Lightweight classifier that decides which guidance to inject."""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.error_window = []
        self.edit_history = []
        self.worker_failures = []

    def analyze(self, hook_input: dict) -> list[str]:
        """Analyze current state and return list of guidance keys to inject."""

        guidance_keys = []

        # Check error pattern
        if self._check_error_pattern():
            guidance_keys.append("error_recovery")

        # Check doom loop
        if self._check_doom_loop():
            guidance_keys.append("doom_loop")

        # Check worker failures (for orchestrators)
        if self._check_worker_failures():
            guidance_keys.append("consult_external")

        # Limit to max 2 guidance injections (Replit finding)
        return guidance_keys[:2]

    def _check_error_pattern(self) -> bool:
        # Count errors in rolling 5-minute window
        cutoff = time.time() - 300
        recent = [e for e in self.error_window if e["timestamp"] > cutoff]
        return len(recent) >= 4

    def _check_doom_loop(self) -> bool:
        # Same file edited 3+ times in 10 minutes without success
        cutoff = time.time() - 600
        recent_edits = [e for e in self.edit_history if e["timestamp"] > cutoff]

        file_counts = Counter(e["file"] for e in recent_edits)
        return any(count >= 3 for count in file_counts.values())

    def _check_worker_failures(self) -> bool:
        # 2+ worker failures on same task
        cutoff = time.time() - 1800  # 30 minute window
        recent = [f for f in self.worker_failures if f["timestamp"] > cutoff]

        task_counts = Counter(f.get("task_id") for f in recent)
        return any(count >= 2 for count in task_counts.values())
```

## Key Design Principles (from Replit)

1. **False positives are cheap**: Guidance is suggestions, not constraints
2. **Guidance is ephemeral**: Injected reminders don't persist in history
3. **Caching stays intact**: Core prompt never changes
4. **Selectivity is key**: Only inject what's relevant to THIS decision
5. **Limit concurrent guidance**: Max 2-3 reminders to avoid competition

## File Structure

```
.claude/
├── hooks/
│   ├── decision-time-error-tracker.py     # PostToolUse hook for error tracking
│   ├── context-preserver.py               # PreCompact hook for context extraction
│   └── decision_guidance/
│       ├── __init__.py
│       ├── classifier.py                  # Signal tracker/classifier
│       ├── guidance_bank.py               # Micro-prompt storage
│       └── state_manager.py               # Rolling window state management
├── config/
│   └── guidance-bank.yaml                 # Guidance templates
├── state/
│   └── decision-guidance/
│       ├── error-tracker.json             # Rolling error window
│       ├── edit-history.json              # File edit tracking
│       ├── worker-status.json             # Worker failure tracking
│       └── preserved-context.json         # Context preserved across compaction
└── documentation/
    └── DECISION_TIME_GUIDANCE.md          # This document
```

## Integration Points

| Hook | Trigger | Guidance Types |
|------|---------|----------------|
| `PostToolUse` | Every tool call | error_recovery, doom_loop |
| `PreCompact` | Before compaction | (saves context, no injection) |
| `SessionStart` | After compaction | re_read_context, delegation_reminder |
| `Stop` | Session end | consult_external (for orchestrators) |
| `UserPromptSubmit` | User input | delegation_reminder |

## Benefits Over Current System

| Current Approach | Decision-Time Guidance |
|------------------|------------------------|
| All rules in output-style (front-loaded) | Selective injection at decision points |
| One-time reminder after compaction | Continuous monitoring with targeted intervention |
| No error pattern detection | Rolling window error tracking |
| Workers fail silently | Failure triggers System3 consultation |
| Orchestrators stop without escalation | Stop-gate enforces blocker escalation |

## Implementation Status

### Completed Components

1. **Error Tracking Hook** (`.claude/hooks/decision-time-guidance-hook.py`)
   - Tracks errors in a rolling 5-minute window
   - Injects guidance when 4+ errors detected
   - Fast path: <5ms when no issues detected

2. **Signal Classifier** (`.claude/hooks/decision_guidance/classifier.py`)
   - Lightweight classification of tool results
   - Detects error patterns, doom loops, not-found issues
   - Orchestrator delegation violation detection

3. **Guidance Bank** (`.claude/hooks/decision_guidance/guidance_bank.py`)
   - Bank of micro-prompts for injection
   - Priority-based selection
   - Max 2 concurrent guidance (per Replit findings)

4. **Orchestrator Stop-Gate Enhancement** (`.claude/hooks/unified-stop-gate.sh`)
   - Detects `orch-*` session IDs
   - Requires blocker escalation before stopping
   - 2-attempt bypass (like momentum check)

5. **System3 Guidance Protocol** (`.claude/hooks/decision_guidance/system3_protocol.py`)
   - Request/response tracking
   - Bead status integration helpers
   - Response formatting for injection

### Setup Instructions

#### 1. Add the PostToolUse Hook

Add to `.claude/settings.json` in the `hooks.PostToolUse` array:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/decision-time-guidance-hook.py"
          }
        ]
      }
    ]
  }
}
```

#### 2. Configure Orchestrator Session IDs

Update your `launchorchestrator` script to use `orch-` prefix:

```bash
#!/bin/bash
# In launchorchestrator script
epic_name="${1:-default}"
export CLAUDE_SESSION_ID="orch-${epic_name}-$(date +%s)"
claude
```

#### 3. Configure Thresholds (Optional)

Create/edit `.claude/config/decision-guidance.json`:

```json
{
  "error_tracking": {
    "window_seconds": 300,
    "threshold": 4
  },
  "doom_loop": {
    "window_seconds": 600,
    "repeat_threshold": 3
  },
  "max_concurrent_guidance": 2
}
```

### Usage Examples

#### Automatic Error Recovery Guidance

When 4+ errors occur in 5 minutes:

```
## Decision-Time Guidance: Error Pattern Detected

4 errors in the last 5 minutes.

**Recent errors:**
- FileNotFoundError: /path/to/file.py
- SyntaxError: unexpected indent
- ImportError: No module named 'foo'

**Before continuing, consider:**
1. Read the error messages carefully
2. Check your assumptions
3. Try a different approach
```

#### Orchestrator Blocker Escalation

When an orchestrator tries to stop with unescalated blockers:

```
## Orchestrator Guidance: Unescalated Blockers

You have 2 blocker(s) that should be escalated to System3:

- **error_pattern**: 5 errors in last 10 minutes
- **worker_failure**: 2 worker failure(s)

**Recommended Action - Update bead status to signal System3:**
bd update <id> --status=impl_complete

*Attempt 1/2. Stop 2 more time(s) to bypass.*
```

#### Requesting System3 Guidance

From orchestrator, update bead status to signal System3:

```bash
# Signal completion/need for guidance via bead status
bd update <id> --status=impl_complete
```

### Monitoring & Debugging

#### View Error Tracking State

```bash
cat .claude/state/decision-guidance/error-tracker.json
```

#### View Guidance Request History

```bash
cat .claude/state/decision-guidance/guidance-requests.json
```

#### Clear Error State (Reset Tracking)

```bash
rm -rf .claude/state/decision-guidance/
```

#### Debug Logs

```bash
tail -f .claude/state/decision-guidance/errors.log
```

---

*This design adapts Replit's decision-time guidance paradigm to the Claude Code harness, maintaining the principle of injecting guidance exactly when it matters, and only when it matters.*
