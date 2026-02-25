#!/usr/bin/env python3
"""Production Pipeline Runner Agent.

Evolves the poc_pipeline_runner.py proof-of-concept into a production-grade
runner that not only plans but also executes pipeline actions.

Architecture:
    - Uses anthropic.Anthropic().messages.create() (same as POC)
    - Extended tool set (9 tools vs POC's 4)
    - Retry logic: up to 3 failures per node → STUCK signal
    - State persistence: .claude/attractor/state/{pipeline-id}.json
    - Audit trail: .claude/attractor/state/{pipeline-id}-audit.jsonl
    - Guard rail hooks: blocks Edit/Write, enforces separation of concerns
    - Two modes: --plan-only (like POC, no execution) and --execute (full)

Backward compatibility:
    - Produces the same RunnerPlan JSON structure as poc_pipeline_runner.py
    - poc_test_scenarios.py can import run_runner_agent from this module

Usage:
    # Plan-only mode (POC-compatible):
    python3 pipeline_runner.py .claude/attractor/examples/poc-fresh.dot

    # Execute mode (actually spawns orchestrators, runs validation):
    python3 pipeline_runner.py pipeline.dot --execute

    # Show debug tool calls:
    python3 pipeline_runner.py pipeline.dot --verbose

    # Output raw JSON:
    python3 pipeline_runner.py pipeline.dot --json

Files:
    pipeline_runner.py        This file (production runner)
    runner_models.py          Pydantic models (RunnerPlan, RunnerState, etc.)
    runner_tools.py           Tool definitions and implementations
    runner_hooks.py           Guard rail hooks (anti-gaming enforcement)
    adapters/                 Channel adapters (stdout, native_teams)
    poc_pipeline_runner.py    Phase 2 POC (plan-only reference)
    poc_test_scenarios.py     Test scenarios (compatible with this module)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

import anthropic

# Ensure local module imports work regardless of invocation directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from adapters import ChannelAdapter, create_adapter  # noqa: E402
from runner_hooks import RunnerHooks, RunnerHookError  # noqa: E402
from runner_models import RunnerPlan, RunnerState  # noqa: E402
from runner_tools import TOOLS, execute_tool, get_tool_dispatch  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLI_PATH = os.path.join(_THIS_DIR, "cli.py")
MODEL = "claude-sonnet-4-6"

# Directory for runner state persistence
_STATE_DIR = os.path.join(
    os.path.expanduser("~"),
    ".claude",
    "attractor",
    "state",
)

# ---------------------------------------------------------------------------
# System prompt (expanded from POC to include execution tools)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Pipeline Runner agent. Your job is to analyze an Attractor-style
DOT pipeline graph and determine the NEXT ACTIONS to take.

You have two categories of tools:
  READ-ONLY: get_pipeline_status, get_pipeline_graph, get_node_details, check_checkpoint
  EXECUTION: get_dispatchable_nodes, transition_node, save_checkpoint,
             spawn_orchestrator, dispatch_validation, send_approval_request, modify_node

Rules for graph analysis:
1. Always call get_pipeline_status first to understand current node states.
2. Then call get_pipeline_graph to understand the topology (dependencies).
3. Identify nodes that are "pending" with all upstream dependencies satisfied.
4. For each ready node, determine the action based on handler type:
   - handler=start       → no action needed if already validated, otherwise "initialize"
   - handler=codergen    → "spawn_orchestrator" with worker_type from node attrs
   - handler=wait.human  → "dispatch_validation" with mode from node attrs
   - handler=tool        → "execute_tool" with command from node attrs
   - handler=conditional → "evaluate_condition"
   - handler=parallel    → "sync_parallel" (fan-out or fan-in)
   - handler=exit        → "signal_finalize" only if ALL predecessors are validated

Rules for execution:
5. Order actions by pipeline dependency (upstream before downstream).
6. NEVER propose validating a node that has NOT reached impl_complete or validated status.
7. NEVER propose spawning a worker for a node whose dependencies are not validated.
8. If no actions are possible and pipeline is not at exit: report blocked_nodes with reasons.
9. A node with status "validated" is COMPLETE — do not propose actions for it.
10. Nodes with status "active" or "impl_complete" are in progress — propose validation.
11. When proposing "signal_finalize" for an exit node (all predecessors validated), set "pipeline_complete": true in the plan.

Anti-gaming rules (STRICTLY ENFORCED by guard rail hooks):
12. NEVER call Edit, Write, or MultiEdit — you are a coordinator, not an implementer.
13. The guard rails will BLOCK any attempt to call Edit/Write with an error.
14. Always propose transition_node before spawning to mark node active.
15. Save checkpoint after every transition.

Produce a JSON RunnerPlan with this exact structure:
{
  "pipeline_id": "<graph_name>",
  "prd_ref": "<prd_ref from graph attrs>",
  "current_stage": "PARSE|VALIDATE|INITIALIZE|EXECUTE|FINALIZE",
  "summary": "<1-2 sentence description of current state and next steps>",
  "actions": [
    {
      "node_id": "<node_id>",
      "action": "spawn_orchestrator|dispatch_validation|execute_tool|signal_finalize|signal_stuck|initialize|sync_parallel|evaluate_condition|request_approval",
      "reason": "<why this action>",
      "dependencies_satisfied": ["<dep1>", "<dep2>"],
      "worker_type": "<worker type or null>",
      "validation_mode": "<technical|business|e2e or null>",
      "priority": "high|normal|low"
    }
  ],
  "blocked_nodes": [
    {
      "node_id": "<node_id>",
      "reason": "<why blocked>",
      "missing_deps": ["<dep_id>"]
    }
  ],
  "completed_nodes": ["<node_id>", ...],
  "pipeline_complete": false
}

When you have gathered all information needed to produce the plan, output ONLY the JSON object
(no markdown, no explanation). The plan will be parsed directly.
"""


