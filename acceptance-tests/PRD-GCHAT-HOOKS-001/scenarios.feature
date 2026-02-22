# Blind Acceptance Tests: PRD-GCHAT-HOOKS-001
# Programmatic GChat Integration via Hooks
#
# These tests are BLIND — the S3 operator does not see this file.
# Guardian scores each scenario on a 0.0-1.0 gradient.
# Epic 3 (F3.1, F3.2) is pre-validated and excluded.

# =============================================================================
# EPIC 1: AskUserQuestion -> GChat -> Response Delivery
# =============================================================================

Feature: F1.1 — PreToolUse Hook: Block & Forward AskUserQuestion
  Weight: 0.20

  Scenario: Hook file exists and is configured
    Given the claude-harness-setup repository
    When I check for the PreToolUse hook
    Then a Python script exists at .claude/hooks/gchat-ask-user-forward.py
    And .claude/settings.json has a PreToolUse hook entry matching "AskUserQuestion"
    And the hook command points to the correct script path

    # Scoring Guide:
    #   1.0 — File exists, settings.json configured, matcher is "AskUserQuestion"
    #   0.7 — File exists but settings.json not updated (hook won't fire)
    #   0.3 — File exists but is a stub/placeholder with no real logic
    #   0.0 — File does not exist

    # Evidence to check:
    #   - .claude/hooks/gchat-ask-user-forward.py (exists, non-trivial)
    #   - .claude/settings.json → PreToolUse → matcher: "AskUserQuestion"

  Scenario: Hook denies AskUserQuestion in System 3 sessions
    Given a System 3 session (CLAUDE_SESSION_ID with timestamp pattern)
    When AskUserQuestion is called
    Then the hook returns permissionDecision: "deny"
    And the denial reason mentions "forwarded to Google Chat"
    And the denial reason includes a thread key identifier

    # Scoring Guide:
    #   1.0 — Hook returns deny with descriptive reason including thread key
    #   0.7 — Hook returns deny but reason is generic (no thread key)
    #   0.3 — Hook exists but doesn't actually return deny (returns approve or errors)
    #   0.0 — No deny logic implemented

    # Evidence to check:
    #   - Read hook source: look for "deny" in return value
    #   - Look for threadKey generation logic (uuid, session_id)
    #   - Check for output style / session type detection logic

  Scenario: Hook approves AskUserQuestion in non-System-3 sessions
    Given an orchestrator session (CLAUDE_SESSION_ID starting with "orch-")
    When AskUserQuestion is called
    Then the hook returns permissionDecision: "approve"

    # Scoring Guide:
    #   1.0 — Explicit session type check with approve for non-S3
    #   0.5 — Session detection exists but logic is inverted or incomplete
    #   0.0 — No session type detection (denies ALL sessions)

    # Evidence to check:
    #   - Look for CLAUDE_SESSION_ID check or output style detection
    #   - Look for "approve" return path for non-S3 sessions

    # Red flags:
    #   - No conditional logic (blanket deny/approve for all sessions)
    #   - Session detection via file existence instead of env var

  Scenario: Hook formats question via Haiku API and sends to GChat
    Given a System 3 AskUserQuestion with questions[]
    When the hook processes the tool call
    Then the hook calls the Anthropic API with claude-haiku model
    And the formatted message is POST'd to GOOGLE_CHAT_WEBHOOK_URL
    And the POST includes threadKey in the request
    And the webhook response's thread.name is captured

    # Scoring Guide:
    #   1.0 — Haiku API call + webhook POST + threadKey + thread.name capture all present
    #   0.7 — Webhook POST works but no Haiku formatting (raw JSON forwarded)
    #   0.5 — Webhook POST works but threadKey missing or hardcoded
    #   0.3 — Partial implementation (API call without webhook, or vice versa)
    #   0.0 — No outbound messaging implemented in hook

    # Evidence to check:
    #   - anthropic.messages.create() or equivalent API call
    #   - urllib.request or requests POST to webhook URL
    #   - threadKey parameter in POST body
    #   - thread.name extraction from webhook response

  Scenario: Hook writes stop gate marker file
    Given the hook has successfully forwarded a question
    When the webhook POST completes
    Then a JSON marker file is written to .claude/state/gchat-forwarded-ask/
    And the marker contains question_id, session_id, asked_at, status="pending"
    And the marker contains the gchat thread key and thread resource name

    # Scoring Guide:
    #   1.0 — Marker file written with all required fields (question_id, session_id, asked_at, status, threadKey, thread_name)
    #   0.7 — Marker file written but missing some fields (e.g., no thread_name)
    #   0.3 — Marker directory referenced but file not actually written
    #   0.0 — No marker file logic

    # Evidence to check:
    #   - os.makedirs / Path.mkdir for .claude/state/gchat-forwarded-ask/
    #   - json.dump with required fields
    #   - File naming convention (question_id.json)


