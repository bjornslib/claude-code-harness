# PRD-GCHAT-HOOKS-001: Programmatic GChat Integration via Hooks

**Status**: Draft v2.0
**Author**: System 3 Guardian
**Created**: 2026-02-21
**Revised**: 2026-02-21
**Priority**: P1

---

## Problem Statement

The current System 3 architecture uses a persistent Haiku agent (`s3-communicator`) as a Google Chat relay. This design has three fundamental flaws:

1. **Token cost**: The communicator consumes ~$0.20-$0.50/day in Haiku tokens for a simple message relay function that could be near-zero-cost.

2. **Indirect path**: Outbound messages follow a 3-hop path: `System 3 → SendMessage → s3-communicator → GChat MCP tool → GChat`. Each hop adds latency and failure modes.

3. **Cannot forward AskUserQuestion**: When a System 3 session calls `AskUserQuestion`, the dialog blocks the terminal. The s3-communicator cannot detect or respond to this because it runs inside the same Claude Code context. The user must be physically at the terminal to respond.

The AskUserQuestion problem is the most critical. When System 3 hits an `AskUserQuestion` (typically from the stop gate or when genuinely needing user direction), the session blocks indefinitely. The user might not be at the terminal for hours.

**Scope clarification**: Only System 3 operator questions are forwarded to GChat. Orchestrator and worker `AskUserQuestion` calls are handled by the System 3 operators who monitor them — this is existing, working behavior.

---

## Proposed Solution

Replace the persistent `s3-communicator` agent with **two programmatic mechanisms**:

1. **A PreToolUse hook** that intercepts `AskUserQuestion` calls, BLOCKS them (returns `deny`), formats the question via Haiku API, sends to GChat with a unique threadKey, and writes a stop gate marker file.
2. **A one-shot background Task** spawned per question that polls GChat for the user's response in the specific thread, then completes — waking the parent session with the answer.

### Architecture Comparison

**Before (s3-communicator):**
```
System 3 ──SendMessage──► s3-communicator ──MCP tool──► GChat
                              (Haiku agent)
                              ~$0.20-$0.50/day
                              470-line SKILL.md
                              Cannot see AskUserQuestion
```

**After (hook + one-shot Task):**
```
AskUserQuestion fires
    │
    ▼
PreToolUse hook ──deny──► Claude continues with denial reason
    │
    ├── Haiku API formats question
    ├── HTTP POST to GChat (webhook, with unique threadKey)
    ├── Writes stop gate marker file
    │
    └── Spawns one-shot background Haiku Task
            │
            ├── Polls get_thread_messages() for threadKey
            ├── Detects user reply
            ├── COMPLETES → wakes parent session
            │
            └── Parent receives answer, continues work
```

### Key Design Decisions

1. **Block (deny) AskUserQuestion, don't approve it**: Approving creates a terminal dialog that blocks the session. Denying lets Claude continue immediately while the question is forwarded to GChat asynchronously. The denial reason tells Claude: "Your question was forwarded to GChat. A background poller will deliver the response."

2. **One-shot Task, not persistent agent**: Each question spawns a Haiku background Task. When the user responds in GChat, the Task completes — which is the ONLY mechanism that wakes a Claude Code main thread. Cost: ~$0.01 per question vs $0.30-$0.50/day.

3. **ThreadKey for response correlation**: Each question gets a unique GChat threadKey (e.g., `ask-{session-id}-{uuid8}`). The Haiku poller only monitors its specific thread via `get_thread_messages()`. This cleanly handles multiple concurrent S3 sessions.

4. **Stop gate marker files**: Since AskUserQuestion is denied, the stop gate (which requires AskUserQuestion for session exit) would create an infinite loop. Marker files at `.claude/state/gchat-forwarded-ask/` signal to the stop gate that a question WAS presented to the user, just via GChat instead of the terminal.

### Cost Comparison

