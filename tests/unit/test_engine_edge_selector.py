"""Tests for cobuilder.engine.edge_selector — EdgeSelector + 5-step algorithm.

Coverage targets from SD-PIPELINE-ENGINE-001 AC-F16:
  - Step 1 (condition match): evaluates edge.condition against context snapshot
  - Step 2 (preferred label): matches outcome.preferred_label against edge.label
  - Step 3 (suggested next): matches outcome.suggested_next against edge.target
  - Step 4 (weight): selects highest numeric edge.weight when present
  - Step 5 (default): selects first unlabeled/unconditioned edge; falls back to outgoing[0]
  - Raises NoEdgeError when no step produces a result
  - stub_condition_evaluator handles 'true'/'false', 'outcome = X', '$key = X', 'key = X'
  - Condition evaluator is injected (decoupled from expression language)
  - Context snapshot used (not live context)
"""
from __future__ import annotations

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.edge_selector import EdgeSelector, _stub_condition_evaluator
from cobuilder.engine.exceptions import NoEdgeError
from cobuilder.engine.graph import Edge, Graph, Node
from cobuilder.engine.outcome import Outcome, OutcomeStatus


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_outcome(
    status: OutcomeStatus = OutcomeStatus.SUCCESS,
    preferred_label: str | None = None,
    suggested_next: str | None = None,
    context_updates: dict | None = None,
) -> Outcome:
    return Outcome(
        status=status,
        preferred_label=preferred_label,
        suggested_next=suggested_next,
        context_updates=context_updates or {},
    )


def make_graph(*edge_specs: tuple) -> tuple[Graph, Node]:
    """Build a minimal graph from (source, target, **kwargs) tuples.

    The first spec's source becomes the node under test.
    All referenced node IDs are auto-created as 'box' nodes.
    """
    node_ids: set[str] = set()
    edges: list[Edge] = []
    for spec in edge_specs:
        src, tgt = spec[0], spec[1]
        kwargs = spec[2] if len(spec) > 2 else {}
        node_ids.update([src, tgt])
        edges.append(Edge(source=src, target=tgt, **kwargs))

    nodes = {nid: Node(id=nid, shape="box") for nid in node_ids}
    graph = Graph(name="test", nodes=nodes, edges=edges)
    # The node under test is always the first source
    current_node = nodes[edge_specs[0][0]]
    return graph, current_node


def make_context(**kv) -> PipelineContext:
    return PipelineContext(initial=kv)


# Shared selector instance
selector = EdgeSelector()


# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Condition match
# ──────────────────────────────────────────────────────────────────────────────