Feature: F1.2 — One-Shot Background Haiku Task: GChat Response Poller
  Weight: 0.15

  Scenario: System 3 output style spawns poller after denial
    Given the System 3 output style (system3-meta-orchestrator.md)
    When AskUserQuestion is denied with "forwarded to Google Chat" reason
    Then the output style instructs spawning a background Haiku Task
    And the Task prompt includes the thread key for polling
    And the Task is run_in_background=True

    # Scoring Guide:
    #   1.0 — Output style has explicit pattern: denial → extract thread key → spawn Task
    #   0.7 — Output style mentions poller but pattern is vague or incomplete
    #   0.3 — Output style acknowledges denial but no Task spawn pattern
    #   0.0 — No poller pattern in output style

    # Evidence to check:
    #   - system3-meta-orchestrator.md: search for "GCHAT_RESPONSE" or "poller" or "denied"
    #   - Task() call with model="haiku", run_in_background=True
    #   - Thread key extraction from denial reason

  Scenario: Poller detects human response in GChat thread
    Given a poller Task polling a specific thread
    When the user replies in the GChat thread
    Then the poller detects the non-bot message
    And returns "GCHAT_RESPONSE: {message text}"
    And exits immediately

    # Scoring Guide:
    #   1.0 — Poller uses get_thread_messages or list_messages, filters for HUMAN sender, returns immediately
    #   0.7 — Poller detects response but doesn't exit promptly (continues polling)
    #   0.3 — Poller exists but uses wrong API or doesn't filter by sender type
    #   0.0 — No poller implementation

    # Evidence to check:
    #   - Either MCP tool call (get_thread_messages) or direct ChatClient import
    #   - Sender type filtering (HUMAN vs BOT)
    #   - "GCHAT_RESPONSE:" prefix in return value
    #   - Prompt says to EXIT after finding response

  Scenario: Poller times out after 30 minutes
    Given a poller Task polling a thread with no response
    When 30 minutes elapse (120 iterations at 15s)
    Then the poller returns "GCHAT_TIMEOUT: No response in 30 minutes"
    And exits cleanly

    # Scoring Guide:
    #   1.0 — Max iterations defined, timeout return message present
    #   0.5 — Timeout exists but different from spec (e.g., 10 min instead of 30)
    #   0.0 — No timeout handling (polls forever)


Feature: F1.3 — Multi-Session Response Correlation
  Weight: 0.08

  Scenario: Each question gets a unique threadKey
    Given the PreToolUse hook
    When it generates a threadKey for a question
    Then the key format is ask-{session_id}-{uuid8}
    And the key is unique per question (incorporates random component)

    # Scoring Guide:
    #   1.0 — ThreadKey includes session_id AND random component (uuid)
    #   0.7 — ThreadKey has random component but no session_id
    #   0.3 — ThreadKey is deterministic (no random, risk of collision)
    #   0.0 — No threadKey generation

  Scenario: Concurrent sessions don't cross-contaminate
    Given two concurrent System 3 sessions (A and B)
    When both forward AskUserQuestion to GChat
    Then each session's poller only monitors its own threadKey
    And responses to Session A don't appear in Session B's poller

    # Scoring Guide:
    #   1.0 — Thread isolation is architecturally guaranteed (unique keys + thread-specific polling)
    #   0.5 — Thread keys exist but polling isn't thread-specific (checks all messages)
    #   0.0 — No session isolation mechanism