| Component | Before | After |
|-----------|--------|-------|
| Outbound GChat relay | ~$0.20-$0.50/day (Haiku) | $0/day (bash/Python scripts) |
| Inbound GChat polling | ~$0.10/day (Haiku) | ~$0.01/question (one-shot Haiku Task) |
| AskUserQuestion forwarding | Not possible | ~$0.01/question (Haiku API formatting) |
| **Total** | **~$0.30-$0.60/day** | **~$0.02-$0.10/day** |

---

## Scope

### IN Scope

- AskUserQuestion automatic blocking, GChat forwarding, and response delivery via background Task
- Stop gate marker file integration to prevent infinite loop
- Outbound message dispatch via hooks (Notification, Stop, PostToolUse)
- CLI utility (`gchat-send`) for on-demand GChat messaging
- Multi-session response correlation via GChat threadKey
- Migration path from s3-communicator to hooks
- Update to System 3 output style and stop gate

### OUT of Scope

- Changes to the Google Chat bridge MCP server itself (it stays as-is for sessions that want full MCP access)
- Changes to `s3-heartbeat` (it continues as a persistent agent for work scanning)
- Changes to `s3-validator` (it continues as a persistent agent for validation)
- Orchestrator/worker AskUserQuestion forwarding (S3 operators handle these via tmux monitoring)
- Mobile push notifications (GChat handles this natively)
- Multi-space support (single GChat space, as today)

---

## Epic 1: AskUserQuestion → GChat → Response Delivery

**Business Value**: Eliminates the #1 cause of stalled autonomous sessions. Users can respond to System 3 questions from their phone via GChat.

### Feature F1.1: PreToolUse Hook — Block & Forward AskUserQuestion

**Description**: A Python hook script that fires on every `AskUserQuestion` tool call in System 3 sessions. It BLOCKS (denies) the tool call, formats the question via the Anthropic Haiku API, sends to GChat with a unique threadKey, writes a stop gate marker file, and returns a denial reason that tells Claude the question was forwarded.

**Hook Configuration**:
```json
{
  "matcher": "AskUserQuestion",
  "hooks": [{
    "type": "command",
    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/gchat-ask-user-forward.py"
  }]
}
```

**Input**: Standard PreToolUse JSON with `tool_name: "AskUserQuestion"` and `tool_input.questions[]`.

**Behavior**:
1. Check if this is a System 3 session (check `CLAUDE_SESSION_ID` prefix or output style)
2. If NOT a System 3 session → return `{"decision": "approve"}` (let orchestrators/workers use AskUserQuestion normally)
3. Parse `tool_input.questions[]` to extract question text, options, and headers
4. Generate unique question ID: `ask-{session_id}-{uuid8}`
5. Call Anthropic Haiku API to format the question as a clean GChat card message:
   ```python
   # Haiku formats: question text, numbered options, session context
   formatted = anthropic.messages.create(
       model="claude-haiku-4-5-20251001",
       messages=[{"role": "user", "content": f"Format this AskUserQuestion for GChat: {json.dumps(tool_input)}"}],
       max_tokens=500
   )
   ```
6. HTTP POST to `$GOOGLE_CHAT_WEBHOOK_URL` with `threadKey={question_id}`:
   ```
   POST webhook_url&threadKey=ask-{session_id}-{uuid8}
   {"text": "{formatted_message}"}
   ```
7. Write stop gate marker file:
   ```
   .claude/state/gchat-forwarded-ask/{question_id}.json
   {
     "question_id": "ask-{session_id}-{uuid8}",
     "session_id": "{session_id}",
     "asked_at": "2026-02-21T10:30:00Z",
     "questions": [...original questions...],
     "gchat_thread_key": "ask-{session_id}-{uuid8}",
     "status": "pending"
   }
   ```
8. Return DENY with forwarding reason:
   ```json
   {
     "hookSpecificOutput": {
       "hookEventName": "PreToolUse",
       "permissionDecision": "deny",
       "permissionDecisionReason": "Question forwarded to Google Chat (thread: ask-{session_id}-{uuid8}). A background poller will deliver the user's response when they reply. Continue with other work or wait for the response."
     }
   }
   ```

