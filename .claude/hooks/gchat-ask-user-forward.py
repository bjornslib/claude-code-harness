#!/usr/bin/env python3
"""
PreToolUse hook: gchat-ask-user-forward.py
==========================================

Intercepts AskUserQuestion tool calls in System 3 sessions and forwards
the question to Google Chat via webhook instead of asking interactively.

Claude Code will then DENY the interactive ask; a separate poller (Haiku
Task spawned by the stop gate) reads the marker file and waits for the
GChat reply.

Hook type : PreToolUse (matcher: AskUserQuestion, timeout: 10)
Input     : JSON on stdin — {"session_id": "...", "tool_name": "AskUserQuestion",
                              "tool_input": {"questions": [...], ...}}
Output    : JSON on stdout — {"decision": "approve"} or {"decision": "block", "reason": "..."}

S3 Detection:
  - CLAUDE_OUTPUT_STYLE env var contains "system3"
  - OR session_id starts with "system3-" or "s3-"

GChat Integration (stdlib only — no subprocess, no MCP):
  - GOOGLE_CHAT_WEBHOOK_URL     : outbound webhook
  - ANTHROPIC_API_KEY           : optional Haiku formatting call

Marker files written to:
  .claude/state/gchat-forwarded-ask/{question_id}.json
  Fields: question_id, session_id, thread_key, thread_name, questions,
          forwarded_at, status="pending"
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _resolve_webhook_url() -> str:
    """Resolve webhook URL: env var first, then .mcp.json fallback."""
    url = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", "")
    if url:
        return url

    # Walk up from CLAUDE_PROJECT_DIR or cwd to find .mcp.json
    search_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    for _ in range(5):
        mcp_file = os.path.join(search_dir, ".mcp.json")
        if os.path.isfile(mcp_file):
            try:
                with open(mcp_file) as f:
                    mcp_config = json.load(f)
                url = (mcp_config
                       .get("mcpServers", {})
                       .get("google-chat-bridge", {})
                       .get("env", {})
                       .get("GOOGLE_CHAT_WEBHOOK_URL", ""))
                if url:
                    return url
            except (json.JSONDecodeError, OSError):
                pass
            break
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent
    return ""


def _resolve_anthropic_api_key() -> str:
    """
    Resolve ANTHROPIC_API_KEY for the Haiku auto-answer call.

    Priority order:
      1. S3_HAIKU_API_KEY — a dedicated env var that survives Claude Code account switches.
      2. ~/.zshrc — parse the last non-commented export to always use the zshrc key,
         not whatever key Claude Code's session happens to be running with.
      3. ANTHROPIC_API_KEY env — standard fallback.

    This prevents account-switch failures where Claude Code's own API key (used
    for the main session) is different from the personal zshrc key we want for
    the Haiku hook.
    """
    # 1. Dedicated override (set this in zshrc as S3_HAIKU_API_KEY=sk-ant-... for pinning)
    dedicated = os.environ.get("S3_HAIKU_API_KEY", "")
    if dedicated:
        return dedicated

    # 2. Parse zshrc directly — find the last uncommented ANTHROPIC_API_KEY export
    zshrc_path = os.path.expanduser("~/.zshrc")
    if os.path.isfile(zshrc_path):
        try:
            zshrc_key = ""
            with open(zshrc_path) as f:
                for line in f:
                    stripped = line.strip()
                    # Match: export ANTHROPIC_API_KEY=sk-ant-...  (not commented out)
                    if (not stripped.startswith("#")
                            and "ANTHROPIC_API_KEY=" in stripped
                            and "export" in stripped):
                        parts = stripped.split("ANTHROPIC_API_KEY=", 1)
                        if len(parts) == 2:
                            candidate = parts[1].strip().strip('"').strip("'")
                            if candidate.startswith("sk-"):
                                zshrc_key = candidate
            if zshrc_key:
                return zshrc_key
        except OSError:
            pass

    # 3. Standard env fallback (may be Claude Code's own session key)
    return os.environ.get("ANTHROPIC_API_KEY", "")


WEBHOOK_URL: str = _resolve_webhook_url()
ANTHROPIC_API_KEY: str = _resolve_anthropic_api_key()
HAIKU_MODEL: str = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# S3 Session Detection
# ---------------------------------------------------------------------------


def is_system3_session(session_id: str) -> bool:
    """
    Return True if the current session is a System 3 (meta-orchestrator) session.

    Checks (in order):
    1. CLAUDE_OUTPUT_STYLE env var contains "system3"
    2. session_id starts with a known S3 prefix
    """
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "").lower()
    if "system3" in output_style:
        return True

    # Common S3 session ID prefixes (e.g. "system3-20260222T...", "s3-...")
    if session_id.startswith(("system3-", "s3-")):
        return True

    return False


# ---------------------------------------------------------------------------
# Question Formatting
# ---------------------------------------------------------------------------


def auto_answer_via_haiku(questions: list[dict], session_id: str) -> dict:
    """
    Call Haiku to intelligently answer an AskUserQuestion.

    Returns a dict mapping question index to the selected answer:
      {"answers": {"Q1": "Option 2 — Description"}, "reasoning": "..."}

    Falls back to picking the first (recommended) option if API call fails.
    """
    if not ANTHROPIC_API_KEY:
        return _auto_answer_fallback(questions)

    questions_json = json.dumps(questions, indent=2)
    prompt = (
        f"A Claude Code agent (session: {session_id[:30]}) is asking questions "
        f"during automated work. Pick the BEST option for each question.\n\n"
        f"Rules:\n"
        f"- If an option says '(Recommended)', prefer it unless clearly wrong.\n"
        f"- Prefer options that continue work over options that stop/skip.\n"
        f"- Prefer safe, reversible options over destructive ones.\n"
        f"- Be concise in reasoning.\n\n"
        f"Questions payload:\n{questions_json}\n\n"
        f"Respond in this exact JSON format:\n"
        f'{{"answers": {{"Q1": "option label or custom text", "Q2": "..."}}, '
        f'"reasoning": "brief explanation"}}'
    )

    try:
        body = {
            "model": HAIKU_MODEL,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        response_text = result["content"][0]["text"]

        # Try to parse as JSON
        try:
            parsed = json.loads(response_text)
            return parsed
        except json.JSONDecodeError:
            # Haiku returned non-JSON — use the raw text as reasoning
            return {
                "answers": {f"Q{i+1}": q.get("options", [{}])[0].get("label", "Option 1")
                            for i, q in enumerate(questions)},
                "reasoning": response_text[:200],
            }

    except Exception:
        return _auto_answer_fallback(questions)


def _auto_answer_fallback(questions: list[dict]) -> dict:
    """
    Fallback: pick the first option (typically the recommended one) for each question.
    """
    answers = {}
    for i, q in enumerate(questions):
        options = q.get("options", [])
        if options:
            answers[f"Q{i+1}"] = options[0].get("label", "Option 1")
        else:
            answers[f"Q{i+1}"] = "(no options provided)"
    return {"answers": answers, "reasoning": "Fallback: selected first (recommended) option"}


def format_auto_answer_for_agent(questions: list[dict], auto_result: dict) -> str:
    """
    Format the auto-answer as a block reason that the agent can understand and act on.

    The agent receives this as the AskUserQuestion block reason and should
    proceed with the selected answers.
    """
    answers = auto_result.get("answers", {})
    reasoning = auto_result.get("reasoning", "")

    lines = [
        "[gchat-ask-user-forward] AskUserQuestion auto-answered by Haiku.",
        "",
    ]

    for i, q in enumerate(questions):
        q_key = f"Q{i+1}"
        header = q.get("header", "")
        question_text = q.get("question", "")
        answer = answers.get(q_key, "(no answer)")

        if len(questions) > 1:
            prefix = f"Q{i+1}"
            if header:
                prefix += f" ({header})"
            lines.append(f"{prefix}: {question_text}")
        else:
            if header:
                lines.append(f"{header}: {question_text}")
            else:
                lines.append(f"Question: {question_text}")

        lines.append(f"  -> Selected: {answer}")
        lines.append("")

    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
        lines.append("")

    lines.append("Proceed with these selections. If they seem wrong, re-ask with more context.")
    return "\n".join(lines)


def format_auto_answer_for_gchat(
    questions: list[dict], auto_result: dict, session_id: str
) -> str:
    """
    Format the auto-answer as a GChat FYI notification so the user knows what happened.
    """
    answers = auto_result.get("answers", {})
    reasoning = auto_result.get("reasoning", "")
    short_session = session_id[:24]

    project_ctx = _get_project_context()
    lines = [
        f"*[Auto-Answered]* AskUserQuestion from session `{short_session}`",
        f"_{project_ctx}_",
        "",
    ]

    for i, q in enumerate(questions):
        q_key = f"Q{i+1}"
        header = q.get("header", "")
        question_text = q.get("question", "")
        answer = answers.get(q_key, "(no answer)")
        options = q.get("options", [])

        if header:
            lines.append(f"*{header}*: {question_text}")
        else:
            lines.append(f"*Q{i+1}*: {question_text}")

        if options:
            for j, opt in enumerate(options):
                label = opt.get("label", f"Option {j+1}")
                marker = " *<-- selected*" if label == answer else ""
                lines.append(f"  {j+1}. {label}{marker}")

        lines.append(f"  *Answer*: {answer}")
        lines.append("")

    if reasoning:
        lines.append(f"_Reasoning: {reasoning}_")

    return "\n".join(lines)


def _get_project_context() -> str:
    """
    Derive a short project context string from the environment.

    Returns a 1-2 sentence summary like:
      "Project: claude-harness-setup | Output style: system3-meta-orchestrator"
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    project_name = os.path.basename(project_dir)
    output_style = os.environ.get("CLAUDE_OUTPUT_STYLE", "")

    parts = [f"Project: *{project_name}*"]
    if output_style:
        parts.append(f"Style: `{output_style}`")

    # Check for active initiative from CLAUDE_SESSION_DIR or session ID
    session_dir = os.environ.get("CLAUDE_SESSION_DIR", "")
    if session_dir:
        parts.append(f"Initiative: `{session_dir}`")

    return " | ".join(parts)


