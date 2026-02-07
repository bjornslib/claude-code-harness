"""Taxonomy expander that generates additional nodes via combinatorial expansion.

Takes the base seed taxonomy and expands it by generating cross-cutting
variations, tool-specific implementations, and platform-specific variants.
This allows the seed generators to reach the PRD target of 50K+ nodes.

Implements Task 2.1.2 of PRD-RPG-P2-001 (expansion to target node count).
"""

from __future__ import annotations

import itertools
from typing import Optional

from zerorepo.ontology.models import FeatureNode
from zerorepo.ontology.scrapers.base import SeedGenerator

# ---------------------------------------------------------------------------
# Cross-cutting concern data for combinatorial expansion
# ---------------------------------------------------------------------------

_PLATFORMS = [
    "linux", "macos", "windows", "docker", "kubernetes",
    "aws-lambda", "gcp-cloud-run", "azure-functions",
    "raspberry-pi", "wasm",
]

_LANGUAGES = [
    "python", "javascript", "typescript", "rust", "go",
    "java", "csharp", "kotlin", "swift", "ruby",
    "php", "scala", "elixir", "clojure", "haskell",
    "dart", "lua", "r-language", "julia", "zig",
]

_USE_CASES = [
    "web-application", "mobile-app", "cli-tool", "api-service",
    "data-pipeline", "machine-learning-model", "embedded-system",
    "desktop-application", "browser-extension", "microservice",
    "serverless-function", "batch-job", "real-time-system",
    "game-development", "iot-device",
]

_QUALITY_ASPECTS = [
    "performance-optimization", "security-hardening", "accessibility",
    "internationalization", "error-handling", "logging-monitoring",
    "caching-strategy", "rate-limiting", "input-validation",
    "output-sanitization", "memory-management", "concurrency-safety",
    "idempotency", "backwards-compatibility", "graceful-degradation",
]

_ENVIRONMENTS = [
    "development", "staging", "production", "testing",
    "ci-cd-pipeline", "local-development", "cloud-hosted",
    "on-premises", "hybrid-cloud", "edge-computing",
]

_PROJECT_TYPES = [
    "startup-mvp", "enterprise-application", "open-source-library",
    "saas-product", "internal-tool", "proof-of-concept",
    "migration-project", "greenfield-project", "legacy-modernization",
    "monorepo-project",
]

_TEAM_PRACTICES = [
    "code-review-practice", "pair-programming", "mob-programming",
    "documentation-driven", "test-driven", "behavior-driven",
    "trunk-based-flow", "gitflow-workflow", "feature-flags-practice",
    "continuous-deployment",
]

# Industry verticals for domain-specific variants
_INDUSTRIES = [
    "fintech", "healthcare", "ecommerce", "edtech",
    "gaming", "social-media", "logistics", "real-estate",
    "insurance", "telecommunications", "media-entertainment",
    "government", "legal-tech", "agritech", "cleantech",
    "cybersecurity-industry", "biotech", "automotive", "aerospace",
    "retail",
]

# Technology integrations
_INTEGRATIONS = [
    "oauth-integration", "stripe-payment", "twilio-sms",
    "sendgrid-email", "cloudflare-cdn", "algolia-search",
    "elasticsearch-integration", "redis-caching",
    "postgresql-database", "mongodb-integration",
    "rabbitmq-messaging", "kafka-streaming",
    "prometheus-monitoring", "grafana-dashboard",
    "datadog-observability", "sentry-error-tracking",
    "github-actions-ci", "docker-deployment",
    "terraform-infrastructure", "ansible-configuration",
]

# Data types and formats
_DATA_FORMATS = [
    "json-data", "csv-data", "xml-data", "yaml-data",
    "protobuf-data", "avro-data", "parquet-data",
    "arrow-data", "msgpack-data", "toml-data",
    "graphql-schema-data", "openapi-schema-data",
    "json-schema-data", "hcl-data", "ini-data",
]


