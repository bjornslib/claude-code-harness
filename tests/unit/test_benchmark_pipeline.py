"""Tests for the end-to-end benchmark construction pipeline.

Validates the BenchmarkPipeline orchestration: harvesting, filtering,
categorization, sampling, and JSON serialisation.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel

# Handle import path for scripts/benchmark
try:
    from scripts.benchmark.build_repocraft import (
        BenchmarkPipeline,
        PipelineConfig,
        PipelineResult,
        run_multiple,
    )
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from benchmark.build_repocraft import (
        BenchmarkPipeline,
        PipelineConfig,
        PipelineResult,
        run_multiple,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo with varied test files."""
    # tests/test_basic.py - 3 simple tests (will be filtered as trivial)
    basic = tmp_path / "tests" / "test_basic.py"
    basic.parent.mkdir(parents=True)
    basic.write_text(textwrap.dedent("""\
        def test_one():
            assert 1 == 1

        def test_two():
            assert 2 == 2

        def test_three():
            assert 3 == 3
    """))

    # tests/math/test_operations.py - longer tests that survive filtering
    math_dir = tmp_path / "tests" / "math"
    math_dir.mkdir(parents=True)
    ops = math_dir / "test_operations.py"
    lines_add = ["def test_addition():"]
    for i in range(15):
        lines_add.append(f"    x{i} = {i}")
    lines_add.append("    result = sum(range(15))")
    lines_add.append("    assert result == 105")
    lines_add.append("")

    lines_sub = ["def test_subtraction():"]
    for i in range(15):
        lines_sub.append(f"    y{i} = {i}")
    lines_sub.append("    result = 105 - sum(range(15))")
    lines_sub.append("    assert result == 0")
    lines_sub.append("")

    ops.write_text("\n".join(lines_add + lines_sub))

    # tests/io/test_network.py - flaky test
    io_dir = tmp_path / "tests" / "io"
    io_dir.mkdir(parents=True)
    net = io_dir / "test_network.py"
    lines_net = ["import requests", "", "def test_fetch():"]
    for i in range(15):
        lines_net.append(f"    step{i} = {i}")
    lines_net.append("    r = requests.get('http://example.com')")
    lines_net.append("    assert r.status_code == 200")
    net.write_text("\n".join(lines_net))

    # tests/skip/test_skipped.py - skipped test
    skip_dir = tmp_path / "tests" / "skip"
    skip_dir.mkdir(parents=True)
    skipped = skip_dir / "test_skipped.py"
    lines_skip = ["@pytest.mark.skip", "def test_broken():"]
    for i in range(15):
        lines_skip.append(f"    v{i} = {i}")
    lines_skip.append("    assert True")
    skipped.write_text("\n".join(lines_skip))

    # tests/utils/test_helpers.py - good long test
    utils_dir = tmp_path / "tests" / "utils"
    utils_dir.mkdir(parents=True)
    helpers = utils_dir / "test_helpers.py"
    lines_help = ["def test_string_manipulation():"]
    for i in range(20):
        lines_help.append(f'    s{i} = "word{i}"')
    lines_help.append('    combined = " ".join([s0, s1, s2])')
    lines_help.append("    assert len(combined) > 0")
    helpers.write_text("\n".join(lines_help))

    return tmp_path


@pytest.fixture()
def large_repo(tmp_path: Path) -> Path:
    """Create a larger repo for sampling tests."""
    for cat_idx in range(5):
        cat_dir = tmp_path / "tests" / f"category{cat_idx}"
        cat_dir.mkdir(parents=True)
        for file_idx in range(3):
            test_file = cat_dir / f"test_mod{file_idx}.py"
            funcs = []
            for func_idx in range(4):
                lines = [f"def test_func_{cat_idx}_{file_idx}_{func_idx}():"]
                for j in range(15):
                    lines.append(f"    x{j} = {j}")
                lines.append(f"    assert x0 == 0")
                lines.append("")
                funcs.extend(lines)
            test_file.write_text("\n".join(funcs))
    return tmp_path


