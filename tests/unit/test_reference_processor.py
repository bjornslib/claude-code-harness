"""Unit tests for the Reference Material Processor (Task 2.4.3).

Tests cover:
- ProcessorConfig validation
- Content extraction strategies (inline, code, PDF)
- Concept extraction via LLM (mocked)
- Concept cleaning and deduplication
- Response parsing (JSON + fallback)
- Full pipeline: extract_concepts, process_spec_references
- Error handling
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zerorepo.spec_parser.models import (
    ReferenceMaterial,
    ReferenceMaterialType,
    RepositorySpec,
)
from zerorepo.spec_parser.reference_processor import (
    CodeContentExtractor,
    ConceptExtractionError,
    ConceptExtractionResponse,
    ContentExtractor,
    ExtractionError,
    ExtractionResult,
    InlineContentExtractor,
    PDFContentExtractor,
    ProcessorConfig,
    ReferenceProcessor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ref(
    type_: ReferenceMaterialType = ReferenceMaterialType.API_DOCUMENTATION,
    content: str | None = "Sample API content about GridSearchCV and Pipeline",
    url: str | None = None,
    title: str | None = None,
) -> ReferenceMaterial:
    """Helper to create a ReferenceMaterial for tests."""
    kwargs: dict[str, Any] = {"type": type_}
    if content is not None:
        kwargs["content"] = content
    if url is not None:
        kwargs["url"] = url
    if title is not None:
        kwargs["title"] = title
    return ReferenceMaterial(**kwargs)


def _make_mock_gateway(
    response: str = '{"concepts": ["GridSearchCV", "Pipeline", "cross_val_score"]}',
    model: str = "gpt-4o-mini",
) -> MagicMock:
    """Create a mock LLM gateway that returns a canned response."""
    gateway = MagicMock()
    gateway.complete.return_value = response
    gateway.select_model.return_value = model
    return gateway


# ---------------------------------------------------------------------------
# ProcessorConfig Tests
# ---------------------------------------------------------------------------


class TestProcessorConfig:
    """Test ProcessorConfig validation."""

    def test_defaults(self) -> None:
        """Default config has sensible values."""
        config = ProcessorConfig()
        assert config.max_text_length == 50_000
        assert config.max_concepts == 30
        assert config.min_concept_length == 2
        assert config.llm_model is None
        assert config.deduplicate_concepts is True

    def test_custom_values(self) -> None:
        """Custom values are accepted."""
        config = ProcessorConfig(
            max_text_length=10_000,
            max_concepts=50,
            min_concept_length=3,
            llm_model="gpt-4o-mini",
            deduplicate_concepts=False,
        )
        assert config.max_text_length == 10_000
        assert config.max_concepts == 50
        assert config.llm_model == "gpt-4o-mini"

    def test_max_text_length_minimum(self) -> None:
        """max_text_length must be >= 100."""
        with pytest.raises(ValidationError, match="greater than or equal to 100"):
            ProcessorConfig(max_text_length=99)

    def test_max_concepts_minimum(self) -> None:
        """max_concepts must be >= 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ProcessorConfig(max_concepts=0)

    def test_max_concepts_maximum(self) -> None:
        """max_concepts must be <= 200."""
        with pytest.raises(ValidationError, match="less than or equal to 200"):
            ProcessorConfig(max_concepts=201)


# ---------------------------------------------------------------------------
# ExtractionResult Tests
# ---------------------------------------------------------------------------


class TestExtractionResult:
    """Test ExtractionResult model."""

    def test_create(self) -> None:
        """Create an ExtractionResult."""
        result = ExtractionResult(
            text="Hello world",
            char_count=11,
            method="inline",
        )
        assert result.text == "Hello world"
        assert result.char_count == 11
        assert result.method == "inline"
        assert result.was_truncated is False
        assert result.metadata == {}

    def test_truncated(self) -> None:
        """Create a truncated ExtractionResult."""
        result = ExtractionResult(
            text="Hello...",
            char_count=8,
            method="pdf",
            was_truncated=True,
            metadata={"page_count": 5},
        )
        assert result.was_truncated is True
        assert result.metadata["page_count"] == 5


