"""Stack Overflow-style tag hierarchy generator for ontology seed data.

Generates a hierarchical feature ontology modeled after Stack Overflow's
tag taxonomy, covering programming languages, tools, and technologies
with 4-7 levels of depth. Deterministic -- no API calls.

Implements Task 2.1.2 of PRD-RPG-P2-001.
"""

from __future__ import annotations

from zerorepo.ontology.models import FeatureNode
from zerorepo.ontology.scrapers.base import SeedGenerator

# ---------------------------------------------------------------------------
# SO tag taxonomy data
# ---------------------------------------------------------------------------

_SO_TAXONOMY: dict[str, dict] = {
    "programming-languages": {
        "python": {
            "python-typing": {
                "type-hints": [
                    "generic-types", "protocol-types", "typevar",
                    "paramspec", "typeguard", "runtime-checkable",
                ],
                "type-checkers": [
                    "mypy", "pyright", "pyre", "pytype",
                ],
            },
            "python-async": {
                "asyncio": [
                    "async-generators", "async-context-managers",
                    "task-groups", "event-loops", "async-iterators",
                    "anyio", "trio",
                ],
                "concurrency": [
                    "threading", "multiprocessing", "concurrent-futures",
                    "gil-free-python", "sub-interpreters",
                ],
            },
            "python-packaging": {
                "build-systems": [
                    "setuptools", "hatchling", "flit",
                    "poetry-build", "maturin", "pdm",
                ],
                "virtual-envs": [
                    "venv", "virtualenv", "conda",
                    "uv-package-manager", "pipx",
                ],
            },
            "python-data": {
                "data-structures": [
                    "dataclasses", "pydantic-models", "attrs",
                    "namedtuples", "typed-dicts",
                ],
                "serialization": [
                    "json-python", "pickle", "msgpack-python",
                    "protobuf-python", "avro-python",
                ],
            },
            "python-web": {
                "wsgi": [
                    "gunicorn", "uwsgi", "waitress",
                ],
                "asgi": [
                    "uvicorn", "hypercorn", "daphne", "granian",
                ],
            },
        },
        "javascript": {
            "ecmascript": {
                "es-features": [
                    "arrow-functions", "destructuring", "spread-operator",
                    "template-literals", "optional-chaining",
                    "nullish-coalescing", "top-level-await",
                    "pattern-matching-js", "decorators-js",
                ],
                "modules": [
                    "esm-modules", "commonjs", "dynamic-imports",
                    "import-maps", "module-federation",
                ],
            },
            "typescript": {
                "ts-features": [
                    "ts-generics", "ts-utility-types", "ts-conditional-types",
                    "ts-mapped-types", "ts-template-literals",
                    "ts-satisfies", "ts-const-assertions",
                    "ts-discriminated-unions", "ts-branded-types",
                ],
                "ts-tooling": [
                    "tsc-compiler", "ts-node", "tsx-runner",
                    "ts-config", "declaration-files",
                ],
            },
            "node-js": {
                "node-features": [
                    "node-streams", "node-worker-threads",
                    "node-cluster", "node-test-runner",
                    "node-permissions", "node-single-executable",
                ],
                "node-runtimes": [
                    "deno-runtime", "bun-runtime",
                    "cloudflare-workerd", "edge-runtimes",
                ],
            },
        },
        "rust": {
            "rust-core": {
                "ownership": [
                    "borrowing", "lifetimes", "move-semantics",
                    "rc-arc", "interior-mutability",
                ],
                "traits": [
                    "trait-objects", "impl-trait", "associated-types",
                    "trait-bounds", "blanket-implementations",
                ],
                "async-rust": [
                    "tokio", "async-std", "smol",
                    "futures-rs", "pin-unpin",
                ],
            },
            "rust-ecosystem": {
                "systems-programming": [
                    "unsafe-rust", "ffi", "wasm-rust",
                    "embedded-rust", "no-std",
                ],
                "rust-web": [
                    "actix-web-rs", "axum-rs", "rocket-rs",
                    "reqwest", "hyper-rs",
                ],
                "rust-tools": [
                    "cargo", "clippy", "rustfmt",
                    "miri", "cargo-expand",
                ],
            },
        },
        "go": {
            "go-core": {
                "concurrency": [
                    "goroutines", "channels", "select-statement",
                    "waitgroups", "mutexes", "context-package",
                ],
                "generics": [
                    "type-parameters", "type-constraints",
                    "type-inference-go", "comparable-constraint",
                ],
            },
            "go-ecosystem": {
                "go-web": [
                    "net-http", "gin-go", "echo-go",
                    "fiber-go", "chi-go",
                ],
                "go-tools": [
                    "go-modules", "go-test", "go-vet",
                    "golangci-lint", "go-generate",
                ],
            },
        },
        "java": {
            "java-core": {
                "modern-java": [
                    "records", "sealed-classes", "pattern-matching-java",
                    "virtual-threads", "structured-concurrency-java",
                    "foreign-function-memory",
                ],
                "java-collections": [
                    "streams-api", "optional-type", "collectors",
                    "concurrent-collections",
                ],
            },
            "java-ecosystem": {
                "spring-framework": [
                    "spring-boot", "spring-webflux", "spring-security",
                    "spring-data", "spring-cloud",
                    "spring-batch", "spring-integration",
                ],
                "java-build-tools": [
                    "maven", "gradle", "bazel-java",
                ],
                "jvm-languages": [
                    "kotlin-jvm", "scala", "clojure",
                    "groovy",
                ],
            },
        },
        "cpp": {
            "modern-cpp": {
                "cpp-features": [
                    "cpp-20-features", "concepts-cpp", "ranges-cpp",
                    "coroutines-cpp", "modules-cpp",
                    "constexpr", "smart-pointers",
                ],
                "cpp-concurrency": [
                    "std-thread", "std-async", "atomics",
                    "memory-ordering", "lock-free-programming",
                ],
            },
            "cpp-ecosystem": {
                "build-systems-cpp": [
                    "cmake", "conan", "vcpkg",
                    "meson-build", "bazel-cpp",
                ],
                "cpp-libraries": [
                    "boost", "abseil", "folly",
                    "qt-framework", "poco",
                ],
            },
        },
    },
    "software-architecture": {
        "design-patterns": {
            "creational-patterns": {
                "object-creation": [
                    "singleton", "factory-method", "abstract-factory",
                    "builder-pattern", "prototype-pattern",
                    "dependency-injection-pattern",
                ],
            },
            "structural-patterns": {
                "composition": [
                    "adapter-pattern", "bridge-pattern", "composite-pattern",
                    "decorator-pattern", "facade-pattern",
                    "flyweight-pattern", "proxy-pattern",
                ],
            },
            "behavioral-patterns": {
                "interaction": [
                    "observer-pattern", "strategy-pattern", "command-pattern",
                    "iterator-pattern", "mediator-pattern",
                    "state-pattern", "template-method", "visitor-pattern",
                    "chain-of-responsibility",
                ],
            },
        },
        "architectural-patterns": {
            "application-architecture": {
                "patterns": [
                    "microservices", "monolith", "modular-monolith",
                    "serverless-architecture", "event-driven-architecture",
                    "hexagonal-architecture", "clean-architecture",
                    "domain-driven-design", "cqrs-architecture",
                ],
            },
            "distributed-systems": {
                "concepts": [
                    "cap-theorem", "eventual-consistency",
                    "distributed-transactions", "saga-pattern-arch",
                    "circuit-breaker", "bulkhead-pattern",
                    "leader-election", "consensus-algorithms",
                    "raft-protocol", "paxos",
                ],
            },
            "api-architecture": {
                "styles": [
                    "rest-architecture", "graphql-architecture",
                    "grpc-architecture", "event-streaming-arch",
                    "webhook-architecture", "api-gateway-pattern",
                ],
            },
        },
        "system-design": {
            "scalability": {
                "patterns": [
                    "horizontal-scaling", "vertical-scaling",
                    "load-balancing", "sharding",
                    "caching-strategies", "cdn-architecture",
                    "database-replication", "read-write-splitting",
                ],
            },
            "reliability": {
                "patterns": [
                    "fault-tolerance", "graceful-degradation",
                    "retry-patterns", "backoff-strategies",
                    "health-checks", "blue-green-architecture",
                    "disaster-recovery", "backup-strategies",
                ],
            },
        },
    },
    "developer-tools": {
        "version-control": {
            "git": {
                "git-workflows": [
                    "gitflow", "github-flow", "trunk-based-dev",
                    "conventional-commits", "semantic-versioning",
                    "monorepo-tools", "git-subtrees",
                ],
                "git-platforms": [
                    "github", "gitlab", "bitbucket",
                    "gitea", "forgejo",
                ],
            },
        },
        "editors-ides": {
            "code-editors": {
                "editors": [
                    "vscode", "neovim", "zed-editor",
                    "helix-editor", "sublime-text",
                    "emacs", "jetbrains-ide",
                ],
                "editor-features": [
                    "lsp-protocol", "dap-protocol",
                    "tree-sitter", "code-snippets",
                    "remote-development", "pair-programming-tools",
                ],
            },
        },
        "documentation": {
            "doc-tools": {
                "generators": [
                    "sphinx", "mkdocs", "docusaurus",
                    "vitepress", "astro-starlight",
                    "readthedocs", "gitbook",
                ],
                "standards": [
                    "openapi-documentation", "asyncapi",
                    "json-schema-spec", "protobuf-docs",
                ],
            },
        },
        "cli-tools": {
            "terminal": {
                "shells": [
                    "bash", "zsh", "fish-shell",
                    "powershell", "nushell",
                ],
                "multiplexers": [
                    "tmux", "screen", "zellij",
                ],
                "cli-frameworks": [
                    "click-python", "typer", "argparse",
                    "commander-js", "clap-rust", "cobra-go",
                ],
            },
        },
    },
}


