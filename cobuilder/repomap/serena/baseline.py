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

from cobuilder.repomap.models.graph import RPGGraph

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