**Session Detection Logic**:
- System 3 sessions have `CLAUDE_SESSION_ID` starting with a timestamp pattern (set by `ccsystem3`)
- Orchestrator sessions have `CLAUDE_SESSION_ID` starting with `orch-`
- Worker sessions run inside orchestrator processes (no separate session ID)
- **Rule**: Only deny for sessions where output style is `system3-meta-orchestrator` (check via hook environment or marker file)

**Acceptance Criteria**:
- [ ] Hook fires on every AskUserQuestion call in System 3 sessions
- [ ] Hook APPROVES (passes through) AskUserQuestion in non-System-3 sessions
- [ ] Question formatted via Haiku API and sent to GChat with unique threadKey
- [ ] Stop gate marker file written with correct metadata
- [ ] Hook returns `deny` with descriptive reason including thread key
- [ ] Hook completes in < 5 seconds (API call + webhook POST)
- [ ] Works for single-select and multi-select questions

### Feature F1.2: One-Shot Background Haiku Task — GChat Response Poller

**Description**: After the hook denies AskUserQuestion, the System 3 agent spawns a one-shot background Haiku Task that polls the specific GChat thread for the user's response. When the user replies, the Task COMPLETES — which wakes the parent System 3 session with the answer.

**This is NOT a hook** — it's a behavioral pattern coded into the System 3 output style. When Claude receives the denial reason mentioning "background poller will deliver," it spawns the Task.

**System 3 Output Style Pattern**:
```python
# When AskUserQuestion is denied with GChat forwarding reason:
# 1. Extract the thread key from the denial reason
# 2. Spawn the poller Task

Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description=f"Poll GChat for response to {thread_key}",
    prompt=f"""
    You are a GChat response poller. Your ONLY job:

    1. Poll for user response in GChat thread '{thread_key}'
    2. Use the google-chat-bridge MCP tool: get_thread_messages(thread_id="{thread_key}")
    3. If NO response yet → sleep 15 seconds, try again (max 120 iterations = 30 minutes)
    4. If response found → IMMEDIATELY return the response text and EXIT

    CRITICAL: You MUST exit promptly when you find a response. Do NOT analyze it.
    Return format: "GCHAT_RESPONSE: {{user's message text}}"

    If 30 minutes pass with no response: return "GCHAT_TIMEOUT: No response in 30 minutes"
    """
)
```

**Wake-Up Mechanism**: When the background Task completes, the Claude Code main thread receives a `<task-notification>` with the Task's output. System 3 then:
1. Parses the `GCHAT_RESPONSE:` prefix to extract the user's answer
2. Incorporates the answer into its decision-making
3. Updates the stop gate marker file to `status: "resolved"`

**Why Haiku?**: The poller is a simple loop (poll → check → sleep → repeat). No complex reasoning needed. Cost: ~1,000 tokens per poll cycle × ~20 cycles average = ~20,000 tokens = ~$0.01.

**Why `get_thread_messages()` and not `get_new_messages()`?**: Thread-specific polling avoids noise from other GChat messages. The poller only sees messages in its specific thread, which will only contain:
1. The original question (sent by the hook)
2. The user's response (what we're looking for)
3. Possibly follow-up messages (ignored — first non-bot message is the answer)

**Acceptance Criteria**:
- [ ] Task spawns as background Haiku agent after AskUserQuestion denial
- [ ] Polls `get_thread_messages()` for the specific threadKey
- [ ] Detects user's response (first non-bot message in thread)
- [ ] Returns immediately upon finding response (exits promptly)
- [ ] Times out after 30 minutes with clear timeout message
- [ ] Wakes parent System 3 session upon completion
- [ ] Cost per question is < $0.02

### Feature F1.3: Multi-Session Response Correlation

**Description**: When multiple System 3 sessions are running simultaneously (e.g., one per implementation repo), each session's questions must route to and from the correct GChat thread.

