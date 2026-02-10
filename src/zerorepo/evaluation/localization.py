"""Stage 1: Function localization using embedding-based similarity search.

Maps task descriptions to candidate functions in generated repositories
using sentence-transformer embeddings and cosine similarity.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from zerorepo.evaluation.models import BenchmarkTask, FunctionSignature

logger = logging.getLogger(__name__)

# Lazy import for sentence_transformers
try:
    from sentence_transformers import SentenceTransformer

    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


class FunctionLocalizer:
    """Locates candidate functions in generated repos using embedding similarity."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if not _ST_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required. Install: pip install sentence-transformers"
            )
        self._model_name = model_name
        self._model: Any = None  # Lazy load

    @property
    def model(self) -> Any:
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def extract_functions(self, repo_path: str | Path) -> list[FunctionSignature]:
        """Extract all function/class signatures from Python files in repo."""
        repo_path = Path(repo_path)
        functions: list[FunctionSignature] = []

        for py_file in sorted(repo_path.rglob("*.py")):
            if py_file.name.startswith("test_") or "test" in py_file.parts:
                continue  # Skip test files

            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning(f"Skipping {py_file}: {e}")
                continue

            rel_path = str(py_file.relative_to(repo_path))
            module = rel_path.replace("/", ".").replace(".py", "")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = self._build_signature(node, source, module, rel_path)
                    if sig:
                        functions.append(sig)
                elif isinstance(node, ast.ClassDef):
                    # Extract class methods too
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            class_module = f"{module}.{node.name}"
                            sig = self._build_signature(
                                item, source, class_module, rel_path
                            )
                            if sig:
                                functions.append(sig)

        logger.info(f"Extracted {len(functions)} functions from {repo_path}")
        return functions

    def _build_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
        module: str,
        file_path: str,
    ) -> FunctionSignature | None:
        """Build FunctionSignature from AST node."""
        try:
            # Build signature string
            args = (
                ast.get_source_segment(source, node.args)
                if hasattr(ast, "get_source_segment")
                else ""
            )
            if not args:
                # Fallback: reconstruct from args
                arg_names = [a.arg for a in node.args.args]
                args = ", ".join(arg_names)

            prefix = (
                "async def"
                if isinstance(node, ast.AsyncFunctionDef)
                else "def"
            )
            signature = f"{prefix} {node.name}({args})"

            # Get docstring
            docstring = ast.get_docstring(node) or ""

            # Get body source
            source_lines = source.splitlines()
            body_lines = source_lines[
                node.lineno - 1 : node.end_lineno or node.lineno
            ]
            body = "\n".join(body_lines)

            return FunctionSignature(
                name=node.name,
                module=module,
                signature=signature,
                docstring=docstring.split("\n")[0] if docstring else "",
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                body=body,
            )
        except Exception as e:
            logger.debug(f"Could not build signature for {node.name}: {e}")
            return None

    def localize(
        self,
        task: BenchmarkTask,
        repo_path: str | Path,
        top_k: int = 5,
        functions: list[FunctionSignature] | None = None,
    ) -> list[tuple[FunctionSignature, float]]:
        """Find top-k candidate functions matching the task description.

        Args:
            task: The benchmark task to localize
            repo_path: Path to the generated repository
            top_k: Number of top candidates to return
            functions: Pre-extracted functions (optional, avoids re-extraction)

        Returns:
            List of (function, similarity_score) tuples sorted by score descending
        """
        if functions is None:
            functions = self.extract_functions(repo_path)

        if not functions:
            logger.warning(f"No functions found in {repo_path}")
            return []

        # Create embeddings
        task_text = f"{task.description} {task.category} {task.subcategory}"
        func_texts = [
            f"{f.name} {f.signature} {f.docstring} {f.module}" for f in functions
        ]

        task_embedding = self.model.encode([task_text])
        func_embeddings = self.model.encode(func_texts)

        # Compute cosine similarities
        similarities = self._cosine_similarity(task_embedding, func_embeddings)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        return [(functions[i], float(similarities[i])) for i in top_indices]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between arrays."""
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
        return a_norm @ b_norm.T