# ---------------------------------------------------------------------------
# ConceptExtractionResponse Tests
# ---------------------------------------------------------------------------


class TestConceptExtractionResponse:
    """Test ConceptExtractionResponse model."""

    def test_create(self) -> None:
        """Create a ConceptExtractionResponse."""
        resp = ConceptExtractionResponse(
            concepts=["GridSearchCV", "Pipeline"],
        )
        assert resp.concepts == ["GridSearchCV", "Pipeline"]

    def test_empty(self) -> None:
        """Empty concepts list is valid."""
        resp = ConceptExtractionResponse(concepts=[])
        assert resp.concepts == []


# ---------------------------------------------------------------------------
# InlineContentExtractor Tests
# ---------------------------------------------------------------------------


class TestInlineContentExtractor:
    """Test InlineContentExtractor strategy."""

    def test_can_handle_with_content(self) -> None:
        """Can handle references with inline content."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content="some content")
        assert extractor.can_handle(ref) is True

    def test_cannot_handle_without_content(self) -> None:
        """Cannot handle references without content."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content=None, url="https://example.com")
        assert extractor.can_handle(ref) is False

    def test_cannot_handle_empty_content(self) -> None:
        """Cannot handle references with empty/whitespace content."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content="   ", url="https://example.com")
        assert extractor.can_handle(ref) is False

    def test_extract_returns_content(self) -> None:
        """Extract returns the inline content."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content="GridSearchCV enables hyperparameter tuning")
        result = extractor.extract(ref)
        assert result.text == "GridSearchCV enables hyperparameter tuning"
        assert result.method == "inline"
        assert result.was_truncated is False

    def test_extract_truncates_long_content(self) -> None:
        """Extract truncates content exceeding max_length."""
        extractor = InlineContentExtractor()
        long_content = "x" * 60_000
        ref = _make_ref(content=long_content)
        result = extractor.extract(ref, max_length=100)
        assert len(result.text) == 100
        assert result.was_truncated is True

    def test_extract_strips_whitespace(self) -> None:
        """Extract strips leading/trailing whitespace."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content="  hello world  ")
        result = extractor.extract(ref)
        assert result.text == "hello world"

    def test_extract_no_content_raises(self) -> None:
        """Extract raises if no inline content is available."""
        extractor = InlineContentExtractor()
        ref = _make_ref(content=None, url="https://example.com")
        with pytest.raises(ExtractionError, match="no inline content"):
            extractor.extract(ref)


# ---------------------------------------------------------------------------
# CodeContentExtractor Tests
# ---------------------------------------------------------------------------


class TestCodeContentExtractor:
    """Test CodeContentExtractor strategy."""

    def test_can_handle_code_sample(self) -> None:
        """Can handle CODE_SAMPLE references with content."""
        extractor = CodeContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content="def hello(): pass",
        )
        assert extractor.can_handle(ref) is True

    def test_cannot_handle_api_docs(self) -> None:
        """Cannot handle non-CODE_SAMPLE references."""
        extractor = CodeContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.API_DOCUMENTATION,
            content="def hello(): pass",
        )
        assert extractor.can_handle(ref) is False

    def test_cannot_handle_code_without_content(self) -> None:
        """Cannot handle CODE_SAMPLE without content."""
        extractor = CodeContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content=None,
            url="https://example.com",
        )
        assert extractor.can_handle(ref) is False

    def test_extract_python_code(self) -> None:
        """Extract identifies Python functions and classes."""
        extractor = CodeContentExtractor()
        code = """
import os
from pathlib import Path

class DataLoader:
    def load(self, path: str):
        pass

def process_batch(items):
    pass

async def fetch_data():
    pass
"""
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content=code,
        )
        result = extractor.extract(ref)
        assert result.method == "code"
        assert "DataLoader" in result.text
        assert "load" in result.text
        assert "process_batch" in result.text
        assert "fetch_data" in result.text
        assert result.metadata.get("identifiers_found", 0) > 0

    def test_extract_javascript_code(self) -> None:
        """Extract identifies JavaScript functions and classes."""
        extractor = CodeContentExtractor()
        code = """
import React from 'react';
import { useState } from 'react';

