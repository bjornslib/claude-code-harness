#!/usr/bin/env python3
"""Runner Agent (Layer 2) — Guardian Architecture.

Invokes Claude via the claude_code_sdk to monitor an orchestrator tmux session
and signal the Guardian at decision points.

Architecture:
    runner_agent.py (Python process)
        │
        ├── Parse CLI args
        ├── build_system_prompt()    → monitoring instructions for Claude
        ├── build_initial_prompt()   → first user message with immediate context
        ├── build_options()          → ClaudeCodeOptions (Bash only, max_turns, model)
        └── asyncio.run(_run_agent())
               │
               └── async for message in query(initial_prompt, options=options):
                       # Claude uses Bash to run CLI tools in scripts_dir
                       pass

CLAUDECODE environment note:
    The Runner may be launched from inside a Claude Code session. To avoid
    nested-session conflicts, we pass env={"CLAUDECODE": ""} as a workaround
    to suppress the variable. The definitive fix (subprocess.Popen with a
    cleaned env) lives in spawn_runner.py and will be implemented in a later epic.

Usage:
    python runner_agent.py \\
        --node <node_id> \\
        --prd <prd_ref> \\
        --session <tmux_session_name> \\
        [--dot-file <path_to_pipeline.dot>] \\
        [--solution-design <path>] \\
        [--acceptance <text>] \\
        [--target-dir <path>] \\
        [--bead-id <id>] \\
        [--check-interval <seconds>] \\
        [--stuck-threshold <seconds>] \\
        [--max-turns <n>] \\
        [--model <model_id>] \\
        [--signals-dir <path>] \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import warnings
from typing import Any

# Ensure this file's directory is importable regardless of invocation CWD.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# ---------------------------------------------------------------------------
# Logfire instrumentation (required)
# ---------------------------------------------------------------------------
import logfire
logfire.configure(
    inspect_arguments=False,
    scrubbing=logfire.ScrubbingOptions(callback=lambda m: m.value),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_CHECK_INTERVAL = 30      # seconds between polling cycles
DEFAULT_STUCK_THRESHOLD = 300    # seconds before declaring "stuck"
DEFAULT_MAX_TURNS = 100          # enough turns for a long monitoring loop


# ---------------------------------------------------------------------------
# Public helper functions (importable for testing)
# ---------------------------------------------------------------------------


def build_system_prompt(
    node_id: str,
    prd_ref: str,
    session_name: str,
    acceptance: str,
    scripts_dir: str,
    check_interval: int,
    stuck_threshold: int,
) -> str:
    """Return the system prompt that instructs the Claude agent how to monitor.

    Args:
        node_id: Pipeline node identifier (e.g., ``impl_auth``).
        prd_ref: PRD reference string (e.g., ``PRD-AUTH-001``).
        session_name: tmux session name hosting the orchestrator.
        acceptance: Human-readable acceptance criteria text.
        scripts_dir: Absolute path to the attractor scripts directory.
        check_interval: Polling interval in seconds.
        stuck_threshold: Seconds of no progress before raising ORCHESTRATOR_STUCK.

    Returns:
        Formatted system prompt string.
    """
    with logfire.span("runner.build_system_prompt", node_id=node_id, prd_ref=prd_ref):
        return f"""\
You are a Runner agent (Layer 2) in a 4-layer pipeline execution system.

Your role: Monitor an orchestrator tmux session and signal the Guardian at decision points.

## Your Assignment
- Node ID: {node_id}
- PRD Reference: {prd_ref}
- tmux Session: {session_name}
- Acceptance Criteria: {acceptance or "See DOT file"}

## Tools Available (via Bash)
All tool scripts are in {scripts_dir}:
- capture_output.py --session <name> [--lines <n>]    # Read tmux pane content
- check_orchestrator_alive.py --session <name>         # Check if session exists
- signal_guardian.py <TYPE> --node <id> [--evidence <path>] [--question <text>]  # Signal Guardian
- wait_for_guardian.py --node <id> [--timeout <s>]     # Wait for Guardian response
- send_to_orchestrator.py --session <name> --message <text>  # Send to orchestrator

## Monitoring Loop
1. Check if orchestrator is alive: `python {scripts_dir}/capture_output.py --session {session_name} --lines 5`
2. If not alive: signal ORCHESTRATOR_CRASHED to Guardian
3. Capture recent output: `python {scripts_dir}/capture_output.py --session {session_name} --lines 100`
4. Interpret the output with your intelligence (not regex):
   - Has the orchestrator completed the node implementation?
   - Is it asking a question or waiting for input?
   - Is it stuck (no meaningful progress)?
   - Has it violated guard rails (using Edit/Write directly)?
5. Signal the Guardian if a decision point is reached
6. Wait for Guardian response and relay it to the orchestrator if needed
7. Repeat from step 1 (with {check_interval}s sleep between iterations)