**Correlation Mechanism**:

Each question gets a unique threadKey: `ask-{session_id}-{uuid8}`

```
Session A: ask-20260221T103000Z-a7f3b9e1-x4k2m8
Session B: ask-20260221T103500Z-b2c9d4e6-y7n3p5
```

- **Outbound**: The hook includes the threadKey in the GChat webhook POST
- **Inbound**: Each session's poller Task only monitors its own threadKey
- **No cross-contamination**: Session A's poller never sees Session B's responses (different threads)

**GChat Thread Behavior**:
- `threadKey` creates a new thread if one doesn't exist
- Replies in the thread are grouped
- `get_thread_messages(thread_id=threadKey)` returns only messages in that thread
- The user sees each question as a separate thread card in GChat

**Acceptance Criteria**:
- [ ] Each question gets a unique threadKey incorporating session ID
- [ ] Two concurrent sessions can both forward questions without cross-contamination
- [ ] Each poller Task only polls its own thread
- [ ] User can reply to questions in any order
- [ ] GChat displays questions as separate threads (visually distinct)

### Feature F1.4: Stop Gate Marker Integration

**Description**: Prevent the stop gate infinite loop that would occur if AskUserQuestion is globally denied. The stop gate requires AskUserQuestion for session exit — if it's denied, the session can never stop.

**Problem**:
```
System 3 wants to stop
  → Stop gate fires
  → Judge says: "present options via AskUserQuestion"
  → System 3 calls AskUserQuestion
  → Hook denies it (forwarded to GChat)
  → Judge says: "AskUserQuestion not presented" (because it was denied)
  → Infinite loop
```

**Solution**: Marker files at `.claude/state/gchat-forwarded-ask/` serve as proof that a question WAS presented to the user, just via GChat instead of the terminal.

**Stop Gate Integration**:
```python
# In system3_continuation_judge.py:
def check_ask_user_question_presented():
    marker_dir = f"{project_dir}/.claude/state/gchat-forwarded-ask/"
    if os.path.exists(marker_dir):
        recent_markers = [f for f in os.listdir(marker_dir)
                         if f.endswith('.json')
                         and is_recent(f, max_age_minutes=30)]
        if recent_markers:
            return True  # Question was presented (via GChat)
    return False  # No recent questions — block stop
```

**Marker Lifecycle**:
1. **Created**: By PreToolUse hook when question is forwarded to GChat
2. **Updated**: By System 3 when response is received (status: "resolved")
3. **Cleaned up**: Resolved markers older than 24 hours are deleted

**Acceptance Criteria**:
- [ ] Stop gate recognizes GChat-forwarded questions as equivalent to terminal AskUserQuestion
- [ ] Recent marker files (< 30 minutes) prevent infinite loop
- [ ] Stale marker files (> 24 hours) are automatically cleaned up
- [ ] Stop gate still blocks if NO questions have been presented (no markers AND no terminal AskUserQuestion)

---

## Epic 2: Outbound Event Hooks (Replaces s3-communicator Outbound)

**Business Value**: All outbound GChat messaging becomes zero-cost and zero-latency. No more 3-hop relay path.

### Feature F2.1: gchat-send CLI Utility

**Description**: A standalone bash script that any hook, agent, or manual invocation can use to send formatted messages to GChat. This is the single entry point for all outbound GChat messaging.

**Location**: `.claude/scripts/gchat-send.sh`

**Usage**:
```bash
# Simple message
gchat-send "Hello from Claude Code"

# Typed message (uses appropriate formatting)
gchat-send --type task_completion "Epic 3 completed. 12/12 subtasks validated."
gchat-send --type progress_update "Working on F2.1. 60% complete."
gchat-send --type blocked_alert "Need API credentials for GChat service account."
gchat-send --type heartbeat "System healthy. 3 orchestrators active."

# Thread reply
gchat-send --thread-key "ask-user-12345" "Follow-up to previous question"
```

