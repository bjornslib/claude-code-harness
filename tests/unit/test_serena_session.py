"""Unit tests for SerenaSession protocol and FileBasedCodebaseAnalyzer.

Tests cover:
- CodebaseAnalyzerProtocol conformance
- FileBasedCodebaseAnalyzer symbol extraction via ast
- Directory listing (flat and recursive)
- Symbol search and reference finding
- Pattern search
- Activation and error handling
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from zerorepo.serena.session import (
    ActivationResult,
    CodebaseAnalyzerProtocol,
    DirectoryEntry,
    FileBasedCodebaseAnalyzer,
    SymbolEntry,
    _build_function_signature,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project structure for testing.

    Layout::

        tmp_path/
        ├── mypackage/
        │   ├── __init__.py
        │   ├── core.py         # Classes and functions
        │   └── utils/
        │       ├── __init__.py
        │       └── helpers.py  # Helper functions
        └── standalone.py       # Standalone file (no package)
    """
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""My package."""\n\n__version__ = "1.0.0"\n'
    )
    (pkg / "core.py").write_text(
        textwrap.dedent("""\
        \"\"\"Core module.\"\"\"

        from typing import Any


        class BaseProcessor:
            \"\"\"Base processor class.\"\"\"

            def process(self, data: list[str]) -> dict[str, Any]:
                \"\"\"Process input data.\"\"\"
                return {"items": data}

            def validate(self, item: str) -> bool:
                return len(item) > 0


        class AdvancedProcessor(BaseProcessor):
            \"\"\"Advanced processor with extra features.\"\"\"

            def transform(self, data: list[str], *, reverse: bool = False) -> list[str]:
                if reverse:
                    return list(reversed(data))
                return data


        def create_processor(kind: str = "base") -> BaseProcessor:
            \"\"\"Factory function for processors.\"\"\"
            if kind == "advanced":
                return AdvancedProcessor()
            return BaseProcessor()


        async def async_process(data: list[str]) -> dict[str, Any]:
            \"\"\"Async processing function.\"\"\"
            return {"items": data, "async": True}
        """)
    )

    utils = pkg / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("")
    (utils / "helpers.py").write_text(
        textwrap.dedent("""\
        \"\"\"Helper utilities.\"\"\"


        def format_output(items: list[str], separator: str = ", ") -> str:
            \"\"\"Format a list of items into a string.\"\"\"
            return separator.join(items)


        def parse_input(raw: str) -> list[str]:
            \"\"\"Parse raw input into a list.\"\"\"
            return [s.strip() for s in raw.split(",")]
        """)
    )

    (tmp_path / "standalone.py").write_text(
        textwrap.dedent("""\
        \"\"\"A standalone script.\"\"\"


        def main() -> None:
            print("Hello, world!")
        """)
    )

    return tmp_path


@pytest.fixture
def activated_analyzer(sample_project: Path) -> FileBasedCodebaseAnalyzer:
    """Return an analyzer already activated for the sample project."""
    analyzer = FileBasedCodebaseAnalyzer()
    result = analyzer.activate(sample_project)
    assert result.success
    return analyzer


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify FileBasedCodebaseAnalyzer implements CodebaseAnalyzerProtocol."""

    def test_is_instance_of_protocol(self) -> None:
        analyzer = FileBasedCodebaseAnalyzer()
        assert isinstance(analyzer, CodebaseAnalyzerProtocol)

    def test_has_all_protocol_methods(self) -> None:
        analyzer = FileBasedCodebaseAnalyzer()
        assert callable(getattr(analyzer, "activate", None))
        assert callable(getattr(analyzer, "list_directory", None))
        assert callable(getattr(analyzer, "get_symbols", None))
        assert callable(getattr(analyzer, "find_symbol", None))
        assert callable(getattr(analyzer, "find_references", None))
        assert callable(getattr(analyzer, "search_pattern", None))


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


class TestActivation:
    """Tests for the activate method."""

    def test_activate_valid_directory(self, sample_project: Path) -> None:
        analyzer = FileBasedCodebaseAnalyzer()
        result = analyzer.activate(sample_project)
        assert isinstance(result, ActivationResult)
        assert result.success is True
        assert result.project_root == str(sample_project.resolve())

    def test_activate_nonexistent_directory(self, tmp_path: Path) -> None:
        analyzer = FileBasedCodebaseAnalyzer()
        result = analyzer.activate(tmp_path / "does_not_exist")
        assert result.success is False
        assert "error" in result.details

    def test_activate_file_instead_of_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "a_file.txt"
        f.write_text("hello")
        analyzer = FileBasedCodebaseAnalyzer()
        result = analyzer.activate(f)
        assert result.success is False

    def test_not_activated_raises(self) -> None:
        analyzer = FileBasedCodebaseAnalyzer()
        with pytest.raises(RuntimeError, match="not activated"):
            analyzer.list_directory(".")


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------