# ---------------------------------------------------------------------------
# State persistence helpers
# ---------------------------------------------------------------------------


def _state_path(pipeline_id: str) -> str:
    """Return path for the runner state JSON file."""
    os.makedirs(_STATE_DIR, exist_ok=True)
    return os.path.join(_STATE_DIR, f"{pipeline_id}.json")


def _audit_path(pipeline_id: str) -> str:
    """Return path for the audit JSONL file."""
    os.makedirs(_STATE_DIR, exist_ok=True)
    return os.path.join(_STATE_DIR, f"{pipeline_id}-audit.jsonl")


def load_state(pipeline_id: str, pipeline_path: str, session_id: str) -> RunnerState:
    """Load or create RunnerState for a pipeline.

    If a state file exists, loads it. Otherwise creates a fresh state.
    """
    path = _state_path(pipeline_id)
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            state = RunnerState.model_validate(data)
            state.touch()
            return state
        except (OSError, json.JSONDecodeError, Exception):  # noqa: BLE001
            pass

    return RunnerState(
        pipeline_id=pipeline_id,
        pipeline_path=pipeline_path,
        session_id=session_id,
    )


def save_state(state: RunnerState) -> None:
    """Persist RunnerState to disk."""
    path = _state_path(state.pipeline_id)
    state.touch()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(state.model_dump_json(indent=2))
    except OSError as exc:
        print(f"[runner] WARNING: Failed to save state: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def run_runner_agent(
    pipeline_path: str,
    *,
    adapter: ChannelAdapter,
    verbose: bool = False,
    max_iterations: int = 20,
    plan_only: bool = True,
    session_id: str = "pipeline-runner",
) -> dict[str, Any]:
    """Run the Pipeline Runner agent loop.

    Uses anthropic.Anthropic().messages.create() with tool use.
    Iterates until the model produces a final RunnerPlan JSON.

    This function is backward-compatible with poc_pipeline_runner.py's
    run_runner_agent() — same signature and return format.

    Args:
        pipeline_path: Absolute or relative path to the .dot pipeline file.
        adapter: Channel adapter for signaling upstream.
        verbose: If True, print tool call details to stderr.
        max_iterations: Safety limit on tool-use iterations.
        plan_only: If True, execution tools return dry-run descriptions (POC mode).
            If False, execution tools actually spawn orchestrators, run validation, etc.
        session_id: Unique identifier for this runner session (for state + audit).

    Returns:
        The parsed RunnerPlan dict.

    Raises:
        RuntimeError: If the agent exceeds max_iterations or produces malformed output.
    """
    client = anthropic.Anthropic()

    # Derive pipeline ID from file name
    pipeline_id = os.path.splitext(os.path.basename(pipeline_path))[0]

    # Load or create persistent state
    state = load_state(pipeline_id, pipeline_path, session_id)
    save_state(state)

    # Initialize guard rail hooks
    hooks = RunnerHooks(
        state=state,
        audit_path=_audit_path(pipeline_id),
        session_id=session_id,
        verbose=verbose,
    )

    # Build tool dispatch (plan_only controls execution behavior)
    dispatch = get_tool_dispatch(plan_only=plan_only)

    # Prime the conversation
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Analyze the pipeline at: {pipeline_path}\n\n"
                "Produce a RunnerPlan as a JSON object. "
                "Call the available tools to gather all necessary information first."
                + (
                    "\n\nNOTE: You are in PLAN-ONLY mode. Execution tools will return "
                    "dry-run descriptions without actually spawning or validating."
                    if plan_only else ""
                )
            ),
        }
    ]

    adapter.send_signal("RUNNER_STARTED", payload={"pipeline_path": pipeline_path, "plan_only": plan_only})

    final_plan: dict[str, Any] | None = None

    for iteration in range(max_iterations):
        if verbose:
            print(f"[agent] Iteration {iteration + 1}/{max_iterations}", file=sys.stderr)

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if verbose:
            print(
                f"[agent] stop_reason={response.stop_reason} "
                f"content_blocks={len(response.content)}",
                file=sys.stderr,
            )

        # Append assistant response to conversation
        messages.append({"role": "assistant", "content": response.content})

        # If the model produced a final text response, we're done
        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text.strip()
                    break

            if not final_text:
                raise RuntimeError("Agent produced end_turn but no text content.")

            # Parse the JSON plan
            try:
                plan = json.loads(final_text)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", final_text, re.DOTALL)
                if m:
                    plan = json.loads(m.group(0))
                else:
                    raise RuntimeError(
                        f"Agent output is not valid JSON:\n{final_text[:500]}"
                    )

            final_plan = plan

            # Update state with latest plan
            try:
                state.last_plan = RunnerPlan.model_validate(plan)
            except Exception:  # noqa: BLE001
                pass
            save_state(state)

            # Signal completion or stuck state via adapter
            if plan.get("pipeline_complete"):
                adapter.send_signal(
                    "RUNNER_COMPLETE",
                    payload={"pipeline_id": plan.get("pipeline_id")},
                )
                hooks.on_stop(plan, reason="complete")
            elif not plan.get("actions"):
                adapter.send_signal(
                    "RUNNER_STUCK",
                    payload={
                        "pipeline_id": plan.get("pipeline_id"),
                        "blocked_nodes": plan.get("blocked_nodes", []),
                    },
                )
                hooks.on_stop(plan, reason="stuck")
            else:
                hooks.on_stop(plan, reason="planned")

            return plan

        # Handle tool_use stop reason
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    if verbose:
                        print(
                            f"[tool] {tool_name}({json.dumps(tool_input, separators=(',', ':'))})",
                            file=sys.stderr,
                        )

                    # Run pre-tool hook (may raise RunnerHookError)
                    hook_error: str | None = None
                    try:
                        hooks.pre_tool_use(tool_name, tool_input)
                    except RunnerHookError as exc:
                        hook_error = str(exc)

                    if hook_error:
                        result_content = json.dumps({"error": hook_error, "hook": "pre_tool_use"})
                    else:
                        result_content = execute_tool(tool_name, tool_input, dispatch)
                        # Run post-tool hook
                        try:
                            hooks.post_tool_use(tool_name, tool_input, result_content)
                        except Exception as exc:  # noqa: BLE001
                            print(f"[hooks] post_tool_use error: {exc}", file=sys.stderr)

                    if verbose:
                        print(
                            f"[tool] → {result_content[:200]}"
                            f"{'...' if len(result_content) > 200 else ''}",
                            file=sys.stderr,
                        )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        raise RuntimeError(
            f"Unexpected stop_reason: {response.stop_reason} at iteration {iteration + 1}"
        )

    raise RuntimeError(
        f"Agent exceeded max_iterations ({max_iterations}) without producing a plan."
    )