**Implementation**: Pure bash with `curl`. Reads `$GOOGLE_CHAT_WEBHOOK_URL` from environment or from `.mcp.json`.

**Message Types and Formatting**:

| Type | Prefix | Format |
|------|--------|--------|
| `task_completion` | `[Done]` | Bold title, completion details |
| `progress_update` | `[Progress]` | Status bar, current work |
| `blocked_alert` | `[BLOCKED]` | Urgent formatting, action needed |
| `heartbeat` | `[Heartbeat]` | System health summary |
| `session_start` | `[Session]` | Session ID, goals, promise |
| `session_end` | `[Session End]` | Duration, work completed |
| `error` | `[Error]` | Error details, stack trace |
| (default) | (none) | Plain text |

**Acceptance Criteria**:
- [ ] Script works with only `curl` and `jq` as dependencies
- [ ] Reads webhook URL from environment or `.mcp.json`
- [ ] All 8 message types produce correctly formatted GChat messages
- [ ] Thread reply support via `--thread-key`
- [ ] Exit code 0 on success, non-zero on failure
- [ ] Completes in < 2 seconds

### Feature F2.2: Notification Hook for GChat Dispatch

**Description**: Populate the currently-empty `Notification` hook with a script that forwards Claude Code notifications to GChat.

**Hook Configuration**:
```json
{
  "Notification": [
    {
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/gchat-notification-dispatch.py"
      }]
    }
  ]
}
```

**Behavior**:
1. Parse the notification content from hook input
2. Determine notification type (subagent completion, background task, etc.)
3. Call `gchat-send` with appropriate `--type` flag
4. Return immediately (notifications are fire-and-forget)

**Acceptance Criteria**:
- [ ] Subagent completion notifications forwarded to GChat
- [ ] Background task completion forwarded to GChat
- [ ] Hook completes in < 1 second
- [ ] Does not block Claude Code execution

### Feature F2.3: Stop Hook GChat Integration

**Description**: Enhance the existing Stop hook to send a session-end summary to GChat before the session exits.

**Behavior**: At the end of the `unified-stop-gate.sh` flow (after all checks pass), call `gchat-send --type session_end` with a summary of work completed, promises verified, and session duration.

**Acceptance Criteria**:
- [ ] Session end notification sent to GChat on clean exit
- [ ] Summary includes session ID, duration, work completed, promise status
- [ ] Does not interfere with existing stop gate logic

### Feature F2.4: Direct gchat-send Usage in System 3

**Description**: Update the System 3 output style to use `gchat-send` directly instead of routing through s3-communicator. When System 3 wants to send a message to the user, it calls the CLI script instead of SendMessage to a teammate.

**Before**:
```python
SendMessage(type="message", recipient="s3-communicator",
            content="TASK_COMPLETION: Epic 3 done")
```

**After**:
```bash
Bash("gchat-send --type task_completion 'Epic 3 done. 12/12 subtasks validated.'")
```

**Acceptance Criteria**:
- [ ] System 3 output style updated to use `gchat-send` for outbound
- [ ] All 6 message types previously sent via s3-communicator are covered
- [ ] No SendMessage calls to s3-communicator remain in output style

---

## Epic 3: Response Correlation Prototype & Validation

**Business Value**: Before full implementation, validate that the threadKey-based response correlation mechanism works reliably with the GChat API.

### Feature F3.1: ThreadKey Prototype Script

**Description**: A standalone Python script that:
1. Sends a test question to GChat with a unique threadKey
2. Polls `get_thread_messages()` for that threadKey
3. Detects a human reply
4. Prints the response

This validates the core mechanism before integrating into hooks.

**Location**: `.claude/scripts/prototypes/gchat-thread-correlation.py`

**Test Scenarios**:
1. Send question → user replies → script detects reply
2. Send two questions (different threadKeys) → user replies to second → script detects correct match
3. Send question → no reply for 5 minutes → script reports timeout
4. Send question → user replies with just a number → script maps to option