class TestListDirectory:
    """Tests for the list_directory method."""

    def test_list_root(
        self, activated_analyzer: FileBasedCodebaseAnalyzer, sample_project: Path
    ) -> None:
        entries = activated_analyzer.list_directory(".")
        names = {e.name for e in entries}
        assert "mypackage" in names
        assert "standalone.py" in names
        # Hidden dirs and __pycache__ should be excluded
        assert "__pycache__" not in names

    def test_list_package_dir(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        entries = activated_analyzer.list_directory("mypackage")
        names = {e.name for e in entries}
        assert "__init__.py" in names
        assert "core.py" in names
        assert "utils" in names

    def test_list_nonexistent_dir(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        entries = activated_analyzer.list_directory("does_not_exist")
        assert entries == []

    def test_list_recursive(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        entries = activated_analyzer.list_directory("mypackage", recursive=True)
        paths = {e.path for e in entries}
        # Should contain files from nested utils/ too
        assert any("helpers.py" in p for p in paths)

    def test_directory_entry_is_dir_flag(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        entries = activated_analyzer.list_directory(".")
        dir_entries = [e for e in entries if e.is_dir]
        file_entries = [e for e in entries if not e.is_dir]
        dir_names = {e.name for e in dir_entries}
        file_names = {e.name for e in file_entries}
        assert "mypackage" in dir_names
        assert "standalone.py" in file_names


# ---------------------------------------------------------------------------
# get_symbols
# ---------------------------------------------------------------------------


class TestGetSymbols:
    """Tests for the get_symbols method."""

    def test_extract_classes_and_functions(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        names = [s.name for s in symbols]
        # Top-level symbols
        assert "BaseProcessor" in names
        assert "AdvancedProcessor" in names
        assert "create_processor" in names
        assert "async_process" in names

    def test_class_methods_included(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        method_names = [s.name for s in symbols if s.kind == "method"]
        assert "BaseProcessor.process" in method_names
        assert "BaseProcessor.validate" in method_names
        assert "AdvancedProcessor.transform" in method_names

    def test_symbol_kinds(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        kinds = {s.name: s.kind for s in symbols}
        assert kinds["BaseProcessor"] == "class"
        assert kinds["create_processor"] == "function"

    def test_symbol_has_line_number(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        for sym in symbols:
            assert sym.line >= 1

    def test_symbol_has_signature(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        for sym in symbols:
            assert sym.signature is not None, f"{sym.name} missing signature"

    def test_class_signature_includes_bases(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        adv = next(s for s in symbols if s.name == "AdvancedProcessor")
        assert "BaseProcessor" in adv.signature

    def test_function_signature_with_defaults(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        factory = next(s for s in symbols if s.name == "create_processor")
        assert 'kind' in factory.signature
        assert '"base"' in factory.signature or "'base'" in factory.signature

    def test_async_function_signature(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        async_fn = next(s for s in symbols if s.name == "async_process")
        assert async_fn.signature.startswith("async def")

    def test_docstrings_extracted(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/core.py")
        bp = next(s for s in symbols if s.name == "BaseProcessor")
        assert bp.docstring is not None
        assert "Base processor" in bp.docstring

    def test_nonexistent_file(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("no_such_file.py")
        assert symbols == []

    def test_non_python_file(
        self, activated_analyzer: FileBasedCodebaseAnalyzer, sample_project: Path
    ) -> None:
        (sample_project / "readme.md").write_text("# Readme")
        symbols = activated_analyzer.get_symbols("readme.md")
        assert symbols == []

    def test_empty_init_file(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        symbols = activated_analyzer.get_symbols("mypackage/utils/__init__.py")
        assert symbols == []


# ---------------------------------------------------------------------------
# find_symbol
# ---------------------------------------------------------------------------


class TestFindSymbol:
    """Tests for the find_symbol method."""

    def test_find_class_by_exact_name(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.find_symbol("BaseProcessor")
        assert len(results) >= 1
        assert any(s.name == "BaseProcessor" for s in results)

    def test_find_function_by_name(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.find_symbol("format_output")
        assert len(results) >= 1
        assert results[0].kind == "function"

    def test_find_nonexistent_symbol(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.find_symbol("NoSuchSymbol12345")
        assert results == []


# ---------------------------------------------------------------------------
# find_references
# ---------------------------------------------------------------------------


class TestFindReferences:
    """Tests for the find_references method."""

    def test_find_reference_to_class(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.find_references("BaseProcessor")
        # BaseProcessor is referenced in create_processor's return type and body
        assert len(results) >= 1

    def test_find_no_references(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.find_references("UnusedSymbol12345")
        assert results == []


# ---------------------------------------------------------------------------
# search_pattern
# ---------------------------------------------------------------------------


class TestSearchPattern:
    """Tests for the search_pattern method."""

    def test_search_simple_pattern(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.search_pattern("def main")
        assert len(results) >= 1
        assert any(r["file"] == "standalone.py" for r in results)

    def test_search_regex_pattern(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.search_pattern(r"class \w+Processor")
        assert len(results) >= 2  # BaseProcessor and AdvancedProcessor

    def test_search_invalid_regex(
        self, activated_analyzer: FileBasedCodebaseAnalyzer
    ) -> None:
        results = activated_analyzer.search_pattern("[invalid")
        assert results == []


# ---------------------------------------------------------------------------
# _build_function_signature helper
# ---------------------------------------------------------------------------


class TestBuildFunctionSignature:
    """Tests for the _build_function_signature helper."""

    def test_simple_function(self) -> None:
        import ast

        tree = ast.parse("def foo(x: int) -> str: pass")
        func = tree.body[0]
        sig = _build_function_signature(func)
        assert sig == "def foo(x: int) -> str"

    def test_function_with_defaults(self) -> None:
        import ast

        tree = ast.parse("def bar(a, b: int = 5): pass")
        func = tree.body[0]
        sig = _build_function_signature(func)
        assert "b: int = 5" in sig

    def test_async_function(self) -> None:
        import ast

        tree = ast.parse("async def baz(x): pass")
        func = tree.body[0]
        sig = _build_function_signature(func)
        assert sig.startswith("async def")

    def test_varargs_and_kwargs(self) -> None:
        import ast

        tree = ast.parse("def qux(*args, **kwargs): pass")
        func = tree.body[0]
        sig = _build_function_signature(func)
        assert "*args" in sig
        assert "**kwargs" in sig