## Signal Types
Signal the Guardian using: python {scripts_dir}/signal_guardian.py <TYPE> --node {node_id} [options]

- NEEDS_REVIEW: Implementation appears complete, needs validation
  Use: signal_guardian.py NEEDS_REVIEW --node {node_id} --commit <hash> --summary <text>

- NEEDS_INPUT: Orchestrator is asking a question or waiting for decision
  Use: signal_guardian.py NEEDS_INPUT --node {node_id} --question "<text>" --options '<json>'

- VIOLATION: Orchestrator violated guard rails (used Edit/Write directly)
  Use: signal_guardian.py VIOLATION --node {node_id} --reason "<description>"

- ORCHESTRATOR_STUCK: No meaningful progress for {stuck_threshold}s
  Use: signal_guardian.py ORCHESTRATOR_STUCK --node {node_id} --duration <seconds> --last-output "<text>"

- ORCHESTRATOR_CRASHED: tmux session no longer exists
  Use: signal_guardian.py ORCHESTRATOR_CRASHED --node {node_id} --last-output "<text>"

- NODE_COMPLETE: Node finished with committed work
  Use: signal_guardian.py NODE_COMPLETE --node {node_id} --commit <hash> --summary <text>

## After Signaling
After signaling NEEDS_REVIEW, NEEDS_INPUT, or VIOLATION, wait for Guardian:
  python {scripts_dir}/wait_for_guardian.py --node {node_id} --timeout 600

The Guardian response will have signal_type one of:
- VALIDATION_PASSED: Node validated, work is done → exit
- VALIDATION_FAILED: Re-work needed → relay feedback to orchestrator and continue monitoring
- INPUT_RESPONSE: Guardian made a decision → relay via send_to_orchestrator
- KILL_ORCHESTRATOR: Guardian wants to abort → exit with appropriate code
- GUIDANCE: Guardian sending proactive guidance → relay to orchestrator

After receiving VALIDATION_PASSED, also notify the terminal layer:
  python {scripts_dir}/signal_guardian.py VALIDATION_COMPLETE --node {node_id} --target terminal --summary "Node {node_id} validated"
  Then exit normally.

## Completion
- Exit normally when you receive VALIDATION_PASSED or KILL_ORCHESTRATOR
- Exit with error code if orchestrator crashes and Guardian cannot recover

## Indicators to Watch For

Completion indicators:
- "All tasks complete", "Implementation done", "Committed", git commit messages
- Orchestrator reporting completion via its own signals

Input needed indicators:
- AskUserQuestion dialogs in Claude's output
- "Do you want to...", "Should I...", "Awaiting your input"
- Long pauses with no output change

Violation indicators:
- "Editing file...", "Writing to...", direct file modification by orchestrator (it should delegate)
- Edit/Write tool usage in orchestrator's output

