#!/bin/bash
# gchat-send.sh — Send formatted messages to Google Chat via webhook
#
# Usage:
#   gchat-send.sh [OPTIONS] "message text"
#   gchat-send.sh --type task_completion --title "Task done" "Details here"
#   gchat-send.sh --type blocked_alert --thread-key orch-session1 "Blocked on X"
#
# Options:
#   --type TYPE       Message type (see Types below). Default: message
#   --title TEXT      Bold header line prepended to the message
#   --thread-key KEY  Reply to a named thread (creates thread if new)
#   --session TEXT    Session ID for context (defaults to $CLAUDE_SESSION_ID)
#   --webhook URL     Override webhook URL (also reads GOOGLE_CHAT_WEBHOOK_URL)
#   --dry-run         Print payload without sending
#   --help            Show this help
#
# Types:
#   task_completion   ✅ Task completed successfully
#   progress_update   🔄 Progress update on ongoing work
#   blocked_alert     🚨 Blocked — needs attention
#   heartbeat         💓 Periodic alive check-in
#   session_start     🚀 Session starting
#   session_end       🏁 Session ending / wrap-up
#   error             ❌ Error occurred
#   message           (default) Plain message
#
# Webhook URL resolution order:
#   1. --webhook flag
#   2. $GOOGLE_CHAT_WEBHOOK_URL env var
#   3. google-chat-bridge.env.GOOGLE_CHAT_WEBHOOK_URL in .mcp.json (project root)
#
# Exit codes:
#   0  Message sent (or dry-run)
#   1  No webhook URL found
#   2  curl error / HTTP error from API
#   3  Missing required argument

set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
TYPE="message"
TITLE=""
THREAD_KEY=""
SESSION_ID="${CLAUDE_SESSION_ID:-}"
WEBHOOK_URL="${GOOGLE_CHAT_WEBHOOK_URL:-}"
DRY_RUN=false
MESSAGE=""

# ─── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            TYPE="$2"; shift 2 ;;
        --title)
            TITLE="$2"; shift 2 ;;
        --thread-key)
            THREAD_KEY="$2"; shift 2 ;;
        --session)
            SESSION_ID="$2"; shift 2 ;;
        --webhook)
            WEBHOOK_URL="$2"; shift 2 ;;
        --dry-run)
            DRY_RUN=true; shift ;;
        --help|-h)
            sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        --)
            shift; MESSAGE="$*"; break ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Run with --help for usage." >&2
            exit 3 ;;
        *)
            MESSAGE="$*"
            break ;;
    esac
done

if [[ -z "$MESSAGE" ]]; then
    echo "Error: no message provided." >&2
    echo "Usage: gchat-send.sh [OPTIONS] \"message text\"" >&2
    exit 3
fi

# ─── Webhook URL resolution ───────────────────────────────────────────────────
if [[ -z "$WEBHOOK_URL" ]]; then
    # Walk up from cwd to find .mcp.json (up to 5 levels)
    search_dir="$(pwd)"
    for _ in 1 2 3 4 5; do
        mcp_file="$search_dir/.mcp.json"
        if [[ -f "$mcp_file" ]]; then
            if command -v jq &>/dev/null; then
                WEBHOOK_URL=$(jq -r \
                    '.mcpServers["google-chat-bridge"].env.GOOGLE_CHAT_WEBHOOK_URL // empty' \
                    "$mcp_file" 2>/dev/null || true)
            fi
            break
        fi
        parent="$(dirname "$search_dir")"
        [[ "$parent" == "$search_dir" ]] && break
        search_dir="$parent"
    done
fi

if [[ -z "$WEBHOOK_URL" ]]; then
    echo "Error: no GOOGLE_CHAT_WEBHOOK_URL found." >&2
    echo "Set env var or add google-chat-bridge to .mcp.json." >&2
    exit 1
fi

# ─── Type metadata ────────────────────────────────────────────────────────────
case "$TYPE" in
    task_completion)  EMOJI="✅"; LABEL="Task Completed" ;;
    progress_update)  EMOJI="🔄"; LABEL="Progress Update" ;;
    blocked_alert)    EMOJI="🚨"; LABEL="BLOCKED" ;;
    heartbeat)        EMOJI="💓"; LABEL="Heartbeat" ;;
    session_start)    EMOJI="🚀"; LABEL="Session Start" ;;
    session_end)      EMOJI="🏁"; LABEL="Session End" ;;
    error)            EMOJI="❌"; LABEL="Error" ;;
    message|*)        EMOJI="💬"; LABEL="" ;;
esac

# ─── Build text body ──────────────────────────────────────────────────────────
body=""

# Header line: emoji + label
if [[ -n "$LABEL" ]]; then
    body="*${EMOJI} ${LABEL}*"
fi

# Optional bold title
if [[ -n "$TITLE" ]]; then
    [[ -n "$body" ]] && body="${body}\n"
    body="${body}*${TITLE}*"
fi

# Message body
if [[ -n "$body" ]]; then
    body="${body}\n${MESSAGE}"
else
    body="${MESSAGE}"
fi

# Session context footer
if [[ -n "$SESSION_ID" ]]; then
    body="${body}\n_Session: ${SESSION_ID}_"
fi

# ─── Build JSON payload ───────────────────────────────────────────────────────
# Escape body for JSON (jq handles this cleanly)
payload=$(jq -n --arg text "$body" '{"text": $text}')

# Add thread if requested
if [[ -n "$THREAD_KEY" ]]; then
    payload=$(echo "$payload" | jq \
        --arg key "$THREAD_KEY" \
        '. + {"thread": {"threadKey": $key}}')
fi

# ─── Send (or dry-run) ────────────────────────────────────────────────────────
if $DRY_RUN; then
    echo "=== DRY RUN — would POST to ==="
    echo "$WEBHOOK_URL"
    echo ""
    echo "=== Payload ==="
    echo "$payload" | jq .
    exit 0
fi

# Append thread reply option to URL if thread key set
send_url="$WEBHOOK_URL"
if [[ -n "$THREAD_KEY" ]]; then
    send_url="${send_url}&messageReplyOption=REPLY_MESSAGE_OR_FAIL"
fi

http_code=$(curl -s -o /tmp/gchat_send_response.json -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$send_url" 2>/tmp/gchat_send_curl_err || true)

curl_exit=$?

if [[ $curl_exit -ne 0 ]]; then
    echo "Error: curl failed (exit $curl_exit)" >&2
    cat /tmp/gchat_send_curl_err >&2 2>/dev/null || true
    exit 2
fi

if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
    echo "Error: Google Chat API returned HTTP $http_code" >&2
    cat /tmp/gchat_send_response.json >&2 2>/dev/null || true
    exit 2
fi

# Success — optionally surface the thread name for caller to store
thread_name=$(jq -r '.thread.name // empty' /tmp/gchat_send_response.json 2>/dev/null || true)
if [[ -n "$thread_name" ]]; then
    echo "$thread_name"
fi

exit 0
