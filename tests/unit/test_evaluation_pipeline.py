"""Unit tests for the evaluation pipeline: localization, semantic validation,
execution testing, pipeline orchestration, and metrics.

All external dependencies (SentenceTransformer, LLM, Docker sandbox) are mocked.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from cobuilder.repomap.evaluation.models import (
    BenchmarkTask,
    CodeStats,
    DifficultyLevel,
    ExecutionResult,
    FunctionSignature,
    RepositoryResult,
    StageFailed,
    TaskResult,
    ValidationResult,
    Vote,
    VoteResult,
)
from cobuilder.repomap.evaluation.execution_testing import ExecutionTester
from cobuilder.repomap.evaluation.localization import FunctionLocalizer
from cobuilder.repomap.evaluation.metrics import MetricsCalculator
from cobuilder.repomap.evaluation.pipeline import EvaluationPipeline
from cobuilder.repomap.evaluation.semantic_validation import SemanticValidator


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str = "task-001",
    project: str = "test-project",
    category: str = "ml.linear",
    subcategory: str = "ridge",
    description: str = "Implement ridge regression",
    test_code: str = "def test_ridge(): assert True",
    imports: list[str] | None = None,
    auxiliary_code: str = "",
) -> BenchmarkTask:
    return BenchmarkTask(
        id=task_id,
        project=project,
        category=category,
        subcategory=subcategory,
        description=description,
        test_code=test_code,
        imports=imports or [],
        auxiliary_code=auxiliary_code,
    )


def _make_function(
    name: str = "ridge_regression",
    module: str = "ml.linear",
    signature: str = "def ridge_regression(X, y, alpha=1.0)",
    docstring: str = "Ridge regression.",
    file_path: str = "ml/linear.py",
    body: str = "def ridge_regression(X, y, alpha=1.0):\n    pass",
) -> FunctionSignature:
    return FunctionSignature(
        name=name,
        module=module,
        signature=signature,
        docstring=docstring,
        file_path=file_path,
        start_line=1,
        end_line=2,
        body=body,
    )


# ---------------------------------------------------------------------------
# TestFunctionLocalizer
# ---------------------------------------------------------------------------


class TestFunctionLocalizer:
    """Tests for FunctionLocalizer."""

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_init_success(self, mock_st: MagicMock) -> None:
        """Localizer initializes when sentence-transformers is available."""
        localizer = FunctionLocalizer()
        assert localizer._model_name == "all-MiniLM-L6-v2"
        assert localizer._model is None

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", False)
    def test_init_missing_dependency(self) -> None:
        """Raises ImportError when sentence-transformers is missing."""
        with pytest.raises(ImportError, match="sentence-transformers"):
            FunctionLocalizer()

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_lazy_model_loading(self, mock_st_cls: MagicMock) -> None:
        """Model is loaded lazily on first access."""
        localizer = FunctionLocalizer()
        assert localizer._model is None
        _ = localizer.model
        mock_st_cls.assert_called_once_with("all-MiniLM-L6-v2")

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_functions_from_synthetic_repo(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Extract functions from a synthetic repo with .py files."""
        (tmp_path / "module.py").write_text(
            textwrap.dedent("""\
            def add(a, b):
                \"\"\"Add two numbers.\"\"\"
                return a + b

            def subtract(a, b):
                return a - b
            """)
        )
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "add" in names
        assert "subtract" in names

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_functions_skips_test_files(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Test files (test_*.py) are skipped during extraction."""
        (tmp_path / "test_something.py").write_text("def test_foo(): pass")
        (tmp_path / "core.py").write_text("def real_func(): pass")
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "test_foo" not in names
        assert "real_func" in names

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_functions_skips_test_dirs(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Test directories are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "helpers.py").write_text("def helper(): pass")
        (tmp_path / "main.py").write_text("def main(): pass")
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "helper" not in names
        assert "main" in names

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_functions_handles_syntax_error(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Files with syntax errors are skipped gracefully."""
        (tmp_path / "broken.py").write_text("def foo(:\n  pass")
        (tmp_path / "good.py").write_text("def bar(): pass")
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "bar" in names

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_functions_empty_repo(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Empty repo returns no functions."""
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        assert funcs == []

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_class_methods(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Class methods are extracted with class prefix in module."""
        (tmp_path / "models.py").write_text(
            textwrap.dedent("""\
            class MyModel:
                def predict(self, x):
                    return x
            """)
        )
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        predict_func = [f for f in funcs if f.name == "predict"][0]
        assert "MyModel" in predict_func.module

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_extract_async_functions(
        self, mock_st: MagicMock, tmp_path: Path
    ) -> None:
        """Async functions are extracted correctly."""
        (tmp_path / "async_mod.py").write_text(
            "async def fetch_data(url): pass"
        )
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        assert len(funcs) >= 1
        assert funcs[0].name == "fetch_data"
        assert "async def" in funcs[0].signature

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_build_signature(self, mock_st: MagicMock, tmp_path: Path) -> None:
        """_build_signature creates a valid FunctionSignature with correct fields."""
        (tmp_path / "sig_test.py").write_text(
            textwrap.dedent("""\
            def my_func(x, y=10):
                \"\"\"My docstring.\"\"\"
                return x + y
            """)
        )
        localizer = FunctionLocalizer()
        funcs = localizer.extract_functions(tmp_path)
        assert len(funcs) == 1
        sig = funcs[0]
        assert sig.name == "my_func"
        assert "def my_func" in sig.signature
        assert "My docstring" in sig.docstring
        assert sig.file_path == "sig_test.py"
        assert sig.start_line > 0
        assert sig.end_line >= sig.start_line

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_localize_returns_top_k(self, mock_st_cls: MagicMock) -> None:
        """Localize returns results sorted by score descending, limited by top_k."""
        mock_model = MagicMock()
        mock_st_cls.return_value = mock_model
        mock_model.encode.side_effect = [
            np.array([[1.0, 0.0, 0.0]]),  # task embedding
            np.array([
                [0.1, 0.9, 0.0],  # func0 - low sim
                [0.9, 0.1, 0.0],  # func1 - high sim
                [0.5, 0.5, 0.0],  # func2 - medium sim
            ]),
        ]

        localizer = FunctionLocalizer()
        functions = [
            _make_function(name="low_sim"),
            _make_function(name="high_sim"),
            _make_function(name="med_sim"),
        ]
        task = _make_task()
        results = localizer.localize(task, "/fake/path", top_k=3, functions=functions)

        assert len(results) == 3
        assert results[0][0].name == "high_sim"
        assert results[0][1] > results[1][1]

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_localize_empty_functions(self, mock_st_cls: MagicMock) -> None:
        """Localize with no functions returns empty list."""
        localizer = FunctionLocalizer()
        task = _make_task()
        results = localizer.localize(task, "/fake/path", functions=[])
        assert results == []

    @patch("cobuilder.repomap.evaluation.localization._ST_AVAILABLE", True)
    @patch("cobuilder.repomap.evaluation.localization.SentenceTransformer")
    def test_localize_top_k_limit(self, mock_st_cls: MagicMock) -> None:
        """Localize respects top_k parameter."""
        mock_model = MagicMock()
        mock_st_cls.return_value = mock_model
        mock_model.encode.side_effect = [
            np.array([[1.0, 0.0]]),
            np.array([[0.1, 0.9], [0.9, 0.1], [0.5, 0.5]]),
        ]
        localizer = FunctionLocalizer()
        functions = [_make_function(name=f"f{i}") for i in range(3)]
        task = _make_task()
        results = localizer.localize(task, "/fake", top_k=2, functions=functions)
        assert len(results) == 2

    def test_cosine_similarity_identical_vectors(self) -> None:
        """Identical vectors have similarity 1.0."""
        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[1.0, 0.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert pytest.approx(sim[0, 0], abs=1e-6) == 1.0

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        """Orthogonal vectors have similarity 0.0."""
        a = np.array([[1.0, 0.0]])
        b = np.array([[0.0, 1.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert pytest.approx(sim[0, 0], abs=1e-6) == 0.0

    def test_cosine_similarity_shape(self) -> None:
        """Batch cosine similarity returns correct shape (1, N)."""
        a = np.array([[1.0, 0.0]])
        b = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert sim.shape == (1, 3)

    def test_cosine_similarity_opposite(self) -> None:
        """Opposite vectors have similarity -1.0."""
        a = np.array([[1.0, 0.0]])
        b = np.array([[-1.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert pytest.approx(sim[0, 0], abs=1e-6) == -1.0


# ---------------------------------------------------------------------------
# TestSemanticValidator
# ---------------------------------------------------------------------------


class TestSemanticValidator:
    """Tests for SemanticValidator."""

    def _make_validator(
        self,
        responses: list[str] | None = None,
        num_voters: int = 3,
        num_rounds: int = 2,
    ) -> SemanticValidator:
        """Create a validator with mock LLM client."""
        mock_llm = MagicMock()
        if responses:
            mock_llm.complete.side_effect = responses
        return SemanticValidator(
            llm_client=mock_llm,
            model="test-model",
            num_voters=num_voters,
            num_rounds=num_rounds,
        )

    def test_clear_yes_majority_round1(self) -> None:
        """3/3 YES in round 1 returns high confidence pass."""
        validator = self._make_validator(["YES. Good.", "YES. Fine.", "YES. OK."])
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert result.passed is True
        assert result.confidence == "high"
        assert len(result.votes) == 3  # Only round 1

    def test_clear_no_majority_round1(self) -> None:
        """3/3 NO in round 1 returns high confidence fail."""
        validator = self._make_validator(["NO. Bad.", "NO. Wrong.", "NO. Missing."])
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert result.passed is False
        assert result.confidence == "high"

    def test_split_triggers_round2(self) -> None:
        """Split vote in round 1 triggers round 2, producing 6 total votes."""
        validator = self._make_validator([
            "YES. OK.", "NO. Bad.", "PARTIAL. Half.",  # Round 1: no majority
            "YES. Fine.", "YES. Good.", "YES. Great.",  # Round 2
        ])
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert len(result.votes) == 6  # Both rounds

    def test_partial_votes(self) -> None:
        """PARTIAL votes are counted correctly; majority PARTIAL means not passed."""
        validator = self._make_validator([
            "PARTIAL. Some.", "PARTIAL. Some.", "PARTIAL. Some.",
        ])
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert result.passed is False  # PARTIAL != YES
        assert result.confidence == "high"  # Clear majority of PARTIAL

    def test_parse_vote_yes(self) -> None:
        """'YES. Good.' parses as VoteResult.YES."""
        result, just = SemanticValidator._parse_vote("YES. Good implementation.")
        assert result == VoteResult.YES
        assert "Good implementation" in just

    def test_parse_vote_no(self) -> None:
        """'NO: Missing feature.' parses as VoteResult.NO."""
        result, just = SemanticValidator._parse_vote("NO: Missing feature.")
        assert result == VoteResult.NO
        assert "Missing feature" in just

    def test_parse_vote_partial(self) -> None:
        """'PARTIAL - Some done.' parses as VoteResult.PARTIAL."""
        result, just = SemanticValidator._parse_vote("PARTIAL - Some parts done.")
        assert result == VoteResult.PARTIAL

    def test_parse_vote_with_justification(self) -> None:
        """Vote parsing extracts justification text after the keyword."""
        result, just = SemanticValidator._parse_vote("YES. It works correctly.")
        assert result == VoteResult.YES
        assert "It works correctly" in just

    def test_parse_vote_yes_in_sentence(self) -> None:
        """Fallback: YES found in the first sentence."""
        result, just = SemanticValidator._parse_vote(
            "The function is a YES implementation."
        )
        assert result == VoteResult.YES

    def test_parse_vote_unknown_defaults_no(self) -> None:
        """Unknown response defaults to NO."""
        result, just = SemanticValidator._parse_vote("I'm not sure about this.")
        assert result == VoteResult.NO

    def test_check_majority_clear(self) -> None:
        """3/3 YES is a clear majority."""
        votes = [
            Vote(result=VoteResult.YES, round_num=1),
            Vote(result=VoteResult.YES, round_num=1),
            Vote(result=VoteResult.YES, round_num=1),
        ]
        assert SemanticValidator._check_majority(votes) == VoteResult.YES

    def test_check_majority_no_majority(self) -> None:
        """1 YES, 1 NO, 1 PARTIAL has no majority."""
        votes = [
            Vote(result=VoteResult.YES, round_num=1),
            Vote(result=VoteResult.NO, round_num=1),
            Vote(result=VoteResult.PARTIAL, round_num=1),
        ]
        assert SemanticValidator._check_majority(votes) is None

    def test_majority_vote_tiebreak(self) -> None:
        """_majority_vote returns the most common vote result."""
        votes = [
            Vote(result=VoteResult.YES, round_num=1),
            Vote(result=VoteResult.YES, round_num=1),
            Vote(result=VoteResult.NO, round_num=1),
        ]
        assert SemanticValidator._majority_vote(votes) == VoteResult.YES

    def test_majority_vote_empty_defaults_no(self) -> None:
        """Empty votes default to NO."""
        assert SemanticValidator._majority_vote([]) == VoteResult.NO

    def test_error_handling_in_vote(self) -> None:
        """LLM errors result in NO votes."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = Exception("API error")
        validator = SemanticValidator(
            llm_client=mock_llm, model="test", num_voters=3, num_rounds=1,
        )
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert result.passed is False
        assert all(v.result == VoteResult.NO for v in result.votes)

    def test_low_confidence_no_majority(self) -> None:
        """No majority across both rounds yields low confidence."""
        validator = self._make_validator([
            "YES. a", "NO. b", "PARTIAL. c",  # Round 1: all different
            "YES. d", "NO. e", "PARTIAL. f",  # Round 2: still no majority
        ])
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert result.confidence == "low"

    def test_single_round_mode(self) -> None:
        """With num_rounds=1, no round 2 even on split."""
        validator = self._make_validator(
            ["YES. a", "NO. b", "PARTIAL. c"],
            num_rounds=1,
        )
        task = _make_task()
        func = _make_function()
        result = validator.validate_function(task, func)
        assert len(result.votes) == 3  # Only round 1

    def test_candidate_function_name_in_result(self) -> None:
        """Result includes the candidate function name."""
        validator = self._make_validator(["YES. OK.", "YES. OK.", "YES. OK."])
        task = _make_task()
        func = _make_function(name="my_func")
        result = validator.validate_function(task, func)
        assert result.candidate_function == "my_func"

    def test_check_majority_empty(self) -> None:
        """Empty list returns None."""
        assert SemanticValidator._check_majority([]) is None

    def test_check_majority_two_of_three_no(self) -> None:
        """2/3 NO is a majority (>50%)."""
        votes = [
            Vote(result=VoteResult.NO, round_num=1),
            Vote(result=VoteResult.NO, round_num=1),
            Vote(result=VoteResult.YES, round_num=1),
        ]
        assert SemanticValidator._check_majority(votes) == VoteResult.NO

    def test_parse_vote_lowercase_yes(self) -> None:
        """Lowercase 'yes' at start is parsed."""
        result, just = SemanticValidator._parse_vote("yes, it implements everything")
        assert result == VoteResult.YES


# ---------------------------------------------------------------------------
# TestExecutionTester
# ---------------------------------------------------------------------------


class TestExecutionTester:
    """Tests for ExecutionTester."""

    def _mock_sandbox(self) -> MagicMock:
        """Create a mock sandbox."""
        sandbox = MagicMock()
        sandbox.start.return_value = "container-123"
        sandbox.install_dependencies.return_value = True
        return sandbox

    def test_adapt_test_basic(self) -> None:
        """Adapt test creates a valid test file with imports and runner."""
        tester = ExecutionTester(sandbox=MagicMock())
        task = _make_task(
            test_code="def test_add():\n    assert add(1, 2) == 3",
            imports=["from mylib import add"],
        )
        adapted = tester.adapt_test(task, "/fake/repo")
        assert "from mylib import add" in adapted
        assert "def test_add():" in adapted
        assert "TEST_PASSED" in adapted

    def test_adapt_test_with_import_mapping(self) -> None:
        """Import mapping rewrites imports correctly."""
        tester = ExecutionTester(sandbox=MagicMock())
        task = _make_task(
            test_code="def test_it(): pass",
            imports=["from sklearn.linear_model import Ridge"],
        )
        adapted = tester.adapt_test(
            task, "/fake", import_mapping={"sklearn": "ml_lib"}
        )
        assert "from ml_lib.linear_model import Ridge" in adapted

    def test_adapt_test_with_auxiliary_code(self) -> None:
        """Auxiliary code is included in adapted test."""
        tester = ExecutionTester(sandbox=MagicMock())
        task = _make_task(
            test_code="def test_it(): pass",
            auxiliary_code="FIXTURE = [1, 2, 3]",
        )
        adapted = tester.adapt_test(task, "/fake")
        assert "FIXTURE = [1, 2, 3]" in adapted

    def test_execute_test_success(self) -> None:
        """Successful test execution returns passed=True."""
        sandbox = self._mock_sandbox()
        result_mock = MagicMock()
        result_mock.stdout = "PASSED: test_it\nTEST_PASSED"
        result_mock.stderr = ""
        result_mock.exit_code = 0
        result_mock.duration_ms = 150.0
        sandbox.run_code.return_value = result_mock

        tester = ExecutionTester(sandbox=sandbox)
        task = _make_task(test_code="def test_it(): pass")
        result = tester.execute_test(task, "/fake/repo")

        assert result.passed is True
        assert result.exit_code == 0

    def test_execute_test_failure(self) -> None:
        """Failed test execution returns passed=False."""
        sandbox = self._mock_sandbox()
        result_mock = MagicMock()
        result_mock.stdout = "FAILED: test_it\nTEST_FAILED"
        result_mock.stderr = "AssertionError"
        result_mock.exit_code = 1
        result_mock.duration_ms = 50.0
        sandbox.run_code.return_value = result_mock

        tester = ExecutionTester(sandbox=sandbox)
        task = _make_task(test_code="def test_it(): assert False")
        result = tester.execute_test(task, "/fake/repo")

        assert result.passed is False
        assert result.error is not None

    def test_execute_test_sandbox_error(self) -> None:
        """Sandbox exception returns passed=False with error message."""
        sandbox = self._mock_sandbox()
        sandbox.start.side_effect = RuntimeError("Docker not available")

        tester = ExecutionTester(sandbox=sandbox)
        task = _make_task()
        result = tester.execute_test(task, "/fake/repo")

        assert result.passed is False
        assert "Docker not available" in result.error

    def test_execute_test_cleanup_on_failure(self) -> None:
        """Sandbox.stop is called even on test failure."""
        sandbox = self._mock_sandbox()
        result_mock = MagicMock()
        result_mock.stdout = "TEST_FAILED"
        result_mock.stderr = ""
        result_mock.exit_code = 1
        result_mock.duration_ms = 0
        sandbox.run_code.return_value = result_mock

        tester = ExecutionTester(sandbox=sandbox)
        task = _make_task()
        tester.execute_test(task, "/fake/repo")
        sandbox.stop.assert_called_once_with("container-123")

    def test_extract_package_name_from_import(self) -> None:
        """Extract 'sklearn' from 'from sklearn.linear_model import Ridge'."""
        assert ExecutionTester._extract_package_name(
            "from sklearn.linear_model import Ridge"
        ) == "sklearn"

    def test_extract_package_name_import_from(self) -> None:
        """Extract 'numpy' from 'import numpy as np'."""
        assert ExecutionTester._extract_package_name(
            "import numpy as np"
        ) == "numpy"

    def test_extract_package_name_none(self) -> None:
        """Non-import returns None."""
        assert ExecutionTester._extract_package_name("# comment") is None

    def test_extract_package_name_simple(self) -> None:
        """Extract 'json' from 'import json'."""
        assert ExecutionTester._extract_package_name("import json") == "json"

    def test_extract_package_name_dotted(self) -> None:
        """Extract top-level from dotted import."""
        assert ExecutionTester._extract_package_name("import os.path") == "os"

    def test_default_dependencies(self) -> None:
        """Default dependencies include pytest and numpy."""
        tester = ExecutionTester(sandbox=MagicMock())
        assert "pytest" in tester.default_dependencies
        assert "numpy" in tester.default_dependencies

    def test_custom_dependencies(self) -> None:
        """Custom dependencies override defaults."""
        tester = ExecutionTester(
            sandbox=MagicMock(), default_dependencies=["scipy"]
        )
        assert tester.default_dependencies == ["scipy"]

    def test_execute_test_extracts_deps_from_imports(self) -> None:
        """Dependencies are extracted from task imports and installed."""
        sandbox = self._mock_sandbox()
        result_mock = MagicMock()
        result_mock.stdout = "TEST_PASSED"
        result_mock.stderr = ""
        result_mock.exit_code = 0
        result_mock.duration_ms = 0
        sandbox.run_code.return_value = result_mock

        tester = ExecutionTester(sandbox=sandbox)
        task = _make_task(imports=["from pandas import DataFrame"])
        tester.execute_test(task, "/fake/repo")

        call_args = sandbox.install_dependencies.call_args[0]
        deps = call_args[1]
        assert "pandas" in deps


# ---------------------------------------------------------------------------
# TestEvaluationPipeline
# ---------------------------------------------------------------------------


class TestEvaluationPipeline:
    """Tests for EvaluationPipeline."""

    def _make_pipeline(
        self,
        localize_result: list | None = None,
        validate_passed: bool = True,
        exec_passed: bool = True,
    ) -> EvaluationPipeline:
        """Create a pipeline with all stages mocked."""
        localizer = MagicMock()
        validator = MagicMock()
        tester = MagicMock()

        func = _make_function()
        if localize_result is None:
            localize_result = [(func, 0.9)]
        localizer.localize.return_value = localize_result
        localizer.extract_functions.return_value = [func]

        validator.validate_function.return_value = ValidationResult(
            passed=validate_passed,
            confidence="high",
            votes=[],
            candidate_function=func.name,
        )

        tester.execute_test.return_value = ExecutionResult(
            passed=exec_passed,
            exit_code=0 if exec_passed else 1,
            stdout="TEST_PASSED" if exec_passed else "TEST_FAILED",
        )

        return EvaluationPipeline(
            localizer=localizer,
            validator=validator,
            tester=tester,
        )

    def test_full_success_path(self) -> None:
        """All 3 stages pass."""
        pipeline = self._make_pipeline()
        task = _make_task()
        result = pipeline.evaluate_task(task, "/fake")
        assert result.localized is True
        assert result.validated is True
        assert result.passed is True
        assert result.stage_failed is None

    def test_localization_failure(self) -> None:
        """No candidates found -> localization failure."""
        pipeline = self._make_pipeline(localize_result=[])
        task = _make_task()
        result = pipeline.evaluate_task(task, "/fake")
        assert result.localized is False
        assert result.stage_failed == StageFailed.LOCALIZATION

    def test_validation_failure(self) -> None:
        """Validation fails -> stage_failed=VALIDATION."""
        pipeline = self._make_pipeline(validate_passed=False)
        task = _make_task()
        result = pipeline.evaluate_task(task, "/fake")
        assert result.localized is True
        assert result.validated is False
        assert result.stage_failed == StageFailed.VALIDATION

    def test_execution_failure(self) -> None:
        """Execution fails -> stage_failed=EXECUTION."""
        pipeline = self._make_pipeline(exec_passed=False)
        task = _make_task()
        result = pipeline.evaluate_task(task, "/fake")
        assert result.localized is True
        assert result.validated is True
        assert result.passed is False
        assert result.stage_failed == StageFailed.EXECUTION

    def test_evaluate_repository_aggregation(self) -> None:
        """Repository evaluation aggregates task results correctly."""
        pipeline = self._make_pipeline()
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat2"),
        ]
        repo_result = pipeline.evaluate_repository(tasks, "/fake")
        assert repo_result.total_tasks == 2
        assert repo_result.passed == 2
        assert repo_result.project_name == "test-project"

    def test_evaluate_repository_coverage(self) -> None:
        """Coverage is 1.0 when all categories have passing tests."""
        pipeline = self._make_pipeline()
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat2"),
        ]
        repo_result = pipeline.evaluate_repository(tasks, "/fake")
        assert repo_result.coverage == 1.0

    def test_evaluate_repository_empty_tasks(self) -> None:
        """Empty task list returns sensible defaults."""
        pipeline = self._make_pipeline()
        repo_result = pipeline.evaluate_repository([], "/fake")
        assert repo_result.total_tasks == 0
        assert repo_result.coverage == 0.0
        assert repo_result.project_name == "unknown"

    def test_pre_extracts_functions_once(self) -> None:
        """evaluate_repository calls extract_functions once, not per task."""
        pipeline = self._make_pipeline()
        tasks = [
            _make_task(task_id="t1"),
            _make_task(task_id="t2"),
            _make_task(task_id="t3"),
        ]
        pipeline.evaluate_repository(tasks, "/fake")
        # extract_functions should be called exactly once
        pipeline.localizer.extract_functions.assert_called_once_with("/fake")
        # localize should be called for each task with pre-extracted functions
        assert pipeline.localizer.localize.call_count == 3

    def test_evaluate_repository_partial_pass(self) -> None:
        """Partial pass gives correct coverage."""
        localizer = MagicMock()
        validator = MagicMock()
        tester = MagicMock()

        func = _make_function()
        localizer.localize.return_value = [(func, 0.9)]
        localizer.extract_functions.return_value = [func]

        validator.validate_function.side_effect = [
            ValidationResult(passed=True, confidence="high", votes=[]),
            ValidationResult(passed=False, confidence="low", votes=[]),
        ]
        tester.execute_test.return_value = ExecutionResult(
            passed=True, exit_code=0, stdout="TEST_PASSED"
        )

        pipeline = EvaluationPipeline(
            localizer=localizer, validator=validator, tester=tester
        )
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat2"),
        ]
        repo_result = pipeline.evaluate_repository(tasks, "/fake")
        assert repo_result.passed == 1
        assert repo_result.validated == 1
        assert repo_result.coverage == 0.5

    def test_pipeline_validation_candidates(self) -> None:
        """Pipeline tries multiple candidates for validation."""
        localizer = MagicMock()
        validator = MagicMock()
        tester = MagicMock()

        funcs = [_make_function(name=f"f{i}") for i in range(3)]
        localizer.localize.return_value = [
            (f, 0.9 - i * 0.1) for i, f in enumerate(funcs)
        ]
        localizer.extract_functions.return_value = funcs

        # First two fail, third passes
        validator.validate_function.side_effect = [
            ValidationResult(passed=False, confidence="low", votes=[]),
            ValidationResult(passed=False, confidence="low", votes=[]),
            ValidationResult(passed=True, confidence="high", votes=[]),
        ]
        tester.execute_test.return_value = ExecutionResult(
            passed=True, exit_code=0, stdout="TEST_PASSED"
        )

        pipeline = EvaluationPipeline(
            localizer=localizer,
            validator=validator,
            tester=tester,
            validation_candidates=3,
        )
        task = _make_task()
        result = pipeline.evaluate_task(task, "/fake")
        assert result.validated is True
        assert result.candidate_function == "f2"

    def test_pipeline_top_k_setting(self) -> None:
        """Pipeline uses top_k setting for localization."""
        pipeline = self._make_pipeline()
        pipeline.top_k = 10
        task = _make_task()
        pipeline.evaluate_task(task, "/fake")
        call_kwargs = pipeline.localizer.localize.call_args
        assert call_kwargs[1]["top_k"] == 10


# ---------------------------------------------------------------------------
# TestMetricsCalculator
# ---------------------------------------------------------------------------


class TestMetricsCalculator:
    """Tests for MetricsCalculator."""

    def test_calculate_coverage_all_pass(self) -> None:
        """100% coverage when all categories have passing tests."""
        calc = MetricsCalculator()
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat2"),
        ]
        results = [
            TaskResult(task_id="t1", passed=True),
            TaskResult(task_id="t2", passed=True),
        ]
        assert calc.calculate_coverage(tasks, results) == 1.0

    def test_calculate_coverage_partial(self) -> None:
        """50% coverage when 1 of 2 categories passes."""
        calc = MetricsCalculator()
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat2"),
        ]
        results = [
            TaskResult(task_id="t1", passed=True),
            TaskResult(task_id="t2", passed=False),
        ]
        assert calc.calculate_coverage(tasks, results) == 0.5

    def test_calculate_coverage_none_pass(self) -> None:
        """0% coverage when nothing passes."""
        calc = MetricsCalculator()
        tasks = [_make_task(task_id="t1")]
        results = [TaskResult(task_id="t1", passed=False)]
        assert calc.calculate_coverage(tasks, results) == 0.0

    def test_calculate_coverage_empty(self) -> None:
        """Empty tasks returns 0."""
        calc = MetricsCalculator()
        assert calc.calculate_coverage([], []) == 0.0

    def test_calculate_coverage_multiple_same_category(self) -> None:
        """Category counts as covered if any task in it passes."""
        calc = MetricsCalculator()
        tasks = [
            _make_task(task_id="t1", category="cat1"),
            _make_task(task_id="t2", category="cat1"),
        ]
        results = [
            TaskResult(task_id="t1", passed=False),
            TaskResult(task_id="t2", passed=True),
        ]
        assert calc.calculate_coverage(tasks, results) == 1.0

    def test_calculate_novelty_all_novel(self) -> None:
        """100% novelty when all generated categories are new."""
        calc = MetricsCalculator()
        tasks = [_make_task(category="ref_cat")]
        generated = {"novel_cat1", "novel_cat2"}
        assert calc.calculate_novelty(tasks, generated) == 1.0

    def test_calculate_novelty_none_novel(self) -> None:
        """0% novelty when all generated match reference."""
        calc = MetricsCalculator()
        tasks = [_make_task(category="cat1")]
        generated = {"cat1"}
        assert calc.calculate_novelty(tasks, generated) == 0.0

    def test_calculate_novelty_partial(self) -> None:
        """50% novelty when half are novel."""
        calc = MetricsCalculator()
        tasks = [_make_task(category="cat1")]
        generated = {"cat1", "novel"}
        assert calc.calculate_novelty(tasks, generated) == 0.5

    def test_calculate_novelty_empty(self) -> None:
        """Empty generated returns 0."""
        calc = MetricsCalculator()
        assert calc.calculate_novelty([], set()) == 0.0

    def test_calculate_pass_rate(self) -> None:
        """Pass rate with mixed results."""
        calc = MetricsCalculator()
        results = [
            TaskResult(task_id="t1", passed=True),
            TaskResult(task_id="t2", passed=False),
        ]
        assert calc.calculate_pass_rate(results) == 0.5

    def test_calculate_pass_rate_all(self) -> None:
        """100% pass rate."""
        calc = MetricsCalculator()
        results = [
            TaskResult(task_id="t1", passed=True),
            TaskResult(task_id="t2", passed=True),
        ]
        assert calc.calculate_pass_rate(results) == 1.0

    def test_calculate_pass_rate_empty(self) -> None:
        """Empty results returns 0."""
        calc = MetricsCalculator()
        assert calc.calculate_pass_rate([]) == 0.0

    def test_calculate_voting_rate(self) -> None:
        """Voting rate calculation."""
        calc = MetricsCalculator()
        results = [
            TaskResult(task_id="t1", validated=True),
            TaskResult(task_id="t2", validated=False),
        ]
        assert calc.calculate_voting_rate(results) == 0.5

    def test_calculate_voting_rate_empty(self) -> None:
        """Empty results returns 0."""
        calc = MetricsCalculator()
        assert calc.calculate_voting_rate([]) == 0.0

    def test_calculate_code_stats(self, tmp_path: Path) -> None:
        """Code stats counts files, lines, and estimates tokens."""
        (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
        (tmp_path / "b.py").write_text("line1\n")
        calc = MetricsCalculator()
        stats = calc.calculate_code_stats(tmp_path)
        assert stats.files == 2
        assert stats.loc == 4  # 3 + 1
        assert stats.estimated_tokens > 0

    def test_calculate_code_stats_empty_dir(self, tmp_path: Path) -> None:
        """Empty repo has 0 stats."""
        calc = MetricsCalculator()
        stats = calc.calculate_code_stats(tmp_path)
        assert stats.files == 0
        assert stats.loc == 0
        assert stats.estimated_tokens == 0

    def test_calculate_code_stats_nested(self, tmp_path: Path) -> None:
        """Stats include nested directories."""
        subdir = tmp_path / "pkg"
        subdir.mkdir()
        (subdir / "mod.py").write_text("x = 1\ny = 2\n")
        calc = MetricsCalculator()
        stats = calc.calculate_code_stats(tmp_path)
        assert stats.files == 1
        assert stats.loc == 2