Stuck indicators:
- Same output for multiple polling cycles
- Repeated identical tool calls
- Error loops (same error repeating)
"""


def build_initial_prompt(
    node_id: str,
    prd_ref: str,
    session_name: str,
    acceptance: str,
    scripts_dir: str,
    check_interval: int,
    stuck_threshold: int,
) -> str:
    """Return the first user message sent to Claude to start the monitoring loop.

    Args:
        node_id: Pipeline node identifier.
        prd_ref: PRD reference string.
        session_name: tmux session name hosting the orchestrator.
        acceptance: Acceptance criteria text.
        scripts_dir: Absolute path to the attractor scripts directory.
        check_interval: Polling interval in seconds.
        stuck_threshold: Seconds of no progress before declaring stuck.

    Returns:
        Formatted initial prompt string.
    """
    with logfire.span("runner.build_initial_prompt", node_id=node_id, prd_ref=prd_ref):
        return (
            f"You are monitoring orchestrator in tmux session '{session_name}' "
            f"implementing node '{node_id}' for {prd_ref}.\n\n"
            f"Your assignment:\n"
            f"- Node: {node_id}\n"
            f"- PRD: {prd_ref}\n"
            f"- Session: {session_name}\n"
            f"- Acceptance criteria: {acceptance or 'See DOT file'}\n"
            f"- Check interval: {check_interval}s\n"
            f"- Stuck threshold: {stuck_threshold}s\n\n"
            f"Start by checking if the orchestrator is alive, then begin the monitoring loop.\n"
            f"Scripts directory: {scripts_dir}\n"
        )


def build_options(
    system_prompt: str,
    cwd: str,
    model: str,
    max_turns: int,
) -> Any:
    """Construct a ClaudeCodeOptions instance for the Runner agent.

    The Runner is restricted to Bash only — it must not call Edit/Write/etc.
    CLAUDECODE is overridden to an empty string to suppress nested session
    warnings (the authoritative fix is in spawn_runner.py using Popen).

    Args:
        system_prompt: Monitoring instructions for Claude.
        cwd: Working directory for the agent (project root).
        model: Claude model identifier.
        max_turns: Maximum turns before the SDK stops the conversation.

    Returns:
        Configured ClaudeCodeOptions instance.
    """
    with logfire.span("runner.build_options", model=model):
        from claude_code_sdk import ClaudeCodeOptions

        return ClaudeCodeOptions(
            allowed_tools=["Bash"],
            system_prompt=system_prompt,
            cwd=cwd,
            model=model,
            max_turns=max_turns,
            # Suppress CLAUDECODE env var to avoid nested-session conflicts.
            # Definitive fix (subprocess.Popen with cleaned env) is in spawn_runner.py.
            env={"CLAUDECODE": ""},
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for runner_agent.py.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        prog="runner_agent.py",
        description="Runner Agent (Layer 2): monitors orchestrator via claude_code_sdk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner_agent.py --node impl_auth --prd PRD-AUTH-001 --session orch-auth

  python runner_agent.py --node impl_auth --prd PRD-AUTH-001 --session orch-auth \\
      --acceptance "Auth module passes all tests" --check-interval 60 --dry-run
        """,
    )
    parser.add_argument("--node", required=True, help="Pipeline node identifier")
    parser.add_argument("--prd", required=True, help="PRD reference (e.g. PRD-AUTH-001)")
    parser.add_argument("--session", required=True, help="tmux session name for orchestrator")
    parser.add_argument("--dot-file", default=None, dest="dot_file",
                        help="Path to pipeline .dot file")
    parser.add_argument("--solution-design", default=None, dest="solution_design",
                        help="Path to solution design document")
    parser.add_argument("--acceptance", default=None,
                        help="Acceptance criteria text")
    parser.add_argument("--target-dir", required=True, dest="target_dir",
                        help="Working directory for the agent")
    parser.add_argument("--bead-id", default=None, dest="bead_id",
                        help="Beads issue/task identifier")
    parser.add_argument("--check-interval", type=int, default=DEFAULT_CHECK_INTERVAL,
                        dest="check_interval",
                        help=f"Seconds between polling cycles (default: {DEFAULT_CHECK_INTERVAL})")
    parser.add_argument("--stuck-threshold", type=int, default=DEFAULT_STUCK_THRESHOLD,
                        dest="stuck_threshold",
                        help=f"Seconds of no progress before ORCHESTRATOR_STUCK (default: {DEFAULT_STUCK_THRESHOLD})")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                        dest="max_turns",
                        help=f"Max SDK turns (default: {DEFAULT_MAX_TURNS})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--signals-dir", default=None, dest="signals_dir",
                        help="Override signals directory path")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Log config without spawning the SDK agent (for testing)")

    args = parser.parse_args(argv)

    # Warn if session name uses reserved s3-live- prefix (runner monitors an existing
    # session, doesn't create one, so we warn but don't block).
    if args.session and re.match(r"s3-live-", args.session):
        warnings.warn(
            f"Session name '{args.session}' uses reserved 's3-live-' prefix. "
            "Expected prefix is 'orch-' for orchestrator sessions.",
            UserWarning,
            stacklevel=2,
        )

    return args


def resolve_scripts_dir() -> str:
    """Return the absolute path to the attractor scripts directory.

    Resolution order:
    1. The directory containing this file (runner_agent.py is inside attractor/).
    2. Falls back to current working directory if for some reason _THIS_DIR is unavailable.

    Returns:
        Absolute path string.
    """
    return _THIS_DIR


def build_env_config() -> dict[str, str]:
    """Return environment overrides that suppress the CLAUDECODE variable.

    We cannot *delete* env keys via ClaudeCodeOptions.env (it only adds/overrides),
    so we override CLAUDECODE to an empty string. The authoritative fix is in
    spawn_runner.py which uses subprocess.Popen with a fully cleaned environment.

    Returns:
        Dict of env var overrides to pass to ClaudeCodeOptions.
    """
    return {"CLAUDECODE": ""}


# ---------------------------------------------------------------------------
# Async agent runner
# ---------------------------------------------------------------------------


