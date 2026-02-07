"""Integration tests: Self-dogfooding zerorepo's own source through the Serena pipeline.

This test suite walks ``src/zerorepo/`` using the FileBasedCodebaseAnalyzer
and CodebaseWalker to produce a baseline RPGGraph, then exercises the full
pipeline: save/load via BaselineManager, delta reporting, and enrichment
with mocked LLM calls.

The tests verify that zerorepo can analyse its own source code end-to-end,
proving the pipeline works on a real (non-trivial) Python project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from zerorepo.models.edge import RPGEdge
from zerorepo.models.enums import (
    DeltaStatus,
    EdgeType,
    InterfaceType,
    NodeLevel,
    NodeType,
)
from zerorepo.models.graph import RPGGraph
from zerorepo.models.node import RPGNode
from zerorepo.serena.baseline import BaselineManager
from zerorepo.serena.delta_report import DeltaReportGenerator, DeltaSummary
from zerorepo.serena.session import FileBasedCodebaseAnalyzer
from zerorepo.serena.walker import CodebaseWalker


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Resolve once: the zerorepo source directory
_ZEROREPO_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "zerorepo"

# Known top-level packages inside src/zerorepo/
_EXPECTED_PACKAGES = {
    "models",
    "cli",
    "rpg_enrichment",
    "serena",
    "graph_construction",
    "codegen",
    "evaluation",
    "graph_ops",
    "llm",
    "ontology",
    "sandbox",
    "selection",
    "spec_parser",
    "vectordb",
}

# Known key classes that must appear as FEATURE nodes
_EXPECTED_CLASSES = {
    "RPGGraph",
    "RPGNode",
    "RPGEdge",
    "RPGBuilder",
    "CodebaseWalker",
    "BaselineManager",
    "FileBasedCodebaseAnalyzer",
    "DeltaReportGenerator",
}

# Known key files that must appear as COMPONENT nodes
_EXPECTED_COMPONENTS = {
    "graph",       # models/graph.py
    "node",        # models/node.py
    "edge",        # models/edge.py
    "walker",      # serena/walker.py
    "baseline",    # serena/baseline.py
    "session",     # serena/session.py
    "pipeline",    # rpg_enrichment/pipeline.py
}


# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------


def _skip_if_no_source() -> None:
    """Skip the test if the zerorepo source tree is not available."""
    if not (_ZEROREPO_SRC / "__init__.py").exists():
        pytest.skip("Cannot find zerorepo source tree at " + str(_ZEROREPO_SRC))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def zerorepo_baseline_graph() -> RPGGraph:
    """Walk src/zerorepo/ once and cache the result for the whole module.

    This avoids re-walking the entire source tree for every test.
    """
    _skip_if_no_source()
    analyzer = FileBasedCodebaseAnalyzer()
    walker = CodebaseWalker(analyzer)
    return walker.walk(_ZEROREPO_SRC)


@pytest.fixture
def baseline_manager() -> BaselineManager:
    """Return a fresh BaselineManager instance."""
    return BaselineManager()


@pytest.fixture
def delta_generator() -> DeltaReportGenerator:
    """Return a fresh DeltaReportGenerator instance."""
    return DeltaReportGenerator()


# ===========================================================================
# 1. SELF-DOGFOODING: Walk zerorepo's own source
# ===========================================================================


class TestSelfDogfoodWalk:
    """Walk src/zerorepo/ and verify the baseline graph structure."""

    def test_graph_is_nonempty(self, zerorepo_baseline_graph: RPGGraph) -> None:
        """The baseline graph must contain a significant number of nodes."""
        assert zerorepo_baseline_graph.node_count > 50, (
            f"Expected > 50 nodes but got {zerorepo_baseline_graph.node_count}"
        )
        assert zerorepo_baseline_graph.edge_count > 50, (
            f"Expected > 50 edges but got {zerorepo_baseline_graph.edge_count}"
        )

    def test_has_expected_module_nodes(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Key packages must appear as MODULE nodes."""
        module_names = {
            n.name
            for n in zerorepo_baseline_graph.nodes.values()
            if n.level == NodeLevel.MODULE
        }
        missing = _EXPECTED_PACKAGES - module_names
        assert not missing, f"Missing MODULE nodes for packages: {missing}"

    def test_has_expected_component_nodes(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Key .py files must appear as COMPONENT nodes."""
        component_names = {
            n.name
            for n in zerorepo_baseline_graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        }
        missing = _EXPECTED_COMPONENTS - component_names
        assert not missing, f"Missing COMPONENT nodes for files: {missing}"

    def test_has_expected_feature_nodes(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Key classes must appear as FEATURE nodes."""
        feature_names = {
            n.name
            for n in zerorepo_baseline_graph.nodes.values()
            if n.level == NodeLevel.FEATURE
        }
        missing = _EXPECTED_CLASSES - feature_names
        assert not missing, f"Missing FEATURE nodes for classes: {missing}"

    def test_three_level_hierarchy_exists(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """MODULE -> COMPONENT -> FEATURE hierarchy must be connected via edges."""
        graph = zerorepo_baseline_graph
        hierarchy_edges = [
            e for e in graph.edges.values() if e.edge_type == EdgeType.HIERARCHY
        ]
        assert len(hierarchy_edges) > 30, (
            f"Expected > 30 HIERARCHY edges, got {len(hierarchy_edges)}"
        )

        # Verify that there exist chains: MODULE -> COMPONENT -> FEATURE
        module_ids = {
            n.id for n in graph.nodes.values() if n.level == NodeLevel.MODULE
        }
        component_ids = {
            n.id for n in graph.nodes.values() if n.level == NodeLevel.COMPONENT
        }
        feature_ids = {
            n.id for n in graph.nodes.values() if n.level == NodeLevel.FEATURE
        }

        # At least one MODULE -> COMPONENT edge
        mod_to_comp = [
            e for e in hierarchy_edges
            if e.source_id in module_ids and e.target_id in component_ids
        ]
        assert len(mod_to_comp) > 0, "No MODULE -> COMPONENT edges found"

        # At least one COMPONENT -> FEATURE edge
        comp_to_feat = [
            e for e in hierarchy_edges
            if e.source_id in component_ids and e.target_id in feature_ids
        ]
        assert len(comp_to_feat) > 0, "No COMPONENT -> FEATURE edges found"

    def test_all_nodes_serena_validated(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """All nodes must be marked serena_validated=True."""
        for node in zerorepo_baseline_graph.nodes.values():
            assert node.serena_validated is True, (
                f"Node {node.name!r} is not serena_validated"
            )

    def test_all_nodes_have_baseline_metadata(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """All nodes must have metadata['baseline'] = True."""
        for node in zerorepo_baseline_graph.nodes.values():
            assert node.metadata.get("baseline") is True, (
                f"Node {node.name!r} missing baseline metadata"
            )

    def test_all_nodes_are_functionality_type(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Baseline nodes must be FUNCTIONALITY type (not FUNCTION_AUGMENTED)."""
        for node in zerorepo_baseline_graph.nodes.values():
            assert node.node_type == NodeType.FUNCTIONALITY, (
                f"Node {node.name!r} has type {node.node_type}"
            )

    def test_no_self_loops(self, zerorepo_baseline_graph: RPGGraph) -> None:
        """No edge should have source_id == target_id."""
        for edge in zerorepo_baseline_graph.edges.values():
            assert edge.source_id != edge.target_id, (
                f"Self-loop found: edge {edge.id}"
            )

    def test_all_edges_reference_valid_nodes(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """All edge endpoints must reference existing nodes."""
        graph = zerorepo_baseline_graph
        for edge in graph.edges.values():
            assert edge.source_id in graph.nodes, (
                f"Edge {edge.id} references unknown source {edge.source_id}"
            )
            assert edge.target_id in graph.nodes, (
                f"Edge {edge.id} references unknown target {edge.target_id}"
            )

    def test_feature_nodes_have_metadata(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """FEATURE nodes should have 'kind' and 'line' in metadata."""
        features = [
            n for n in zerorepo_baseline_graph.nodes.values()
            if n.level == NodeLevel.FEATURE
        ]
        for feat in features:
            assert "kind" in feat.metadata, (
                f"Feature {feat.name!r} missing 'kind' metadata"
            )
            assert feat.metadata["kind"] in ("class", "function"), (
                f"Feature {feat.name!r} has unexpected kind: {feat.metadata['kind']}"
            )
            assert "line" in feat.metadata, (
                f"Feature {feat.name!r} missing 'line' metadata"
            )
            assert isinstance(feat.metadata["line"], int), (
                f"Feature {feat.name!r} line is not int"
            )

    def test_graph_metadata_has_stats(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Graph metadata must include baseline_stats with correct counts."""
        stats = zerorepo_baseline_graph.metadata.get("baseline_stats")
        assert stats is not None, "Missing baseline_stats in graph metadata"
        assert stats["total_nodes"] == zerorepo_baseline_graph.node_count
        assert stats["total_edges"] == zerorepo_baseline_graph.edge_count
        assert stats["modules"] >= len(_EXPECTED_PACKAGES)
        assert stats["components"] > 0
        assert stats["features"] > 0

    def test_graph_metadata_has_project_root(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Graph metadata must contain the project root path."""
        root = zerorepo_baseline_graph.metadata.get("project_root")
        assert root is not None
        assert str(_ZEROREPO_SRC.resolve()) in root

    def test_parent_ids_form_valid_chain(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """Every node's parent_id (if set) must reference an existing node at same or higher level.

        Note: MODULE -> MODULE is valid for nested packages (e.g. zerorepo -> cli).
        """
        graph = zerorepo_baseline_graph
        level_rank = {NodeLevel.MODULE: 0, NodeLevel.COMPONENT: 1, NodeLevel.FEATURE: 2}

        for node in graph.nodes.values():
            if node.parent_id is not None:
                parent = graph.get_node(node.parent_id)
                assert parent is not None, (
                    f"Node {node.name!r} references missing parent {node.parent_id}"
                )
                assert level_rank[parent.level] <= level_rank[node.level], (
                    f"Node {node.name!r} (level={node.level}) has parent "
                    f"{parent.name!r} (level={parent.level}) at a lower level"
                )

    def test_file_paths_are_relative(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """All file_path and folder_path values must be relative."""
        for node in zerorepo_baseline_graph.nodes.values():
            if node.file_path:
                assert not node.file_path.startswith("/"), (
                    f"Node {node.name!r} has absolute file_path: {node.file_path}"
                )
            if node.folder_path:
                assert not node.folder_path.startswith("/"), (
                    f"Node {node.name!r} has absolute folder_path: {node.folder_path}"
                )

    def test_component_file_paths_end_with_py(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """COMPONENT nodes must have file_path ending in .py."""
        components = [
            n for n in zerorepo_baseline_graph.nodes.values()
            if n.level == NodeLevel.COMPONENT
        ]
        for comp in components:
            assert comp.file_path is not None, (
                f"Component {comp.name!r} has no file_path"
            )
            assert comp.file_path.endswith(".py"), (
                f"Component {comp.name!r} file_path doesn't end with .py: {comp.file_path}"
            )


# ===========================================================================
# 2. BASELINE PERSISTENCE: Save/Load round-trip
# ===========================================================================


class TestBaselinePersistence:
    """Test save/load round-trip of the self-dogfooded baseline."""

    def test_save_and_load_roundtrip(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """Graph can be serialized and deserialized without data loss."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )

        loaded = baseline_manager.load(output)

        assert loaded.node_count == zerorepo_baseline_graph.node_count
        assert loaded.edge_count == zerorepo_baseline_graph.edge_count

    def test_roundtrip_preserves_node_names(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """All node names survive serialization round-trip."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )
        loaded = baseline_manager.load(output)

        original_names = sorted(n.name for n in zerorepo_baseline_graph.nodes.values())
        loaded_names = sorted(n.name for n in loaded.nodes.values())
        assert loaded_names == original_names

    def test_roundtrip_preserves_edge_types(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """Edge types survive serialization round-trip."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )
        loaded = baseline_manager.load(output)

        original_types = sorted(e.edge_type.value for e in zerorepo_baseline_graph.edges.values())
        loaded_types = sorted(e.edge_type.value for e in loaded.edges.values())
        assert loaded_types == original_types

    def test_roundtrip_preserves_node_levels(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """Node levels survive serialization round-trip."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )
        loaded = baseline_manager.load(output)

        original_levels = sorted(n.level.value for n in zerorepo_baseline_graph.nodes.values())
        loaded_levels = sorted(n.level.value for n in loaded.nodes.values())
        assert loaded_levels == original_levels

    def test_roundtrip_preserves_metadata(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """Baseline metadata survives serialization round-trip."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )
        loaded = baseline_manager.load(output)

        assert loaded.metadata.get("baseline_version") == "1.0"
        assert "baseline_generated_at" in loaded.metadata

    def test_saved_file_is_valid_json(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """The saved file is valid JSON with expected structure."""
        output = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=output,
            project_root=_ZEROREPO_SRC,
        )

        content = output.read_text(encoding="utf-8")
        data = json.loads(content)
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data
        assert len(data["nodes"]) == zerorepo_baseline_graph.node_count

    def test_default_path_matches_convention(self) -> None:
        """Default path follows .zerorepo/baseline.json convention."""
        path = BaselineManager.default_path(Path("/some/project"))
        assert path == Path("/some/project/.zerorepo/baseline.json")


# ===========================================================================
# 3. DELTA REPORTING: Baseline vs enriched graph
# ===========================================================================


class TestDeltaReporting:
    """Test delta reporting using the self-dogfooded baseline."""

    def test_all_baseline_nodes_are_existing(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """A pure baseline graph (no delta_status) defaults all nodes to NEW."""
        summary = delta_generator.summarize(zerorepo_baseline_graph)
        # Default delta_status is NEW when not set in metadata
        assert summary.new == zerorepo_baseline_graph.node_count
        assert summary.existing == 0
        assert summary.modified == 0

    def test_delta_with_existing_markers(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """Nodes marked as 'existing' are counted correctly."""
        # Make a copy and mark all nodes as existing
        graph = RPGGraph.from_json(zerorepo_baseline_graph.to_json())
        for node in graph.nodes.values():
            node.metadata["delta_status"] = DeltaStatus.EXISTING.value

        summary = delta_generator.summarize(graph)
        assert summary.existing == graph.node_count
        assert summary.new == 0
        assert summary.modified == 0
        assert summary.actionable == 0

    def test_delta_with_mixed_statuses(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """Mixed delta statuses are counted correctly."""
        graph = RPGGraph.from_json(zerorepo_baseline_graph.to_json())
        nodes = list(graph.nodes.values())

        # Mark first 1/3 as existing, second 1/3 as modified, rest as new
        third = len(nodes) // 3
        for i, node in enumerate(nodes):
            if i < third:
                node.metadata["delta_status"] = DeltaStatus.EXISTING.value
            elif i < 2 * third:
                node.metadata["delta_status"] = DeltaStatus.MODIFIED.value
            else:
                node.metadata["delta_status"] = DeltaStatus.NEW.value

        summary = delta_generator.summarize(graph)
        assert summary.existing + summary.modified + summary.new == graph.node_count
        assert summary.total == graph.node_count
        assert summary.actionable == summary.new + summary.modified

    def test_delta_summary_has_by_level(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """DeltaSummary includes per-level breakdown."""
        summary = delta_generator.summarize(zerorepo_baseline_graph)
        assert isinstance(summary.by_level, dict)
        # Should have MODULE, COMPONENT, FEATURE
        assert "MODULE" in summary.by_level
        assert "COMPONENT" in summary.by_level
        assert "FEATURE" in summary.by_level

    def test_generate_markdown_report(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """generate() produces a well-formed markdown report."""
        report = delta_generator.generate(zerorepo_baseline_graph)
        assert isinstance(report, str)
        assert "# Delta Report" in report
        assert "## Delta Summary" in report
        assert "nodes" in report

    def test_generate_report_with_custom_title(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """generate() respects custom title."""
        report = delta_generator.generate(
            zerorepo_baseline_graph, title="ZeroRepo Self-Analysis"
        )
        assert "# ZeroRepo Self-Analysis" in report

    def test_implementation_order_returns_items(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """implementation_order() returns items for a graph with new nodes."""
        # All baseline nodes default to NEW delta_status
        order = delta_generator.implementation_order(zerorepo_baseline_graph)
        assert len(order) > 0
        # Verify items have expected attributes
        for item in order[:5]:
            assert item.name
            assert item.level in ("MODULE", "COMPONENT", "FEATURE")
            assert item.delta_status in ("new", "modified")

    def test_implementation_order_sorted_by_level(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """implementation_order() sorts MODULE before COMPONENT before FEATURE."""
        order = delta_generator.implementation_order(zerorepo_baseline_graph)
        level_order = {"MODULE": 0, "COMPONENT": 1, "FEATURE": 2}
        prev_rank = -1
        for item in order:
            rank = level_order[item.level]
            if rank < prev_rank:
                # This would be a violation of sort order
                pytest.fail(
                    f"Sort violation: {item.name} (level={item.level}) "
                    f"came after a higher-rank level"
                )
            prev_rank = rank

    def test_all_existing_graph_has_no_actionable_items(
        self,
        zerorepo_baseline_graph: RPGGraph,
        delta_generator: DeltaReportGenerator,
    ) -> None:
        """Graph with all EXISTING nodes has no implementation items."""
        graph = RPGGraph.from_json(zerorepo_baseline_graph.to_json())
        for node in graph.nodes.values():
            node.metadata["delta_status"] = DeltaStatus.EXISTING.value

        order = delta_generator.implementation_order(graph)
        assert len(order) == 0


# ===========================================================================
# 4. ENRICHMENT PIPELINE: Mock-LLM enrichment on the self-dogfooded baseline
# ===========================================================================


class MockLLMGateway:
    """Mock LLM gateway for integration testing without real API calls."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        prompt = messages[0]["content"]
        if "docstring" in prompt.lower():
            return "Auto-generated docstring for integration test."
        return "def mock_function(self) -> None:"


class TestEnrichmentWithBaseline:
    """Test enrichment encoders using the self-dogfooded baseline."""

    def test_interface_encoder_uses_baseline_for_existing_features(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """InterfaceDesignEncoder should use baseline signatures for existing nodes.

        Note: The walker produces signatures WITHOUT trailing colons (e.g.
        ``def foo() -> None``).  The enrichment encoder's ``_validate_signature_syntax``
        requires a trailing colon.  An enriched baseline stores colon-terminated
        signatures, so we add the colon when building the enriched baseline.
        """
        from zerorepo.rpg_enrichment.interface_design_encoder import (
            InterfaceDesignEncoder,
        )

        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)

        # Take a small subset of features for a focused test
        baseline = zerorepo_baseline_graph
        features_in_baseline = [
            n for n in baseline.nodes.values()
            if n.level == NodeLevel.FEATURE
        ][:5]

        # Create a new small graph with the same named features
        graph = RPGGraph()
        for feat in features_in_baseline:
            new_node = RPGNode(
                name=feat.name,
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTIONALITY,
                file_path=feat.file_path,
                folder_path=feat.folder_path,
            )
            graph.add_node(new_node)

        # The walker's raw signatures lack a trailing colon. An enriched baseline
        # would have properly formatted signatures with colons, so we add them.
        enriched_baseline = RPGGraph()
        for feat in features_in_baseline:
            raw_sig = feat.metadata.get("signature", "")
            kind = feat.metadata.get("kind", "function")
            if raw_sig and not raw_sig.rstrip().endswith(":"):
                sig = raw_sig.rstrip() + ":"
            elif raw_sig:
                sig = raw_sig
            else:
                sig = f"def {feat.name}() -> None:" if kind == "function" else f"class {feat.name}:"

            itype = InterfaceType.FUNCTION if kind == "function" else InterfaceType.CLASS
            b_node = RPGNode(
                name=feat.name,
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTION_AUGMENTED,
                interface_type=itype,
                signature=sig,
                docstring=feat.docstring or f"Docstring for {feat.name}",
                file_path=feat.file_path,
                folder_path=feat.folder_path,
                serena_validated=True,
                metadata={"baseline": True, "signature": sig},
            )
            enriched_baseline.add_node(b_node)

        encoder.encode(graph, baseline=enriched_baseline)

        # All nodes should have used baseline signatures (no LLM calls)
        assert llm.call_count == 0, (
            f"Expected 0 LLM calls but got {llm.call_count}"
        )
        for node in graph.nodes.values():
            assert node.signature is not None, (
                f"Node {node.name!r} has no signature after encoding"
            )
            assert node.serena_validated is True
            assert node.metadata.get("baseline_signature_used") is True

    def test_folder_encoder_uses_baseline_paths(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """FolderEncoder should use baseline folder_path/file_path for existing nodes."""
        from zerorepo.rpg_enrichment.folder_encoder import FolderEncoder

        encoder = FolderEncoder()

        # Take a small subset of nodes
        all_nodes = list(zerorepo_baseline_graph.nodes.values())[:10]

        # Create a new graph with same names but no paths
        graph = RPGGraph()
        node_map: dict[str, RPGNode] = {}
        for orig in all_nodes:
            new_node = RPGNode(
                name=orig.name,
                level=orig.level,
                node_type=orig.node_type,
            )
            graph.add_node(new_node)
            node_map[orig.name] = new_node

        encoder.encode(graph, baseline=zerorepo_baseline_graph)

        # Nodes that matched baseline should have baseline paths
        matched = [
            n for n in graph.nodes.values()
            if n.metadata.get("baseline_folder_used") is True
        ]
        # At least some should match
        assert len(matched) > 0, "No nodes matched baseline for folder paths"

    def test_dataflow_encoder_handles_baseline(
        self, zerorepo_baseline_graph: RPGGraph
    ) -> None:
        """DataFlowEncoder should handle a real baseline without errors."""
        from zerorepo.rpg_enrichment.dataflow_encoder import DataFlowEncoder

        encoder = DataFlowEncoder()

        # Build a small graph with some nodes and HIERARCHY edges
        graph = RPGGraph()
        mod = RPGNode(
            name="models",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="models",
        )
        comp = RPGNode(
            name="graph",
            level=NodeLevel.COMPONENT,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="models",
            file_path="models/graph.py",
        )
        feat = RPGNode(
            name="RPGGraph",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="models",
            file_path="models/graph.py",
        )
        graph.add_node(mod)
        graph.add_node(comp)
        graph.add_node(feat)
        graph.add_edge(
            RPGEdge(source_id=mod.id, target_id=comp.id, edge_type=EdgeType.HIERARCHY)
        )
        graph.add_edge(
            RPGEdge(source_id=comp.id, target_id=feat.id, edge_type=EdgeType.HIERARCHY)
        )

        # Should not raise
        result = encoder.encode(graph, baseline=zerorepo_baseline_graph)
        assert result is graph


# ===========================================================================
# 5. ANALYZER SPECIFIC TESTS: FileBasedCodebaseAnalyzer on real code
# ===========================================================================


class TestAnalyzerOnRealCode:
    """Test FileBasedCodebaseAnalyzer directly against zerorepo source."""

    @pytest.fixture
    def activated_analyzer(self) -> FileBasedCodebaseAnalyzer:
        """Return an analyzer activated for zerorepo source."""
        _skip_if_no_source()
        analyzer = FileBasedCodebaseAnalyzer()
        result = analyzer.activate(_ZEROREPO_SRC)
        assert result.success, f"Activation failed: {result.details}"
        return analyzer

    def test_list_root_directory(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Listing root should show known packages."""
        entries = activated_analyzer.list_directory(".")
        names = {e.name for e in entries}
        assert "models" in names
        assert "serena" in names
        assert "rpg_enrichment" in names

    def test_list_models_directory(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Listing models/ should show key files."""
        entries = activated_analyzer.list_directory("models")
        names = {e.name for e in entries}
        assert "graph.py" in names
        assert "node.py" in names
        assert "edge.py" in names

    def test_get_symbols_from_graph_py(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Extracting symbols from models/graph.py should find RPGGraph."""
        symbols = activated_analyzer.get_symbols("models/graph.py")
        names = [s.name for s in symbols]
        assert "RPGGraph" in names

        rpg_graph_sym = next(s for s in symbols if s.name == "RPGGraph")
        assert rpg_graph_sym.kind == "class"
        assert rpg_graph_sym.line >= 1
        assert rpg_graph_sym.signature is not None
        assert rpg_graph_sym.docstring is not None

    def test_get_symbols_from_node_py(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Extracting symbols from models/node.py should find RPGNode."""
        symbols = activated_analyzer.get_symbols("models/node.py")
        names = [s.name for s in symbols]
        assert "RPGNode" in names

    def test_get_symbols_from_walker_py(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Extracting symbols from serena/walker.py should find CodebaseWalker."""
        symbols = activated_analyzer.get_symbols("serena/walker.py")
        names = [s.name for s in symbols]
        assert "CodebaseWalker" in names

    def test_find_symbol_rpggraph(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """find_symbol should locate RPGGraph across the codebase."""
        results = activated_analyzer.find_symbol("RPGGraph")
        assert len(results) >= 1
        assert any(s.name == "RPGGraph" for s in results)

    def test_find_references_to_rpgnode(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """find_references should find references to RPGNode."""
        results = activated_analyzer.find_references("RPGNode")
        assert len(results) >= 1

    def test_search_pattern_class_definitions(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """search_pattern should find class definitions."""
        results = activated_analyzer.search_pattern(r"class RPG\w+")
        assert len(results) >= 3  # RPGGraph, RPGNode, RPGEdge at minimum

    def test_symbols_have_proper_signatures(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        """Symbols should include proper signature strings."""
        symbols = activated_analyzer.get_symbols("serena/session.py")
        fba = next(
            (s for s in symbols if s.name == "FileBasedCodebaseAnalyzer"),
            None,
        )
        assert fba is not None
        assert fba.kind == "class"
        # Should have methods as well
        methods = [s for s in symbols if s.name.startswith("FileBasedCodebaseAnalyzer.")]
        assert len(methods) > 0


# ===========================================================================
# 6. END-TO-END PIPELINE: Walk -> Save -> Load -> Delta -> Enrich
# ===========================================================================


class TestEndToEndPipeline:
    """Full pipeline: walk -> save -> load -> mark delta -> report."""

    def test_full_pipeline_flow(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        delta_generator: DeltaReportGenerator,
        tmp_path: Path,
    ) -> None:
        """End-to-end: walk -> save -> load -> delta report."""
        # Step 1: The graph was already walked (via fixture)
        original_count = zerorepo_baseline_graph.node_count
        assert original_count > 50

        # Step 2: Save baseline
        baseline_path = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=baseline_path,
            project_root=_ZEROREPO_SRC,
        )
        assert baseline_path.exists()

        # Step 3: Load baseline
        loaded_baseline = baseline_manager.load(baseline_path)
        assert loaded_baseline.node_count == original_count

        # Step 4: Create an "enriched" graph simulating new spec additions
        enriched = RPGGraph.from_json(loaded_baseline.to_json())

        # Mark existing nodes as EXISTING
        for node in enriched.nodes.values():
            node.metadata["delta_status"] = DeltaStatus.EXISTING.value

        # Add some new nodes to simulate spec additions
        new_module = RPGNode(
            name="new_auth_module",
            level=NodeLevel.MODULE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="new_auth",
            metadata={"delta_status": DeltaStatus.NEW.value},
        )
        enriched.add_node(new_module)

        new_feature = RPGNode(
            name="validate_jwt",
            level=NodeLevel.FEATURE,
            node_type=NodeType.FUNCTIONALITY,
            folder_path="new_auth",
            file_path="new_auth/jwt.py",
            metadata={"delta_status": DeltaStatus.NEW.value},
        )
        enriched.add_node(new_feature)

        # Step 5: Generate delta report
        summary = delta_generator.summarize(enriched)
        assert summary.existing == original_count
        assert summary.new == 2  # new_auth_module + validate_jwt
        assert summary.total == original_count + 2

        # Step 6: Generate markdown report
        report = delta_generator.generate(
            enriched, title="ZeroRepo Self-Dogfood Delta"
        )
        assert "# ZeroRepo Self-Dogfood Delta" in report
        assert "new_auth_module" in report
        assert "validate_jwt" in report

        # Step 7: Verify implementation order
        order = delta_generator.implementation_order(enriched)
        assert len(order) == 2  # Only new nodes
        item_names = {item.name for item in order}
        assert "new_auth_module" in item_names
        assert "validate_jwt" in item_names

    def test_baseline_to_enriched_with_mock_llm(
        self,
        zerorepo_baseline_graph: RPGGraph,
        baseline_manager: BaselineManager,
        tmp_path: Path,
    ) -> None:
        """Full pipeline with mock LLM: walk -> save -> load -> enrich subset."""
        from zerorepo.rpg_enrichment.interface_design_encoder import (
            InterfaceDesignEncoder,
        )

        # Save and reload
        baseline_path = tmp_path / "baseline.json"
        baseline_manager.save(
            zerorepo_baseline_graph,
            output_path=baseline_path,
            project_root=_ZEROREPO_SRC,
        )
        loaded = baseline_manager.load(baseline_path)

        # Prepare enriched baseline with colon-terminated signatures for matching.
        # Walker produces raw signatures without trailing colons; an enriched
        # baseline stores them with colons.
        enriched_baseline = RPGGraph()
        for node in loaded.nodes.values():
            if node.level == NodeLevel.FEATURE:
                raw_sig = node.metadata.get("signature", "")
                kind = node.metadata.get("kind", "function")
                if raw_sig and not raw_sig.rstrip().endswith(":"):
                    sig = raw_sig.rstrip() + ":"
                elif raw_sig:
                    sig = raw_sig
                else:
                    sig = f"def {node.name}() -> None:" if kind == "function" else f"class {node.name}:"

                b_node = RPGNode(
                    name=node.name,
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTION_AUGMENTED,
                    interface_type=(
                        InterfaceType.CLASS if kind == "class" else InterfaceType.FUNCTION
                    ),
                    signature=sig,
                    docstring=node.docstring or f"Docstring for {node.name}",
                    file_path=node.file_path,
                    folder_path=node.folder_path,
                    serena_validated=True,
                    metadata={"baseline": True, "signature": sig},
                )
                enriched_baseline.add_node(b_node)

        # Create a small graph with just 3 features from baseline + 1 new
        features = [
            n for n in loaded.nodes.values()
            if n.level == NodeLevel.FEATURE
        ][:3]

        graph = RPGGraph()
        for feat in features:
            graph.add_node(
                RPGNode(
                    name=feat.name,
                    level=NodeLevel.FEATURE,
                    node_type=NodeType.FUNCTIONALITY,
                    file_path=feat.file_path,
                    folder_path=feat.folder_path,
                )
            )
        # Add one truly new feature
        graph.add_node(
            RPGNode(
                name="brand_new_feature",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTIONALITY,
                file_path="new/module.py",
                folder_path="new",
            )
        )

        llm = MockLLMGateway()
        encoder = InterfaceDesignEncoder(llm_gateway=llm)
        encoder.encode(graph, baseline=enriched_baseline)

        # 3 nodes from baseline should use cached signatures (0 LLM calls)
        # 1 new node should use LLM (2 calls: signature + docstring)
        assert llm.call_count == 2, (
            f"Expected 2 LLM calls for new feature, got {llm.call_count}"
        )

        # Verify all 4 nodes have signatures
        for node in graph.nodes.values():
            assert node.signature is not None, (
                f"Node {node.name!r} missing signature"
            )

    def test_idempotent_re_walk(self) -> None:
        """Walking the same source tree twice produces equivalent results."""
        _skip_if_no_source()
        analyzer1 = FileBasedCodebaseAnalyzer()
        walker1 = CodebaseWalker(analyzer1)
        graph1 = walker1.walk(_ZEROREPO_SRC)

        analyzer2 = FileBasedCodebaseAnalyzer()
        walker2 = CodebaseWalker(analyzer2)
        graph2 = walker2.walk(_ZEROREPO_SRC)

        assert graph1.node_count == graph2.node_count
        assert graph1.edge_count == graph2.edge_count

        names1 = sorted(n.name for n in graph1.nodes.values())
        names2 = sorted(n.name for n in graph2.nodes.values())
        assert names1 == names2


# ===========================================================================
# 7. CLI INTEGRATION: CliRunner-based end-to-end tests
# ===========================================================================


class TestCLIInitBaseline:
    """Test `zerorepo init --project-path` via CliRunner."""

    def test_init_with_project_path_creates_baseline(
        self, tmp_path: Path
    ) -> None:
        """init --project-path walks the codebase and saves a baseline file."""
        _skip_if_no_source()
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init",
                str(tmp_path),
                "--project-path",
                str(_ZEROREPO_SRC),
            ],
        )
        assert result.exit_code == 0, (
            f"CLI init failed (exit={result.exit_code}): {result.output}"
        )

        # .zerorepo directory should exist
        zerorepo_dir = tmp_path / ".zerorepo"
        assert zerorepo_dir.is_dir()

        # Baseline file should exist
        baseline_file = zerorepo_dir / "baseline.json"
        assert baseline_file.exists(), "Baseline file not created"

        # Baseline should be valid JSON loadable as RPGGraph
        loaded = BaselineManager().load(baseline_file)
        assert loaded.node_count > 50

    def test_init_with_project_path_and_exclude(
        self, tmp_path: Path
    ) -> None:
        """init --project-path --exclude should skip excluded patterns."""
        _skip_if_no_source()
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init",
                str(tmp_path),
                "--project-path",
                str(_ZEROREPO_SRC),
                "--exclude",
                "evaluation,sandbox",
            ],
        )
        assert result.exit_code == 0, (
            f"CLI init failed (exit={result.exit_code}): {result.output}"
        )

        baseline_file = tmp_path / ".zerorepo" / "baseline.json"
        assert baseline_file.exists()

        loaded = BaselineManager().load(baseline_file)
        module_names = {
            n.name
            for n in loaded.nodes.values()
            if n.level == NodeLevel.MODULE
        }
        # "evaluation" and "sandbox" should be excluded
        assert "evaluation" not in module_names
        assert "sandbox" not in module_names
        # Other packages should still be present
        assert "models" in module_names
        assert "cli" in module_names

    def test_init_with_custom_output_path(
        self, tmp_path: Path
    ) -> None:
        """init --project-path --output writes to specified path."""
        _skip_if_no_source()
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        custom_output = tmp_path / "custom_baseline.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init",
                str(tmp_path),
                "--project-path",
                str(_ZEROREPO_SRC),
                "--output",
                str(custom_output),
            ],
        )
        assert result.exit_code == 0, (
            f"CLI init failed (exit={result.exit_code}): {result.output}"
        )
        assert custom_output.exists(), "Custom baseline output not created"


class TestCLIGenerateWithBaseline:
    """Test `zerorepo generate` with and without --baseline via CliRunner."""

    @pytest.fixture
    def spec_file(self, tmp_path: Path) -> Path:
        """Create a simple spec file for generate testing."""
        spec = tmp_path / "test-spec.txt"
        spec.write_text(
            "A simple TODO application with:\n"
            "- User authentication (login, register)\n"
            "- Task management (create, update, delete tasks)\n"
            "- REST API backend with Python Flask\n"
        )
        return spec

    @pytest.fixture
    def baseline_file(
        self, zerorepo_baseline_graph: RPGGraph, tmp_path: Path
    ) -> Path:
        """Save the self-dogfooded baseline to a temp file for CLI testing."""
        mgr = BaselineManager()
        path = tmp_path / "baseline.json"
        mgr.save(
            zerorepo_baseline_graph,
            output_path=path,
            project_root=_ZEROREPO_SRC,
        )
        return path

    def test_generate_help(self) -> None:
        """generate --help shows expected options."""
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--baseline" in result.output
        assert "--skip-enrichment" in result.output
        assert "--output" in result.output

    def _make_mock_spec(self) -> Any:
        """Create a valid mock RepositorySpec with epics/components."""
        from zerorepo.spec_parser.models import Component, Epic, RepositorySpec

        return RepositorySpec(
            description="A TODO application with task management and authentication",
            core_functionality="Task management and authentication",
            epics=[
                Epic(
                    title="Authentication",
                    description="User auth features",
                    components=["Login", "Register"],
                ),
                Epic(
                    title="Task Management",
                    description="CRUD for tasks",
                    components=["CreateTask", "UpdateTask"],
                ),
            ],
            components=[
                Component(name="Login", description="User login"),
                Component(name="Register", description="User registration"),
                Component(name="CreateTask", description="Create tasks"),
                Component(name="UpdateTask", description="Update tasks"),
            ],
        )

    def test_generate_without_baseline_succeeds(
        self, spec_file: Path, tmp_path: Path
    ) -> None:
        """generate with --skip-enrichment and no baseline produces output."""
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        output_dir = tmp_path / "output"
        runner = CliRunner()

        with patch(
            "zerorepo.spec_parser.parser.SpecParser.parse"
        ) as mock_parse:
            mock_parse.return_value = self._make_mock_spec()

            result = runner.invoke(
                app,
                [
                    "generate",
                    str(spec_file),
                    "--output",
                    str(output_dir),
                    "--skip-enrichment",
                ],
            )
            assert result.exit_code == 0, (
                f"Generate failed: {result.output}"
            )

        # Should produce expected output files
        assert (output_dir / "01-spec.json").exists()
        assert (output_dir / "04-rpg.json").exists()
        assert (output_dir / "pipeline-report.md").exists()

    def test_generate_with_baseline_flag_accepted(
        self,
        spec_file: Path,
        baseline_file: Path,
        tmp_path: Path,
    ) -> None:
        """generate --baseline loads the baseline and threads it through."""
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        output_dir = tmp_path / "output-with-baseline"
        runner = CliRunner()

        with patch(
            "zerorepo.spec_parser.parser.SpecParser.parse"
        ) as mock_parse:
            mock_parse.return_value = self._make_mock_spec()

            result = runner.invoke(
                app,
                [
                    "generate",
                    str(spec_file),
                    "--output",
                    str(output_dir),
                    "--baseline",
                    str(baseline_file),
                    "--skip-enrichment",
                ],
            )
            assert result.exit_code == 0, (
                f"Generate with baseline failed: {result.output}"
            )

        # Should print baseline info
        assert "Baseline" in result.output
        # Output files should exist
        assert (output_dir / "01-spec.json").exists()
        assert (output_dir / "04-rpg.json").exists()

    def test_generate_with_invalid_baseline_fails(
        self, spec_file: Path, tmp_path: Path
    ) -> None:
        """generate --baseline with non-existent file fails gracefully."""
        from typer.testing import CliRunner
        from zerorepo.cli.app import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "generate",
                str(spec_file),
                "--baseline",
                str(tmp_path / "nonexistent.json"),
                "--skip-enrichment",
            ],
        )
        assert result.exit_code != 0


# ===========================================================================
# 8. REGRESSION: Pipeline without baseline is identical to pre-integration
# ===========================================================================


class TestRegressionNoBaseline:
    """Ensure the pipeline without --baseline behaves identically to pre-integration."""

    @staticmethod
    def _make_regression_spec() -> Any:
        """Create a simple RepositorySpec for regression tests."""
        from zerorepo.spec_parser.models import Component, Epic, RepositorySpec

        return RepositorySpec(
            description="Test spec for regression testing of pipeline behaviour",
            core_functionality="Test functionality",
            epics=[
                Epic(
                    title="Auth",
                    description="Authentication",
                    components=["Login"],
                ),
            ],
            components=[
                Component(name="Login", description="Login component"),
            ],
        )

    def test_converter_without_baseline_no_delta_metadata(self) -> None:
        """converter.convert() without baseline produces nodes with no delta_status."""
        from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
        from zerorepo.graph_construction.converter import FunctionalityGraphConverter

        spec = self._make_regression_spec()
        builder = FunctionalityGraphBuilder()
        func_graph = builder.build_from_spec(spec)

        converter = FunctionalityGraphConverter()
        rpg_graph = converter.convert(func_graph, spec=spec, baseline=None)

        # No node should have delta_status metadata
        for node in rpg_graph.nodes.values():
            assert "delta_status" not in node.metadata, (
                f"Node {node.name!r} has delta_status without baseline"
            )
        # No has_baseline in graph metadata
        assert rpg_graph.metadata.get("has_baseline") is not True

    def test_converter_with_baseline_has_delta_metadata(self) -> None:
        """converter.convert() with baseline produces nodes WITH delta_status."""
        from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
        from zerorepo.graph_construction.converter import FunctionalityGraphConverter

        spec = self._make_regression_spec()
        builder = FunctionalityGraphBuilder()
        func_graph = builder.build_from_spec(spec)

        # Provide an empty baseline (simulates a real baseline with no matches)
        baseline = RPGGraph()

        converter = FunctionalityGraphConverter()
        rpg_graph = converter.convert(func_graph, spec=spec, baseline=baseline)

        # All nodes should have delta_status since baseline was provided
        for node in rpg_graph.nodes.values():
            assert "delta_status" in node.metadata, (
                f"Node {node.name!r} missing delta_status with baseline"
            )
        # has_baseline should be True
        assert rpg_graph.metadata.get("has_baseline") is True

    def test_spec_parser_without_baseline_no_baseline_context(self) -> None:
        """SpecParser.parse() without baseline doesn't inject baseline context."""
        from zerorepo.spec_parser.parser import SpecParser, ParserConfig

        # Use a mock to capture what prompt is sent
        with patch(
            "zerorepo.spec_parser.parser.SpecParser._call_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"description": "test"}'

            parser = SpecParser(config=ParserConfig())
            try:
                parser.parse("A simple test app", baseline=None)
            except Exception:
                pass  # We only care about the prompt

            if mock_llm.called:
                prompt_arg = mock_llm.call_args[0][0] if mock_llm.call_args[0] else ""
                assert "EXISTING CODEBASE BASELINE" not in str(prompt_arg)

    def test_pipeline_output_structure_identical_without_baseline(
        self,
    ) -> None:
        """RPGGraph produced without baseline has same schema as with baseline."""
        from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
        from zerorepo.graph_construction.converter import FunctionalityGraphConverter

        spec = self._make_regression_spec()
        builder = FunctionalityGraphBuilder()
        func_graph = builder.build_from_spec(spec)

        converter = FunctionalityGraphConverter()

        # Without baseline
        graph_no_baseline = converter.convert(func_graph, spec=spec, baseline=None)

        # With empty baseline
        graph_with_baseline = converter.convert(
            func_graph, spec=spec, baseline=RPGGraph()
        )

        # Same number of nodes and edges
        assert graph_no_baseline.node_count == graph_with_baseline.node_count
        assert graph_no_baseline.edge_count == graph_with_baseline.edge_count

        # Same node names
        names_no = sorted(n.name for n in graph_no_baseline.nodes.values())
        names_with = sorted(n.name for n in graph_with_baseline.nodes.values())
        assert names_no == names_with

        # Same edge types
        types_no = sorted(e.edge_type.value for e in graph_no_baseline.edges.values())
        types_with = sorted(e.edge_type.value for e in graph_with_baseline.edges.values())
        assert types_no == types_with

    def test_enrichment_encoders_without_baseline_backward_compatible(
        self,
    ) -> None:
        """Enrichment encoders work identically when baseline=None."""
        from zerorepo.rpg_enrichment import (
            DataFlowEncoder,
            FileEncoder,
            FolderEncoder,
            IntraModuleOrderEncoder,
            BaseClassEncoder,
        )

        # Build a small graph - FolderEncoder assigns paths, so omit them
        # and let the encoder fill them in.  Run each encoder on an
        # independent copy to avoid path-validation conflicts.
        def _make_graph() -> RPGGraph:
            g = RPGGraph()
            mod = RPGNode(
                name="core",
                level=NodeLevel.MODULE,
                node_type=NodeType.FUNCTIONALITY,
            )
            comp = RPGNode(
                name="handler",
                level=NodeLevel.COMPONENT,
                node_type=NodeType.FUNCTIONALITY,
            )
            feat = RPGNode(
                name="handle_request",
                level=NodeLevel.FEATURE,
                node_type=NodeType.FUNCTIONALITY,
            )
            g.add_node(mod)
            g.add_node(comp)
            g.add_node(feat)
            g.add_edge(RPGEdge(source_id=mod.id, target_id=comp.id, edge_type=EdgeType.HIERARCHY))
            g.add_edge(RPGEdge(source_id=comp.id, target_id=feat.id, edge_type=EdgeType.HIERARCHY))
            return g

        # Each encoder should work without baseline on its own graph copy
        for encoder_cls in [FolderEncoder, FileEncoder, DataFlowEncoder, IntraModuleOrderEncoder, BaseClassEncoder]:
            graph = _make_graph()
            encoder = encoder_cls()
            result = encoder.encode(graph, baseline=None)
            assert result is graph, f"{encoder_cls.__name__} failed with baseline=None"

    def test_two_runs_without_baseline_produce_same_structure(
        self,
    ) -> None:
        """Two independent runs without baseline produce identical graph structure."""
        from zerorepo.graph_construction.builder import FunctionalityGraphBuilder
        from zerorepo.graph_construction.converter import FunctionalityGraphConverter
        from zerorepo.spec_parser.models import Component, Epic, RepositorySpec

        spec = RepositorySpec(
            description="Idempotency test for pipeline regression verification",
            core_functionality="Test functionality",
            epics=[
                Epic(
                    title="Module1",
                    description="First module",
                    components=["Comp1", "Comp2"],
                ),
            ],
            components=[
                Component(name="Comp1", description="Component 1"),
                Component(name="Comp2", description="Component 2"),
            ],
        )

        builder = FunctionalityGraphBuilder()
        converter = FunctionalityGraphConverter()

        # Run 1
        fg1 = builder.build_from_spec(spec)
        g1 = converter.convert(fg1, spec=spec, baseline=None)

        # Run 2
        fg2 = builder.build_from_spec(spec)
        g2 = converter.convert(fg2, spec=spec, baseline=None)

        assert g1.node_count == g2.node_count
        assert g1.edge_count == g2.edge_count

        names1 = sorted(n.name for n in g1.nodes.values())
        names2 = sorted(n.name for n in g2.nodes.values())
        assert names1 == names2

        levels1 = sorted(n.level.value for n in g1.nodes.values())
        levels2 = sorted(n.level.value for n in g2.nodes.values())
        assert levels1 == levels2
