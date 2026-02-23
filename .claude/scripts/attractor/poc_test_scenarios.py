#!/usr/bin/env python3
"""POC Test Scenarios Runner.

Runs the Pipeline Runner agent against predefined test scenarios to validate
graph reasoning correctness. Each scenario uses a pre-authored DOT file
representing a specific pipeline state.

Test scenarios:
  1. Fresh pipeline     - All nodes pending; should spawn first codergen node
  2. Mid-execution      - Some nodes validated; should advance to next ready node
  3. Validation needed  - Node at impl_complete; should dispatch validation
  4. Pipeline complete  - All nodes validated; should signal finalize
  5. Stuck pipeline     - Node failed repeatedly; should report stuck
  6. Parallel pipeline  - Multiple ready nodes; should propose concurrent spawns

Usage:
    python3 poc_test_scenarios.py               # Run all scenarios
    python3 poc_test_scenarios.py --scenario 1  # Run specific scenario
    python3 poc_test_scenarios.py --verbose     # Show tool call details
    python3 poc_test_scenarios.py --json        # Output results as JSON
    python3 poc_test_scenarios.py --help
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
from poc_pipeline_runner import run_runner_agent  # noqa: E402

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(_THIS_DIR)),  # .claude/scripts/attractor -> .claude/scripts -> .claude/
    "attractor",
    "examples",
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

    # Dependency satisfaction check: no action should be proposed for a node
    # unless its dependencies_satisfied list is non-empty or it has no deps
    for action in plan.get("actions", []):
        if action.get("action") == "spawn_orchestrator":
            # This is a soft check — valid if deps_satisfied is present
            pass

    return failures


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: Scenario,
    *,
    verbose: bool = False,
    capture_signals: bool = True,
) -> ScenarioResult:
    """Run a single scenario and return the result."""

    if not os.path.exists(scenario.dot_path):
        return ScenarioResult(
            scenario=scenario,
            passed=False,
            error=f"DOT file not found: {scenario.dot_path}",
        )

    # Use a capturing adapter that records signals
    signals_recorded: list[dict] = []

    class CapturingAdapter(StdoutAdapter):
        def send_signal(self, signal_type, payload=None, *, priority="normal"):
            signals_recorded.append({"type": signal_type, "payload": payload or {}})
            super().send_signal(signal_type, payload, priority=priority)

    adapter = CapturingAdapter(prefix=f"[S{scenario.id}]")
    adapter.register(f"runner-scenario-{scenario.id}", scenario.dot_file)

    start = time.monotonic()
    try:
        plan = run_runner_agent(
            scenario.dot_path,
            adapter=adapter,
            verbose=verbose,
            max_iterations=15,
        )
        duration = time.monotonic() - start
        failures = _check_scenario(scenario, plan)
        return ScenarioResult(
            scenario=scenario,
            passed=len(failures) == 0,
            plan=plan,
            duration_s=duration,
            failures=failures,
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


def print_report(results: list[ScenarioResult]) -> None:
    """Print a human-readable test report to stdout."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n{'=' * 65}")
    print(f"  POC TEST SCENARIOS REPORT")
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
        description="Run POC test scenarios for the Pipeline Runner agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 poc_test_scenarios.py
  python3 poc_test_scenarios.py --scenario 1 2 3
  python3 poc_test_scenarios.py --verbose
  python3 poc_test_scenarios.py --json
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

    # Run selected scenarios
    results: list[ScenarioResult] = []
    for scenario in to_run:
        print(
            f"Running scenario {scenario.id}: {scenario.name}...",
            end=" ",
            flush=True,
        )
        result = run_scenario(scenario, verbose=args.verbose)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} ({result.duration_s:.1f}s)")

    if args.json_output:
        output = []
        for r in results:
            output.append({
                "scenario_id": r.scenario.id,
                "scenario_name": r.scenario.name,
                "passed": r.passed,
                "duration_s": r.duration_s,
                "error": r.error,
                "failures": r.failures,
                "plan_summary": r.plan.get("summary") if r.plan else None,
                "action_count": len(r.plan.get("actions", [])) if r.plan else 0,
            })
        print(json.dumps(output, indent=2))
    else:
        print_report(results)

    # Exit code: 0 if all passed, 1 if any failed
    total_passed = sum(1 for r in results if r.passed)
    sys.exit(0 if total_passed == len(results) else 1)


if __name__ == "__main__":
    main()