export class UserProfile extends React.Component {
    render() {}
}

const handleSubmit = async (e) => {
    e.preventDefault();
};

function validateForm(data) {
    return true;
}
"""
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content=code,
        )
        result = extractor.extract(ref)
        assert result.method == "code"
        assert "UserProfile" in result.text

    def test_extract_empty_code_raises(self) -> None:
        """Extract raises for empty code content."""
        extractor = CodeContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content="   ",
            url="https://example.com",
        )
        # can_handle returns False for whitespace-only content
        assert extractor.can_handle(ref) is False


# ---------------------------------------------------------------------------
# PDFContentExtractor Tests
# ---------------------------------------------------------------------------


class TestPDFContentExtractor:
    """Test PDFContentExtractor strategy."""

    def test_can_handle_research_paper(self) -> None:
        """Can handle RESEARCH_PAPER references."""
        extractor = PDFContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.RESEARCH_PAPER,
            content="Paper abstract...",
        )
        assert extractor.can_handle(ref) is True

    def test_can_handle_pdf_url(self) -> None:
        """Can handle references with .pdf URLs."""
        extractor = PDFContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.OTHER,
            url="https://example.com/paper.pdf",
            content="Some content",
        )
        assert extractor.can_handle(ref) is True

    def test_cannot_handle_non_pdf(self) -> None:
        """Cannot handle non-PDF, non-research-paper references."""
        extractor = PDFContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.API_DOCUMENTATION,
            content="API docs",
        )
        assert extractor.can_handle(ref) is False

    def test_extract_inline_content(self) -> None:
        """PDF extractor uses inline content when available."""
        extractor = PDFContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.RESEARCH_PAPER,
            content="This paper presents a novel approach to...",
        )
        result = extractor.extract(ref)
        assert result.method == "pdf_content"
        assert "novel approach" in result.text

    def test_extract_no_content_no_file_raises(self) -> None:
        """PDF extractor raises if no content and no file:// URL."""
        extractor = PDFContentExtractor()
        ref = _make_ref(
            type_=ReferenceMaterialType.RESEARCH_PAPER,
            content=None,
            url="https://example.com/paper.pdf",
        )
        with pytest.raises(ExtractionError, match="requires either"):
            extractor.extract(ref)


# ---------------------------------------------------------------------------
# ReferenceProcessor Tests
# ---------------------------------------------------------------------------