def format_question_for_gchat(questions: list[dict], session_id: str) -> str:
    """
    Format the AskUserQuestion payload into a Google Chat message string.

    Tries Haiku API first for richer formatting; falls back to manual format
    if the API call fails or the key is not set.
    """
    if ANTHROPIC_API_KEY:
        try:
            return _format_via_haiku(questions, session_id)
        except Exception:
            pass  # Fall through to manual formatting

    return _format_manually(questions, session_id)


def _format_via_haiku(questions: list[dict], session_id: str) -> str:
    """Call claude-haiku to produce a well-formatted GChat message."""
    questions_json = json.dumps(questions, indent=2)
    project_ctx = _get_project_context()
    prompt = (
        f"Format the following Claude Code AskUserQuestion payload as a Google Chat "
        f"message.\n\n"
        f"Be concise and clear. Use Google Chat markdown (*bold*, _italic_, `code`).\n"
        f"Start with a 1-2 sentence context summary so the reader knows which "
        f"project/topic this relates to. Use this context: {project_ctx}\n"
        f"Then include: the question(s), options (numbered), and a note to reply with the "
        f"option number or custom text.\n\n"
        f"Session: {session_id[:30]}\n\n"
        f"Questions payload:\n{questions_json}\n\n"
        f"Produce ONLY the message text, no preamble."
    )

    body = {
        "model": HAIKU_MODEL,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"]


def _format_manually(questions: list[dict], session_id: str) -> str:
    """
    Manual formatting fallback (no external API call).

    Produces a readable GChat message with *bold* labels and numbered options.
    """
    short_session = session_id[:24]
    project_ctx = _get_project_context()
    lines: list[str] = [
        f"*[Claude Code — System 3]* Question from session `{short_session}`",
        f"_{project_ctx}_",
        "",
    ]

    for i, q in enumerate(questions):
        header = q.get("header", "")
        question_text = q.get("question", "(no question text)")
        options: list[dict] = q.get("options", [])
        multi = q.get("multiSelect", False)

        if len(questions) > 1:
            prefix = f"*Q{i + 1}*"
            if header:
                prefix += f" ({header})"
            lines.append(f"{prefix}: {question_text}")
        else:
            if header:
                lines.append(f"*{header}*: {question_text}")
            else:
                lines.append(f"*Question:* {question_text}")

        if options:
            lines.append("*Options:*")
            for j, opt in enumerate(options):
                label = opt.get("label", f"Option {j + 1}")
                desc = opt.get("description", "")
                if desc:
                    lines.append(f"  {j + 1}. *{label}* — {desc}")
                else:
                    lines.append(f"  {j + 1}. {label}")

        if multi:
            lines.append(
                "_(Multi-select — reply with comma-separated numbers or free text)_"
            )
        else:
            lines.append("_(Reply with the option number or type a custom response)_")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GChat Webhook
# ---------------------------------------------------------------------------


def send_to_gchat(message_text: str, thread_key: str) -> dict:
    """
    POST a message to the GChat webhook with the given threadKey.

    Uses messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD so that
    subsequent messages with the same threadKey are grouped in one thread.
    The full API response is returned (contains thread.name for polling).
    """
    url = f"{WEBHOOK_URL}&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
    body = {
        "text": message_text,
        "thread": {"threadKey": thread_key},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Marker File
# ---------------------------------------------------------------------------


def _cleanup_stale_markers(marker_dir: str, max_age_hours: int = 24) -> None:
    """Remove marker files: pending >24h, resolved/timeout >1h."""
    if not os.path.isdir(marker_dir):
        return
    now = time.time()
    for filename in os.listdir(marker_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(marker_dir, filename)
        try:
            age_seconds = now - os.path.getmtime(filepath)
            # Always remove markers older than max_age_hours
            if age_seconds > max_age_hours * 3600:
                os.remove(filepath)
                continue
            # Clean resolved/timeout markers after 1 hour
            if age_seconds > 3600:
                with open(filepath) as f:
                    data = json.load(f)
                if data.get("status") in ("resolved", "timeout"):
                    os.remove(filepath)
        except (OSError, json.JSONDecodeError):
            pass


def write_marker(
    question_id: str,
    thread_key: str,
    thread_name: str,
    questions: list[dict],
    session_id: str,
    project_dir: str,
) -> Path:
    """
    Write a JSON marker file to .claude/state/gchat-forwarded-ask/{question_id}.json.

    The marker is used by the stop gate / Haiku poller to:
      - Know which GChat thread to poll (thread_name)
      - Match the reply back to the original question (question_id)
      - Track resolution status (status: "pending" → "resolved")
    """
    state_dir = Path(project_dir) / ".claude" / "state" / "gchat-forwarded-ask"
    state_dir.mkdir(parents=True, exist_ok=True)

    marker_path = state_dir / f"{question_id}.json"
    marker = {
        "question_id": question_id,
        "session_id": session_id,
        "thread_key": thread_key,
        "thread_name": thread_name,
        "questions": questions,
        "forwarded_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    marker_path.write_text(json.dumps(marker, indent=2))
    return marker_path


# ---------------------------------------------------------------------------
# Non-S3 Auto-Answer Handler
# ---------------------------------------------------------------------------


def _handle_non_s3_auto_answer(
    questions: list[dict], session_id: str, project_dir: str
) -> None:
    """
    Handle AskUserQuestion for non-S3 sessions (orchestrators/workers in tmux).

    Strategy:
      1. Call Haiku to pick the best answer(s) for the question(s).
      2. Send an FYI notification to GChat so the user knows what was auto-answered.
      3. Block the interactive AskUserQuestion with the auto-answer as the reason
         so the agent proceeds without hanging.

    Fails open: if anything goes wrong, approve the interactive ask instead of
    silently blocking the agent.
    """
    try:
        # 1. Auto-answer via Haiku (or fallback to first option)
        auto_result = auto_answer_via_haiku(questions, session_id)

        # 2. Send FYI notification to GChat (best-effort; don't fail if missing)
        if WEBHOOK_URL:
            try:
                short_uuid = uuid.uuid4().hex[:8]
                safe_session = "".join(
                    c if c.isalnum() or c == "-" else "-" for c in session_id[:20]
                ).rstrip("-")
                thread_key = f"auto-{safe_session}-{short_uuid}"
                gchat_text = format_auto_answer_for_gchat(questions, auto_result, session_id)
                send_to_gchat(gchat_text, thread_key)
            except Exception:
                pass  # GChat FYI is non-critical; continue regardless

        # 3. Block the interactive ask with the auto-answer as the reason
        block_reason = format_auto_answer_for_agent(questions, auto_result)
        print(json.dumps({"decision": "block", "reason": block_reason}))

    except Exception as exc:
        # Fail open: let the agent ask interactively rather than hang
        error_log = (
            Path(project_dir) / ".claude" / "state" / "gchat-forwarded-ask" / "errors.log"
        )
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with open(error_log, "a") as fh:
                fh.write(
                    f"{datetime.now(timezone.utc).isoformat()} "
                    f"ERROR [non-s3-auto-answer session={session_id[:24]}]: {exc}\n"
                )
        except Exception:
            pass

        print(json.dumps({
            "decision": "approve",
            "systemMessage": (
                f"[gchat-ask-user-forward] Auto-answer failed ({exc}); "
                f"falling back to interactive ask."
            ),
        }))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    session_id: str = hook_input.get("session_id", "")
    # Prefer CLAUDE_SESSION_ID (set by ccsystem3) for marker file consistency.
    # The stop gate uses this env var to filter markers by session.
    claude_session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if claude_session_id:
        session_id = claude_session_id
    tool_name: str = hook_input.get("tool_name", "")
    tool_input: dict = hook_input.get("tool_input", {})

    # ── Cleanup stale markers early (before creating any new marker) ──
    project_dir: str = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    _marker_dir = os.path.join(project_dir, ".claude", "state", "gchat-forwarded-ask")
    _cleanup_stale_markers(_marker_dir)

    # ── Fast path: tool name guard (matcher should prevent this, but be defensive) ──
    if tool_name != "AskUserQuestion":
        print(json.dumps({"decision": "approve"}))
        return

    # ── Parse questions ──
    questions: list[dict] = tool_input.get("questions", [])
    if not questions:
        print(json.dumps({"decision": "approve"}))
        return

    # ── Branch: S3 sessions → forward to GChat and wait for user reply ──
    # ── Branch: Non-S3 sessions → Haiku auto-answer + GChat FYI notification ──

    is_s3 = is_system3_session(session_id)

    if not is_s3:
        # ── Non-S3 path: Auto-answer via Haiku, send FYI to GChat ──
        _handle_non_s3_auto_answer(questions, session_id, project_dir)
        return

    # ── S3 path: Forward to GChat and wait for user reply ──
    if not WEBHOOK_URL:
        print(json.dumps({
            "decision": "approve",
            "systemMessage": "[gchat-ask-user-forward] GOOGLE_CHAT_WEBHOOK_URL not set; using interactive ask.",
        }))
        return

    # ── Generate unique IDs ──
    short_uuid = uuid.uuid4().hex[:8]
    # Sanitise session_id for use in threadKey (alphanumeric + hyphens only)
    safe_session = "".join(
        c if c.isalnum() or c == "-" else "-" for c in session_id[:20]
    ).rstrip("-")
    thread_key = f"ask-{safe_session}-{short_uuid}"
    question_id = f"{safe_session}-{short_uuid}"

    try:
        # 1. Format the question for GChat
        message_text = format_question_for_gchat(questions, session_id)

        # 2. POST to webhook
        webhook_response = send_to_gchat(message_text, thread_key)

        # 3. Extract the thread resource name (used by poller for targeted polling)
        thread_name: str = webhook_response.get("thread", {}).get("name", "")
        message_name: str = webhook_response.get("name", "")

        # 4. Write marker file
        marker_path = write_marker(
            question_id=question_id,
            thread_key=thread_key,
            thread_name=thread_name,
            questions=questions,
            session_id=session_id,
            project_dir=project_dir,
        )

        # 5. Block the interactive AskUserQuestion — forwarded to GChat
        block_reason = (
            f"[gchat-ask-user-forward] Question forwarded to Google Chat.\n\n"
            f"  Thread key    : {thread_key}\n"
            f"  Thread name   : {thread_name or '(not returned by webhook)'}\n"
            f"  Message name  : {message_name or '(not returned by webhook)'}\n"
            f"  Marker file   : {marker_path}\n\n"
            f"Awaiting GChat response. "
            f"The stop gate will check for a pending reply before allowing the session to end."
        )
        print(json.dumps({"decision": "block", "reason": block_reason}))

    except Exception as exc:
        # Fail open: let the agent ask interactively rather than block on error
        error_log = (
            Path(project_dir) / ".claude" / "state" / "gchat-forwarded-ask" / "errors.log"
        )
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with open(error_log, "a") as fh:
                fh.write(
                    f"{datetime.now(timezone.utc).isoformat()} ERROR [{question_id}]: {exc}\n"
                )
        except Exception:
            pass

        print(json.dumps({
            "decision": "approve",
            "systemMessage": (
                f"[gchat-ask-user-forward] GChat forwarding failed ({exc}); "
                f"falling back to interactive ask."
            ),
        }))


if __name__ == "__main__":
    main()
