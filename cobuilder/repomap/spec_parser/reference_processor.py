"""Reference Material Processor for the User Specification Parser.

Extracts key concepts from various reference material types (API docs,
research papers, code samples, GitHub repos) using content extraction
strategies and LLM-based concept summarisation.

Implements Task 2.4.3 of PRD-RPG-P2-001 (Epic 2.4: User Specification
Parser).

Supported workflows:
    1. Extract raw text from a reference material (URL, inline content, PDF)
    2. Feed extracted text to LLM for concept identification
    3. Store extracted concepts back into the ``ReferenceMaterial`` model
    4. Augment a ``RepositorySpec`` by processing all attached references

Example::

    from cobuilder.repomap.llm.gateway import LLMGateway
    from cobuilder.repomap.spec_parser.models import ReferenceMaterial, ReferenceMaterialType
    from cobuilder.repomap.spec_parser.reference_processor import ReferenceProcessor

    gateway = LLMGateway()
    processor = ReferenceProcessor(llm_gateway=gateway)

    ref = ReferenceMaterial(
        type=ReferenceMaterialType.API_DOCUMENTATION,
        url="https://scikit-learn.org/stable/",
        content="GridSearchCV, Pipeline, cross_val_score ...",
    )
    concepts = processor.extract_concepts(ref)
    # ["GridSearchCV", "Pipeline", "cross_val_score", ...]
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cobuilder.repomap.spec_parser.models import (
    ReferenceMaterial,
    ReferenceMaterialType,
    RepositorySpec,
)

# ---------------------------------------------------------------------------
# Optional dependency imports (lazy, following llm/gateway.py pattern)
# ---------------------------------------------------------------------------

try:
    import pdfplumber

    _PDFPLUMBER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PDFPLUMBER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum text length sent to LLM for concept extraction (chars).
# Longer documents are truncated to avoid exceeding context windows.
MAX_TEXT_LENGTH_FOR_LLM = 50_000

# Default maximum concepts to extract from a single reference.
DEFAULT_MAX_CONCEPTS = 30

# Minimum concept string length to be considered valid.
MIN_CONCEPT_LENGTH = 2


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ProcessorConfig(BaseModel):
    """Configuration for the Reference Material Processor.

    Controls text extraction limits, LLM prompting behaviour, and
    concept filtering thresholds.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    max_text_length: int = Field(
        default=MAX_TEXT_LENGTH_FOR_LLM,
        ge=100,
        description="Maximum character length of text sent to LLM for concept extraction",
    )
    max_concepts: int = Field(
        default=DEFAULT_MAX_CONCEPTS,
        ge=1,
        le=200,
        description="Maximum number of concepts to extract per reference",
    )
    min_concept_length: int = Field(
        default=MIN_CONCEPT_LENGTH,
        ge=1,
        description="Minimum character length for a concept to be valid",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description=(
            "Explicit LLM model to use for concept extraction. "
            "When None, uses the gateway's tier-based selection with CHEAP tier."
        ),
    )
    deduplicate_concepts: bool = Field(
        default=True,
        description="Whether to deduplicate extracted concepts (case-insensitive)",
    )


# ---------------------------------------------------------------------------
# Content Extraction Result
# ---------------------------------------------------------------------------