class TestReferenceProcessorInit:
    """Test ReferenceProcessor initialization."""

    def test_default_extractors(self) -> None:
        """Default extractors include code, PDF, and inline."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(llm_gateway=gateway)
        extractor_types = [type(e) for e in processor.extractors]
        assert CodeContentExtractor in extractor_types
        assert PDFContentExtractor in extractor_types
        assert InlineContentExtractor in extractor_types

    def test_custom_extractors(self) -> None:
        """Custom extractors override defaults."""
        gateway = _make_mock_gateway()
        custom = [InlineContentExtractor()]
        processor = ReferenceProcessor(llm_gateway=gateway, extractors=custom)
        assert len(processor.extractors) == 1

    def test_custom_config(self) -> None:
        """Custom config is used."""
        gateway = _make_mock_gateway()
        config = ProcessorConfig(max_concepts=10)
        processor = ReferenceProcessor(llm_gateway=gateway, config=config)
        assert processor.config.max_concepts == 10


class TestReferenceProcessorExtractContent:
    """Test ReferenceProcessor.extract_content()."""

    def test_extract_inline(self) -> None:
        """Extract content from inline reference."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(llm_gateway=gateway)
        ref = _make_ref(content="API documentation text")
        result = processor.extract_content(ref)
        assert result.method == "inline"
        assert "API documentation" in result.text

    def test_extract_code_sample(self) -> None:
        """Extract content from code sample (uses CodeContentExtractor)."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(llm_gateway=gateway)
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content="def hello(): pass",
        )
        result = processor.extract_content(ref)
        assert result.method == "code"

    def test_extract_no_extractor_raises(self) -> None:
        """Raise ExtractionError if no extractor can handle reference."""
        gateway = _make_mock_gateway()
        # Use empty extractor list
        processor = ReferenceProcessor(
            llm_gateway=gateway, extractors=[]
        )
        ref = _make_ref(content="Some content")
        with pytest.raises(ExtractionError, match="No content extractor"):
            processor.extract_content(ref)


class TestReferenceProcessorConceptExtraction:
    """Test ReferenceProcessor.extract_concepts()."""

    def test_extract_concepts_json_response(self) -> None:
        """Extract concepts from a well-formed JSON LLM response."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["GridSearchCV", "Pipeline", "cross_val_score"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(content="scikit-learn GridSearchCV and Pipeline docs")
        concepts = processor.extract_concepts(ref)
        assert "GridSearchCV" in concepts
        assert "Pipeline" in concepts
        assert "cross_val_score" in concepts
        # Also updated on the reference
        assert ref.extracted_concepts == concepts

    def test_extract_concepts_json_with_code_fence(self) -> None:
        """Handle JSON wrapped in markdown code fences."""
        gateway = _make_mock_gateway(
            response='```json\n{"concepts": ["React", "useState"]}\n```'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(content="React hooks documentation")
        concepts = processor.extract_concepts(ref)
        assert "React" in concepts
        assert "useState" in concepts

    def test_extract_concepts_fallback_bullet_list(self) -> None:
        """Fall back to line-based parsing for non-JSON responses."""
        gateway = _make_mock_gateway(
            response="- GridSearchCV\n- Pipeline\n- cross_val_score"
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(content="scikit-learn documentation")
        concepts = processor.extract_concepts(ref)
        assert "GridSearchCV" in concepts
        assert "Pipeline" in concepts

    def test_extract_concepts_deduplication(self) -> None:
        """Duplicate concepts are removed (case-insensitive)."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["React", "react", "REACT", "Vue"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(content="Frontend frameworks")
        concepts = processor.extract_concepts(ref)
        # Only one React variant should survive
        react_count = sum(1 for c in concepts if c.lower() == "react")
        assert react_count == 1
        assert "Vue" in concepts

    def test_extract_concepts_max_limit(self) -> None:
        """Concepts are capped at max_concepts."""
        many_concepts = [f"concept_{i}" for i in range(50)]
        gateway = _make_mock_gateway(
            response=f'{{"concepts": {json.dumps(many_concepts)}}}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini", max_concepts=5),
        )
        ref = _make_ref(content="Lots of concepts")
        concepts = processor.extract_concepts(ref)
        assert len(concepts) <= 5

    def test_extract_concepts_min_length_filter(self) -> None:
        """Short concepts below min_concept_length are filtered out."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["a", "OK", "GridSearchCV"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(
                llm_model="gpt-4o-mini", min_concept_length=2
            ),
        )
        ref = _make_ref(content="Mixed concepts")
        concepts = processor.extract_concepts(ref)
        assert "a" not in concepts  # too short
        assert "OK" in concepts
        assert "GridSearchCV" in concepts

    def test_extract_concepts_llm_failure_raises(self) -> None:
        """LLM call failure raises ConceptExtractionError."""
        gateway = _make_mock_gateway()
        gateway.complete.side_effect = RuntimeError("API error")
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(content="Some content")
        with pytest.raises(ConceptExtractionError, match="LLM call failed"):
            processor.extract_concepts(ref)

    def test_extract_concepts_extraction_failure_raises(self) -> None:
        """Content extraction failure raises ExtractionError."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(
            llm_gateway=gateway, extractors=[]
        )
        ref = _make_ref(content="Content")
        with pytest.raises(ExtractionError):
            processor.extract_concepts(ref)


class TestReferenceProcessorFromText:
    """Test ReferenceProcessor.extract_concepts_from_text()."""

    def test_extract_from_text(self) -> None:
        """Extract concepts from raw text."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["REST API", "authentication"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        concepts = processor.extract_concepts_from_text(
            "Build a REST API with authentication"
        )
        assert "REST API" in concepts

    def test_extract_from_empty_text(self) -> None:
        """Empty text returns empty list."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        concepts = processor.extract_concepts_from_text("   ")
        assert concepts == []


class TestReferenceProcessorBatch:
    """Test ReferenceProcessor.process_spec_references()."""

    def test_process_spec_references(self) -> None:
        """Process all references in a spec."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["concept_a", "concept_b"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        spec = RepositorySpec(
            description="Build a web application with authentication and database",
            references=[
                _make_ref(content="First reference material"),
                _make_ref(content="Second reference material"),
            ],
        )
        results = processor.process_spec_references(spec)
        assert len(results) == 2
        for ref_id, concepts in results.items():
            assert len(concepts) > 0

    def test_process_spec_references_handles_failures(self) -> None:
        """Failed references get empty concept lists."""
        gateway = _make_mock_gateway()
        # Make gateway fail
        gateway.complete.side_effect = RuntimeError("API error")
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        spec = RepositorySpec(
            description="Build a web application with authentication and database",
            references=[
                _make_ref(content="Reference content"),
            ],
        )
        results = processor.process_spec_references(spec)
        assert len(results) == 1
        # Failed reference gets empty concepts
        for ref_id, concepts in results.items():
            assert concepts == []

    def test_process_spec_no_references(self) -> None:
        """Spec with no references returns empty dict."""
        gateway = _make_mock_gateway()
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        spec = RepositorySpec(
            description="Build a simple web application with no references needed",
        )
        results = processor.process_spec_references(spec)
        assert results == {}