# ---------------------------------------------------------------------------
# Plan display (same as poc_pipeline_runner for compatibility)
# ---------------------------------------------------------------------------


def print_plan(plan: dict[str, Any]) -> None:
    """Pretty-print the RunnerPlan to stdout."""
    pipeline_id = plan.get("pipeline_id", "unknown")
    prd_ref = plan.get("prd_ref", "")
    stage = plan.get("current_stage", "UNKNOWN")
    summary = plan.get("summary", "")
    actions = plan.get("actions", [])
    blocked = plan.get("blocked_nodes", [])
    completed = plan.get("completed_nodes", [])
    pipeline_complete = plan.get("pipeline_complete", False)

    print(f"\n{'=' * 60}")
    print(f"  PIPELINE RUNNER PLAN")
    print(f"{'=' * 60}")
    print(f"  Pipeline:  {pipeline_id}")
    if prd_ref:
        print(f"  PRD:       {prd_ref}")
    print(f"  Stage:     {stage}")
    print(f"  Summary:   {summary}")

    if pipeline_complete:
        print("\n  *** PIPELINE COMPLETE — All nodes validated ***")

    if completed:
        print(f"\n  Completed nodes ({len(completed)}):")
        for nid in completed:
            print(f"    ✓ {nid}")

    if actions:
        print(f"\n  Actions ({len(actions)}):")
        for i, action in enumerate(actions, 1):
            prio = action.get("priority", "normal")
            prio_tag = f" [{prio.upper()}]" if prio != "normal" else ""
            print(
                f"  {i:2}. [{action.get('action', '?')}]{prio_tag} {action.get('node_id', '?')}"
            )
            print(f"      Reason: {action.get('reason', '')}")
            deps = action.get("dependencies_satisfied", [])
            if deps:
                print(f"      Deps:   {', '.join(deps)}")
            if action.get("worker_type"):
                print(f"      Worker: {action['worker_type']}")
            if action.get("validation_mode"):
                print(f"      Mode:   {action['validation_mode']}")
    else:
        print("\n  No actions proposed.")

    if blocked:
        print(f"\n  Blocked nodes ({len(blocked)}):")
        for b in blocked:
            node_id = b if isinstance(b, str) else b.get("node_id", "?")
            reason = "" if isinstance(b, str) else b.get("reason", "")
            missing = [] if isinstance(b, str) else b.get("missing_deps", [])
            print(f"    ✗ {node_id}: {reason}")
            if missing:
                print(f"      Missing: {', '.join(missing)}")

    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Production Pipeline Runner — analyze and execute Attractor DOT pipelines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plan-only (no execution, compatible with poc_test_scenarios.py):
  python3 pipeline_runner.py .claude/attractor/examples/poc-fresh.dot

  # Execute mode (actual spawning and validation):
  python3 pipeline_runner.py pipeline.dot --execute

  # Verbose with JSON output:
  python3 pipeline_runner.py pipeline.dot --verbose --json

        """,
    )
    ap.add_argument("pipeline", help="Path to the .dot pipeline file.")
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Execute actions (spawn orchestrators, run validation). Default: plan-only.",
    )
    ap.add_argument(
        "--channel",
        default="stdout",
        choices=["stdout", "native_teams"],
        help="Communication channel adapter (default: stdout).",
    )
    ap.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print tool call details to stderr.",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw RunnerPlan JSON instead of formatted display.",
    )
    ap.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum tool-use iterations (default: 20).",
    )
    ap.add_argument(
        "--session-id",
        default="pipeline-runner",
        help="Unique session ID for state persistence and audit trail.",
    )
    # Channel-specific options
    ap.add_argument(
        "--team-name", default="s3-live-workers", help="Native teams team name."
    )

    args = ap.parse_args()

    # Resolve pipeline path
    pipeline_path = os.path.abspath(args.pipeline)
    if not os.path.exists(pipeline_path):
        print(f"Error: Pipeline file not found: {pipeline_path}", file=sys.stderr)
        sys.exit(1)

    # Create channel adapter
    channel_kwargs: dict[str, Any] = {}
    if args.channel == "native_teams":
        channel_kwargs = {"team_name": args.team_name}

    adapter = create_adapter(args.channel, **channel_kwargs)

    # Derive pipeline ID for registration
    pipeline_id = os.path.splitext(os.path.basename(pipeline_path))[0]
    adapter.register(args.session_id, pipeline_id)

    plan_only = not args.execute

    if args.execute:
        print(
            f"[runner] EXECUTE mode — will spawn orchestrators and run validation.",
            file=sys.stderr,
        )
    else:
        print(
            f"[runner] PLAN-ONLY mode — will plan but not execute. Use --execute to run.",
            file=sys.stderr,
        )

    try:
        plan = run_runner_agent(
            pipeline_path,
            adapter=adapter,
            verbose=args.verbose,
            max_iterations=args.max_iterations,
            plan_only=plan_only,
            session_id=args.session_id,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        adapter.send_signal("RUNNER_ERROR", payload={"error": str(exc)})
        sys.exit(1)
    except anthropic.APIError as exc:
        print(f"Anthropic API error: {exc}", file=sys.stderr)
        adapter.send_signal("RUNNER_ERROR", payload={"error": str(exc)})
        sys.exit(1)
    finally:
        adapter.unregister()

    if args.json_output:
        print(json.dumps(plan, indent=2))
    else:
        print_plan(plan)


if __name__ == "__main__":
    main()
