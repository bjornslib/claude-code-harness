"""BaselineManager -- save and load RPGGraph baselines.

Provides persistence for RPGGraph baselines produced by
:class:`~zerorepo.serena.walker.CodebaseWalker` (or any other source).
Baselines are stored as JSON files using RPGGraph's native serialization,
with added metadata for provenance tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cobuilder.repomap.models.edge import RPGEdge
from cobuilder.repomap.models.graph import RPGGraph
from cobuilder.repomap.models.node import RPGNode

logger = logging.getLogger(__name__)


class BaselineManager:
    """Save and load RPGGraph baselines.

    The default storage path is ``.zerorepo/baseline.json`` relative to
    the project root, but callers may override via explicit *output_path*.

    Example::

        manager = BaselineManager()
        path = manager.save(graph, output_path=Path("baseline.json"), project_root=Path("."))
        loaded = manager.load(path)
    """

    DEFAULT_FILENAME = "baseline.json"
    DEFAULT_DIR = ".zerorepo"

    @classmethod
    def default_path(cls, project_root: Path) -> Path:
        """Return the default baseline path for a project root.

        Args:
            project_root: The project root directory.

        Returns:
            ``project_root / .zerorepo / baseline.json``
        """
        return project_root / cls.DEFAULT_DIR / cls.DEFAULT_FILENAME

    def save(
        self,
        graph: RPGGraph,
        output_path: Path,
        project_root: Path,
        *,
        extra_metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save an RPGGraph as a baseline JSON file with metadata.

        Adds provenance metadata (generation timestamp, project root,
        baseline version) to the graph before serialization.

        Args:
            graph: The RPGGraph to persist.
            output_path: Where to write the JSON file.
            project_root: The project root directory (stored in metadata).
            extra_metadata: Optional additional key-value pairs to include
                in the graph metadata.

        Returns:
            The resolved output path.
        """
        # Set baseline metadata
        graph.metadata["baseline_generated_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        graph.metadata["project_root"] = str(project_root.resolve())
        graph.metadata["baseline_version"] = "1.0"

        if extra_metadata:
            graph.metadata.update(extra_metadata)

        # Ensure parent directory exists
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize via RPGGraph's native to_json
        output_path.write_text(graph.to_json(indent=2), encoding="utf-8")

        logger.info(
            "Saved baseline (%d nodes, %d edges) to %s",
            graph.node_count,
            graph.edge_count,
            output_path,
        )
        return output_path

    def load(self, baseline_path: Path) -> RPGGraph:
        """Load a baseline RPGGraph from a JSON file.

        Args:
            baseline_path: Path to the baseline JSON file.

        Returns:
            The deserialized RPGGraph with baseline metadata intact.

        Raises:
            FileNotFoundError: If the baseline file does not exist.
            ValueError: If the JSON is invalid or cannot be parsed as RPGGraph.
        """
        baseline_path = baseline_path.resolve()

        if not baseline_path.exists():
            raise FileNotFoundError(
                f"Baseline file not found: {baseline_path}"
            )

        json_str = baseline_path.read_text(encoding="utf-8")

        try:
            graph = RPGGraph.from_json(json_str)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse baseline from {baseline_path}: {exc}"
            ) from exc

        logger.info(
            "Loaded baseline (%d nodes, %d edges) from %s",
            graph.node_count,
            graph.edge_count,
            baseline_path,
        )
        return graph

    def merge_nodes(
        self,
        existing: RPGGraph,
        scoped: RPGGraph,
    ) -> RPGGraph:
        """Merge scoped graph nodes into an existing baseline graph.

        Nodes in ``scoped`` replace nodes with the same ID in ``existing``.
        Nodes in ``scoped`` with IDs not present in ``existing`` are appended.
        Nodes in ``existing`` with IDs not present in ``scoped`` are kept
        unchanged.

        Args:
            existing: The full baseline graph to merge into.
            scoped: The restricted graph produced by
                :meth:`~CodebaseWalker.walk_paths`.

        Returns:
            A new RPGGraph containing the merged result.
        """
        merged = RPGGraph()

        # Start with all nodes from existing, then overwrite/extend with scoped
        merged_nodes: dict = dict(existing.nodes)
        merged_nodes.update(scoped.nodes)

        for node in merged_nodes.values():
            merged.nodes[node.id] = node

        # Start with existing edges, then add scoped edges (duplicates are harmless
        # since RPGGraph uses UUID keys and add_edge overwrites by ID)
        for edge in existing.edges.values():
            merged.edges[edge.id] = edge
        for edge in scoped.edges.values():
            merged.edges[edge.id] = edge

        # Preserve existing metadata, update timestamp
        merged.metadata.update(existing.metadata)
        merged.metadata["baseline_generated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        logger.info(
            "merge_nodes: existing=%d nodes → merged=%d nodes (%d from scoped)",
            existing.node_count,
            merged.node_count,
            scoped.node_count,
        )
        return merged

    def scoped_save(
        self,
        repo_name: str,
        scoped: RPGGraph,
        *,
        project_root: Path,
        repomap_dir: Path,
    ) -> dict[str, Any]:
        """Load existing baseline, merge scoped nodes, rotate, and save.

        Steps:
        1. Load ``baseline.json`` → RPGGraph (empty if file not found).
        2. ``merge_nodes(existing, scoped)`` → merged graph.
        3. Rotate: ``baseline.json`` → ``baseline.prev.json``.
        4. Save merged → ``baseline.json``.
        5. Update manifest YAML metadata.
        6. Return updated config entry dict.

        Args:
            repo_name: Registered repository name.
            scoped: The restricted RPGGraph produced by a scoped walk.
            project_root: The project root for metadata storage.
            repomap_dir: The ``.repomap/`` directory path.

        Returns:
            A dict with keys ``baseline_hash``, ``node_count``,
            ``last_synced``, and ``duration_seconds``.
        """
        import hashlib
        import time

        baseline_dir = repomap_dir / "baselines" / repo_name
        baseline_dir.mkdir(parents=True, exist_ok=True)
        current = baseline_dir / "baseline.json"
        prev = baseline_dir / "baseline.prev.json"

        # Step 1: Load existing baseline
        if current.exists():
            try:
                existing = self.load(current)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(
                    "scoped_save: could not load existing baseline (%s); "
                    "starting from empty graph.",
                    exc,
                )
                existing = RPGGraph()
        else:
            existing = RPGGraph()

        # Step 2: Merge
        start = time.monotonic()
        merged = self.merge_nodes(existing, scoped)
        elapsed = time.monotonic() - start

        # Step 3: Rotate
        if current.exists():
            current.rename(prev)
            logger.debug("scoped_save: rotated baseline → baseline.prev.json")

        # Step 4: Save merged
        self.save(
            merged,
            output_path=current,
            project_root=project_root,
            extra_metadata={"repo_name": repo_name, "scoped_merge": True},
        )

        # Step 5: Compute hash and counts
        raw = merged.to_json(indent=0).encode()
        baseline_hash = "sha256:" + hashlib.sha256(raw).hexdigest()[:16]

        from cobuilder.repomap.models.enums import NodeLevel as _NL
        node_count = len(merged.nodes)
        file_count = sum(
            1 for n in merged.nodes.values() if n.level == _NL.COMPONENT
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            "scoped_save: repo=%s nodes=%d files=%d hash=%s",
            repo_name,
            node_count,
            file_count,
            baseline_hash,
        )

        return {
            "baseline_hash": baseline_hash,
            "node_count": node_count,
            "file_count": file_count,
            "last_synced": now_iso,
            "duration_seconds": elapsed,
        }
