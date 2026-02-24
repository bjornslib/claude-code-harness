#!/usr/bin/env python3
"""Test Scenarios Runner for the Production Pipeline Runner Agent.

Validates pipeline_runner.py against the same 6 scenarios as poc_test_scenarios.py.
This test suite verifies that the production runner maintains behavioral compatibility
with the POC while adding production capabilities.

Compatibility:
    - Imports run_runner_agent from pipeline_runner (not poc_pipeline_runner)
    - Uses the same DOT files and scenario definitions as poc_test_scenarios.py
    - Same pass/fail criteria and report format

Additional checks over poc_test_scenarios.py:
    - Verifies RunnerState is persisted to .claude/attractor/state/
    - Verifies audit trail entries are written
    - Verifies RunnerPlan validates against the Pydantic model (runner_models.py)
    - Verifies retry_counts field is present in plan

Usage:
    python3 runner_test_scenarios.py               # Run all scenarios
    python3 runner_test_scenarios.py --scenario 1  # Run specific scenario
    python3 runner_test_scenarios.py --verbose     # Show tool call details
    python3 runner_test_scenarios.py --json        # Output results as JSON
    python3 runner_test_scenarios.py --poc         # Run against poc_pipeline_runner (regression)
    python3 runner_test_scenarios.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Ensure imports work regardless of invocation directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from adapters import StdoutAdapter, create_adapter  # noqa: E402
from runner_models import RunnerPlan  # noqa: E402

# ---------------------------------------------------------------------------
# Scenario definitions (identical to poc_test_scenarios.py for compatibility)
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(_THIS_DIR)),  # .claude/scripts/attractor -> .claude/
    "attractor",
    "examples",
)

# State directory for verifying persistence
_STATE_DIR = os.path.join(
    os.path.expanduser("~"),
    ".claude",
    "attractor",
    "state",
)


@dataclass
class Scenario:
    """Definition of a single test scenario."""

    id: int
    name: str
    dot_file: str
    description: str
    expected_actions: list[str]  # Expected action types (subset match)
    expected_no_actions: list[str] = field(default_factory=list)  # Must NOT appear
    expect_complete: bool = False
    expect_stuck: bool = False

    @property
    def dot_path(self) -> str:
        return os.path.join(_EXAMPLES_DIR, self.dot_file)


SCENARIOS: list[Scenario] = [
    Scenario(
        id=1,
        name="Fresh Pipeline",
        dot_file="poc-fresh.dot",
        description=(
            "All nodes pending. Runner should identify the first codergen node "
            "after start as ready and propose spawn_orchestrator."
        ),
        expected_actions=["spawn_orchestrator"],
        expected_no_actions=["signal_finalize"],
        expect_complete=False,
    ),
    Scenario(
        id=2,
        name="Mid-Execution Pipeline",
        dot_file="poc-midway.dot",
        description=(
            "First codergen node validated. Runner should identify the second "
            "node as ready and propose spawn_orchestrator for it."
        ),
        expected_actions=["spawn_orchestrator"],
        expected_no_actions=["signal_finalize"],
        expect_complete=False,
    ),
    Scenario(
        id=3,
        name="Validation Needed",
        dot_file="poc-needs-validation.dot",
        description=(
            "A codergen node is at impl_complete status. Runner should propose "
            "dispatch_validation for the wait.human validation gate."
        ),
        expected_actions=["dispatch_validation"],
        expected_no_actions=["spawn_orchestrator"],
        expect_complete=False,
    ),
    Scenario(
        id=4,
        name="Pipeline Complete",
        dot_file="poc-all-validated.dot",
        description=(
            "All implementation and validation nodes are validated. Runner should "
            "detect that all predecessors of the exit node are done and propose "
            "signal_finalize."
        ),
        expected_actions=["signal_finalize"],
        expect_complete=True,
    ),
    Scenario(
        id=5,
        name="Stuck Pipeline",
        dot_file="poc-stuck.dot",
        description=(
            "A node has failed multiple times with no path forward. "
            "Runner should detect this and propose signal_stuck."
        ),
        expected_actions=["signal_stuck"],
        expect_stuck=True,
    ),
    Scenario(
        id=6,
        name="Parallel Pipeline",
        dot_file="poc-parallel.dot",
        description=(
            "Multiple independent nodes are ready simultaneously. "
            "Runner should propose spawn_orchestrator for each ready node."
        ),
        expected_actions=["spawn_orchestrator"],
        expect_complete=False,
    ),
]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    scenario: Scenario
    passed: bool
    plan: dict[str, Any] | None = None
    error: str | None = None
    duration_s: float = 0.0
    failures: list[str] = field(default_factory=list)
    model_valid: bool = True  # RunnerPlan Pydantic validation
    state_persisted: bool = False
    audit_written: bool = False


def _check_scenario(scenario: Scenario, plan: dict[str, Any]) -> list[str]:
    """Check plan against scenario expectations. Returns list of failures."""
    failures = []
    actual_actions = {a.get("action", "") for a in plan.get("actions", [])}

    # Check expected actions are present
    for expected in scenario.expected_actions:
        if expected not in actual_actions:
            failures.append(
                f"Expected action '{expected}' not found in plan. "
                f"Got: {sorted(actual_actions) or '(none)'}"
            )

    # Check forbidden actions are absent
    for forbidden in scenario.expected_no_actions:
        if forbidden in actual_actions:
            failures.append(
                f"Unexpected action '{forbidden}' found in plan — should not be proposed."
            )

    # Check completion expectation
    if scenario.expect_complete and not plan.get("pipeline_complete"):
        failures.append("Expected pipeline_complete=true but got false.")
    if not scenario.expect_complete and plan.get("pipeline_complete"):
        failures.append("Expected pipeline_complete=false but got true.")

    # Verify retry_counts field is present (production requirement)
    if "retry_counts" not in plan:
        failures.append("Missing 'retry_counts' field in plan (required for production runner).")

    return failures


def _check_pydantic_model(plan: dict[str, Any]) -> tuple[bool, str]:
    """Validate the plan against the RunnerPlan Pydantic model."""
    try:
        RunnerPlan.model_validate(plan)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _check_state_persisted(pipeline_id: str) -> bool:
    """Check if runner state was written to disk."""
    path = os.path.join(_STATE_DIR, f"{pipeline_id}.json")
    return os.path.exists(path)


def _check_audit_written(pipeline_id: str) -> bool:
    """Check if audit trail entries were written."""
    path = os.path.join(_STATE_DIR, f"{pipeline_id}-audit.jsonl")
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            lines = [l.strip() for l in f if l.strip()]
        return len(lines) > 0
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: Scenario,
    *,
    verbose: bool = False,
    use_poc: bool = False,
) -> ScenarioResult:
    """Run a single scenario and return the result.

    Args:
        scenario: The scenario to run.
        verbose: If True, show tool call details.
        use_poc: If True, use poc_pipeline_runner instead of pipeline_runner.
    """
    if not os.path.exists(scenario.dot_path):
        return ScenarioResult(
            scenario=scenario,
            passed=False,
            error=f"DOT file not found: {scenario.dot_path}",
        )

    # Select the runner module
    if use_poc:
        from poc_pipeline_runner import run_runner_agent as _run_runner_agent
    else:
        from pipeline_runner import run_runner_agent as _run_runner_agent

    # Use a capturing adapter that records signals
    signals_recorded: list[dict] = []

    class CapturingAdapter(StdoutAdapter):
        def send_signal(self, signal_type, payload=None, *, priority="normal"):
            signals_recorded.append({"type": signal_type, "payload": payload or {}})
            super().send_signal(signal_type, payload, priority=priority)

    session_id = f"runner-scenario-{scenario.id}-test"
    adapter = CapturingAdapter(prefix=f"[S{scenario.id}]")
    adapter.register(session_id, scenario.dot_file)

    start = time.monotonic()
    try:
        # Production runner accepts session_id; POC does not
        if use_poc:
            plan = _run_runner_agent(
                scenario.dot_path,
                adapter=adapter,
                verbose=verbose,
                max_iterations=15,
            )
        else:
            plan = _run_runner_agent(
                scenario.dot_path,
                adapter=adapter,
                verbose=verbose,
                max_iterations=15,
                plan_only=True,
                session_id=session_id,
            )
        duration = time.monotonic() - start

        # Core scenario checks
        failures = _check_scenario(scenario, plan)

        # Production-only checks (only when not using POC)
        model_valid = True
        state_persisted = False
        audit_written = False

        if not use_poc:
            # Pydantic model validation
            model_valid, model_error = _check_pydantic_model(plan)
            if not model_valid:
                failures.append(f"RunnerPlan Pydantic validation failed: {model_error}")

            # State persistence check
            pipeline_id = os.path.splitext(os.path.basename(scenario.dot_file))[0]
            state_persisted = _check_state_persisted(pipeline_id)
            audit_written = _check_audit_written(pipeline_id)

            if not state_persisted:
                failures.append(
                    f"RunnerState not persisted to {_STATE_DIR}/{pipeline_id}.json"
                )
            if not audit_written:
                failures.append(
                    f"Audit trail not written to {_STATE_DIR}/{pipeline_id}-audit.jsonl"
                )

        return ScenarioResult(
            scenario=scenario,
            passed=len(failures) == 0,
            plan=plan,
            duration_s=duration,
            failures=failures,
            model_valid=model_valid,
            state_persisted=state_persisted,
            audit_written=audit_written,
        )
    except Exception as exc:  # noqa: BLE001
        duration = time.monotonic() - start
        return ScenarioResult(
            scenario=scenario,
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
            duration_s=duration,
        )
    finally:
        adapter.unregister()


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def print_report(results: list[ScenarioResult], use_poc: bool = False) -> None:
    """Print a human-readable test report to stdout."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    runner_label = "poc_pipeline_runner" if use_poc else "pipeline_runner (production)"

    print(f"\n{'=' * 65}")
    print(f"  RUNNER TEST SCENARIOS REPORT")
    print(f"  Runner: {runner_label}")
    print(f"{'=' * 65}")
    print(f"  Ran: {total}  Passed: {passed}  Failed: {total - passed}")
    print(f"{'=' * 65}")

    for result in results:
        s = result.scenario
        status = "PASS" if result.passed else "FAIL"
        dur = f"{result.duration_s:.1f}s"
        print(f"\n  [{status}] Scenario {s.id}: {s.name} ({dur})")
        print(f"         {s.description}")

        if result.error:
            print(f"         Error: {result.error}")
        elif result.failures:
            for f in result.failures:
                print(f"         ✗ {f}")

        if not use_poc and result.plan:
            # Show production-specific status
            model_ok = "✓" if result.model_valid else "✗"
            state_ok = "✓" if result.state_persisted else "✗"
            audit_ok = "✓" if result.audit_written else "✗"
            print(
                f"         Model:{model_ok} State:{state_ok} Audit:{audit_ok}"
            )

        if result.plan:
            actions = result.plan.get("actions", [])
            if actions:
                action_summary = ", ".join(
                    f"{a.get('action', '?')}({a.get('node_id', '?')})"
                    for a in actions[:4]
                )
                if len(actions) > 4:
                    action_summary += f" ... +{len(actions)-4} more"
                print(f"         Actions: {action_summary}")
            else:
                print(f"         Actions: (none)")

            blocked = result.plan.get("blocked_nodes", [])
            if blocked:
                blocked_ids = [
                    b if isinstance(b, str) else b.get("node_id", "?")
                    for b in blocked[:3]
                ]
                print(f"         Blocked: {', '.join(blocked_ids)}")

    print(f"\n{'=' * 65}")
    if passed == total:
        print(f"  ✓ All {total} scenarios passed.")
    else:
        print(f"  ✗ {total - passed} scenario(s) failed.")
    print(f"{'=' * 65}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run test scenarios for the production Pipeline Runner agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 runner_test_scenarios.py
  python3 runner_test_scenarios.py --scenario 1 2 3
  python3 runner_test_scenarios.py --verbose
  python3 runner_test_scenarios.py --json
  python3 runner_test_scenarios.py --poc          # Regression: run against POC
        """,
    )
    ap.add_argument(
        "--scenario",
        type=int,
        nargs="*",
        metavar="N",
        help="Scenario IDs to run (default: all). E.g.: --scenario 1 2 3",
    )
    ap.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print tool call details during scenario execution.",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios without running them.",
    )
    ap.add_argument(
        "--poc",
        action="store_true",
        help="Run scenarios against poc_pipeline_runner instead (regression testing).",
    )
    args = ap.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        for s in SCENARIOS:
            exists = "✓" if os.path.exists(s.dot_path) else "✗ (missing DOT)"
            print(f"  {s.id}. [{exists}] {s.name}")
            print(f"       {s.description}")
        print()
        return

    # Select scenarios to run
    if args.scenario:
        ids = set(args.scenario)
        to_run = [s for s in SCENARIOS if s.id in ids]
        missing = ids - {s.id for s in SCENARIOS}
        if missing:
            print(
                f"Warning: Unknown scenario IDs: {sorted(missing)}", file=sys.stderr
            )
    else:
        to_run = SCENARIOS

    if not to_run:
        print("No scenarios selected.", file=sys.stderr)
        sys.exit(1)

    runner_label = "poc_pipeline_runner" if args.poc else "pipeline_runner"
    print(f"\nRunning {len(to_run)} scenario(s) against {runner_label}...\n")

    # Run selected scenarios
    results: list[ScenarioResult] = []
    for scenario in to_run:
        print(
            f"  Scenario {scenario.id}: {scenario.name}...",
            end=" ",
            flush=True,
        )
        result = run_scenario(scenario, verbose=args.verbose, use_poc=args.poc)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} ({result.duration_s:.1f}s)")

    if args.json_output:
        output = []
        for r in results:
            entry: dict[str, Any] = {
                "scenario_id": r.scenario.id,
                "scenario_name": r.scenario.name,
                "passed": r.passed,
                "duration_s": r.duration_s,
                "error": r.error,
                "failures": r.failures,
                "plan_summary": r.plan.get("summary") if r.plan else None,
                "action_count": len(r.plan.get("actions", [])) if r.plan else 0,
            }
            if not args.poc:
                entry["model_valid"] = r.model_valid
                entry["state_persisted"] = r.state_persisted
                entry["audit_written"] = r.audit_written
            output.append(entry)
        print(json.dumps(output, indent=2))
    else:
        print_report(results, use_poc=args.poc)

    # Exit code: 0 if all passed, 1 if any failed
    total_passed = sum(1 for r in results if r.passed)
    sys.exit(0 if total_passed == len(results) else 1)


if __name__ == "__main__":
    main()