async def _run_agent(initial_prompt: str, options: Any) -> None:
    """Stream messages from the claude_code_sdk query and log them.

    Each SDK message type is logged to Logfire as a structured event so that
    tool calls, assistant text, tool results, and session completion are all
    visible in the Logfire dashboard.

    Args:
        initial_prompt: The first user message to send to Claude.
        options: Configured ClaudeCodeOptions instance.
    """
    import time as _time

    from claude_code_sdk import (
        query,
        AssistantMessage,
        UserMessage,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    )

    turn_count = 0
    tool_call_count = 0
    start_time = _time.time()

    with logfire.span("runner.run_agent") as agent_span:
        async for message in query(initial_prompt, options=options):
            if isinstance(message, AssistantMessage):
                turn_count += 1
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_preview = block.text[:300] if block.text else ""
                        logfire.info(
                            "runner.assistant_text",
                            turn=turn_count,
                            text_length=len(block.text) if block.text else 0,
                            text_preview=text_preview,
                        )
                        print(f"[Runner] {block.text}", flush=True)

                    elif isinstance(block, ToolUseBlock):
                        tool_call_count += 1
                        input_preview = json.dumps(block.input)[:500]
                        logfire.info(
                            "runner.tool_use",
                            tool_name=block.name,
                            tool_use_id=block.id,
                            tool_input_preview=input_preview,
                            turn=turn_count,
                            tool_call_number=tool_call_count,
                        )
                        print(f"[Runner tool] {block.name}: {input_preview[:200]}", flush=True)

                    elif isinstance(block, ThinkingBlock):
                        logfire.info(
                            "runner.thinking",
                            turn=turn_count,
                            thinking_length=len(block.thinking) if block.thinking else 0,
                            thinking_preview=(block.thinking or "")[:200],
                        )

            elif isinstance(message, UserMessage):
                # UserMessage carries tool results back from tool execution
                if isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            content_preview = ""
                            content_length = 0
                            if isinstance(block.content, str):
                                content_preview = block.content[:500]
                                content_length = len(block.content)
                            elif isinstance(block.content, list):
                                content_preview = json.dumps(block.content)[:500]
                                content_length = len(json.dumps(block.content))
                            logfire.info(
                                "runner.tool_result",
                                tool_use_id=block.tool_use_id,
                                is_error=block.is_error or False,
                                content_length=content_length,
                                content_preview=content_preview,
                                turn=turn_count,
                            )

            elif isinstance(message, ResultMessage):
                elapsed = _time.time() - start_time
                logfire.info(
                    "runner.result",
                    session_id=message.session_id,
                    is_error=message.is_error,
                    num_turns=message.num_turns,
                    duration_ms=message.duration_ms,
                    duration_api_ms=message.duration_api_ms,
                    total_cost_usd=message.total_cost_usd,
                    usage=message.usage,
                    result_preview=(message.result or "")[:300],
                    wall_time_seconds=round(elapsed, 2),
                    total_tool_calls=tool_call_count,
                )
                print(f"[Runner done] turns={message.num_turns} cost=${message.total_cost_usd} tools={tool_call_count}", flush=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, build prompts/options, and run the monitoring agent."""
    args = parse_args(argv)

    with logfire.span("runner.main", node_id=args.node, prd_ref=args.prd, session=args.session, dry_run=args.dry_run):
        cwd = args.target_dir
        scripts_dir = resolve_scripts_dir()

        system_prompt = build_system_prompt(
            node_id=args.node,
            prd_ref=args.prd,
            session_name=args.session,
            acceptance=args.acceptance or "",
            scripts_dir=scripts_dir,
            check_interval=args.check_interval,
            stuck_threshold=args.stuck_threshold,
        )

        initial_prompt = build_initial_prompt(
            node_id=args.node,
            prd_ref=args.prd,
            session_name=args.session,
            acceptance=args.acceptance or "",
            scripts_dir=scripts_dir,
            check_interval=args.check_interval,
            stuck_threshold=args.stuck_threshold,
        )

        options = build_options(
            system_prompt=system_prompt,
            cwd=cwd,
            model=args.model,
            max_turns=args.max_turns,
        )

        # Dry-run: log config and exit without calling the SDK.
        if args.dry_run:
            config: dict[str, Any] = {
                "dry_run": True,
                "node_id": args.node,
                "prd_ref": args.prd,
                "session_name": args.session,
                "dot_file": args.dot_file,
                "solution_design": args.solution_design,
                "acceptance": args.acceptance,
                "target_dir": cwd,
                "bead_id": args.bead_id,
                "check_interval": args.check_interval,
                "stuck_threshold": args.stuck_threshold,
                "max_turns": args.max_turns,
                "model": args.model,
                "signals_dir": args.signals_dir,
                "scripts_dir": scripts_dir,
                "system_prompt_length": len(system_prompt),
                "initial_prompt_length": len(initial_prompt),
            }
            print(json.dumps(config, indent=2))
            sys.exit(0)

        # Live run: invoke the Agent SDK.
        try:
            asyncio.run(_run_agent(initial_prompt, options))
        except KeyboardInterrupt:
            print("[Runner] Interrupted by user.", flush=True)
            sys.exit(130)
        except Exception as exc:
            print(f"[Runner error] {exc}", file=sys.stderr, flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