Feature: F1.4 — Stop Gate Marker Integration
  Weight: 0.12

  Scenario: Stop gate recognizes GChat-forwarded questions
    Given the system3_continuation_judge.py
    When checking if AskUserQuestion was presented
    Then it checks .claude/state/gchat-forwarded-ask/ for recent marker files
    And markers < 30 minutes old count as "question presented"

    # Scoring Guide:
    #   1.0 — Judge checks marker directory, filters by age, treats as equivalent to terminal AskUserQuestion
    #   0.7 — Marker check exists but no age filtering (stale markers count)
    #   0.3 — Marker directory referenced but check not integrated into judge logic
    #   0.0 — No marker check in stop gate

    # Evidence to check:
    #   - system3_continuation_judge.py: look for "gchat-forwarded-ask" or "marker"
    #   - Age filtering logic (30 minute threshold)
    #   - Return True when recent markers found

    # Red flags:
    #   - Check exists but always returns True (no actual marker file check)
    #   - Age threshold is too long (> 60 minutes) or too short (< 5 minutes)

  Scenario: Stale markers are cleaned up
    Given marker files older than 24 hours exist
    When the hook or a cleanup mechanism runs
    Then markers older than 24 hours are deleted
    And recent markers are preserved

    # Scoring Guide:
    #   1.0 — Cleanup logic exists (either in hook, stop gate, or separate script)
    #   0.5 — Cleanup mentioned in comments/docs but not implemented
    #   0.0 — No cleanup mechanism

  Scenario: Stop gate still blocks when no questions presented
    Given no marker files exist AND no terminal AskUserQuestion was called
    When the stop gate evaluates
    Then the stop gate BLOCKS the session from stopping

    # Scoring Guide:
    #   1.0 — Both paths checked (terminal AskUserQuestion AND marker files), blocks when neither exists
    #   0.5 — Only one path checked (markers OR terminal, but not both)
    #   0.0 — Stop gate doesn't check for question presentation at all


# =============================================================================
# EPIC 2: Outbound Event Hooks
# =============================================================================

Feature: F2.1 — gchat-send CLI Utility
  Weight: 0.10

  Scenario: Script exists and is executable
    Given the claude-harness-setup repository
    When I check for gchat-send
    Then a script exists at .claude/scripts/gchat-send.sh
    And the script is executable (chmod +x)
    And it uses only curl and jq as external dependencies

    # Scoring Guide:
    #   1.0 — Script exists, executable, uses curl/jq
    #   0.7 — Script exists but not executable or uses Python instead
    #   0.3 — Script exists as stub
    #   0.0 — No script

  Scenario: Script reads webhook URL from environment or .mcp.json
    Given GOOGLE_CHAT_WEBHOOK_URL may or may not be set
    When gchat-send runs
    Then it uses $GOOGLE_CHAT_WEBHOOK_URL if set
    And falls back to reading webhook URL from .mcp.json if env var not set

    # Scoring Guide:
    #   1.0 — Both env var check and .mcp.json fallback implemented
    #   0.7 — Only env var check (no .mcp.json fallback)
    #   0.3 — Hardcoded URL
    #   0.0 — No URL resolution

  Scenario: Message types produce formatted output
    Given the 8 message types (task_completion, progress_update, blocked_alert, heartbeat, session_start, session_end, error, default)
    When gchat-send is called with --type flag
    Then each type produces a distinctly formatted message with appropriate prefix

    # Scoring Guide:
    #   1.0 — All 8 types implemented with distinct formatting
    #   0.7 — 5-7 types implemented
    #   0.5 — 3-4 types implemented
    #   0.3 — Only default (no type support)
    #   0.0 — No message formatting

  Scenario: Thread reply support
    Given a --thread-key argument
    When gchat-send is called with --thread-key "ask-user-12345"
    Then the POST includes threadKey in the request body
    And messageReplyOption is set appropriately

    # Scoring Guide:
    #   1.0 — --thread-key flag processed, included in POST body
    #   0.5 — Thread support mentioned but not implemented
    #   0.0 — No thread support


Feature: F2.2 — Notification Hook for GChat Dispatch
  Weight: 0.05

  Scenario: Notification hook forwards to GChat
    Given a Notification hook script at .claude/hooks/gchat-notification-dispatch.py
    When a Claude Code notification fires
    Then the hook parses the notification content
    And calls gchat-send with appropriate --type flag

    # Scoring Guide:
    #   1.0 — Hook exists, parses notification JSON, calls gchat-send
    #   0.5 — Hook exists but doesn't properly parse notification type
    #   0.0 — No notification hook


Feature: F2.3 — Stop Hook GChat Integration
  Weight: 0.05

  Scenario: Session end notification sent to GChat
    Given the unified-stop-gate.sh
    When all stop gate checks pass and session is about to exit
    Then gchat-send --type session_end is called
    And the message includes session ID, duration, and work summary

    # Scoring Guide:
    #   1.0 — Stop gate calls gchat-send on clean exit with session summary
    #   0.5 — GChat notification exists but summary is minimal
    #   0.0 — No GChat notification on session end


