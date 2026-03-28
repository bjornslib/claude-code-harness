"""Tests for _find_dispatchable_nodes() rework-cycle deadlock fix.

When a DOT pipeline has a rework cycle (e.g., rework_decision -> impl_plugin
with condition="fail"), the old predecessor map included the back-edge, making
impl_plugin appear to have an un-satisfied predecessor and blocking initial
dispatch forever.

The fix: exclude condition="fail" and style=dashed edges from the predecessor
map, matching the exclusion logic already present in build_predecessors()
(status.py) and validator._check_cycles().
"""
from __future__ import annotations

from unittest.mock import patch


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------


def _node(node_id: str, status: str = "pending", handler: str = "codergen", shape: str = "box") -> dict:
    return {"id": node_id, "attrs": {"status": status, "handler": handler, "shape": shape}}


def _diamond_node(node_id: str, status: str = "pending") -> dict:
    return {"id": node_id, "attrs": {"status": status, "handler": "conditional", "shape": "diamond"}}


def _edge(src: str, dst: str, **attrs) -> dict:
    return {"src": src, "dst": dst, "attrs": attrs}


def _make_data(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges}


def _make_runner():  # type: ignore[return]
    """Instantiate a PipelineRunner with minimal constructor mocking.

    We use __new__ to skip __init__ and manually set the attributes needed
    by _find_dispatchable_nodes(). Type checkers see PipelineRunner but
    we bypass its constructor.
    """
    from cobuilder.engine.pipeline_runner import PipelineRunner

    # Patch out the file I/O and env loading that happen at __init__ time
    with (
        patch("cobuilder.engine.pipeline_runner.parse_file"),
        patch("cobuilder.engine.pipeline_runner.load_providers_file"),
        patch("os.makedirs"),
    ):
        runner = PipelineRunner.__new__(PipelineRunner)
        runner.active_workers: dict[str, dict] = {}  # type: ignore[annotation-unchecked]
        runner.dot_file = "/fake/pipeline.dot"  # type: ignore[attr-defined]
        runner.signal_dir = "/fake/signals"  # type: ignore[attr-defined]
        return runner


# ---------------------------------------------------------------------------
# Core cycle-deadlock tests
# ---------------------------------------------------------------------------


class TestFindDispatchableCycle:
    def test_impl_node_dispatchable_despite_fail_back_edge(self):
        """impl_plugin must be dispatchable when its only forward predecessor (start)
        is validated, even if a diamond node has a condition='fail' back-edge to it."""
        # Graph: start(validated) -> impl_plugin(pending) -> rework(pending,diamond)
        #         rework --condition=fail--> impl_plugin   ← back-edge (cycle)
        data = _make_data(
            nodes=[
                _node("start", status="validated", handler="start"),
                _node("impl_plugin", status="pending", handler="codergen"),
                _diamond_node("rework_decision", status="pending"),
            ],
            edges=[
                _edge("start", "impl_plugin"),                              # forward — keep
                _edge("impl_plugin", "rework_decision"),                    # forward — keep
                _edge("rework_decision", "impl_plugin", condition="fail"),  # back-edge — exclude
            ],
        )
        runner = _make_runner()
        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "impl_plugin" in ids, (
            "impl_plugin should be dispatchable: its only forward predecessor (start) "
            "is validated, and the condition=fail back-edge must be excluded."
        )

    def test_impl_node_dispatchable_with_dashed_back_edge(self):
        """impl_plugin must be dispatchable when back-edge uses style=dashed
        (alternate retry-edge marker)."""
        data = _make_data(
            nodes=[
                _node("start", status="validated", handler="start"),
                _node("impl_plugin", status="pending", handler="codergen"),
                _diamond_node("rework_decision", status="pending"),
            ],
            edges=[
                _edge("start", "impl_plugin"),
                _edge("impl_plugin", "rework_decision"),
                _edge("rework_decision", "impl_plugin", style="dashed"),  # back-edge — exclude
            ],
        )
        runner = _make_runner()
        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "impl_plugin" in ids

    def test_node_blocked_when_real_forward_predecessor_pending(self):
        """A node whose forward predecessor is still pending must NOT be dispatched."""
        data = _make_data(
            nodes=[
                _node("start", status="pending", handler="start"),
                _node("impl_plugin", status="pending", handler="codergen"),
            ],
            edges=[
                _edge("start", "impl_plugin"),  # forward — must be respected
            ],
        )
        runner = _make_runner()
        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "impl_plugin" not in ids, (
            "impl_plugin must not be dispatched: its forward predecessor start is pending."
        )

    def test_no_predecessors_always_dispatchable(self):
        """A pending node with no predecessors is always dispatchable (start node pattern)."""
        data = _make_data(
            nodes=[_node("orphan", status="pending", handler="codergen")],
            edges=[],
        )
        runner = _make_runner()
        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "orphan" in ids

    def test_already_active_node_excluded(self):
        """A node that is already in active_workers is NOT re-dispatched."""
        data = _make_data(
            nodes=[_node("impl_plugin", status="pending", handler="codergen")],
            edges=[],
        )
        runner = _make_runner()
        runner.active_workers = {"impl_plugin": {}}  # type: ignore[dict-item]

        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "impl_plugin" not in ids

    def test_non_pending_status_excluded(self):
        """Nodes not in 'pending' status are never dispatchable."""
        for status in ("active", "impl_complete", "validated", "accepted", "failed"):
            data = _make_data(
                nodes=[_node("node_a", status=status, handler="codergen")],
                edges=[],
            )
            runner = _make_runner()
            dispatchable = runner._find_dispatchable_nodes(data)
            assert dispatchable == [], f"Status '{status}' should not be dispatchable"

    def test_multi_cycle_pipeline_initial_dispatch(self):
        """Full rework pipeline: start -> impl -> validate(diamond) -> ...
        impl must be dispatchable at pipeline start when start is validated."""
        data = _make_data(
            nodes=[
                _node("start", status="accepted", handler="start"),
                _node("impl_auth", status="pending", handler="codergen"),
                _diamond_node("validate_auth", status="pending"),
                _node("finish", status="pending", handler="exit"),
            ],
            edges=[
                _edge("start", "impl_auth"),
                _edge("impl_auth", "validate_auth"),
                _edge("validate_auth", "finish", condition="pass"),
                _edge("validate_auth", "impl_auth", condition="fail"),  # back-edge — exclude
            ],
        )
        runner = _make_runner()
        dispatchable = runner._find_dispatchable_nodes(data)
        ids = [n["id"] for n in dispatchable]

        assert "impl_auth" in ids, "impl_auth must be dispatchable at pipeline start"
        assert "finish" not in ids, "finish must not be dispatched yet (validate_auth is pending)"