class TaxonomyExpander(SeedGenerator):
    """Expands the base taxonomy with cross-cutting variations.

    Generates additional nodes by combining base taxonomy categories with
    platform, language, use-case, quality, and industry dimensions. This
    creates realistic variations like:
    - ``exp.platform.linux.web-application``
    - ``exp.quality.security-hardening.fintech``
    - ``exp.integration.stripe-payment.ecommerce``

    The expansion is designed to be deterministic and produce
    nodes that complement (not duplicate) the base generators.

    Args:
        target_count: Approximate target number of nodes to generate.
            Default 50000 (PRD requirement).
    """

    def __init__(self, target_count: int = 50000) -> None:
        self._target_count = target_count

    @property
    def name(self) -> str:
        """Return generator name."""
        return "Taxonomy Expander"

    @property
    def source_prefix(self) -> str:
        """Return ID prefix for expanded nodes."""
        return "exp"

    def generate(self) -> list[FeatureNode]:
        """Generate expanded taxonomy nodes.

        Produces cross-cutting nodes organized under dimension-based
        root categories. Stops when target_count is reached.

        Returns:
            List of :class:`FeatureNode` instances.
        """
        nodes: list[FeatureNode] = []

        # Dimension 1: Platform × Use Case combinations
        self._generate_platform_use_cases(nodes)

        # Dimension 2: Language × Quality Aspect combinations
        self._generate_language_quality(nodes)

        # Dimension 3: Industry × Integration combinations
        self._generate_industry_integrations(nodes)

        # Dimension 4: Environment × Team Practice combinations
        self._generate_environment_practices(nodes)

        # Dimension 5: Project Type × Data Format combinations
        self._generate_project_data_formats(nodes)

        # Dimension 6: Deep skill tree per language
        self._generate_language_skill_trees(nodes)

        # Dimension 7: Industry-specific feature trees
        self._generate_industry_feature_trees(nodes)

        # Trim to target count if we overshot
        if len(nodes) > self._target_count:
            nodes = nodes[: self._target_count]

        return nodes

    def _generate_platform_use_cases(self, nodes: list[FeatureNode]) -> None:
        """Generate Platform × Use Case cross-product nodes."""
        root_id = "exp.platforms"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Platform Variants",
                description="Software features organized by target platform",
                level=0,
                tags=["platform", "cross-cutting"],
                metadata={"source": "expander", "generator": "seed", "dimension": "platform"},
            )
        )
        for platform in _PLATFORMS:
            platform_id = f"{root_id}.{platform}"
            nodes.append(
                FeatureNode(
                    id=platform_id,
                    name=self._humanize(platform),
                    description=f"Software development for {self._humanize(platform)} platform",
                    parent_id=root_id,
                    level=1,
                    tags=[platform, "platform"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "platform"},
                )
            )
            for use_case in _USE_CASES:
                uc_id = f"{platform_id}.{use_case}"
                nodes.append(
                    FeatureNode(
                        id=uc_id,
                        name=self._humanize(use_case),
                        description=f"{self._humanize(use_case)} on {self._humanize(platform)}",
                        parent_id=platform_id,
                        level=2,
                        tags=[use_case.split("-")[0], platform],
                        metadata={"source": "expander", "generator": "seed", "dimension": "platform-usecase"},
                    )
                )
                # Add quality aspects per use case
                for quality in _QUALITY_ASPECTS:
                    if len(nodes) >= self._target_count:
                        return
                    q_id = f"{uc_id}.{quality}"
                    nodes.append(
                        FeatureNode(
                            id=q_id,
                            name=self._humanize(quality),
                            description=f"{self._humanize(quality)} for {self._humanize(use_case)} on {self._humanize(platform)}",
                            parent_id=uc_id,
                            level=3,
                            tags=[quality.split("-")[0], use_case.split("-")[0]],
                            metadata={"source": "expander", "generator": "seed", "dimension": "platform-usecase-quality"},
                        )
                    )
                    # Add language implementation variants at level 4
                    for lang in _LANGUAGES:
                        if len(nodes) >= self._target_count:
                            return
                        lang_id = f"{q_id}.{lang}"
                        nodes.append(
                            FeatureNode(
                                id=lang_id,
                                name=f"{self._humanize(lang)} Implementation",
                                description=f"{self._humanize(quality)} for {self._humanize(use_case)} on {self._humanize(platform)} in {self._humanize(lang)}",
                                parent_id=q_id,
                                level=4,
                                tags=[lang, quality.split("-")[0], platform],
                                metadata={"source": "expander", "generator": "seed", "dimension": "platform-usecase-quality-lang"},
                            )
                        )

    def _generate_language_quality(self, nodes: list[FeatureNode]) -> None:
        """Generate Language × Quality Aspect cross-product nodes."""
        if len(nodes) >= self._target_count:
            return

        root_id = "exp.languages"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Language Variants",
                description="Quality aspects organized by programming language",
                level=0,
                tags=["language", "cross-cutting"],
                metadata={"source": "expander", "generator": "seed", "dimension": "language"},
            )
        )
        for lang in _LANGUAGES:
            lang_id = f"{root_id}.{lang}"
            nodes.append(
                FeatureNode(
                    id=lang_id,
                    name=self._humanize(lang),
                    description=f"Quality practices in {self._humanize(lang)}",
                    parent_id=root_id,
                    level=1,
                    tags=[lang, "language"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "language"},
                )
            )
            for quality in _QUALITY_ASPECTS:
                q_id = f"{lang_id}.{quality}"
                nodes.append(
                    FeatureNode(
                        id=q_id,
                        name=self._humanize(quality),
                        description=f"{self._humanize(quality)} in {self._humanize(lang)}",
                        parent_id=lang_id,
                        level=2,
                        tags=[quality.split("-")[0], lang],
                        metadata={"source": "expander", "generator": "seed", "dimension": "language-quality"},
                    )
                )
            if len(nodes) >= self._target_count:
                return

    def _generate_industry_integrations(self, nodes: list[FeatureNode]) -> None:
        """Generate Industry × Integration cross-product nodes."""
        if len(nodes) >= self._target_count:
            return

        root_id = "exp.industries"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Industry Verticals",
                description="Technology integrations by industry vertical",
                level=0,
                tags=["industry", "vertical"],
                metadata={"source": "expander", "generator": "seed", "dimension": "industry"},
            )
        )
        for industry in _INDUSTRIES:
            ind_id = f"{root_id}.{industry}"
            nodes.append(
                FeatureNode(
                    id=ind_id,
                    name=self._humanize(industry),
                    description=f"Software development in {self._humanize(industry)} sector",
                    parent_id=root_id,
                    level=1,
                    tags=[industry, "industry"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "industry"},
                )
            )
            for integration in _INTEGRATIONS:
                int_id = f"{ind_id}.{integration}"
                nodes.append(
                    FeatureNode(
                        id=int_id,
                        name=self._humanize(integration),
                        description=f"{self._humanize(integration)} for {self._humanize(industry)} applications",
                        parent_id=ind_id,
                        level=2,
                        tags=[integration.split("-")[0], industry],
                        metadata={"source": "expander", "generator": "seed", "dimension": "industry-integration"},
                    )
                )
            if len(nodes) >= self._target_count:
                return

    def _generate_environment_practices(self, nodes: list[FeatureNode]) -> None:
        """Generate Environment × Practice cross-product nodes."""
        if len(nodes) >= self._target_count:
            return

        root_id = "exp.environments"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Environment Configurations",
                description="Team practices across deployment environments",
                level=0,
                tags=["environment", "devops"],
                metadata={"source": "expander", "generator": "seed", "dimension": "environment"},
            )
        )
        for env in _ENVIRONMENTS:
            env_id = f"{root_id}.{env}"
            nodes.append(
                FeatureNode(
                    id=env_id,
                    name=self._humanize(env),
                    description=f"Practices for {self._humanize(env)} environment",
                    parent_id=root_id,
                    level=1,
                    tags=[env.split("-")[0], "environment"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "environment"},
                )
            )
            for practice in _TEAM_PRACTICES:
                p_id = f"{env_id}.{practice}"
                nodes.append(
                    FeatureNode(
                        id=p_id,
                        name=self._humanize(practice),
                        description=f"{self._humanize(practice)} in {self._humanize(env)} environment",
                        parent_id=env_id,
                        level=2,
                        tags=[practice.split("-")[0], env.split("-")[0]],
                        metadata={"source": "expander", "generator": "seed", "dimension": "environment-practice"},
                    )
                )
            if len(nodes) >= self._target_count:
                return

    def _generate_project_data_formats(self, nodes: list[FeatureNode]) -> None:
        """Generate Project Type × Data Format cross-product nodes."""
        if len(nodes) >= self._target_count:
            return

        root_id = "exp.projects"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Project Types",
                description="Data format considerations by project type",
                level=0,
                tags=["project", "data-format"],
                metadata={"source": "expander", "generator": "seed", "dimension": "project"},
            )
        )
        for project in _PROJECT_TYPES:
            proj_id = f"{root_id}.{project}"
            nodes.append(
                FeatureNode(
                    id=proj_id,
                    name=self._humanize(project),
                    description=f"Data handling in {self._humanize(project)} projects",
                    parent_id=root_id,
                    level=1,
                    tags=[project.split("-")[0], "project"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "project"},
                )
            )
            for fmt in _DATA_FORMATS:
                fmt_id = f"{proj_id}.{fmt}"
                nodes.append(
                    FeatureNode(
                        id=fmt_id,
                        name=self._humanize(fmt),
                        description=f"{self._humanize(fmt)} handling in {self._humanize(project)}",
                        parent_id=proj_id,
                        level=2,
                        tags=[fmt.split("-")[0], project.split("-")[0]],
                        metadata={"source": "expander", "generator": "seed", "dimension": "project-format"},
                    )
                )
            if len(nodes) >= self._target_count:
                return

    def _generate_language_skill_trees(self, nodes: list[FeatureNode]) -> None:
        """Generate deep skill trees for each language (4-5 levels deep)."""
        if len(nodes) >= self._target_count:
            return

        _SKILL_CATEGORIES = [
            "fundamentals", "intermediate", "advanced",
            "expert", "architecture",
        ]
        _SKILL_TOPICS = {
            "fundamentals": [
                "variables", "control-flow", "functions", "data-types",
                "loops", "conditionals", "string-manipulation",
                "file-io", "error-basics", "debugging-basics",
            ],
            "intermediate": [
                "oop-classes", "inheritance", "polymorphism",
                "generics", "collections", "iterators",
                "lambda-expressions", "closures", "modules-packages",
                "dependency-management",
            ],
            "advanced": [
                "metaprogramming", "decorators-annotations",
                "code-generation", "ast-manipulation",
                "memory-model", "garbage-collection",
                "profiling", "benchmarking",
                "ffi-interop", "plugin-systems",
            ],
            "expert": [
                "compiler-internals", "runtime-optimization",
                "custom-allocators", "lock-free-structures",
                "language-extensions", "macro-systems",
                "type-system-advanced", "effect-systems",
                "dependent-types", "linear-types",
            ],
            "architecture": [
                "clean-architecture-lang", "hexagonal-lang",
                "event-sourcing-lang", "cqrs-lang",
                "ddd-lang", "microservices-lang",
                "monolith-lang", "modular-monolith-lang",
                "serverless-lang", "event-driven-lang",
            ],
        }

        root_id = "exp.skills"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Language Skill Trees",
                description="Progressive skill development paths per language",
                level=0,
                tags=["skills", "learning"],
                metadata={"source": "expander", "generator": "seed", "dimension": "skills"},
            )
        )

        for lang in _LANGUAGES:
            if len(nodes) >= self._target_count:
                return
            lang_id = f"{root_id}.{lang}"
            nodes.append(
                FeatureNode(
                    id=lang_id,
                    name=f"{self._humanize(lang)} Skills",
                    description=f"Skill progression for {self._humanize(lang)} developers",
                    parent_id=root_id,
                    level=1,
                    tags=[lang, "skills"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "skills"},
                )
            )
            for category in _SKILL_CATEGORIES:
                if len(nodes) >= self._target_count:
                    return
                cat_id = f"{lang_id}.{category}"
                nodes.append(
                    FeatureNode(
                        id=cat_id,
                        name=self._humanize(category),
                        description=f"{self._humanize(category)} {self._humanize(lang)} skills",
                        parent_id=lang_id,
                        level=2,
                        tags=[category, lang],
                        metadata={"source": "expander", "generator": "seed", "dimension": "skills"},
                    )
                )
                topics = _SKILL_TOPICS.get(category, [])
                for topic in topics:
                    if len(nodes) >= self._target_count:
                        return
                    topic_id = f"{cat_id}.{topic}"
                    nodes.append(
                        FeatureNode(
                            id=topic_id,
                            name=self._humanize(topic),
                            description=f"{self._humanize(topic)} skill in {self._humanize(lang)}",
                            parent_id=cat_id,
                            level=3,
                            tags=[topic.split("-")[0], lang, category],
                            metadata={"source": "expander", "generator": "seed", "dimension": "skills"},
                        )
                    )
                    # Add sub-skills for deeper hierarchy
                    for sub_skill in [
                        "beginner", "practitioner", "specialist",
                    ]:
                        if len(nodes) >= self._target_count:
                            return
                        sub_id = f"{topic_id}.{sub_skill}"
                        nodes.append(
                            FeatureNode(
                                id=sub_id,
                                name=f"{self._humanize(sub_skill)} Level",
                                description=f"{self._humanize(sub_skill)} proficiency in {self._humanize(topic)} ({self._humanize(lang)})",
                                parent_id=topic_id,
                                level=4,
                                tags=[sub_skill, topic.split("-")[0], lang],
                                metadata={"source": "expander", "generator": "seed", "dimension": "skills"},
                            )
                        )

    def _generate_industry_feature_trees(self, nodes: list[FeatureNode]) -> None:
        """Generate industry-specific feature trees (4-5 levels)."""
        if len(nodes) >= self._target_count:
            return

        _INDUSTRY_FEATURES = {
            "fintech": [
                "payment-processing", "risk-assessment", "fraud-detection",
                "regulatory-compliance", "trading-systems", "banking-api",
                "crypto-integration", "lending-platform",
            ],
            "healthcare": [
                "ehr-integration", "telemedicine", "medical-imaging",
                "clinical-trials", "patient-portal", "health-analytics",
                "hipaa-compliance", "drug-interaction",
            ],
            "ecommerce": [
                "product-catalog", "shopping-cart", "checkout-flow",
                "inventory-management", "recommendation-engine",
                "search-ranking", "dynamic-pricing", "loyalty-program",
            ],
            "edtech": [
                "learning-management", "assessment-engine", "content-delivery",
                "student-analytics", "gamification", "adaptive-learning",
                "virtual-classroom", "certification-system",
            ],
            "gaming": [
                "game-engine", "multiplayer-networking", "physics-simulation",
                "rendering-pipeline", "audio-engine", "input-handling",
                "save-system", "matchmaking",
            ],
        }

        _SUB_FEATURES = [
            "data-model", "api-layer", "business-logic",
            "presentation-layer", "integration-tests",
            "performance-tuning", "security-audit",
        ]

        root_id = "exp.industry-features"
        nodes.append(
            FeatureNode(
                id=root_id,
                name="Industry Feature Trees",
                description="Domain-specific feature hierarchies by industry",
                level=0,
                tags=["industry", "features"],
                metadata={"source": "expander", "generator": "seed", "dimension": "industry-features"},
            )
        )

        for industry, features in _INDUSTRY_FEATURES.items():
            if len(nodes) >= self._target_count:
                return
            ind_id = f"{root_id}.{industry}"
            nodes.append(
                FeatureNode(
                    id=ind_id,
                    name=self._humanize(industry),
                    description=f"{self._humanize(industry)} domain features",
                    parent_id=root_id,
                    level=1,
                    tags=[industry, "domain"],
                    metadata={"source": "expander", "generator": "seed", "dimension": "industry-features"},
                )
            )
            for feature in features:
                if len(nodes) >= self._target_count:
                    return
                feat_id = f"{ind_id}.{feature}"
                nodes.append(
                    FeatureNode(
                        id=feat_id,
                        name=self._humanize(feature),
                        description=f"{self._humanize(feature)} in {self._humanize(industry)}",
                        parent_id=ind_id,
                        level=2,
                        tags=[feature.split("-")[0], industry],
                        metadata={"source": "expander", "generator": "seed", "dimension": "industry-features"},
                    )
                )
                for sub in _SUB_FEATURES:
                    if len(nodes) >= self._target_count:
                        return
                    sub_id = f"{feat_id}.{sub}"
                    nodes.append(
                        FeatureNode(
                            id=sub_id,
                            name=self._humanize(sub),
                            description=f"{self._humanize(sub)} for {self._humanize(feature)} ({self._humanize(industry)})",
                            parent_id=feat_id,
                            level=3,
                            tags=[sub.split("-")[0], feature.split("-")[0]],
                            metadata={"source": "expander", "generator": "seed", "dimension": "industry-features"},
                        )
                    )
                    # Add language variants at level 4
                    for lang in _LANGUAGES[:5]:  # Top 5 languages only
                        if len(nodes) >= self._target_count:
                            return
                        lang_id = f"{sub_id}.{lang}"
                        nodes.append(
                            FeatureNode(
                                id=lang_id,
                                name=f"{self._humanize(lang)} Implementation",
                                description=f"{self._humanize(sub)} for {self._humanize(feature)} in {self._humanize(lang)}",
                                parent_id=sub_id,
                                level=4,
                                tags=[lang, sub.split("-")[0], industry],
                                metadata={"source": "expander", "generator": "seed", "dimension": "industry-features"},
                            )
                        )

    @staticmethod
    def _humanize(slug: str) -> str:
        """Convert a slug to human-readable title."""
        return slug.replace("-", " ").replace("_", " ").title()