# ---------------------------------------------------------------------------
# Response Parsing Tests
# ---------------------------------------------------------------------------


class TestResponseParsing:
    """Test the internal response parsing methods."""

    def _make_processor(self) -> ReferenceProcessor:
        """Create a processor for testing parse methods."""
        gateway = _make_mock_gateway()
        return ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )

    def test_parse_valid_json(self) -> None:
        """Parse valid JSON with concepts key."""
        proc = self._make_processor()
        result = proc._parse_concepts_response(
            '{"concepts": ["a", "b", "c"]}'
        )
        assert result == ["a", "b", "c"]

    def test_parse_json_plain_list(self) -> None:
        """Parse a plain JSON list (no concepts key)."""
        proc = self._make_processor()
        result = proc._parse_concepts_response('["a", "b"]')
        assert result == ["a", "b"]

    def test_parse_json_with_code_fence(self) -> None:
        """Parse JSON wrapped in code fences."""
        proc = self._make_processor()
        result = proc._parse_concepts_response(
            '```json\n{"concepts": ["x", "y"]}\n```'
        )
        assert result == ["x", "y"]

    def test_parse_bullet_list(self) -> None:
        """Parse bullet-point list."""
        proc = self._make_processor()
        result = proc._parse_concepts_response(
            "- React\n- Vue\n- Angular"
        )
        assert "React" in result
        assert "Vue" in result
        assert "Angular" in result

    def test_parse_numbered_list(self) -> None:
        """Parse numbered list."""
        proc = self._make_processor()
        result = proc._parse_concepts_response(
            "1. React\n2. Vue\n3. Angular"
        )
        assert "React" in result
        assert "Vue" in result

    def test_parse_comma_separated(self) -> None:
        """Parse comma-separated list."""
        proc = self._make_processor()
        result = proc._parse_concepts_response(
            "React, Vue, Angular, Svelte"
        )
        assert "React" in result
        assert "Svelte" in result

    def test_parse_empty_response(self) -> None:
        """Parse empty response returns empty list."""
        proc = self._make_processor()
        result = proc._parse_concepts_response("")
        assert result == []


# ---------------------------------------------------------------------------
# Concept Cleaning Tests
# ---------------------------------------------------------------------------


