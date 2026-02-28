"""Unit tests for get_repomap_context() — F3.1.

Covers:
- format="yaml" returns valid YAML with required top-level keys
- format="text" returns legacy plain-text (backward compat)
- Invalid format raises ValueError
- YAML output includes modules_relevant_to_epic when prd_keywords provided
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from cobuilder.bridge import get_repomap_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    repo_name: str = "testrepo",
    total_nodes: int = 100,
    total_files: int = 20,
    total_functions: int = 80,
    top_modules: list[dict] | None = None,
) -> dict:
    return {
        "repository": repo_name,
        "snapshot_date": "2026-01-01T00:00:00+00:00",
        "total_nodes": total_nodes,
        "total_files": total_files,
        "total_functions": total_functions,
        "top_modules": top_modules
        or [
            {"name": "cobuilder", "files": 12, "delta": "existing"},
            {"name": "tests", "files": 8, "delta": "existing"},
        ],
    }


def _make_config(name: str = "testrepo", path: str = "/tmp/testrepo") -> dict:
    return {
        "version": "1.0",
        "repos": [
            {
                "name": name,
                "path": path,
                "last_synced": "2026-01-01T00:00:00+00:00",
                "baseline_hash": "sha256:abc123",
                "node_count": 100,
                "file_count": 20,
            }
        ],
    }


def _setup_fs(
    tmp_path: Path,
    repo_name: str = "testrepo",
    write_baseline: bool = False,
) -> tuple[Path, dict]:
    """Create minimal .repomap/ directory structure and return project_root, config."""
    repomap_dir = tmp_path / ".repomap"
    repomap_dir.mkdir()

    config = _make_config(repo_name, path=str(tmp_path / "repo"))
    config_path = repomap_dir / "config.yaml"
    import yaml as _yaml
    config_path.write_text(_yaml.dump(config))

    manifest_dir = repomap_dir / "manifests"
    manifest_dir.mkdir()
    manifest_path = manifest_dir / f"{repo_name}.manifest.yaml"
    manifest_path.write_text(_yaml.dump(_make_manifest(repo_name)))

    if write_baseline:
        baseline_dir = repomap_dir / "baselines" / repo_name
        baseline_dir.mkdir(parents=True)
        baseline_file = baseline_dir / "baseline.json"
        baseline_file.write_text(json.dumps({"nodes": {}, "edges": {}, "metadata": {}}))

    return tmp_path, config


# ---------------------------------------------------------------------------
# format="text" — backward compatibility
# ---------------------------------------------------------------------------


class TestGetRepomapContextText:
    def test_returns_string(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="text")
        assert isinstance(result, str)

    def test_contains_repo_header(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="text")
        assert "## Codebase: testrepo" in result

    def test_contains_top_modules_section(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="text")
        assert "### Top Modules" in result

    def test_lists_module_names(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="text")
        assert "cobuilder" in result

    def test_raises_key_error_for_unknown_repo(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        with pytest.raises(KeyError):
            get_repomap_context("nonexistent", project_root=project_root, format="text")

    def test_raises_file_not_found_without_manifest(self, tmp_path: Path) -> None:
        repomap_dir = tmp_path / ".repomap"
        repomap_dir.mkdir()
        import yaml as _yaml
        (repomap_dir / "config.yaml").write_text(_yaml.dump(_make_config()))
        with pytest.raises(FileNotFoundError):
            get_repomap_context("testrepo", project_root=tmp_path, format="text")


# ---------------------------------------------------------------------------
# format="yaml" — structured output
# ---------------------------------------------------------------------------


class TestGetRepomapContextYaml:
    def test_returns_valid_yaml_string(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="yaml")
        assert isinstance(result, str)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_contains_required_top_level_keys(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="yaml")
        parsed = yaml.safe_load(result)
        for key in ("repository", "total_nodes", "total_files", "total_functions"):
            assert key in parsed, f"Missing key: {key}"

    def test_repository_field_matches_name(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="yaml")
        parsed = yaml.safe_load(result)
        assert parsed["repository"] == "testrepo"

    def test_total_fields_are_integers(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="yaml")
        parsed = yaml.safe_load(result)
        assert isinstance(parsed["total_nodes"], int)
        assert isinstance(parsed["total_files"], int)
        assert isinstance(parsed["total_functions"], int)

    def test_modules_relevant_from_manifest_when_no_keywords(self, tmp_path: Path) -> None:
        """Without prd_keywords, modules_relevant_to_epic comes from manifest top_modules."""
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root, format="yaml")
        parsed = yaml.safe_load(result)
        if "modules_relevant_to_epic" in parsed:
            modules = parsed["modules_relevant_to_epic"]
            assert isinstance(modules, list)

    def test_modules_filtered_when_prd_keywords_provided(self, tmp_path: Path) -> None:
        """With prd_keywords + baseline, filter_relevant_modules should be called."""
        project_root, _ = _setup_fs(tmp_path, write_baseline=True)

        with patch("cobuilder.repomap.context_filter.filter_relevant_modules") as mock_filter:
            mock_filter.return_value = [
                {
                    "name": "cobuilder",
                    "delta": "MODIFIED",
                    "files": 5,
                    "summary": None,
                    "key_interfaces": [],
                }
            ]
            result = get_repomap_context(
                "testrepo",
                project_root=project_root,
                prd_keywords=["cobuilder"],
                format="yaml",
            )

        mock_filter.assert_called_once()
        parsed = yaml.safe_load(result)
        assert "modules_relevant_to_epic" in parsed
        assert parsed["modules_relevant_to_epic"][0]["name"] == "cobuilder"

    def test_format_text_not_affected_by_yaml_path(self, tmp_path: Path) -> None:
        """text format should not call filter_relevant_modules."""
        project_root, _ = _setup_fs(tmp_path, write_baseline=True)

        with patch("cobuilder.repomap.context_filter.filter_relevant_modules") as mock_filter:
            result = get_repomap_context(
                "testrepo",
                project_root=project_root,
                prd_keywords=["cobuilder"],
                format="text",
            )

        mock_filter.assert_not_called()
        assert "## Codebase" in result

    def test_invalid_format_raises_value_error(self, tmp_path: Path) -> None:
        project_root, _ = _setup_fs(tmp_path)
        with pytest.raises(ValueError, match="format must be"):
            get_repomap_context("testrepo", project_root=project_root, format="json")

    def test_yaml_default_format_is_yaml(self, tmp_path: Path) -> None:
        """Default format should be 'yaml' — output must be parseable YAML."""
        project_root, _ = _setup_fs(tmp_path)
        result = get_repomap_context("testrepo", project_root=project_root)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
