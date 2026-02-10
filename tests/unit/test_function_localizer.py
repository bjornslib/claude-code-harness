"""Unit tests for the FunctionLocalizer class (bead 9rt).

Tests cover:
- Function extraction from Python files using AST
- Class method extraction
- Async function extraction
- Skipping test files
- FunctionSignature construction (name, module, signature, docstring, body)
- Error handling for malformed files
- Cosine similarity computation
- Localization with mocked sentence-transformer model
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from zerorepo.evaluation.localization import FunctionLocalizer
from zerorepo.evaluation.models import BenchmarkTask, DifficultyLevel, FunctionSignature


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a synthetic repository with various Python files."""
    # Main module
    pkg_dir = tmp_path / "ml_lib"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        '"""ML Library package."""\n',
        encoding="utf-8",
    )

    (pkg_dir / "linear_model.py").write_text(
        textwrap.dedent("""\
        \"\"\"Linear regression models.\"\"\"

        import numpy as np


        def ridge_regression(X, y, alpha=1.0):
            \"\"\"Fit a ridge regression model.\"\"\"
            n_features = X.shape[1]
            identity = np.eye(n_features)
            coef = np.linalg.solve(X.T @ X + alpha * identity, X.T @ y)
            return coef


        def lasso_regression(X, y, alpha=1.0):
            \"\"\"Fit a lasso regression model (simplified).\"\"\"
            return np.zeros(X.shape[1])


        async def async_solver(X, y):
            \"\"\"Async placeholder for distributed solving.\"\"\"
            return np.linalg.solve(X, y)
        """),
        encoding="utf-8",
    )

    (pkg_dir / "tree.py").write_text(
        textwrap.dedent("""\
        \"\"\"Decision tree models.\"\"\"


        class DecisionTree:
            \"\"\"Simple decision tree classifier.\"\"\"

            def __init__(self, max_depth=5):
                self.max_depth = max_depth
                self.tree_ = None

            def fit(self, X, y):
                \"\"\"Fit the decision tree to training data.\"\"\"
                self.tree_ = {"depth": 0}
                return self

            def predict(self, X):
                \"\"\"Predict class labels for samples in X.\"\"\"
                return [0] * len(X)
        """),
        encoding="utf-8",
    )

    # Test file (should be skipped)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_linear.py").write_text(
        textwrap.dedent("""\
        import pytest
        from ml_lib.linear_model import ridge_regression


        def test_ridge():
            assert True
        """),
        encoding="utf-8",
    )

    # File with syntax error
    (pkg_dir / "broken.py").write_text(
        "def this_is_broken(\n    not valid python!!\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def localizer() -> FunctionLocalizer:
    """Create a FunctionLocalizer with mocked model loading."""
    with patch("zerorepo.evaluation.localization._ST_AVAILABLE", True):
        with patch("zerorepo.evaluation.localization.SentenceTransformer"):
            loc = FunctionLocalizer(model_name="all-MiniLM-L6-v2")
    return loc


# ---------------------------------------------------------------------------
# Function extraction tests
# ---------------------------------------------------------------------------


class TestExtractFunctions:
    """Tests for extract_functions() - AST-based function extraction."""

    def test_extracts_top_level_functions(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Should extract top-level def functions."""
        functions = localizer.extract_functions(tmp_repo)
        names = [f.name for f in functions]
        assert "ridge_regression" in names
        assert "lasso_regression" in names

    def test_extracts_async_functions(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Should extract async def functions."""
        functions = localizer.extract_functions(tmp_repo)
        names = [f.name for f in functions]
        assert "async_solver" in names

    def test_extracts_class_methods(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Should extract class methods."""
        functions = localizer.extract_functions(tmp_repo)
        names = [f.name for f in functions]
        assert "fit" in names
        assert "predict" in names
        assert "__init__" in names

    def test_skips_test_files(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Test files (test_*.py and in test/ dirs) should be skipped."""
        functions = localizer.extract_functions(tmp_repo)
        names = [f.name for f in functions]
        assert "test_ridge" not in names

    def test_skips_syntax_error_files(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Files with syntax errors should be skipped gracefully."""
        functions = localizer.extract_functions(tmp_repo)
        names = [f.name for f in functions]
        assert "this_is_broken" not in names

    def test_returns_function_signatures(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Every result should be a FunctionSignature instance."""
        functions = localizer.extract_functions(tmp_repo)
        for f in functions:
            assert isinstance(f, FunctionSignature)

    def test_empty_directory(
        self, localizer: FunctionLocalizer, tmp_path: Path
    ) -> None:
        """Empty directory should return no functions."""
        functions = localizer.extract_functions(tmp_path)
        assert functions == []


# ---------------------------------------------------------------------------
# FunctionSignature field tests
# ---------------------------------------------------------------------------


class TestFunctionSignatureFields:
    """Tests for correct FunctionSignature field population."""

    def test_module_path(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Module should be the dotted path from file."""
        functions = localizer.extract_functions(tmp_repo)
        ridge = next(f for f in functions if f.name == "ridge_regression")
        assert "ml_lib" in ridge.module
        assert "linear_model" in ridge.module

    def test_class_method_module(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Class methods should include class name in module."""
        functions = localizer.extract_functions(tmp_repo)
        fit = next(f for f in functions if f.name == "fit")
        assert "DecisionTree" in fit.module

    def test_file_path(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """file_path should be relative to repo root."""
        functions = localizer.extract_functions(tmp_repo)
        ridge = next(f for f in functions if f.name == "ridge_regression")
        assert ridge.file_path.endswith("linear_model.py")
        assert not ridge.file_path.startswith("/")

    def test_signature_string(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Signature should contain def/async def and function name."""
        functions = localizer.extract_functions(tmp_repo)
        ridge = next(f for f in functions if f.name == "ridge_regression")
        assert "def ridge_regression" in ridge.signature

    def test_async_signature(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Async functions should have 'async def' in signature."""
        functions = localizer.extract_functions(tmp_repo)
        async_func = next(f for f in functions if f.name == "async_solver")
        assert "async def" in async_func.signature

    def test_docstring_extracted(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """First line of docstring should be captured."""
        functions = localizer.extract_functions(tmp_repo)
        ridge = next(f for f in functions if f.name == "ridge_regression")
        assert "ridge" in ridge.docstring.lower()

    def test_line_numbers(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Start and end line numbers should be positive."""
        functions = localizer.extract_functions(tmp_repo)
        for f in functions:
            assert f.start_line > 0
            assert f.end_line >= f.start_line

    def test_body_contains_code(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Body should contain the function source code."""
        functions = localizer.extract_functions(tmp_repo)
        ridge = next(f for f in functions if f.name == "ridge_regression")
        assert "np.linalg.solve" in ridge.body


# ---------------------------------------------------------------------------
# Cosine similarity tests
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Tests for _cosine_similarity static method."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity ~1.0."""
        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[1.0, 0.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert sim[0][0] == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity ~0.0."""
        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[0.0, 1.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert sim[0][0] == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors should have similarity ~-1.0."""
        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[-1.0, 0.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert sim[0][0] == pytest.approx(-1.0, abs=1e-6)

    def test_batch_similarity(self) -> None:
        """Should handle batch computation (1 query vs N candidates)."""
        a = np.array([[1.0, 0.0]])
        b = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
        sim = FunctionLocalizer._cosine_similarity(a, b)
        assert sim.shape == (1, 3)
        assert sim[0][0] == pytest.approx(1.0, abs=1e-6)
        assert sim[0][1] == pytest.approx(0.0, abs=1e-6)
        assert sim[0][2] == pytest.approx(-1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Localize with mocked model
# ---------------------------------------------------------------------------


class TestLocalize:
    """Tests for localize() with mocked sentence-transformer model."""

    def test_localize_returns_sorted_candidates(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Localize should return candidates sorted by descending score."""
        functions = localizer.extract_functions(tmp_repo)
        n = len(functions)

        # Mock model.encode to return predictable embeddings
        mock_model = MagicMock()
        # Task embedding: unit vector in dim 0
        mock_model.encode = MagicMock(side_effect=[
            np.array([[1.0, 0.0, 0.0, 0.0]]),  # task embedding
            np.random.randn(n, 4),  # function embeddings
        ])
        localizer._model = mock_model

        task = BenchmarkTask(
            id="task-001",
            project="test",
            category="ml_lib.linear_model",
            description="ridge regression",
            test_code="def test_x(): pass",
        )

        results = localizer.localize(task, tmp_repo, top_k=3, functions=functions)
        assert len(results) <= 3

        # Scores should be descending
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_localize_empty_repo(
        self, localizer: FunctionLocalizer, tmp_path: Path
    ) -> None:
        """Localizing in an empty repo should return empty list."""
        task = BenchmarkTask(
            id="task-001",
            project="test",
            category="cat",
            description="desc",
            test_code="def test_x(): pass",
        )

        results = localizer.localize(task, tmp_path, top_k=5)
        assert results == []

    def test_localize_returns_function_score_tuples(
        self, localizer: FunctionLocalizer, tmp_repo: Path
    ) -> None:
        """Each result should be a (FunctionSignature, float) tuple."""
        functions = localizer.extract_functions(tmp_repo)
        n = len(functions)

        mock_model = MagicMock()
        mock_model.encode = MagicMock(side_effect=[
            np.array([[1.0, 0.0]]),
            np.random.randn(n, 2),
        ])
        localizer._model = mock_model

        task = BenchmarkTask(
            id="task-001",
            project="test",
            category="cat",
            description="desc",
            test_code="def test_x(): pass",
        )

        results = localizer.localize(task, tmp_repo, top_k=2, functions=functions)
        for func, score in results:
            assert isinstance(func, FunctionSignature)
            assert isinstance(score, float)


# ---------------------------------------------------------------------------
# Import error handling
# ---------------------------------------------------------------------------


class TestImportHandling:
    """Tests for graceful handling when sentence-transformers is missing."""

    def test_import_error_when_unavailable(self) -> None:
        """Should raise ImportError when sentence-transformers is not installed."""
        with patch("zerorepo.evaluation.localization._ST_AVAILABLE", False):
            with pytest.raises(ImportError, match="sentence-transformers"):
                FunctionLocalizer()