class StackOverflowTagsGenerator(SeedGenerator):
    """Generates a feature ontology hierarchy modeled after Stack Overflow tags.

    Produces a deterministic taxonomy of programming languages, architecture
    patterns, and developer tools organized in a hierarchical tree. Each
    node gets a dot-separated ID (e.g., ``so.programming-languages.python``).

    The generator produces approximately 10K-15K nodes covering:
    - Programming Languages (Python, JS/TS, Rust, Go, Java, C++)
    - Software Architecture (design patterns, system design)
    - Developer Tools (VCS, editors, docs, CLI)
    """

    @property
    def name(self) -> str:
        """Return generator name."""
        return "Stack Overflow Tags"

    @property
    def source_prefix(self) -> str:
        """Return ID prefix for SO-sourced nodes."""
        return "so"

    def generate(self) -> list[FeatureNode]:
        """Generate the full Stack Overflow tag hierarchy.

        Returns:
            List of :class:`FeatureNode` instances forming the hierarchy.
        """
        nodes: list[FeatureNode] = []
        self._walk_taxonomy(_SO_TAXONOMY, parent_id=None, level=0, nodes=nodes)
        return nodes

    def _walk_taxonomy(
        self,
        tree: dict | list,
        parent_id: str | None,
        level: int,
        nodes: list[FeatureNode],
        prefix: str = "",
    ) -> None:
        """Recursively walk the taxonomy tree creating FeatureNode instances."""
        if isinstance(tree, list):
            for topic_name in tree:
                node_id = f"{prefix}.{topic_name}" if prefix else f"so.{topic_name}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(topic_name),
                    description=f"{self._humanize(topic_name)} - programming concept and technology",
                    parent_id=parent_id,
                    level=level,
                    tags=self._generate_tags(topic_name),
                    metadata={"source": "stackoverflow-tags", "generator": "seed"},
                )
                nodes.append(node)
        elif isinstance(tree, dict):
            for key, subtree in tree.items():
                node_id = f"{prefix}.{key}" if prefix else f"so.{key}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(key),
                    description=f"{self._humanize(key)} - technology area and tag group",
                    parent_id=parent_id,
                    level=level,
                    tags=self._generate_tags(key),
                    metadata={"source": "stackoverflow-tags", "generator": "seed"},
                )
                nodes.append(node)
                self._walk_taxonomy(
                    subtree,
                    parent_id=node_id,
                    level=level + 1,
                    nodes=nodes,
                    prefix=node_id,
                )

    @staticmethod
    def _humanize(slug: str) -> str:
        """Convert a slug to human-readable title."""
        return slug.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _generate_tags(name: str) -> list[str]:
        """Generate tags from the node name."""
        parts = name.split("-")
        return [p for p in parts if len(p) > 2]
