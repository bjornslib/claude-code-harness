"""Conflict Detector for the User Specification Parser.

Detects conflicting requirements in a :class:`RepositorySpec` using both
rule-based heuristics (fast, deterministic) and LLM-based analysis
(nuanced, context-aware).

Implements Task 2.4.4 of PRD-RPG-P2-001 (Epic 2.4: User Specification
Parser).

Conflict severity levels:

* **ERROR** – blocking incompatibility (e.g., *backend-only* + React frontend).
* **WARNING** – questionable combination that may work but deserves review.
* **INFO** – informational suggestion for the user.

Example::

    from zerorepo.spec_parser.conflict_detector import ConflictDetector

    detector = ConflictDetector()
    conflicts = detector.detect(spec)
    for c in conflicts:
        print(f"[{c.severity.value}] {c.description}")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zerorepo.llm.exceptions import LLMGatewayError
from zerorepo.llm.gateway import LLMGateway
from zerorepo.llm.models import ModelTier
from zerorepo.llm.prompt_templates import PromptTemplate
from zerorepo.spec_parser.models import (
    ConflictSeverity,
    RepositorySpec,
    ScopeType,
    SpecConflict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known framework → scope associations for rule-based checks
# ---------------------------------------------------------------------------

# Frameworks that are clearly frontend-only
_FRONTEND_FRAMEWORKS: frozenset[str] = frozenset({
    "react", "vue", "angular", "svelte", "next.js", "nextjs", "nuxt",
    "nuxt.js", "gatsby", "remix", "solid", "solidjs", "ember", "backbone",
    "preact", "astro", "htmx",
})

# Frameworks that are clearly backend-only
_BACKEND_FRAMEWORKS: frozenset[str] = frozenset({
    "django", "flask", "fastapi", "express", "nestjs", "spring", "spring boot",
    "rails", "ruby on rails", "laravel", "gin", "echo", "fiber",
    "actix", "rocket", "axum",
})

# Languages incompatible with JVM deployment
_NON_JVM_LANGUAGES: frozenset[str] = frozenset({
    "python", "ruby", "go", "rust", "c", "c++", "php", "perl",
})

# JVM-compatible languages
_JVM_LANGUAGES: frozenset[str] = frozenset({
    "java", "kotlin", "scala", "groovy", "clojure",
})

# Frameworks associated with long-running processes
_LONG_RUNNING_FRAMEWORKS: frozenset[str] = frozenset({
    "celery", "rq", "dramatiq", "huey", "sidekiq", "bull",
    "kafka", "rabbitmq", "redis-streams",
})


# ---------------------------------------------------------------------------
# LLM Response Schema
# ---------------------------------------------------------------------------


class LLMConflictItem(BaseModel):
    """A single conflict item from LLM output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    severity: str = Field(
        ...,
        description="Severity level (ERROR, WARNING, INFO)",
    )
    description: str = Field(
        ...,
        description="Description of the conflict",
    )
    conflicting_fields: list[str] = Field(
        default_factory=list,
        description="Field paths involved in the conflict",
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggested resolution",
    )


class LLMConflictResponse(BaseModel):
    """Top-level response model for LLM conflict detection."""

    model_config = ConfigDict(str_strip_whitespace=True)

    conflicts: list[LLMConflictItem] = Field(
        default_factory=list,
        description="Detected conflicts",
    )


# ---------------------------------------------------------------------------
# Detector Configuration
# ---------------------------------------------------------------------------


