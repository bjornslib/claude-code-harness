"""Unit tests for bridge.scoped_refresh() — F4.3.

Tests cover:
- scoped_refresh updates last_synced in config.yaml
- scoped_refresh debounce (second call within 30s returns {"skipped": True})
- scoped_refresh with unregistered repo raises KeyError
- scoped_refresh returns expected result dict keys
- scoped_refresh on a single real Python file (1 component in graph)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

import cobuilder.bridge as bridge_module
from cobuilder.bridge import init_repo, scoped_refresh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_repo(
    tmp_path: Path,
    repo_name: str = "testrepo",
    *,
    write_python_file: bool = True,
) -> tuple[Path, Path]:
    """Register a repo in .repomap and optionally create a Python source file.

    Returns (project_root, target_dir).
    """
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    target_dir = tmp_path / "repo"
    target_dir.mkdir()

    if write_python_file:
        pkg = target_dir / "mylib"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My library."""\n')
        (pkg / "sample.py").write_text(
            textwrap.dedent("""\
            \"\"\"Sample module.\"\"\"


            def sample_fn() -> str:
                \"\"\"Return sample.\"\"\"
                return "sample"
            """)
        )

    init_repo(repo_name, target_dir=target_dir, project_root=project_root)
    return project_root, target_dir


def _load_config(project_root: Path) -> dict:
    config_path = project_root / ".repomap" / "config.yaml"
    with config_path.open() as fh:
        return yaml.safe_load(fh) or {}


def _get_last_synced(project_root: Path, repo_name: str) -> str | None:
    config = _load_config(project_root)
    for entry in config.get("repos", []):
        if entry.get("name") == repo_name:
            return entry.get("last_synced")
    return None


# ---------------------------------------------------------------------------
# TestScopedRefresh
# ---------------------------------------------------------------------------


class TestScopedRefresh:
    """Tests for bridge.scoped_refresh()."""

    def setup_method(self) -> None:
        """Reset the module-level debounce state before each test."""
        bridge_module._last_refresh_times.clear()

    # ------------------------------------------------------------------
    # Basic correctness
    # ------------------------------------------------------------------

    def test_scoped_refresh_updates_last_synced(self, tmp_path: Path) -> None:
        """scoped_refresh updates last_synced in config.yaml."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        # last_synced should be None before first refresh
        assert _get_last_synced(project_root, "testrepo") is None

        scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        last_synced = _get_last_synced(project_root, "testrepo")
        assert last_synced is not None, "last_synced should be set after refresh"
        assert "T" in last_synced, "last_synced should be an ISO timestamp"

    def test_scoped_refresh_returns_expected_keys(self, tmp_path: Path) -> None:
        """scoped_refresh returns dict with required keys."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        result = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        assert "refreshed_nodes" in result
        assert "duration_seconds" in result
        assert "baseline_hash" in result
        assert "skipped" in result

    def test_scoped_refresh_skipped_false_on_first_call(self, tmp_path: Path) -> None:
        """First call within a repo is never skipped."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        result = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        assert result["skipped"] is False

    def test_scoped_refresh_refreshed_nodes_positive(self, tmp_path: Path) -> None:
        """refreshed_nodes should be > 0 when real files are scoped."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        result = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        assert result["refreshed_nodes"] > 0, (
            "Scanning a real Python file should produce at least 1 node"
        )

    def test_scoped_refresh_baseline_hash_set(self, tmp_path: Path) -> None:
        """baseline_hash should be a non-empty sha256 string after refresh."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        result = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        assert result["baseline_hash"].startswith("sha256:"), (
            f"Expected sha256: prefix, got: {result['baseline_hash']}"
        )

    def test_scoped_refresh_creates_baseline_file(self, tmp_path: Path) -> None:
        """scoped_refresh creates baseline.json under .repomap/baselines/<name>/."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        baseline_path = (
            project_root / ".repomap" / "baselines" / "testrepo" / "baseline.json"
        )
        assert baseline_path.exists(), "baseline.json should be written after refresh"

    # ------------------------------------------------------------------
    # Debounce
    # ------------------------------------------------------------------

    def test_scoped_refresh_debounce_second_call_skipped(self, tmp_path: Path) -> None:
        """Second call within the 30s debounce window returns skipped=True."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        # First call: should execute
        first = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )
        assert first["skipped"] is False

        # Second call immediately after: should be debounced
        second = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )
        assert second["skipped"] is True, (
            "Second call within 30s window should be debounced"
        )

    def test_scoped_refresh_debounce_returns_zero_nodes(self, tmp_path: Path) -> None:
        """Debounced call returns refreshed_nodes=0."""
        project_root, target_dir = _setup_repo(tmp_path)
        sample_py = target_dir / "mylib" / "sample.py"

        scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        result = scoped_refresh(
            "testrepo",
            scope=[str(sample_py)],
            project_root=project_root,
        )

        assert result["refreshed_nodes"] == 0
        assert result["duration_seconds"] == 0.0
        assert result["baseline_hash"] == ""

    def test_scoped_refresh_different_repos_not_debounced(self, tmp_path: Path) -> None:
        """Debounce is per-repo: different repo names are independent."""
        (tmp_path / "a").mkdir(parents=True, exist_ok=True)
        (tmp_path / "b").mkdir(parents=True, exist_ok=True)
        project_root_a, target_dir_a = _setup_repo(tmp_path / "a", "repo_a")
        project_root_b, target_dir_b = _setup_repo(tmp_path / "b", "repo_b")

        sample_a = target_dir_a / "mylib" / "sample.py"
        sample_b = target_dir_b / "mylib" / "sample.py"

        first_a = scoped_refresh(
            "repo_a", scope=[str(sample_a)], project_root=project_root_a
        )
        # repo_b has a DIFFERENT key in _last_refresh_times
        first_b = scoped_refresh(
            "repo_b", scope=[str(sample_b)], project_root=project_root_b
        )

        assert first_a["skipped"] is False
        assert first_b["skipped"] is False

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_scoped_refresh_unregistered_repo_raises_key_error(
        self, tmp_path: Path
    ) -> None:
        """scoped_refresh with unregistered name raises KeyError."""
        project_root = tmp_path / "workspace"
        project_root.mkdir()
        (project_root / ".repomap").mkdir()
        # Write an empty config
        import yaml as _yaml

        config_path = project_root / ".repomap" / "config.yaml"
        config_path.write_text(_yaml.dump({"version": "1.0", "repos": []}))

        with pytest.raises(KeyError, match="not registered"):
            scoped_refresh(
                "ghost_repo",
                scope=["/some/file.py"],
                project_root=project_root,
            )

    def test_scoped_refresh_empty_scope_still_works(self, tmp_path: Path) -> None:
        """scoped_refresh with empty scope list completes without error."""
        project_root, target_dir = _setup_repo(tmp_path)

        # Empty scope → walk_paths([]) → empty graph → merge into empty existing
        result = scoped_refresh(
            "testrepo",
            scope=[],
            project_root=project_root,
        )

        # Should not raise; skipped=False since it's the first call
        assert result["skipped"] is False
        assert result["refreshed_nodes"] == 0