# ---------------------------------------------------------------------------
# PipelineConfig tests
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    """Tests for pipeline configuration."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        cfg = PipelineConfig()
        assert cfg.sample_size == 200
        assert cfg.seed == 42
        assert cfg.min_loc == 10
        assert cfg.require_assertions is True
        assert cfg.filter_flaky is True
        assert cfg.filter_skipped is True

    def test_custom_config(self) -> None:
        """Custom config values are stored."""
        cfg = PipelineConfig(
            project_name="myproj",
            sample_size=50,
            seed=99,
            min_loc=5,
            require_assertions=False,
        )
        assert cfg.project_name == "myproj"
        assert cfg.sample_size == 50
        assert cfg.seed == 99
        assert cfg.min_loc == 5
        assert cfg.require_assertions is False


# ---------------------------------------------------------------------------
# BenchmarkPipeline tests
# ---------------------------------------------------------------------------


class TestBenchmarkPipeline:
    """Tests for the BenchmarkPipeline orchestrator."""

    def test_run_harvests_tests(self, mini_repo: Path) -> None:
        """Pipeline harvests tests from the repo."""
        config = PipelineConfig(project_name="test", min_loc=1, filter_flaky=False, filter_skipped=False, require_assertions=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        # 3 basic + 2 math + 1 network + 1 skipped + 1 utils = 8
        assert result.harvested_count == 8

    def test_run_filters_trivial(self, mini_repo: Path) -> None:
        """Pipeline filters trivial (short) tests."""
        config = PipelineConfig(project_name="test", min_loc=10, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        # The 3 basic tests (< 10 LOC) should be filtered out
        assert result.filtered_count < result.harvested_count

    def test_run_filters_flaky(self, mini_repo: Path) -> None:
        """Pipeline filters flaky tests with network calls."""
        config = PipelineConfig(project_name="test", min_loc=1, require_assertions=False, filter_flaky=True, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        # The network test should be filtered
        task_descriptions = [t.description for t in result.tasks]
        assert not any("fetch" in d.lower() for d in task_descriptions)

    def test_run_filters_skipped(self, mini_repo: Path) -> None:
        """Pipeline filters skipped tests."""
        config = PipelineConfig(project_name="test", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=True)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        task_subcats = [t.subcategory for t in result.tasks]
        assert "broken" not in task_subcats

    def test_run_builds_taxonomy(self, mini_repo: Path) -> None:
        """Pipeline builds a taxonomy from filtered tasks."""
        config = PipelineConfig(project_name="test", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        assert result.taxonomy is not None
        assert result.taxonomy.total_tasks > 0
        assert result.taxonomy.total_categories > 0

    def test_run_with_sampling(self, large_repo: Path) -> None:
        """Pipeline applies stratified sampling when sample_size < total."""
        config = PipelineConfig(project_name="large", sample_size=10, seed=42, min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(large_repo)

        # Should have more harvested than sampled
        assert result.harvested_count > 10
        assert result.sampled_count == 10

    def test_run_no_sampling_when_disabled(self, large_repo: Path) -> None:
        """When sample_size=0, no sampling occurs."""
        config = PipelineConfig(project_name="large", sample_size=0, min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(large_repo)

        assert result.sampled_count == result.filtered_count

    def test_run_no_sampling_when_below_threshold(self, mini_repo: Path) -> None:
        """When filtered tasks < sample_size, keep all."""
        config = PipelineConfig(project_name="test", sample_size=1000, min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        assert result.sampled_count == result.filtered_count

    def test_run_empty_repo(self, tmp_path: Path) -> None:
        """Pipeline handles empty repository gracefully."""
        config = PipelineConfig(project_name="empty")
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(tmp_path)

        assert result.harvested_count == 0
        assert result.filtered_count == 0
        assert result.sampled_count == 0
        assert result.tasks == []

    def test_result_tasks_are_benchmark_tasks(self, mini_repo: Path) -> None:
        """All returned tasks are proper BenchmarkTask instances."""
        config = PipelineConfig(project_name="test", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        for task in result.tasks:
            assert isinstance(task, BenchmarkTask)
            assert task.project == "test"
            assert len(task.id) > 0
            assert len(task.test_code) > 0


# ---------------------------------------------------------------------------
# save_tasks tests
# ---------------------------------------------------------------------------


class TestSaveTasks:
    """Tests for JSON serialisation of pipeline results."""

    def test_save_creates_file(self, mini_repo: Path, tmp_path: Path) -> None:
        """save_tasks creates a JSON file in the output directory."""
        config = PipelineConfig(project_name="myproj", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        output_dir = tmp_path / "output"
        output_path = pipeline.save_tasks(result, output_dir)

        assert output_path.exists()
        assert output_path.name == "myproj-tasks.json"

    def test_save_creates_output_dir(self, tmp_path: Path) -> None:
        """save_tasks creates the output directory if it doesn't exist."""
        config = PipelineConfig(project_name="test")
        pipeline = BenchmarkPipeline(config)
        result = PipelineResult(project_name="test", tasks=[])

        output_dir = tmp_path / "deep" / "nested" / "dir"
        pipeline.save_tasks(result, output_dir)

        assert output_dir.exists()

    def test_save_valid_json(self, mini_repo: Path, tmp_path: Path) -> None:
        """Saved file is valid, parseable JSON."""
        config = PipelineConfig(project_name="jsontest", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        output_dir = tmp_path / "output"
        output_path = pipeline.save_tasks(result, output_dir)

        data = json.loads(output_path.read_text())
        assert "project" in data
        assert "summary" in data
        assert "tasks" in data
        assert data["project"] == "jsontest"

    def test_save_summary_counts(self, mini_repo: Path, tmp_path: Path) -> None:
        """Summary section has correct counts."""
        config = PipelineConfig(project_name="counts", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        output_dir = tmp_path / "output"
        output_path = pipeline.save_tasks(result, output_dir)

        data = json.loads(output_path.read_text())
        summary = data["summary"]
        assert summary["harvested"] == result.harvested_count
        assert summary["filtered"] == result.filtered_count
        assert summary["sampled"] == result.sampled_count

    def test_save_tasks_have_required_fields(self, mini_repo: Path, tmp_path: Path) -> None:
        """Each serialised task has all required fields."""
        config = PipelineConfig(project_name="fields", min_loc=1, require_assertions=False, filter_flaky=False, filter_skipped=False)
        pipeline = BenchmarkPipeline(config)
        result = pipeline.run(mini_repo)

        output_dir = tmp_path / "output"
        output_path = pipeline.save_tasks(result, output_dir)

        data = json.loads(output_path.read_text())
        for task_dict in data["tasks"]:
            assert "id" in task_dict
            assert "project" in task_dict
            assert "category" in task_dict
            assert "description" in task_dict
            assert "test_code" in task_dict
            assert "loc" in task_dict
            assert "difficulty" in task_dict

    def test_save_default_project_name(self, tmp_path: Path) -> None:
        """When project_name is empty, filename defaults to 'benchmark'."""
        config = PipelineConfig(project_name="")
        pipeline = BenchmarkPipeline(config)
        result = PipelineResult(project_name="", tasks=[])

        output_dir = tmp_path / "output"
        output_path = pipeline.save_tasks(result, output_dir)

        assert output_path.name == "benchmark-tasks.json"


# ---------------------------------------------------------------------------
# run_multiple tests
# ---------------------------------------------------------------------------


class TestRunMultiple:
    """Tests for multi-project pipeline runner."""

    def test_run_two_projects(self, tmp_path: Path) -> None:
        """Process multiple projects in one call."""
        # Create two mini repos
        for name in ("proj_a", "proj_b"):
            test_file = tmp_path / name / "tests" / "test_basics.py"
            test_file.parent.mkdir(parents=True)
            lines = ["def test_hello():"]
            for i in range(15):
                lines.append(f"    x{i} = {i}")
            lines.append("    assert True")
            test_file.write_text("\n".join(lines))

        output_dir = tmp_path / "output"
        projects = {
            "proj_a": tmp_path / "proj_a",
            "proj_b": tmp_path / "proj_b",
        }
        results = run_multiple(projects, output_dir, sample_size=0, seed=42)

        assert len(results) == 2
        assert "proj_a" in results
        assert "proj_b" in results
        assert (output_dir / "proj_a-tasks.json").exists()
        assert (output_dir / "proj_b-tasks.json").exists()

    def test_run_multiple_empty(self, tmp_path: Path) -> None:
        """Empty project dict returns empty results."""
        output_dir = tmp_path / "output"
        results = run_multiple({}, output_dir)
        assert results == {}


# ---------------------------------------------------------------------------
# PipelineResult tests
# ---------------------------------------------------------------------------


class TestPipelineResult:
    """Tests for the PipelineResult dataclass."""

    def test_default_values(self) -> None:
        """Default result has zero counts and empty lists."""
        result = PipelineResult()
        assert result.project_name == ""
        assert result.harvested_count == 0
        assert result.filtered_count == 0
        assert result.sampled_count == 0
        assert result.tasks == []
        assert result.taxonomy is None

    def test_with_values(self) -> None:
        """Result stores provided values."""
        result = PipelineResult(
            project_name="test",
            harvested_count=100,
            filtered_count=80,
            sampled_count=50,
        )
        assert result.project_name == "test"
        assert result.harvested_count == 100
        assert result.filtered_count == 80
        assert result.sampled_count == 50