class DetectorConfig(BaseModel):
    """Configuration for the Conflict Detector."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    model: str = Field(
        default="gpt-4o-mini",
        description="Model identifier for LLM calls",
    )
    tier: ModelTier = Field(
        default=ModelTier.CHEAP,
        description="Model tier for cost/quality selection",
    )
    template_name: str = Field(
        default="conflict_detection",
        description="Name of the prompt template (without .jinja2)",
    )
    use_llm: bool = Field(
        default=True,
        description="Whether to use LLM analysis (False = rule-based only)",
    )
    use_rules: bool = Field(
        default=True,
        description="Whether to use rule-based checks",
    )
    deduplicate: bool = Field(
        default=True,
        description="Whether to deduplicate conflicts from rules and LLM",
    )


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------


class ConflictDetectorError(Exception):
    """Raised when the conflict detector encounters an unrecoverable error.

    Examples: LLM response is not valid JSON, configuration error, etc.
    """


# ---------------------------------------------------------------------------
# Conflict Detector
# ---------------------------------------------------------------------------


class ConflictDetector:
    """Detects conflicting requirements in a RepositorySpec.

    Combines fast rule-based heuristics with optional LLM-based analysis
    for nuanced conflict detection. Rule-based checks catch well-known
    conflict patterns instantly, while LLM analysis identifies subtle
    or domain-specific conflicts.

    Example::

        detector = ConflictDetector()
        conflicts = detector.detect(spec)
        errors = [c for c in conflicts if c.severity == ConflictSeverity.ERROR]

    The detector can operate in three modes:

    * **rules + LLM** (default): both rule-based and LLM checks run.
    * **rules only**: ``DetectorConfig(use_llm=False)`` – fast, deterministic.
    * **LLM only**: ``DetectorConfig(use_rules=False)`` – for nuanced analysis.

    Attributes:
        config: Detector configuration.
        gateway: LLMGateway for making LLM calls.
        templates: PromptTemplate for rendering prompts.
    """

    def __init__(
        self,
        config: DetectorConfig | None = None,
        gateway: LLMGateway | None = None,
        templates: PromptTemplate | None = None,
    ) -> None:
        """Initialise the conflict detector.

        Args:
            config: Detector configuration. Defaults to DetectorConfig().
            gateway: Pre-configured LLMGateway. If None, creates a new one.
                Required when ``config.use_llm`` is True.
            templates: Pre-configured PromptTemplate. If None, creates one
                using the default template directory.
        """
        self.config = config or DetectorConfig()
        self.gateway = gateway or (LLMGateway() if self.config.use_llm else None)
        self.templates = templates or PromptTemplate()

    def detect(self, spec: RepositorySpec) -> list[SpecConflict]:
        """Detect conflicts in a repository specification.

        Runs rule-based checks and/or LLM analysis depending on the
        detector configuration. Results are merged and optionally
        deduplicated.

        Args:
            spec: The :class:`RepositorySpec` to analyse.

        Returns:
            List of :class:`SpecConflict` instances, sorted by severity
            (ERROR first, then WARNING, then INFO).

        Raises:
            ConflictDetectorError: If LLM analysis fails and ``use_llm``
                is True.
        """
        conflicts: list[SpecConflict] = []

        # Phase 1: Rule-based checks (fast, deterministic)
        if self.config.use_rules:
            rule_conflicts = self._run_rule_checks(spec)
            conflicts.extend(rule_conflicts)
            logger.debug(
                "Rule-based checks found %d conflicts", len(rule_conflicts)
            )

        # Phase 2: LLM-based analysis (nuanced, context-aware)
        if self.config.use_llm:
            llm_conflicts = self._run_llm_analysis(spec)
            conflicts.extend(llm_conflicts)
            logger.debug(
                "LLM analysis found %d conflicts", len(llm_conflicts)
            )

        # Deduplicate if both sources are active
        if self.config.deduplicate and self.config.use_rules and self.config.use_llm:
            conflicts = self._deduplicate(conflicts)

        # Sort by severity: ERROR first, then WARNING, then INFO
        severity_order = {
            ConflictSeverity.ERROR: 0,
            ConflictSeverity.WARNING: 1,
            ConflictSeverity.INFO: 2,
        }
        conflicts.sort(key=lambda c: severity_order.get(c.severity, 99))

        logger.info("Total conflicts detected: %d", len(conflicts))
        return conflicts

    def detect_and_attach(self, spec: RepositorySpec) -> list[SpecConflict]:
        """Detect conflicts and attach them to the specification.

        Convenience method that calls :meth:`detect` and also adds the
        resulting conflicts to ``spec.conflicts``.

        Args:
            spec: The :class:`RepositorySpec` to analyse and update.

        Returns:
            List of :class:`SpecConflict` instances that were attached.
        """
        conflicts = self.detect(spec)
        for conflict in conflicts:
            spec.add_conflict(conflict)
        return conflicts

    # ------------------------------------------------------------------
    # Rule-based checks
    # ------------------------------------------------------------------

    def _run_rule_checks(self, spec: RepositorySpec) -> list[SpecConflict]:
        """Run all rule-based conflict checks.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found by rules.
        """
        conflicts: list[SpecConflict] = []

        conflicts.extend(self._check_scope_vs_frameworks(spec))
        conflicts.extend(self._check_language_vs_deployment(spec))
        conflicts.extend(self._check_serverless_vs_long_running(spec))
        conflicts.extend(self._check_scope_vs_platforms(spec))
        conflicts.extend(self._check_frontend_scope_with_backend_framework(spec))

        return conflicts

    def _check_scope_vs_frameworks(
        self, spec: RepositorySpec
    ) -> list[SpecConflict]:
        """Check for scope vs framework conflicts.

        For example: backend-only scope + React framework = ERROR.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found.
        """
        conflicts: list[SpecConflict] = []
        scope = spec.technical_requirements.scope
        frameworks = {f.lower() for f in spec.technical_requirements.frameworks}

        if scope == ScopeType.BACKEND_ONLY:
            frontend_matches = frameworks & _FRONTEND_FRAMEWORKS
            if frontend_matches:
                conflicts.append(SpecConflict(
                    severity=ConflictSeverity.ERROR,
                    description=(
                        f"Scope is 'BACKEND_ONLY' but frontend frameworks "
                        f"specified: {', '.join(sorted(frontend_matches))}"
                    ),
                    conflicting_fields=[
                        "technical_requirements.scope",
                        "technical_requirements.frameworks",
                    ],
                    suggestion=(
                        "Change scope to 'FULL_STACK' or remove the "
                        "frontend frameworks."
                    ),
                ))

        if scope == ScopeType.FRONTEND_ONLY:
            backend_matches = frameworks & _BACKEND_FRAMEWORKS
            if backend_matches:
                conflicts.append(SpecConflict(
                    severity=ConflictSeverity.ERROR,
                    description=(
                        f"Scope is 'FRONTEND_ONLY' but backend frameworks "
                        f"specified: {', '.join(sorted(backend_matches))}"
                    ),
                    conflicting_fields=[
                        "technical_requirements.scope",
                        "technical_requirements.frameworks",
                    ],
                    suggestion=(
                        "Change scope to 'FULL_STACK' or remove the "
                        "backend frameworks."
                    ),
                ))

        return conflicts

    def _check_language_vs_deployment(
        self, spec: RepositorySpec
    ) -> list[SpecConflict]:
        """Check for language vs deployment target conflicts.

        For example: Python + JVM deployment = WARNING.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found.
        """
        conflicts: list[SpecConflict] = []
        languages = {lang.lower() for lang in spec.technical_requirements.languages}
        frameworks = {f.lower() for f in spec.technical_requirements.frameworks}

        # Check for non-JVM language with JVM-specific frameworks
        jvm_frameworks = frameworks & {"spring", "spring boot"}
        if jvm_frameworks and languages:
            non_jvm = languages & _NON_JVM_LANGUAGES
            if non_jvm and not (languages & _JVM_LANGUAGES):
                conflicts.append(SpecConflict(
                    severity=ConflictSeverity.WARNING,
                    description=(
                        f"JVM framework(s) ({', '.join(sorted(jvm_frameworks))}) "
                        f"specified with non-JVM language(s): "
                        f"{', '.join(sorted(non_jvm))}"
                    ),
                    conflicting_fields=[
                        "technical_requirements.languages",
                        "technical_requirements.frameworks",
                    ],
                    suggestion=(
                        "Add a JVM language (Java, Kotlin, Scala) or "
                        "replace the JVM framework."
                    ),
                ))

        return conflicts

    def _check_serverless_vs_long_running(
        self, spec: RepositorySpec
    ) -> list[SpecConflict]:
        """Check for serverless deployment with long-running process frameworks.

        For example: serverless + Celery = WARNING.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found.
        """
        conflicts: list[SpecConflict] = []
        from zerorepo.spec_parser.models import DeploymentTarget

        is_serverless = DeploymentTarget.SERVERLESS in (
            spec.technical_requirements.deployment_targets
        )
        if not is_serverless:
            return conflicts

        frameworks = {f.lower() for f in spec.technical_requirements.frameworks}
        long_running_matches = frameworks & _LONG_RUNNING_FRAMEWORKS

        if long_running_matches:
            conflicts.append(SpecConflict(
                severity=ConflictSeverity.WARNING,
                description=(
                    f"Serverless deployment target specified with "
                    f"long-running process framework(s): "
                    f"{', '.join(sorted(long_running_matches))}"
                ),
                conflicting_fields=[
                    "technical_requirements.deployment_targets",
                    "technical_requirements.frameworks",
                ],
                suggestion=(
                    "Consider using serverless-compatible alternatives "
                    "or changing to a non-serverless deployment target."
                ),
            ))

        return conflicts

    def _check_scope_vs_platforms(
        self, spec: RepositorySpec
    ) -> list[SpecConflict]:
        """Check for scope vs platform conflicts.

        For example: CLI tool + Mobile platform = WARNING.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found.
        """
        conflicts: list[SpecConflict] = []
        scope = spec.technical_requirements.scope
        platforms = {p.lower() for p in spec.technical_requirements.platforms}

        mobile_platforms = platforms & {"mobile", "ios", "android"}

        if scope == ScopeType.CLI_TOOL and mobile_platforms:
            conflicts.append(SpecConflict(
                severity=ConflictSeverity.WARNING,
                description=(
                    f"Scope is 'CLI_TOOL' but mobile platform(s) specified: "
                    f"{', '.join(sorted(mobile_platforms))}"
                ),
                conflicting_fields=[
                    "technical_requirements.scope",
                    "technical_requirements.platforms",
                ],
                suggestion=(
                    "CLI tools typically target desktop platforms. "
                    "Consider changing scope or removing mobile platforms."
                ),
            ))

        if scope == ScopeType.LIBRARY and mobile_platforms:
            # Libraries targeting mobile is actually valid (SDK/library for mobile)
            # so this is just INFO level
            conflicts.append(SpecConflict(
                severity=ConflictSeverity.INFO,
                description=(
                    f"Scope is 'LIBRARY' with mobile platform(s) "
                    f"({', '.join(sorted(mobile_platforms))}). Ensure the "
                    f"library is designed as a mobile SDK."
                ),
                conflicting_fields=[
                    "technical_requirements.scope",
                    "technical_requirements.platforms",
                ],
                suggestion=(
                    "Verify the library is intended as a mobile SDK or "
                    "mobile-compatible package."
                ),
            ))

        return conflicts

    def _check_frontend_scope_with_backend_framework(
        self, spec: RepositorySpec
    ) -> list[SpecConflict]:
        """Check for frontend-only scope with backend frameworks.

        This is the inverse of _check_scope_vs_frameworks for frontend scope.

        Args:
            spec: The specification to check.

        Returns:
            List of conflicts found.
        """
        # Already handled by _check_scope_vs_frameworks
        return []

    # ------------------------------------------------------------------
    # LLM-based analysis
    # ------------------------------------------------------------------

    def _run_llm_analysis(self, spec: RepositorySpec) -> list[SpecConflict]:
        """Run LLM-based conflict analysis.

        Args:
            spec: The specification to analyse.

        Returns:
            List of conflicts found by the LLM.

        Raises:
            ConflictDetectorError: If the LLM call or response parsing fails.
        """
        if self.gateway is None:
            raise ConflictDetectorError(
                "LLM analysis requires a configured LLMGateway"
            )

        # Build prompt context
        quality_attrs: dict[str, str | None] = {}
        qa = spec.quality_attributes
        if qa.performance:
            quality_attrs["performance"] = qa.performance
        if qa.security:
            quality_attrs["security"] = qa.security
        if qa.scalability:
            quality_attrs["scalability"] = qa.scalability
        if qa.reliability:
            quality_attrs["reliability"] = qa.reliability
        if qa.maintainability:
            quality_attrs["maintainability"] = qa.maintainability

        constraint_dicts = [
            {
                "priority": c.priority.value,
                "description": c.description,
                "category": c.category,
            }
            for c in spec.constraints
        ]

        prompt = self.templates.render(
            self.config.template_name,
            description=spec.description,
            core_functionality=spec.core_functionality,
            languages=spec.technical_requirements.languages,
            frameworks=spec.technical_requirements.frameworks,
            platforms=spec.technical_requirements.platforms,
            deployment_targets=[
                dt.value for dt in spec.technical_requirements.deployment_targets
            ],
            scope=spec.technical_requirements.scope.value if spec.technical_requirements.scope else None,
            quality_attributes=quality_attrs if quality_attrs else None,
            constraints=constraint_dicts if constraint_dicts else None,
        )

        # Call LLM
        messages = [{"role": "user", "content": prompt}]

        try:
            raw_response = self.gateway.complete(
                messages=messages,
                model=self.config.model,
                tier=self.config.tier,
                response_format={"type": "json_object"},
            )
        except LLMGatewayError:
            logger.exception("LLM conflict analysis failed")
            raise ConflictDetectorError(
                "LLM conflict analysis failed. See logs for details."
            )

        # Parse response
        return self._parse_llm_response(raw_response)

    def _parse_llm_response(self, raw_response: str) -> list[SpecConflict]:
        """Parse the raw LLM response into SpecConflict instances.

        Handles markdown code fences and normalises severity values.

        Args:
            raw_response: Raw text from the LLM.

        Returns:
            List of :class:`SpecConflict` instances.

        Raises:
            ConflictDetectorError: If the response cannot be parsed.
        """
        text = raw_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3].rstrip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConflictDetectorError(
                f"LLM response is not valid JSON: {e}\n"
                f"Response preview: {text[:200]}"
            ) from e

        try:
            llm_response = LLMConflictResponse.model_validate(data)
        except Exception as e:
            raise ConflictDetectorError(
                f"LLM response does not match expected schema: {e}"
            ) from e

        # Convert to SpecConflict instances
        conflicts: list[SpecConflict] = []
        for item in llm_response.conflicts:
            severity = _normalize_severity(item.severity)
            conflicts.append(SpecConflict(
                severity=severity,
                description=item.description,
                conflicting_fields=item.conflicting_fields,
                suggestion=item.suggestion,
            ))

        return conflicts

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(
        self, conflicts: list[SpecConflict]
    ) -> list[SpecConflict]:
        """Remove duplicate conflicts based on description similarity.

        Uses a simple approach: conflicts with the same set of conflicting
        fields and similar severity are considered duplicates, keeping the
        one with the higher severity.

        Args:
            conflicts: List of conflicts to deduplicate.

        Returns:
            Deduplicated list of conflicts.
        """
        if len(conflicts) <= 1:
            return conflicts

        severity_rank = {
            ConflictSeverity.ERROR: 0,
            ConflictSeverity.WARNING: 1,
            ConflictSeverity.INFO: 2,
        }

        # Group by frozenset of conflicting fields
        seen: dict[frozenset[str], SpecConflict] = {}
        unique: list[SpecConflict] = []

        for conflict in conflicts:
            key = frozenset(conflict.conflicting_fields)
            if not key:
                # No conflicting fields specified – keep it
                unique.append(conflict)
                continue

            if key in seen:
                existing = seen[key]
                # Keep the higher severity one
                if severity_rank.get(conflict.severity, 99) < severity_rank.get(
                    existing.severity, 99
                ):
                    seen[key] = conflict
            else:
                seen[key] = conflict

        unique.extend(seen.values())
        return unique


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_severity(raw: str) -> ConflictSeverity:
    """Normalize a severity string to a ConflictSeverity enum value.

    Args:
        raw: Severity string from LLM.

    Returns:
        ConflictSeverity enum value.
    """
    normalized = raw.strip().upper()

    mapping: dict[str, ConflictSeverity] = {
        "ERROR": ConflictSeverity.ERROR,
        "WARNING": ConflictSeverity.WARNING,
        "WARN": ConflictSeverity.WARNING,
        "INFO": ConflictSeverity.INFO,
        "INFORMATION": ConflictSeverity.INFO,
        "CRITICAL": ConflictSeverity.ERROR,
        "HIGH": ConflictSeverity.ERROR,
        "MEDIUM": ConflictSeverity.WARNING,
        "LOW": ConflictSeverity.INFO,
    }

    return mapping.get(normalized, ConflictSeverity.WARNING)