class ExtractionResult(BaseModel):
    """Result of extracting text content from a reference material.

    Holds the extracted text along with metadata about the extraction
    process (character count, extraction method used, truncation status).
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(
        ...,
        description="Extracted text content from the reference material",
    )
    char_count: int = Field(
        ...,
        ge=0,
        description="Total character count of extracted text",
    )
    method: str = Field(
        ...,
        description="Extraction method used (e.g., 'inline', 'pdf', 'code')",
    )
    was_truncated: bool = Field(
        default=False,
        description="Whether the extracted text was truncated to fit limits",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extraction metadata",
    )


# ---------------------------------------------------------------------------
# LLM Concept Extraction Response Schema
# ---------------------------------------------------------------------------


class ConceptExtractionResponse(BaseModel):
    """Structured LLM response for concept extraction.

    Used with ``LLMGateway.complete_json()`` to ensure the LLM
    returns concepts in a parseable format.
    """

    model_config = ConfigDict(frozen=True)

    concepts: list[str] = Field(
        ...,
        description="List of key concepts extracted from the text",
    )


# ---------------------------------------------------------------------------
# Content Extractors (Strategy pattern)
# ---------------------------------------------------------------------------


class ContentExtractor(ABC):
    """Abstract base class for content extraction strategies.

    Each subclass handles a specific type of reference material content
    extraction (inline text, PDF, code samples, etc.).
    """

    @abstractmethod
    def can_handle(self, reference: ReferenceMaterial) -> bool:
        """Return True if this extractor can handle the given reference.

        Args:
            reference: The reference material to check.

        Returns:
            True if this extractor supports the reference's type/content.
        """

    @abstractmethod
    def extract(
        self,
        reference: ReferenceMaterial,
        max_length: int = MAX_TEXT_LENGTH_FOR_LLM,
    ) -> ExtractionResult:
        """Extract text content from the reference material.

        Args:
            reference: The reference material to extract content from.
            max_length: Maximum character length for the extracted text.

        Returns:
            An ExtractionResult containing the extracted text.

        Raises:
            ExtractionError: If extraction fails.
        """


class InlineContentExtractor(ContentExtractor):
    """Extracts text from inline content stored directly in the reference.

    Handles all reference types that have ``content`` populated directly
    (code samples, pasted documentation text, etc.).
    """

    def can_handle(self, reference: ReferenceMaterial) -> bool:
        """Return True if the reference has inline content."""
        return reference.content is not None and len(reference.content.strip()) > 0

    def extract(
        self,
        reference: ReferenceMaterial,
        max_length: int = MAX_TEXT_LENGTH_FOR_LLM,
    ) -> ExtractionResult:
        """Extract text from the reference's inline content field.

        Args:
            reference: Reference material with inline content.
            max_length: Maximum text length.

        Returns:
            ExtractionResult with the inline content.

        Raises:
            ExtractionError: If no inline content is available.
        """
        if reference.content is None or not reference.content.strip():
            raise ExtractionError(
                f"Reference {reference.id} has no inline content to extract"
            )

        text = reference.content.strip()
        was_truncated = len(text) > max_length
        if was_truncated:
            text = text[:max_length]

        return ExtractionResult(
            text=text,
            char_count=len(text),
            method="inline",
            was_truncated=was_truncated,
        )


class CodeContentExtractor(ContentExtractor):
    """Extracts structured text from code samples.

    For CODE_SAMPLE references, applies lightweight syntax analysis
    to extract meaningful identifiers (function names, class names,
    imports, etc.) alongside the raw code text.
    """

    # Regex patterns for common code structures
    _PATTERNS = {
        "python_def": re.compile(r"^\s*(?:async\s+)?def\s+(\w+)", re.MULTILINE),
        "python_class": re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),
        "python_import": re.compile(
            r"^\s*(?:from\s+(\S+)\s+)?import\s+(.+)", re.MULTILINE
        ),
        "js_function": re.compile(
            r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\(|function))",
            re.MULTILINE,
        ),
        "js_class": re.compile(r"^\s*(?:export\s+)?class\s+(\w+)", re.MULTILINE),
        "js_import": re.compile(
            r"^\s*import\s+.*?\s+from\s+['\"](.+?)['\"]", re.MULTILINE
        ),
    }

    def can_handle(self, reference: ReferenceMaterial) -> bool:
        """Return True if this is a code sample reference with content."""
        return (
            reference.type == ReferenceMaterialType.CODE_SAMPLE
            and reference.content is not None
            and len(reference.content.strip()) > 0
        )

    def extract(
        self,
        reference: ReferenceMaterial,
        max_length: int = MAX_TEXT_LENGTH_FOR_LLM,
    ) -> ExtractionResult:
        """Extract structured text from code content.

        Extracts both the raw code and identified identifiers (functions,
        classes, imports) to give the LLM better context for concept
        extraction.

        Args:
            reference: Code sample reference material.
            max_length: Maximum text length.

        Returns:
            ExtractionResult with structured code analysis.
        """
        if reference.content is None or not reference.content.strip():
            raise ExtractionError(
                f"Reference {reference.id} has no code content to extract"
            )

        code = reference.content.strip()
        identifiers = self._extract_identifiers(code)

        # Build structured output: identifiers summary + code
        parts = []
        if identifiers:
            parts.append(
                "Identified code structures:\n"
                + "\n".join(f"  - {ident}" for ident in identifiers)
            )
        parts.append(f"\nSource code:\n{code}")

        text = "\n".join(parts)
        was_truncated = len(text) > max_length
        if was_truncated:
            text = text[:max_length]

        return ExtractionResult(
            text=text,
            char_count=len(text),
            method="code",
            was_truncated=was_truncated,
            metadata={"identifiers_found": len(identifiers)},
        )

    def _extract_identifiers(self, code: str) -> list[str]:
        """Extract function names, class names, and imports from code.

        Uses regex-based lightweight parsing (not a full AST) to
        identify key structures in Python and JavaScript code.

        Args:
            code: Source code text.

        Returns:
            List of identified structure names.
        """
        identifiers: list[str] = []

        for pattern_name, pattern in self._PATTERNS.items():
            for match in pattern.finditer(code):
                groups = [g for g in match.groups() if g is not None]
                for group in groups:
                    # Split comma-separated imports
                    for item in group.split(","):
                        item = item.strip()
                        # Remove 'as alias' from imports
                        item = item.split(" as ")[0].strip()
                        if item and item not in identifiers:
                            identifiers.append(item)

        return identifiers


class PDFContentExtractor(ContentExtractor):
    """Extracts text from PDF reference materials.

    Uses pdfplumber (when available) for high-quality text extraction
    from PDF documents. Falls back to treating the URL/content as text
    when pdfplumber is not installed.

    Requires: ``pip install pdfplumber``
    """

    def can_handle(self, reference: ReferenceMaterial) -> bool:
        """Return True if the reference is a PDF (research paper or file:// URL).

        Identifies PDFs by:
        - ReferenceMaterialType.RESEARCH_PAPER type
        - URL ending in .pdf
        """
        if reference.type == ReferenceMaterialType.RESEARCH_PAPER:
            return True
        if reference.url and reference.url.lower().endswith(".pdf"):
            return True
        return False

    def extract(
        self,
        reference: ReferenceMaterial,
        max_length: int = MAX_TEXT_LENGTH_FOR_LLM,
    ) -> ExtractionResult:
        """Extract text from a PDF reference.

        For file:// URLs, reads the PDF locally using pdfplumber.
        For inline content, treats it as already-extracted text.

        Args:
            reference: PDF reference material.
            max_length: Maximum text length.

        Returns:
            ExtractionResult with extracted PDF text.

        Raises:
            ExtractionError: If PDF extraction fails or pdfplumber is unavailable.
        """
        # If there's inline content, use it directly (already extracted)
        if reference.content and reference.content.strip():
            text = reference.content.strip()
            was_truncated = len(text) > max_length
            if was_truncated:
                text = text[:max_length]
            return ExtractionResult(
                text=text,
                char_count=len(text),
                method="pdf_content",
                was_truncated=was_truncated,
            )

        # Try pdfplumber for file:// URLs
        if reference.url and reference.url.startswith("file://"):
            return self._extract_from_file(reference.url, max_length)

        raise ExtractionError(
            f"Reference {reference.id}: PDF extraction requires either "
            f"inline content or a file:// URL. "
            f"Remote URL fetching is not yet supported."
        )

    def _extract_from_file(
        self, file_url: str, max_length: int
    ) -> ExtractionResult:
        """Extract text from a local PDF file using pdfplumber.

        Args:
            file_url: A file:// URL pointing to a local PDF.
            max_length: Maximum text length.

        Returns:
            ExtractionResult with extracted text.

        Raises:
            ExtractionError: If pdfplumber is unavailable or file can't be read.
        """
        if not _PDFPLUMBER_AVAILABLE:
            raise ExtractionError(
                "pdfplumber is not installed. "
                "Run: pip install pdfplumber"
            )

        # Convert file:// URL to local path
        file_path = file_url.replace("file://", "")

        try:
            pages_text: list[str] = []
            total_chars = 0

            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    pages_text.append(page_text)
                    total_chars += len(page_text)

            text = "\n\n".join(pages_text)
            was_truncated = len(text) > max_length
            if was_truncated:
                text = text[:max_length]

            return ExtractionResult(
                text=text,
                char_count=len(text),
                method="pdf_pdfplumber",
                was_truncated=was_truncated,
                metadata={"page_count": page_count},
            )

        except FileNotFoundError:
            raise ExtractionError(
                f"PDF file not found: {file_path}"
            )
        except Exception as e:
            raise ExtractionError(
                f"Failed to extract text from PDF {file_path}: {e}"
            )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Raised when content extraction from a reference material fails.

    Examples: missing content, unsupported format, PDF read error.
    """


class ConceptExtractionError(Exception):
    """Raised when LLM-based concept extraction fails.

    Examples: LLM response parsing failure, empty response, gateway error.
    """


# ---------------------------------------------------------------------------
# LLM Gateway Protocol (for dependency injection / testing)
# ---------------------------------------------------------------------------


class LLMGatewayProtocol(Protocol):
    """Protocol for LLM gateway used by the reference processor.

    Enables dependency injection and testing without importing
    the full LLMGateway implementation.
    """

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str: ...

    def select_model(
        self,
        tier: Any,
        provider_preference: str | None = None,
    ) -> str: ...


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

_CONCEPT_EXTRACTION_PROMPT = """\
You are an expert software engineer analysing reference material.
Extract the key technical concepts, APIs, patterns, and tools mentioned
in the following text.

Rules:
- Return ONLY a JSON object with a single key "concepts" containing a list of strings.
- Each concept should be a concise identifier (1-5 words).
- Focus on: API names, function/class names, design patterns, libraries, protocols.
- Ignore generic words like "introduction", "overview", "example".
- Extract at most {max_concepts} concepts.
- Order by importance (most important first).

Text to analyse:
---
{text}
---

Respond with ONLY valid JSON, for example:
{{"concepts": ["GridSearchCV", "Pipeline", "cross_val_score"]}}
"""

_CODE_CONCEPT_PROMPT = """\
You are an expert software engineer analysing a code sample.
Extract the key technical concepts, patterns, and notable implementations
from the following code.

Rules:
- Return ONLY a JSON object with a single key "concepts" containing a list of strings.
- Each concept should be a concise identifier (1-5 words).
- Focus on: function names, class names, design patterns, algorithms, libraries used.
- Ignore variable names, boilerplate, and standard library imports.
- Extract at most {max_concepts} concepts.
- Order by importance (most important first).

Code to analyse:
---
{text}
---

Respond with ONLY valid JSON, for example:
{{"concepts": ["Observer Pattern", "async generator", "WebSocket handler"]}}
"""


# ---------------------------------------------------------------------------
# Reference Processor
# ---------------------------------------------------------------------------


class ReferenceProcessor:
    """Processes reference materials to extract key concepts using LLM.

    Orchestrates content extraction from various reference material types
    and uses the LLM Gateway to identify key technical concepts.

    The processor follows a pipeline approach:
        1. Select appropriate content extractor for the reference type
        2. Extract raw text from the reference
        3. Send extracted text to LLM for concept identification
        4. Clean and deduplicate extracted concepts
        5. Store concepts back into the ReferenceMaterial model

    Example::

        from cobuilder.repomap.llm.gateway import LLMGateway
        from cobuilder.repomap.spec_parser.reference_processor import ReferenceProcessor

        gateway = LLMGateway()
        processor = ReferenceProcessor(llm_gateway=gateway)

        ref = ReferenceMaterial(
            type=ReferenceMaterialType.API_DOCUMENTATION,
            content="GridSearchCV enables hyperparameter tuning...",
        )
        concepts = processor.extract_concepts(ref)
        # ["GridSearchCV", "hyperparameter tuning", ...]

    Args:
        llm_gateway: An LLM gateway for concept extraction (uses complete()).
        config: Optional processor configuration.
        extractors: Optional list of custom content extractors.
            When None, the default extractors are used.
    """

    def __init__(
        self,
        llm_gateway: LLMGatewayProtocol,
        config: ProcessorConfig | None = None,
        extractors: list[ContentExtractor] | None = None,
    ) -> None:
        self._gateway = llm_gateway
        self._config = config or ProcessorConfig()

        # Register extractors in priority order (more specific first)
        if extractors is not None:
            self._extractors = list(extractors)
        else:
            self._extractors: list[ContentExtractor] = [
                CodeContentExtractor(),
                PDFContentExtractor(),
                InlineContentExtractor(),  # Fallback: handles any content
            ]

    @property
    def config(self) -> ProcessorConfig:
        """Return the processor configuration."""
        return self._config

    @property
    def extractors(self) -> list[ContentExtractor]:
        """Return the registered content extractors."""
        return list(self._extractors)

    # ------------------------------------------------------------------
    # Content Extraction
    # ------------------------------------------------------------------

    def extract_content(
        self, reference: ReferenceMaterial
    ) -> ExtractionResult:
        """Extract text content from a reference material.

        Selects the first matching content extractor and delegates
        extraction to it.

        Args:
            reference: The reference material to extract content from.

        Returns:
            An ExtractionResult with the extracted text.

        Raises:
            ExtractionError: If no extractor can handle the reference
                or extraction fails.
        """
        for extractor in self._extractors:
            if extractor.can_handle(reference):
                return extractor.extract(
                    reference,
                    max_length=self._config.max_text_length,
                )

        raise ExtractionError(
            f"No content extractor can handle reference {reference.id} "
            f"(type={reference.type.value}, "
            f"has_url={reference.url is not None}, "
            f"has_content={reference.content is not None})"
        )

    # ------------------------------------------------------------------
    # Concept Extraction (LLM-based)
    # ------------------------------------------------------------------

    def extract_concepts(
        self, reference: ReferenceMaterial
    ) -> list[str]:
        """Extract key concepts from a reference material using LLM.

        Complete pipeline: extract content → LLM summarisation → clean concepts.
        Also updates the reference's ``extracted_concepts`` field in-place.

        Args:
            reference: The reference material to process.

        Returns:
            List of extracted concept strings (cleaned, deduplicated).

        Raises:
            ExtractionError: If content extraction fails.
            ConceptExtractionError: If LLM concept extraction fails.
        """
        # Step 1: Extract text content
        extraction = self.extract_content(reference)

        if not extraction.text.strip():
            return []

        # Step 2: Select prompt based on reference type
        if reference.type == ReferenceMaterialType.CODE_SAMPLE:
            prompt_template = _CODE_CONCEPT_PROMPT
        else:
            prompt_template = _CONCEPT_EXTRACTION_PROMPT

        prompt = prompt_template.format(
            text=extraction.text,
            max_concepts=self._config.max_concepts,
        )

        # Step 3: Call LLM for concept extraction
        raw_concepts = self._call_llm_for_concepts(prompt)

        # Step 4: Clean and filter concepts
        concepts = self._clean_concepts(raw_concepts)

        # Step 5: Update the reference in-place
        reference.extracted_concepts = concepts

        return concepts

    def extract_concepts_from_text(self, text: str) -> list[str]:
        """Extract concepts from raw text without a ReferenceMaterial wrapper.

        Convenience method for when you have text content directly
        without a full ReferenceMaterial model.

        Args:
            text: Raw text to extract concepts from.

        Returns:
            List of extracted concept strings.

        Raises:
            ConceptExtractionError: If LLM concept extraction fails.
        """
        if not text.strip():
            return []

        # Truncate if necessary
        if len(text) > self._config.max_text_length:
            text = text[: self._config.max_text_length]

        prompt = _CONCEPT_EXTRACTION_PROMPT.format(
            text=text,
            max_concepts=self._config.max_concepts,
        )

        raw_concepts = self._call_llm_for_concepts(prompt)
        return self._clean_concepts(raw_concepts)

    def process_spec_references(
        self, spec: RepositorySpec
    ) -> dict[str, list[str]]:
        """Process all reference materials in a RepositorySpec.

        Iterates over all references in the spec and extracts concepts
        from each one, updating the ``extracted_concepts`` field in-place.

        Args:
            spec: The repository specification to process.

        Returns:
            A dict mapping reference ID (str) → extracted concepts list.
            References that fail extraction are included with empty lists.
        """
        results: dict[str, list[str]] = {}

        for reference in spec.references:
            ref_id = str(reference.id)
            try:
                concepts = self.extract_concepts(reference)
                results[ref_id] = concepts
            except (ExtractionError, ConceptExtractionError):
                # Log failure but continue processing other references
                results[ref_id] = []

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm_for_concepts(self, prompt: str) -> list[str]:
        """Call the LLM gateway to extract concepts from a prompt.

        Tries to parse the LLM response as JSON with a "concepts" key.
        Falls back to line-based parsing if JSON parsing fails.

        Args:
            prompt: The fully formatted prompt for concept extraction.

        Returns:
            Raw list of concept strings from the LLM.

        Raises:
            ConceptExtractionError: If the LLM call fails or response
                cannot be parsed.
        """
        # Determine which model to use
        model = self._config.llm_model
        if model is None:
            try:
                from cobuilder.repomap.llm.models import ModelTier

                model = self._gateway.select_model(tier=ModelTier.CHEAP)
            except Exception:
                raise ConceptExtractionError(
                    "No LLM model configured and tier-based selection failed. "
                    "Set ProcessorConfig.llm_model explicitly."
                )

        messages = [{"role": "user", "content": prompt}]

        try:
            response_text = self._gateway.complete(
                messages=messages,
                model=model,
            )
        except Exception as e:
            raise ConceptExtractionError(
                f"LLM call failed during concept extraction: {e}"
            ) from e

        return self._parse_concepts_response(response_text)

    def _parse_concepts_response(self, response_text: str) -> list[str]:
        """Parse the LLM response to extract a list of concepts.

        Attempts JSON parsing first, then falls back to line-based
        extraction for robustness.

        Args:
            response_text: Raw LLM response text.

        Returns:
            List of concept strings.
        """
        # Try JSON parsing first
        try:
            # Strip markdown code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                # Remove ```json or ``` prefix and trailing ```
                lines = cleaned.split("\n")
                # Find first and last ``` lines
                start = 0
                end = len(lines)
                for i, line in enumerate(lines):
                    if line.strip().startswith("```") and i == 0:
                        start = i + 1
                    elif line.strip() == "```" and i > 0:
                        end = i
                        break
                cleaned = "\n".join(lines[start:end])

            data = json.loads(cleaned)
            if isinstance(data, dict) and "concepts" in data:
                concepts = data["concepts"]
                if isinstance(concepts, list):
                    return [str(c) for c in concepts if c]

            # Handle plain list response
            if isinstance(data, list):
                return [str(c) for c in data if c]

        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # Fallback: line-based extraction
        return self._parse_concepts_fallback(response_text)

    def _parse_concepts_fallback(self, text: str) -> list[str]:
        """Fallback parser for non-JSON LLM responses.

        Extracts concepts from bullet points, numbered lists, or
        comma-separated values.

        Args:
            text: Raw response text that failed JSON parsing.

        Returns:
            List of extracted concept strings.
        """
        concepts: list[str] = []

        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Remove bullet markers: -, *, •, numbered (1., 2., etc.)
            line = re.sub(r"^[\-\*•]\s*", "", line)
            line = re.sub(r"^\d+[\.\)]\s*", "", line)

            # Remove quotes
            line = line.strip("\"'`")

            if line:
                # Check if line contains comma-separated concepts
                if "," in line and len(line.split(",")) > 2:
                    for part in line.split(","):
                        part = part.strip().strip("\"'`")
                        if part:
                            concepts.append(part)
                else:
                    concepts.append(line)

        return concepts

    def _clean_concepts(self, raw_concepts: list[str]) -> list[str]:
        """Clean, filter, and deduplicate extracted concepts.

        Args:
            raw_concepts: Raw concept strings from LLM.

        Returns:
            Cleaned and filtered concept list.
        """
        cleaned: list[str] = []
        seen_lower: set[str] = set()

        for concept in raw_concepts:
            # Strip whitespace and quotes
            concept = concept.strip().strip("\"'`")

            # Skip too short or empty
            if len(concept) < self._config.min_concept_length:
                continue

            # Deduplicate (case-insensitive)
            if self._config.deduplicate_concepts:
                lower = concept.lower()
                if lower in seen_lower:
                    continue
                seen_lower.add(lower)

            cleaned.append(concept)

            # Respect max concepts limit
            if len(cleaned) >= self._config.max_concepts:
                break

        return cleaned