class TestStep1ConditionMatch:
    def test_condition_true_literal_selected(self):
        graph, node = make_graph(
            ("n", "a", {"condition": "true", "label": "cond"}),
            ("n", "b", {"label": "other"}),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "a"

    def test_condition_false_literal_skipped(self):
        graph, node = make_graph(
            ("n", "a", {"condition": "false", "label": "cond"}),
            ("n", "b"),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "b"  # falls through to step 5

    def test_condition_outcome_equals_success(self):
        graph, node = make_graph(
            ("n", "pass", {"condition": "outcome = success"}),
            ("n", "fail", {"condition": "outcome = failure"}),
        )
        ctx = make_context()
        outcome = make_outcome(status=OutcomeStatus.SUCCESS)
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "pass"

    def test_condition_outcome_equals_failure(self):
        graph, node = make_graph(
            ("n", "pass", {"condition": "outcome = success"}),
            ("n", "fail", {"condition": "outcome = failure"}),
        )
        ctx = make_context()
        outcome = make_outcome(status=OutcomeStatus.FAILURE)
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "fail"

    def test_condition_context_key_match(self):
        graph, node = make_graph(
            ("n", "branch_a", {"condition": "$auth_result = jwt"}),
            ("n", "branch_b", {"condition": "$auth_result = oauth"}),
        )
        ctx = make_context(**{"$auth_result": "jwt"})
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "branch_a"

    def test_condition_without_dollar_prefix(self):
        """Context keys stored without $ prefix are also resolved."""
        graph, node = make_graph(
            ("n", "branch_a", {"condition": "$status = ok"}),
            ("n", "branch_b"),
        )
        ctx = make_context(status="ok")  # stored without $
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "branch_a"

    def test_condition_false_falls_through_to_step2(self):
        """All conditions False → falls through to preferred_label check."""
        graph, node = make_graph(
            ("n", "cond_target", {"condition": "false", "label": "x"}),
            ("n", "label_target", {"label": "pass"}),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "label_target"

    def test_condition_evaluated_before_preferred_label(self):
        """Step 1 beats Step 2 even if both match."""
        graph, node = make_graph(
            ("n", "cond_target", {"condition": "true", "label": "other"}),
            ("n", "label_target", {"label": "pass"}),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "cond_target"  # condition wins

    def test_custom_evaluator_injected(self):
        """Step 1 uses the injected evaluator, not the stub."""
        always_true_evaluator = lambda cond, ctx, outcome: True
        custom_selector = EdgeSelector(condition_evaluator=always_true_evaluator)
        graph, node = make_graph(
            ("n", "a", {"condition": "some_complex_expression"}),
            ("n", "b"),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = custom_selector.select(graph, node, outcome, ctx)
        assert edge.target == "a"  # custom evaluator returned True

    def test_context_snapshot_used_not_live(self):
        """Modifications to context after snapshot do not affect condition eval."""
        ctx = make_context(**{"$status": "pending"})

        # Evaluator captures the snapshot value — we test it sees "pending" not "done"
        captured_ctx: list[dict] = []

        def recording_evaluator(cond: str, snapshot: dict, outcome: Outcome) -> bool:
            captured_ctx.append(dict(snapshot))
            return False

        custom_selector = EdgeSelector(condition_evaluator=recording_evaluator)
        graph, node = make_graph(
            ("n", "a", {"condition": "check"}),
            ("n", "b"),
        )
        outcome = make_outcome()
        custom_selector.select(graph, node, outcome, ctx)

        assert len(captured_ctx) == 1
        assert captured_ctx[0].get("$status") == "pending"


# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Preferred label match
# ──────────────────────────────────────────────────────────────────────────────

class TestStep2PreferredLabel:
    def test_preferred_label_matched(self):
        graph, node = make_graph(
            ("n", "pass_node", {"label": "pass"}),
            ("n", "fail_node", {"label": "fail"}),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "pass_node"

    def test_preferred_label_fail_route(self):
        graph, node = make_graph(
            ("n", "pass_node", {"label": "pass"}),
            ("n", "fail_node", {"label": "fail"}),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="fail")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "fail_node"

    def test_preferred_label_none_skips_step2(self):
        """outcome.preferred_label=None skips Step 2 entirely."""
        graph, node = make_graph(
            ("n", "a", {"label": "specific"}),
            ("n", "b"),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label=None)
        edge = selector.select(graph, node, outcome, ctx)
        # No preferred_label → step 5 (default unlabeled edge = 'b')
        assert edge.target == "b"

    def test_preferred_label_no_match_falls_through(self):
        """preferred_label set but no edge has that label → steps 3-5."""
        graph, node = make_graph(
            ("n", "a", {"label": "alpha"}),
            ("n", "b", {"label": "beta"}),
            ("n", "c"),  # unlabeled default
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="gamma")  # no match
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "c"  # step 5 default


# ──────────────────────────────────────────────────────────────────────────────
# Step 3: Suggested next node
# ──────────────────────────────────────────────────────────────────────────────

class TestStep3SuggestedNext:
    def test_suggested_next_matched(self):
        graph, node = make_graph(
            ("n", "alpha", {"label": "route_a"}),
            ("n", "beta", {"label": "route_b"}),
        )
        ctx = make_context()
        outcome = make_outcome(suggested_next="beta")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "beta"

    def test_suggested_next_none_skips_step3(self):
        graph, node = make_graph(
            ("n", "alpha", {"label": "route_a"}),
            ("n", "beta"),
        )
        ctx = make_context()
        outcome = make_outcome(suggested_next=None)
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "beta"  # step 5

    def test_suggested_next_no_match_falls_through(self):
        graph, node = make_graph(
            ("n", "a", {"label": "route_a"}),
            ("n", "b", {"label": "route_b"}),
            ("n", "c"),
        )
        ctx = make_context()
        outcome = make_outcome(suggested_next="nonexistent")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "c"  # step 5 default

    def test_step2_beats_step3(self):
        """preferred_label (Step 2) takes priority over suggested_next (Step 3)."""
        graph, node = make_graph(
            ("n", "label_target", {"label": "pass"}),
            ("n", "suggested_target", {"label": "other"}),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass", suggested_next="suggested_target")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "label_target"  # step 2 wins


# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Edge weight
# ──────────────────────────────────────────────────────────────────────────────

class TestStep4Weight:
    def test_highest_weight_selected(self):
        graph, node = make_graph(
            ("n", "low", {"weight": 1.0, "label": "low"}),
            ("n", "high", {"weight": 5.0, "label": "high"}),
            ("n", "mid", {"weight": 3.0, "label": "mid"}),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "high"

    def test_weight_tie_first_wins(self):
        """When weights are equal, max() returns the first in iteration order."""
        graph, node = make_graph(
            ("n", "a", {"weight": 2.0, "label": "a"}),
            ("n", "b", {"weight": 2.0, "label": "b"}),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.weight == 2.0  # some edge selected, both correct

    def test_no_weighted_edges_skips_step4(self):
        """No edges have weight → step 5."""
        graph, node = make_graph(
            ("n", "a", {"label": "labeled"}),
            ("n", "b"),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "b"  # unlabeled default

    def test_step3_beats_step4(self):
        """suggested_next (Step 3) takes priority over weight (Step 4)."""
        graph, node = make_graph(
            ("n", "heavy", {"weight": 100.0, "label": "heavy"}),
            ("n", "suggested", {"weight": 1.0, "label": "light"}),
        )
        ctx = make_context()
        outcome = make_outcome(suggested_next="suggested")
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "suggested"


# ──────────────────────────────────────────────────────────────────────────────
# Step 5: Default edge
# ──────────────────────────────────────────────────────────────────────────────

class TestStep5Default:
    def test_unlabeled_unconditioned_selected(self):
        graph, node = make_graph(
            ("n", "labeled", {"label": "specific"}),
            ("n", "default"),  # no label, no condition
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "default"

    def test_first_unlabeled_wins_when_multiple(self):
        graph, node = make_graph(
            ("n", "labeled", {"label": "x"}),
            ("n", "default1"),
            ("n", "default2"),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "default1"

    def test_fallback_to_first_edge_when_all_labeled(self):
        """All edges have labels but none match → fall back to outgoing[0]."""
        graph, node = make_graph(
            ("n", "a", {"label": "alpha"}),
            ("n", "b", {"label": "beta"}),
        )
        ctx = make_context()
        outcome = make_outcome()  # no preferred_label, no suggested_next
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "a"  # first outgoing edge

    def test_step4_beats_step5(self):
        """Weighted edges (Step 4) take priority over default (Step 5)."""
        graph, node = make_graph(
            ("n", "weighted", {"weight": 10.0, "label": "w"}),
            ("n", "default"),
        )
        ctx = make_context()
        outcome = make_outcome()
        edge = selector.select(graph, node, outcome, ctx)
        assert edge.target == "weighted"


# ──────────────────────────────────────────────────────────────────────────────
# NoEdgeError
# ──────────────────────────────────────────────────────────────────────────────

class TestNoEdgeError:
    def test_raises_when_no_outgoing_edges(self):
        node = Node(id="isolated", shape="box")
        graph = Graph(name="test", nodes={"isolated": node}, edges=[])
        ctx = make_context()
        outcome = make_outcome()
        with pytest.raises(NoEdgeError) as exc_info:
            selector.select(graph, node, outcome, ctx)
        assert "isolated" in str(exc_info.value)

    def test_error_attributes(self):
        node = Node(id="sink", shape="box")
        graph = Graph(name="test", nodes={"sink": node}, edges=[])
        ctx = make_context()
        outcome = make_outcome()
        with pytest.raises(NoEdgeError) as exc_info:
            selector.select(graph, node, outcome, ctx)
        err = exc_info.value
        assert err.node_id == "sink"


# ──────────────────────────────────────────────────────────────────────────────
# Stub condition evaluator
# ──────────────────────────────────────────────────────────────────────────────

class TestStubConditionEvaluator:
    """Direct unit tests for _stub_condition_evaluator."""

    def _eval(self, condition: str, ctx: dict | None = None, status: OutcomeStatus = OutcomeStatus.SUCCESS) -> bool:
        outcome = Outcome(status=status)
        return _stub_condition_evaluator(condition, ctx or {}, outcome)

    def test_literal_true(self):
        assert self._eval("true") is True

    def test_literal_true_case_insensitive(self):
        assert self._eval("TRUE") is True
        assert self._eval("True") is True

    def test_literal_false(self):
        assert self._eval("false") is False

    def test_literal_false_case_insensitive(self):
        assert self._eval("FALSE") is False

    def test_outcome_equals_success(self):
        assert self._eval("outcome = success", status=OutcomeStatus.SUCCESS) is True

    def test_outcome_equals_failure(self):
        assert self._eval("outcome = failure", status=OutcomeStatus.FAILURE) is True

    def test_outcome_mismatch(self):
        assert self._eval("outcome = success", status=OutcomeStatus.FAILURE) is False

    def test_dollar_key_match(self):
        assert self._eval("$status = ok", ctx={"$status": "ok"}) is True

    def test_dollar_key_mismatch(self):
        assert self._eval("$status = ok", ctx={"$status": "fail"}) is False

    def test_dollar_key_missing_in_context(self):
        assert self._eval("$status = ok", ctx={}) is False

    def test_dollar_key_with_bare_stored_key(self):
        """$key in condition should find value stored without $ in context."""
        assert self._eval("$status = ok", ctx={"status": "ok"}) is True

    def test_unknown_condition_returns_false(self):
        assert self._eval("complex_expression(x, y)") is False

    def test_whitespace_trimmed(self):
        assert self._eval("  true  ") is True
        assert self._eval("  outcome = success  ", status=OutcomeStatus.SUCCESS) is True

    def test_double_equals_not_treated_as_equality(self):
        """'==' must NOT trigger the simple equality branch."""
        result = self._eval("$a == b", ctx={"$a": "b"})
        assert result is False  # double-equals not supported in stub


# ──────────────────────────────────────────────────────────────────────────────
# Priority ordering — all 5 steps in sequence
# ──────────────────────────────────────────────────────────────────────────────

class TestPriorityOrdering:
    """Verify strict priority: Step 1 > Step 2 > Step 3 > Step 4 > Step 5."""

    def test_step1_beats_all(self):
        graph, node = make_graph(
            ("n", "cond",     {"condition": "true"}),
            ("n", "labeled",  {"label": "pass"}),
            ("n", "suggested",{"label": "suggest"}),
            ("n", "weighted", {"weight": 99.0, "label": "weight"}),
            ("n", "default"),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass", suggested_next="suggested")
        assert selector.select(graph, node, outcome, ctx).target == "cond"

    def test_step2_beats_3_4_5(self):
        graph, node = make_graph(
            ("n", "labeled",  {"label": "pass"}),
            ("n", "suggested",{"label": "suggest"}),
            ("n", "weighted", {"weight": 99.0, "label": "weight"}),
            ("n", "default"),
        )
        ctx = make_context()
        outcome = make_outcome(preferred_label="pass", suggested_next="suggested")
        assert selector.select(graph, node, outcome, ctx).target == "labeled"

    def test_step3_beats_4_5(self):
        graph, node = make_graph(
            ("n", "suggested",{"label": "suggest"}),
            ("n", "weighted", {"weight": 99.0, "label": "weight"}),
            ("n", "default"),
        )
        ctx = make_context()
        outcome = make_outcome(suggested_next="suggested")
        assert selector.select(graph, node, outcome, ctx).target == "suggested"

    def test_step4_beats_5(self):
        graph, node = make_graph(
            ("n", "weighted", {"weight": 5.0, "label": "weight"}),
            ("n", "default"),
        )
        ctx = make_context()
        outcome = make_outcome()
        assert selector.select(graph, node, outcome, ctx).target == "weighted"

    def test_step5_is_last_resort(self):
        graph, node = make_graph(
            ("n", "first"),
            ("n", "second"),
        )
        ctx = make_context()
        outcome = make_outcome()
        assert selector.select(graph, node, outcome, ctx).target == "first"


# ──────────────────────────────────────────────────────────────────────────────
# Single outgoing edge
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleEdge:
    def test_single_unlabeled_edge_always_selected(self):
        graph, node = make_graph(("n", "only"))
        ctx = make_context()
        outcome = make_outcome()
        assert selector.select(graph, node, outcome, ctx).target == "only"

    def test_single_labeled_edge_selected_via_step5_fallback(self):
        graph, node = make_graph(("n", "only", {"label": "go"}))
        ctx = make_context()
        outcome = make_outcome()  # no preferred_label
        assert selector.select(graph, node, outcome, ctx).target == "only"

    def test_single_conditioned_false_edge_falls_back_to_outgoing0(self):
        """Even if the only edge has a failing condition, Step 5 returns it as fallback."""
        graph, node = make_graph(("n", "only", {"condition": "false", "label": "c"}))
        ctx = make_context()
        outcome = make_outcome()
        # Step 5: all edges have label/condition → outgoing[0]
        assert selector.select(graph, node, outcome, ctx).target == "only"