class TestConceptCleaning:
    """Test the _clean_concepts method."""

    def _make_processor(
        self, **config_kwargs: Any
    ) -> ReferenceProcessor:
        """Create a processor with custom config for cleaning tests."""
        gateway = _make_mock_gateway()
        config = ProcessorConfig(llm_model="gpt-4o-mini", **config_kwargs)
        return ReferenceProcessor(llm_gateway=gateway, config=config)

    def test_strips_whitespace_and_quotes(self) -> None:
        """Concepts are stripped of whitespace and quotes."""
        proc = self._make_processor()
        result = proc._clean_concepts(
            ['  "React"  ', "'Vue'", "`Angular`"]
        )
        assert result == ["React", "Vue", "Angular"]

    def test_deduplication_case_insensitive(self) -> None:
        """Deduplication is case-insensitive."""
        proc = self._make_processor()
        result = proc._clean_concepts(["React", "react", "REACT"])
        assert len(result) == 1
        assert result[0] == "React"  # First one wins

    def test_no_deduplication_when_disabled(self) -> None:
        """No deduplication when disabled."""
        proc = self._make_processor(deduplicate_concepts=False)
        result = proc._clean_concepts(["React", "react"])
        assert len(result) == 2

    def test_min_length_filter(self) -> None:
        """Concepts below min length are filtered."""
        proc = self._make_processor(min_concept_length=3)
        result = proc._clean_concepts(["a", "ab", "abc", "abcd"])
        assert result == ["abc", "abcd"]

    def test_max_concepts_limit(self) -> None:
        """Concepts are capped at max_concepts."""
        proc = self._make_processor(max_concepts=2)
        result = proc._clean_concepts(["a1", "b2", "c3", "d4"])
        assert len(result) == 2

    def test_empty_concepts_filtered(self) -> None:
        """Empty strings are filtered out."""
        proc = self._make_processor()
        result = proc._clean_concepts(["", "  ", "React"])
        assert result == ["React"]


# ---------------------------------------------------------------------------
# Import for json (used in test)
# ---------------------------------------------------------------------------

import json


# ---------------------------------------------------------------------------
# Integration-like Tests
# ---------------------------------------------------------------------------


class TestReferenceProcessorIntegration:
    """Test full processing pipeline with mocked LLM."""

    def test_api_docs_pipeline(self) -> None:
        """Full pipeline for API documentation."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["GridSearchCV", "Pipeline", "cross_val_score", "RandomForestClassifier"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(
            type_=ReferenceMaterialType.API_DOCUMENTATION,
            content="scikit-learn provides GridSearchCV for hyperparameter tuning, "
            "Pipeline for workflow composition, cross_val_score for model evaluation, "
            "and RandomForestClassifier for ensemble learning.",
            title="scikit-learn API Reference",
        )
        concepts = processor.extract_concepts(ref)
        assert len(concepts) == 4
        assert "GridSearchCV" in concepts
        assert ref.extracted_concepts == concepts

    def test_code_sample_pipeline(self) -> None:
        """Full pipeline for code sample."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["DataLoader", "process_batch", "fetch_data"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(
            type_=ReferenceMaterialType.CODE_SAMPLE,
            content="class DataLoader:\n    def process_batch(self): pass\n\nasync def fetch_data(): pass",
        )
        concepts = processor.extract_concepts(ref)
        assert "DataLoader" in concepts

    def test_github_repo_pipeline(self) -> None:
        """Full pipeline for GitHub repo reference."""
        gateway = _make_mock_gateway(
            response='{"concepts": ["FastAPI", "Pydantic", "async routes"]}'
        )
        processor = ReferenceProcessor(
            llm_gateway=gateway,
            config=ProcessorConfig(llm_model="gpt-4o-mini"),
        )
        ref = _make_ref(
            type_=ReferenceMaterialType.GITHUB_REPO,
            content="FastAPI web framework with Pydantic validation and async route support",
        )
        concepts = processor.extract_concepts(ref)
        assert "FastAPI" in concepts
        assert "Pydantic" in concepts


# ---------------------------------------------------------------------------
# Package Import Tests
# ---------------------------------------------------------------------------


class TestPackageImports:
    """Test that reference_processor exports are importable."""

    def test_import_from_module(self) -> None:
        """All public symbols importable from reference_processor."""
        from zerorepo.spec_parser.reference_processor import (
            CodeContentExtractor,
            ConceptExtractionError,
            ConceptExtractionResponse,
            ContentExtractor,
            ExtractionError,
            ExtractionResult,
            InlineContentExtractor,
            PDFContentExtractor,
            ProcessorConfig,
            ReferenceProcessor,
        )

        assert ReferenceProcessor is not None
        assert ProcessorConfig is not None
        assert ExtractionResult is not None