Feature: F2.4 — Direct gchat-send Usage in System 3
  Weight: 0.05

  Scenario: Output style uses gchat-send instead of SendMessage to communicator
    Given the system3-meta-orchestrator.md output style
    When System 3 wants to send a GChat message
    Then Bash("gchat-send ...") is used instead of SendMessage to s3-communicator

    # Scoring Guide:
    #   1.0 — All SendMessage-to-communicator patterns replaced with gchat-send
    #   0.7 — Some patterns replaced, some still use SendMessage
    #   0.3 — gchat-send mentioned but SendMessage patterns still primary
    #   0.0 — No changes to outbound messaging in output style


# =============================================================================
# EPIC 4: s3-communicator Removal + Migration
# =============================================================================

Feature: F4.1 — Update System 3 Output Style
  Weight: 0.08

  Scenario: No references to s3-communicator in output style
    Given system3-meta-orchestrator.md
    When searching for "s3-communicator"
    Then no references to spawning s3-communicator exist
    And the Persistent Agent Launch section spawns only heartbeat + validator
    And the Post-Compaction Recovery checks for 2 agents (not 3)

    # Scoring Guide:
    #   1.0 — All s3-communicator references removed, agent counts updated
    #   0.7 — Spawn removed but some stale references remain
    #   0.3 — Spawn still present, output style not updated
    #   0.0 — No changes to output style

    # Red flags:
    #   - "s3-communicator" still in Persistent Agent Launch code block
    #   - Cost table still lists $0.20-$0.50/day for communicator
    #   - Post-Compaction Recovery still checks for 3 agents

  Scenario: AskUserQuestion denial -> poller pattern documented
    Given the updated output style
    When AskUserQuestion is denied with GChat forwarding
    Then the output style includes a behavioral pattern for spawning the poller Task
    And the pattern shows how to extract thread key from denial reason

    # Scoring Guide:
    #   1.0 — Complete pattern with denial detection + thread key extraction + Task spawn
    #   0.5 — Pattern exists but incomplete (missing one of the three parts)
    #   0.0 — No pattern for handling denied AskUserQuestion


Feature: F4.2 — Update Stop Gate
  Weight: 0.07

  Scenario: Stop gate works without s3-communicator
    Given the stop gate checks
    When s3-communicator is NOT present in the s3-live team
    Then the stop gate still passes (checks for heartbeat or validator instead)
    And GChat marker files are accepted as valid AskUserQuestion

    # Scoring Guide:
    #   1.0 — Stop gate checks for ANY persistent agent (not specifically communicator) AND marker files work
    #   0.7 — Persistent agent check updated but marker file integration missing
    #   0.3 — Stop gate still hard-checks for s3-communicator (will fail without it)
    #   0.0 — No stop gate changes

    # Evidence to check:
    #   - communicator_checker.py or persistent_agent_checker.py
    #   - system3_continuation_judge.py for marker file check
    #   - Backward compatibility test (works WITH communicator too)

  Scenario: Backward compatible — works with communicator present
    Given s3-communicator IS present in the s3-live team (legacy state)
    When the stop gate evaluates
    Then the stop gate still passes

    # Scoring Guide:
    #   1.0 — Both with and without communicator work
    #   0.5 — Only works without communicator (breaks legacy)
    #   0.0 — Only works with communicator (not migrated)


Feature: F4.3 — Archive s3-communicator Skill
  Weight: 0.05

  Scenario: Skill archived to _archived directory
    Given .claude/skills/s3-communicator/ currently exists
    When the migration is complete
    Then .claude/skills/_archived/s3-communicator/ exists
    And .claude/skills/s3-communicator/ is removed or symlinked to archive
    And no broken references exist in active skills

    # Scoring Guide:
    #   1.0 — Moved to _archived/, no broken references, changelog updated
    #   0.7 — Moved but some references still point to old location
    #   0.3 — Marked as deprecated but not moved
    #   0.0 — No archival action taken

    # Evidence to check:
    #   - .claude/skills/_archived/s3-communicator/ exists
    #   - .claude/skills/s3-communicator/ removed or is symlink
    #   - grep -r "s3-communicator" in active skills (should be minimal/none)
    #   - .claude/documentation/SYSTEM3_CHANGELOG.md updated