**Acceptance Criteria**:
- [ ] Script successfully creates a GChat thread via webhook
- [ ] Script polls and detects user replies in the specific thread
- [ ] Two concurrent threads do not interfere with each other
- [ ] Script correctly identifies the first non-bot message as the user's response
- [ ] Timeout behavior works correctly

### Feature F3.2: GChat Thread API Validation

**Description**: Validate that the google-chat-bridge MCP server's thread tools work as expected for our use case.

**Questions to Answer**:
1. Does `get_thread_messages(thread_id=threadKey)` work with webhook-created threads?
2. What is the `thread_id` format returned by the webhook vs what `get_thread_messages` expects?
3. Is there latency between a webhook POST and the thread being queryable?
4. Can we distinguish bot messages (our question) from human messages (user's response)?

**Acceptance Criteria**:
- [ ] Document thread ID format mapping (webhook threadKey → API thread_id)
- [ ] Confirm latency characteristics (webhook POST → queryable via API)
- [ ] Confirm bot vs human message discrimination
- [ ] Document any API rate limits that affect polling frequency

---

## Epic 4: s3-communicator Removal + Migration

**Business Value**: Eliminates ongoing token cost, simplifies the s3-live team, and reduces cognitive overhead.

### Feature F4.1: Update System 3 Output Style

**Description**: Remove all references to s3-communicator spawning from `system3-meta-orchestrator.md`. Replace SendMessage-based GChat relay with `gchat-send` CLI calls. Add the AskUserQuestion denial handling pattern.

**Changes**:
- Remove "Spawn s3-communicator" from Persistent Agent Launch section
- Update "Persistent Agent Summary" table (remove s3-communicator row)
- Replace all `SendMessage(recipient="s3-communicator", ...)` patterns with `Bash("gchat-send ...")`
- Add behavioral pattern: when AskUserQuestion is denied with GChat forwarding reason, spawn one-shot poller Task
- Update cost estimates (remove ~$0.20-$0.50/day line)
- Update Post-Compaction Recovery (2 agents instead of 3)

**Acceptance Criteria**:
- [ ] No references to s3-communicator in output style
- [ ] All outbound GChat paths use `gchat-send`
- [ ] AskUserQuestion denial → poller Task pattern documented
- [ ] Cost estimates updated
- [ ] Post-compaction recovery checks 2 agents (heartbeat + validator)

### Feature F4.2: Update Stop Gate

**Description**: The stop gate's `communicator_checker.py` currently checks for `s3-communicator` in the team config to keep the session alive. Update to check for `s3-heartbeat` instead (or any persistent agent). Also add the GChat marker file check.

**Changes**:
- Update `communicator_checker.py` to check for ANY persistent agent in s3-live, not specifically `s3-communicator`
- Add marker file check to `system3_continuation_judge.py` (see F1.4)
- Rename to `persistent_agent_checker.py` for clarity

**Acceptance Criteria**:
- [ ] Stop gate passes with heartbeat + validator only (no communicator)
- [ ] Stop gate recognizes GChat marker files as valid AskUserQuestion
- [ ] Stop gate still blocks if ALL persistent agents are missing
- [ ] Backward compatible (still works if s3-communicator IS present)

### Feature F4.3: Archive s3-communicator Skill

**Description**: Move the s3-communicator skill to an archive directory and update all references.

**Changes**:
- Move `.claude/skills/s3-communicator/` to `.claude/skills/_archived/s3-communicator/`
- Update s3-heartbeat SKILL.md to remove sibling reference
- Update system3-orchestrator SKILL.md to remove communicator references
- Add migration note to `.claude/documentation/SYSTEM3_CHANGELOG.md`

**Acceptance Criteria**:
- [ ] Skill archived, not deleted (preserves history)
- [ ] No broken references in active skills
- [ ] Changelog updated with migration notes
- [ ] s3-heartbeat works independently without communicator sibling

---

## Technical Constraints

1. **Webhook-only outbound**: Outbound messages use the GChat webhook URL (already configured in `.mcp.json`). No service account needed for outbound.

2. **API-based inbound**: Inbound polling requires GChat API credentials (service account or ADC). The `get_thread_messages()` MCP tool handles auth via `GOOGLE_CHAT_CREDENTIALS_FILE`.

3. **Haiku API for formatting**: The PreToolUse hook calls the Anthropic API with `claude-haiku-4-5-20251001` to format questions. Requires `ANTHROPIC_API_KEY` in the hook environment.

4. **Background Task wake-up**: Only completing background Tasks (not background Bash) wake the Claude Code main thread. This is the fundamental constraint that drives the one-shot Task design.

5. **Hook timeout**: Claude Code hooks have a configurable timeout (default 10 seconds). The hook must complete within this window: Haiku API call (~2s) + webhook POST (~1s) + marker file write (~0.1s) ≈ 3s total, well within budget.

6. **No tmux injection**: Unlike the previous design, this architecture does NOT inject responses via tmux send-keys. The response comes back through the completing background Task, which is a native Claude Code mechanism.

7. **Session detection**: The hook must distinguish System 3 sessions from orchestrator/worker sessions. Only System 3 sessions get AskUserQuestion denied. Detection via `CLAUDE_SESSION_ID` prefix or output style marker.

---

## Dependencies

- Google Chat webhook URL (already configured)
- Google Chat API credentials for inbound polling via `get_thread_messages()` (already configured via google-chat-bridge MCP server)
- Anthropic API key for Haiku formatting (already configured in `.mcp.json`)
- Python 3 with `urllib.request` and `json` (stdlib only for hook)
- `curl` and `jq` for the bash CLI script (`gchat-send`)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Daily GChat relay token cost | ~$0.30-$0.60/day | ~$0.02-$0.10/day |
| AskUserQuestion response time | Infinite (not forwarded) | < 60 seconds to appear in GChat |
| Outbound message latency | ~5-10s (3-hop relay) | < 2s (direct HTTP POST) |
| Persistent agents in s3-live | 3 (communicator + heartbeat + validator) | 2 (heartbeat + validator) |
| Lines of code for GChat relay | 470 (SKILL.md) | ~300 (hook + CLI + output style pattern) |
| Response correlation accuracy | N/A | 100% (threadKey per question) |

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Haiku API call in hook exceeds timeout | Low | Medium | 10s hook timeout is generous; Haiku responds in ~1-2s |
| GChat threadKey doesn't create separate threads | Low | High | F3.1 prototype validates this before implementation |
| `get_thread_messages()` format mismatch with webhook threadKey | Medium | High | F3.2 validates API format mapping |
| Multiple sessions cause GChat thread confusion | Low | Medium | Unique threadKey per question includes session ID |
| User doesn't reply within 30 minutes | Medium | Low | Task times out, System 3 continues autonomously |
| Stop gate infinite loop (hook denies AskUserQuestion) | Eliminated | N/A | Marker file integration (F1.4) breaks the loop |
| Haiku poller Task doesn't exit promptly | Low | Medium | Use Sonnet if Haiku exhibits exit discipline issues (known from monitoring experience) |

---

## Implementation Order

1. **Epic 3 FIRST** (F3.1, F3.2): Prototype and validate the threadKey correlation mechanism
2. **Epic 1** (F1.1 → F1.4): Core AskUserQuestion flow (hook + poller + correlation + stop gate)
3. **Epic 2** (F2.1 → F2.4): Outbound hooks (can be done in parallel with Epic 1)
4. **Epic 4 LAST** (F4.1 → F4.3): s3-communicator removal (only after Epics 1-3 are validated)

---

## Version

- PRD Version: 2.0.0
- Previous Version: 1.0.0 (tmux injection architecture — superseded)
- Related PRD: PRD-S3-CLAWS-001 (original s3-communicator implementation)
- Supersedes: s3-communicator SKILL.md v2.0.0
- Key Architecture Change: Replaced tmux send-keys injection with one-shot background Task + threadKey correlation
