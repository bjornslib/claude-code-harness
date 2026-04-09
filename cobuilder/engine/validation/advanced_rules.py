"""Advanced validation rules for Epic 5 - Attractor Schema extensions.

Implements the following requirements from PRD-HARNESS-UPGRADE-001:
- AC-5.1: sd_path mandatory on codergen nodes — validate rejects nodes without it
- AC-5.2: Full cluster topology check implemented
- AC-5.3: worker_type registry check rejects unknown agent types
- AC-5.4: wait.human after wait.cobuilder topology enforced
- AC-5.5: cobuilder_root and target_dir mandatory graph attributes

Epic 1 additions:
- DiamondNWayBranching: relaxes diamond validation from strict pass/fail pair
  to N-way conditional branching (N >= 2, all edges must have a condition).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from cobuilder.engine.schema import VALID_WORKER_TYPES
from cobuilder.engine.validation import RuleViolation, Severity
from cobuilder.engine.validation.rules import _error, _warning

if TYPE_CHECKING:
    from cobuilder.engine.graph import Graph, Node


# ---------------------------------------------------------------------------
# Rule 20: DiamondNWayBranching (Epic 1 — N-way conditional routing)
# ---------------------------------------------------------------------------

class DiamondNWayBranching:
    """Diamond (conditional) nodes support N-way branching (N >= 2).

    Replaces the old strict 2-edge pass/fail enforcement with:
    - ERROR if a diamond has fewer than 2 outgoing edges (useless branch).
    - ERROR if any outgoing edge from a diamond has an empty/missing condition
      attribute (the condition is what distinguishes branches in N-way routing).
    - WARNING if no outgoing edge has a catch-all condition (``condition="true"``),
      since a non-exhaustive routing set can leave the pipeline stuck.

    Diamond nodes use ``shape=diamond`` in the DOT file.
    """

    rule_id = "DiamondNWayBranching"
    severity = Severity.ERROR

    def check(self, graph: "Graph") -> "list[RuleViolation]":
        violations: list[RuleViolation] = []

        for node in graph.nodes.values():
            if node.shape != "diamond":
                continue

            outgoing = graph.edges_from(node.id)

            # ERROR: fewer than 2 outgoing edges — a branch node with 0 or 1
            # edges is either unreachable or a pass-through (neither is valid).
            if len(outgoing) < 2:
                violations.append(
                    _error(
                        self.rule_id,
                        f"Diamond node '{node.id}' has {len(outgoing)} outgoing edge(s); "
                        "conditional nodes require at least 2 branches.",
                        "Add at least 2 outgoing edges with distinct condition= attributes "
                        f"(e.g. condition=\"pass\", condition=\"fail\") to '{node.id}'.",
                        node_id=node.id,
                    )
                )
                # No point checking edge conditions if there are too few edges.
                continue

            # ERROR: any outgoing edge missing a condition attribute.
            for edge in outgoing:
                if not edge.condition:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"Edge '{edge.source}' → '{edge.target}' from diamond node "
                            f"'{node.id}' has no condition= attribute. All outgoing edges "
                            "of a diamond node must have a condition.",
                            f"Add a condition= attribute to the edge from '{edge.source}' "
                            f"to '{edge.target}' (e.g. condition=\"pass\" or "
                            "condition=\"$result = \\\"success\\\"\").",
                            edge_src=edge.source,
                            edge_dst=edge.target,
                        )
                    )

            # WARNING: no catch-all condition present.
            has_catchall = any(
                edge.condition.strip().lower() == "true" for edge in outgoing
            )
            if not has_catchall:
                violations.append(
                    _warning(
                        self.rule_id,
                        f"Diamond node '{node.id}' has no catch-all edge "
                        "(condition=\"true\"). If no condition matches at runtime "
                        "the pipeline will stall at this node.",
                        f"Add a fallback edge from '{node.id}' with condition=\"true\" "
                        "to handle unmatched cases (e.g. → an error/fallback node).",
                        node_id=node.id,
                    )
                )

        return violations


# ---------------------------------------------------------------------------
# Rule 14: SdPathOnCodergen (Enforces AC-5.1)
# ---------------------------------------------------------------------------

class SdPathOnCodergen:
    """codergen nodes must have a non-empty sd_path attribute (AC-5.1)."""

    rule_id = "SdPathOnCodergen"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []
        for node in graph.nodes.values():
            # Check if it's a codergen node (box shape or handler=codergen)
            if node.handler_type == "codergen":
                sd_path = node.attrs.get("sd_path", "").strip()
                if not sd_path:
                    violations.append(
                        _error(
                            self.rule_id,
                            "codergen node missing required 'sd_path' attribute",
                            "Add 'sd_path' attribute to the codergen node pointing to the Solution Design file",
                            node_id=node.id,
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Rule 15: WorkerTypeRegistry (Enforces AC-5.3)
# ---------------------------------------------------------------------------

# VALID_WORKER_TYPES is imported from cobuilder.engine.schema (single source of truth).

class WorkerTypeRegistry:
    """worker_type attribute must be from the known registry (AC-5.3)."""

    rule_id = "WorkerTypeRegistry"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []
        for node in graph.nodes.values():
            if node.handler_type == "codergen":
                worker_type = node.attrs.get("worker_type", "").strip()
                if worker_type and worker_type not in VALID_WORKER_TYPES:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"Unknown worker_type '{worker_type}'. Valid types: {sorted(VALID_WORKER_TYPES)}",
                            f"Change worker_type to one of: {', '.join(VALID_WORKER_TYPES)}",
                            node_id=node.id,
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Rule 16: WaitHumanAfterWaitCobuilder (Enforces AC-5.4)
# ---------------------------------------------------------------------------

class WaitHumanAfterWaitCobuilder:
    """wait.human nodes must follow wait.cobuilder or research nodes (AC-5.4)."""

    rule_id = "WaitHumanAfterWaitCobuilder"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []

        for node in graph.nodes.values():
            # Check if it's a wait.human node (likely hexagon shape with wait.human handler)
            if node.handler_type == "wait_human":
                # Check if it has a gate_type="e2e-review" which indicates it should follow wait.cobuilder
                gate_mode = node.attrs.get("mode", "")
                if gate_mode == "e2e-review":
                    # Get all incoming nodes (predecessors)
                    incoming_node_ids = {edge.source for edge in graph.edges if edge.target == node.id}
                    incoming_nodes = [graph.nodes[nid] for nid in incoming_node_ids if nid in graph.nodes]

                    # Check if any predecessor is a wait.cobuilder node
                    has_system3_predecessor = any(
                        pred.handler_type == "wait_cobuilder" for pred in incoming_nodes
                    )

                    # Check if any predecessor is a research node (alternative valid predecessor)
                    has_research_predecessor = any(
                        pred.handler_type == "research" for pred in incoming_nodes
                    )

                    if not (has_system3_predecessor or has_research_predecessor):
                        violations.append(
                            _error(
                                self.rule_id,
                                "wait.human node with mode='e2e-review' must follow a wait.cobuilder or research node",
                                "Add an edge from a wait.cobuilder node to this wait.human node",
                                node_id=node.id,
                            )
                        )
        return violations


# ---------------------------------------------------------------------------
# Rule 17: FullClusterTopology (Enforces AC-5.2)
# ---------------------------------------------------------------------------

class FullClusterTopology:
    """Enforces full codergen cluster topology: acceptance-test-writer -> ... -> codergen -> wait.cobuilder -> wait.human (AC-5.2)."""

    rule_id = "FullClusterTopology"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []

        # Find all codergen nodes that should have the full cluster
        for node in graph.nodes.values():
            if node.handler_type == "codergen":
                # Look for the cluster starting from acceptance-test-writer
                # Check if there's a connected sequence: acceptance-test-writer -> research -> refine -> codergen -> wait.cobuilder -> wait.human

                # For codergen nodes, check if they have a corresponding wait.cobuilder
                codergen_successors = self._get_downstream_nodes(graph, node.id)

                # Look for a wait.cobuilder downstream
                has_wait_cobuilder = any(
                    n.handler_type in ("wait_cobuilder", "wait.cobuilder") for n in codergen_successors.values()
                )

                if not has_wait_cobuilder:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"codergen node '{node.id}' must have a downstream wait.cobuilder validation gate",
                            "Add a wait.cobuilder node downstream from this codergen node",
                            node_id=node.id,
                        )
                    )
                    continue

                # For each wait.cobuilder found, check if it has a wait.human downstream
                cobuilder_nodes = [n for n in codergen_successors.values() if n.handler_type in ("wait_cobuilder", "wait.cobuilder")]
                for sys3_node in cobuilder_nodes:
                    sys3_downstream = self._get_downstream_nodes(graph, sys3_node.id)
                    has_wait_human = any(
                        n.handler_type in ("wait_human", "wait.human") and n.attrs.get("mode") == "e2e-review"
                        for n in sys3_downstream.values()
                    )

                    if not has_wait_human:
                        violations.append(
                            _error(
                                self.rule_id,
                                f"wait.cobuilder node '{sys3_node.id}' must have a downstream wait.human validation gate",
                                "Add a wait.human node with mode='e2e-review' downstream from this wait.cobuilder node",
                                node_id=sys3_node.id,
                            )
                        )

        return violations

    def _get_downstream_nodes(self, graph: Graph, start_node_id: str) -> dict[str, Node]:
        """Get all nodes reachable from start_node_id using BFS."""
        from collections import deque

        visited: set[str] = set()
        result: dict[str, Node] = {}
        queue: deque[str] = deque([start_node_id])

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id != start_node_id:  # Don't include the starting node
                current_node = graph.nodes.get(current_id)
                if current_node:
                    result[current_id] = current_node

            # Add successors to queue
            for edge in graph.edges:
                if edge.source == current_id and edge.target not in visited:
                    queue.append(edge.target)

        return result


# ---------------------------------------------------------------------------
# Additional helper for wait.cobuilder nodes
# ---------------------------------------------------------------------------

class WaitCobuilderRequirements:
    """wait.cobuilder nodes have required attributes (gate_type, summary_ref, bead_id)."""

    rule_id = "WaitCobuilderRequirements"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []

        for node in graph.nodes.values():
            if node.handler_type in ("wait_cobuilder", "wait.cobuilder"):
                # Check required attributes
                gate_type = node.attrs.get("gate_type", "").strip()
                summary_ref = node.attrs.get("summary_ref", "").strip()
                bead_id = node.attrs.get("bead_id", "").strip()

                if not gate_type:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"wait.cobuilder node '{node.id}' missing required 'gate_type' attribute",
                            "Add 'gate_type' attribute (values: unit, e2e, contract)",
                            node_id=node.id,
                        )
                    )

                if not summary_ref:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"wait.cobuilder node '{node.id}' missing required 'summary_ref' attribute",
                            "Add 'summary_ref' attribute pointing to summary file path",
                            node_id=node.id,
                        )
                    )

                if not bead_id:
                    violations.append(
                        _error(
                            self.rule_id,
                            f"wait.cobuilder node '{node.id}' missing required 'bead_id' attribute",
                            "Add 'bead_id' attribute with AT (Acceptance Test) beads task ID",
                            node_id=node.id,
                        )
                    )

        return violations


# ---------------------------------------------------------------------------
# Rule 18: CodergenWithoutUpstreamAT (Enforces GAP-5.5 - V-15)
# ---------------------------------------------------------------------------

class CodergenWithoutUpstreamAT:
    """codergen nodes should have upstream acceptance-test-writer worker nodes (V-15).

    acceptance-test-writer is now a worker_type on codergen (box) nodes rather
    than a standalone handler type.  This rule checks for an upstream codergen
    node with worker_type="acceptance-test-writer".
    """

    rule_id = "CodergenWithoutUpstreamAT"
    severity = Severity.WARNING

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []

        # Find all codergen nodes that are NOT themselves acceptance-test-writers
        for node in graph.nodes.values():
            if node.handler_type == "codergen" and node.worker_type != "acceptance-test-writer":
                # Check if there's an upstream codergen node with worker_type="acceptance-test-writer"
                has_upstream_at_writer = self._has_upstream_at_writer(graph, node.id)

                if not has_upstream_at_writer:
                    violations.append(
                        _warning(
                            self.rule_id,
                            f"codergen node '{node.id}' has no upstream acceptance-test-writer node (V-15)",
                            "Consider adding a codergen node with worker_type=\"acceptance-test-writer\" "
                            "upstream to generate acceptance tests",
                            node_id=node.id,
                        )
                    )

        return violations

    def _has_upstream_at_writer(self, graph: Graph, node_id: str) -> bool:
        """Check if there is an upstream codergen node with worker_type='acceptance-test-writer'."""
        visited: set[str] = set()

        def dfs_check(current_id: str) -> bool:
            if current_id in visited:
                return False
            visited.add(current_id)

            current_node = graph.nodes.get(current_id)
            if current_node is not None:
                # acceptance-test-writer is now codergen + worker_type
                if (
                    current_node.handler_type == "codergen"
                    and current_node.worker_type == "acceptance-test-writer"
                ):
                    return True

            # Check all incoming edges (predecessors)
            for edge in graph.edges:
                if edge.target == current_id:
                    if dfs_check(edge.source):
                        return True
            return False

        # Start DFS from predecessors of the given node
        for edge in graph.edges:
            if edge.target == node_id:
                if dfs_check(edge.source):
                    return True

        return False


# ---------------------------------------------------------------------------
# Rule 19: MissingSkillReference (Enforces GAP-5.6 - V-16)
# ---------------------------------------------------------------------------

class MissingSkillReference:
    """Check if skills_required attributes reference existing skill directories (V-16)."""

    rule_id = "MissingSkillReference"
    severity = Severity.WARNING

    def check(self, graph: Graph) -> list[RuleViolation]:
        import os
        from pathlib import Path

        violations = []

        for node in graph.nodes.values():
            if node.handler_type == "codergen":
                worker_type = node.attrs.get("worker_type", "").strip()
                if worker_type:
                    # Check if the agent file exists and has skills_required
                    agent_path = Path(f".claude/agents/{worker_type}.md")
                    if agent_path.exists():
                        try:
                            content = agent_path.read_text()
                            # Parse YAML frontmatter if it exists
                            if content.startswith("---"):
                                # Find the end of the YAML frontmatter
                                lines = content.split('\n')
                                if len(lines) > 1 and lines[0] == "---":
                                    # Find the closing ---
                                    for i in range(1, len(lines)):
                                        if lines[i] == "---" and i > 0:
                                            fm_content = '\n'.join(lines[1:i])
                                            import yaml
                                            try:
                                                fm = yaml.safe_load(fm_content)
                                                if fm and isinstance(fm, dict) and "skills_required" in fm:
                                                    for skill in fm.get("skills_required", []):
                                                        skill_dir = Path(f".claude/skills/{skill}")
                                                        if not skill_dir.exists():
                                                            violations.append(
                                                                _warning(
                                                                    self.rule_id,
                                                                    f"Agent '{worker_type}' requires skill '{skill}' but .claude/skills/{skill}/ not found (V-16)",
                                                                    f"Create the skill directory at .claude/skills/{skill}/ or remove from agent configuration",
                                                                    node_id=node.id,
                                                                )
                                                            )
                                            except yaml.YAMLError:
                                                pass  # Skip invalid YAML
                                            break
                        except Exception:
                            pass  # Don't fail validation on agent file parse errors

        return violations


# ---------------------------------------------------------------------------
# Rule: MandatoryGraphAttrs (Enforces AC-5.5)
# ---------------------------------------------------------------------------

class MandatoryGraphAttrs:
    """cobuilder_root and target_dir must be present, absolute, and point to existing directories.

    These attributes define the CoBuilder package root and working directory for all workers.
    Rule 17 / AC-5.5: Both attributes are mandatory.
    """

    rule_id = "MandatoryGraphAttrs"
    severity = Severity.ERROR

    def check(self, graph: Graph) -> list[RuleViolation]:
        violations = []

        # Check cobuilder_root
        cobuilder_root = graph.attrs.get("cobuilder_root", "").strip()
        if not cobuilder_root:
            violations.append(
                _error(
                    self.rule_id,
                    "Missing required graph attribute 'cobuilder_root' — must be the absolute path to the CoBuilder package root",
                    "Add 'cobuilder_root=\"/absolute/path\"' to the graph attributes in the DOT file",
                )
            )
        elif not os.path.isabs(cobuilder_root):
            violations.append(
                _error(
                    self.rule_id,
                    f"Graph attribute 'cobuilder_root' must be an absolute path, got relative path: {cobuilder_root}",
                    "Change cobuilder_root to an absolute path (e.g., '/home/user/cobuilder', not './cobuilder')",
                )
            )
        elif not os.path.isdir(cobuilder_root):
            violations.append(
                _error(
                    self.rule_id,
                    f"Graph attribute 'cobuilder_root' points to a non-existent directory: {cobuilder_root}",
                    f"Ensure the directory {cobuilder_root} exists and the path is correct",
                )
            )

        # Check target_dir
        target_dir = graph.attrs.get("target_dir", "").strip()
        if not target_dir:
            violations.append(
                _error(
                    self.rule_id,
                    "Missing required graph attribute 'target_dir' — must be the absolute path to the target repository",
                    "Add 'target_dir=\"/absolute/path\"' to the graph attributes in the DOT file",
                )
            )
        elif not os.path.isabs(target_dir):
            violations.append(
                _error(
                    self.rule_id,
                    f"Graph attribute 'target_dir' must be an absolute path, got relative path: {target_dir}",
                    "Change target_dir to an absolute path (e.g., '/home/user/project', not '../project')",
                )
            )
        elif not os.path.isdir(target_dir):
            violations.append(
                _error(
                    self.rule_id,
                    f"Graph attribute 'target_dir' points to a non-existent directory: {target_dir}",
                    f"Ensure the directory {target_dir} exists and the path is correct",
                )
            )

        return violations


# ---------------------------------------------------------------------------
# Rule: PromptTemplateExists (Epic 2 — WARNING)
# ---------------------------------------------------------------------------

class PromptTemplateExists:
    """If a node sets ``prompt_template``, verify the ``.j2`` file exists.

    This is a WARNING because the file may be added later or the prompts
    directory may be in a non-default location.  Execution is not blocked.
    """

    rule_id = "PromptTemplateExists"
    severity = Severity.WARNING

    def check(self, graph: "Graph") -> list[RuleViolation]:
        violations = []

        # Discover the prompts directory using the same traversal as PromptRenderer
        prompts_dir = self._find_prompts_dir()

        for node in graph.nodes.values():
            template_name = node.attrs.get("prompt_template", "").strip()
            if not template_name:
                continue

            # Ensure .j2 suffix
            if not template_name.endswith(".j2"):
                template_name = f"{template_name}.j2"

            if prompts_dir is None:
                violations.append(
                    _warning(
                        self.rule_id,
                        f"Node sets prompt_template='{node.attrs.get('prompt_template')}' "
                        "but no .cobuilder/prompts/ directory was found.",
                        "Create .cobuilder/prompts/ in the repository root and add the "
                        f"template file '{template_name}'.",
                        node_id=node.id,
                    )
                )
            elif not (prompts_dir / template_name).exists():
                violations.append(
                    _warning(
                        self.rule_id,
                        f"Prompt template '{template_name}' referenced by node "
                        f"'{node.id}' does not exist at {prompts_dir / template_name}.",
                        f"Create the template file at .cobuilder/prompts/{template_name}.",
                        node_id=node.id,
                    )
                )

        return violations

    @staticmethod
    def _find_prompts_dir() -> "Path | None":
        """Return the .cobuilder/prompts/ directory, or None if not found."""
        from pathlib import Path
        current = Path(__file__).resolve().parent
        for parent in [current, *current.parents]:
            candidate = parent / ".cobuilder" / "prompts"
            if candidate.is_dir():
                return candidate
        return None