"""GitHub-style topic hierarchy generator for ontology seed data.

Generates a hierarchical feature ontology modeled after GitHub's topic
taxonomy, covering major software engineering domains with 4-7 levels
of depth. This is a deterministic generator -- no API calls are made.

Implements Task 2.1.2 of PRD-RPG-P2-001.
"""

from __future__ import annotations

from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.ontology.scrapers.base import SeedGenerator

# ---------------------------------------------------------------------------
# Domain taxonomy data
# ---------------------------------------------------------------------------
# Structure: {domain: {subdomain: {area: {topic: [subtopics]}}}}
# This produces hierarchical depth from 1 (domain) to 5+ (leaf subtopics).

_TAXONOMY: dict[str, dict] = {
    "machine-learning": {
        "deep-learning": {
            "transformers": {
                "attention-mechanisms": [
                    "self-attention", "multi-head-attention", "cross-attention",
                    "linear-attention", "sparse-attention", "flash-attention",
                    "relative-positional-encoding", "rotary-embeddings",
                ],
                "large-language-models": [
                    "gpt-architecture", "llama-models", "mistral-models",
                    "gemma-models", "phi-models", "qwen-models",
                    "instruction-tuning", "rlhf", "dpo-training",
                    "quantization", "knowledge-distillation", "model-merging",
                ],
                "vision-transformers": [
                    "vit", "deit", "swin-transformer", "beit",
                    "sam-segmentation", "dinov2", "clip-models",
                ],
                "multimodal-models": [
                    "vision-language-models", "text-to-image", "image-to-text",
                    "video-understanding", "audio-language-models",
                ],
            },
            "convolutional-networks": {
                "image-classification": [
                    "resnet", "efficientnet", "convnext", "mobilenet",
                    "inception", "densenet", "vgg",
                ],
                "object-detection": [
                    "yolo-family", "faster-rcnn", "detr", "ssd",
                    "anchor-free-detection", "real-time-detection",
                ],
                "semantic-segmentation": [
                    "unet", "deeplabv3", "mask-rcnn", "panoptic-segmentation",
                    "instance-segmentation", "medical-image-segmentation",
                ],
                "generative-models": [
                    "diffusion-models", "stable-diffusion", "dalle",
                    "midjourney-style", "controlnet", "lora-adapters",
                    "image-inpainting", "super-resolution",
                ],
            },
            "recurrent-networks": {
                "lstm-networks": [
                    "bidirectional-lstm", "stacked-lstm", "attention-lstm",
                    "peephole-connections",
                ],
                "gru-networks": [
                    "bidirectional-gru", "gated-recurrence",
                ],
                "sequence-to-sequence": [
                    "encoder-decoder", "beam-search", "teacher-forcing",
                    "autoregressive-decoding",
                ],
            },
            "graph-neural-networks": {
                "message-passing": [
                    "gcn", "gat", "graphsage", "gin",
                    "equivariant-networks", "geometric-deep-learning",
                ],
                "knowledge-graphs": [
                    "link-prediction", "entity-embeddings", "relation-extraction",
                    "graph-completion", "ontology-learning",
                ],
            },
        },
        "reinforcement-learning": {
            "policy-gradient": {
                "proximal-policy": ["ppo-clip", "ppo-penalty", "trpo"],
                "actor-critic": ["a2c", "a3c", "sac", "td3", "ddpg"],
            },
            "value-based": {
                "q-learning": ["dqn", "double-dqn", "dueling-dqn", "rainbow-dqn"],
                "model-based": ["dreamer", "world-models", "muzero", "alphazero"],
            },
            "multi-agent": {
                "cooperative": ["mappo", "qmix", "maddpg"],
                "competitive": ["self-play", "population-based-training"],
            },
        },
        "natural-language-processing": {
            "text-generation": {
                "language-modeling": [
                    "causal-lm", "masked-lm", "prefix-lm",
                    "retrieval-augmented-generation", "chain-of-thought",
                ],
                "summarization": [
                    "extractive-summarization", "abstractive-summarization",
                    "multi-document-summarization", "dialogue-summarization",
                ],
                "machine-translation": [
                    "neural-machine-translation", "multilingual-models",
                    "low-resource-translation", "simultaneous-translation",
                ],
            },
            "text-understanding": {
                "named-entity-recognition": [
                    "ner-tagging", "nested-ner", "few-shot-ner",
                    "biomedical-ner", "financial-ner",
                ],
                "sentiment-analysis": [
                    "aspect-based-sentiment", "multimodal-sentiment",
                    "stance-detection", "emotion-recognition",
                ],
                "question-answering": [
                    "extractive-qa", "generative-qa", "open-domain-qa",
                    "table-qa", "visual-qa",
                ],
                "text-classification": [
                    "topic-classification", "intent-detection",
                    "spam-detection", "toxicity-detection",
                ],
            },
            "information-retrieval": {
                "dense-retrieval": [
                    "bi-encoder", "cross-encoder", "colbert",
                    "contrastive-learning", "hard-negative-mining",
                ],
                "sparse-retrieval": [
                    "bm25", "splade", "learned-sparse-retrieval",
                ],
                "hybrid-search": [
                    "reciprocal-rank-fusion", "learned-routing",
                ],
            },
        },
        "classical-ml": {
            "supervised-learning": {
                "classification": [
                    "logistic-regression", "svm", "random-forest",
                    "gradient-boosting", "xgboost", "lightgbm", "catboost",
                    "naive-bayes", "knn-classifier",
                ],
                "regression": [
                    "linear-regression", "ridge-regression", "lasso",
                    "elastic-net", "polynomial-regression",
                    "support-vector-regression", "gradient-boosted-regression",
                ],
            },
            "unsupervised-learning": {
                "clustering": [
                    "kmeans", "dbscan", "hierarchical-clustering",
                    "gaussian-mixture-models", "spectral-clustering",
                    "mean-shift", "optics",
                ],
                "dimensionality-reduction": [
                    "pca", "tsne", "umap", "autoencoders",
                    "factor-analysis", "ica",
                ],
                "anomaly-detection": [
                    "isolation-forest", "one-class-svm",
                    "local-outlier-factor", "autoencoder-anomaly",
                ],
            },
            "feature-engineering": {
                "feature-selection": [
                    "mutual-information", "recursive-feature-elimination",
                    "lasso-selection", "boruta",
                ],
                "feature-transformation": [
                    "standard-scaling", "min-max-scaling",
                    "power-transform", "quantile-transform",
                    "target-encoding", "ordinal-encoding",
                ],
            },
        },
        "mlops": {
            "experiment-tracking": {
                "logging-frameworks": [
                    "mlflow", "wandb", "tensorboard", "neptune",
                    "comet-ml", "aim",
                ],
                "hyperparameter-tuning": [
                    "bayesian-optimization", "grid-search", "random-search",
                    "optuna", "ray-tune", "hyperband",
                ],
            },
            "model-serving": {
                "inference-engines": [
                    "triton-server", "torchserve", "tensorflow-serving",
                    "onnx-runtime", "vllm", "text-generation-inference",
                ],
                "model-formats": [
                    "onnx", "torchscript", "saved-model", "gguf",
                    "safetensors", "tensorrt",
                ],
            },
            "data-pipeline": {
                "data-versioning": [
                    "dvc", "lakefs", "delta-lake", "iceberg",
                ],
                "data-validation": [
                    "great-expectations", "pandera", "pydantic-validation",
                    "schema-enforcement",
                ],
                "feature-stores": [
                    "feast", "tecton", "hopsworks", "bytehub",
                ],
            },
        },
    },
    "web-development": {
        "frontend": {
            "javascript-frameworks": {
                "react-ecosystem": [
                    "react-hooks", "react-server-components", "react-suspense",
                    "react-context", "react-portal", "react-query",
                    "next-js", "remix", "gatsby", "react-native",
                    "react-router", "react-hook-form", "zustand", "jotai",
                ],
                "vue-ecosystem": [
                    "vue-composition-api", "vuex", "pinia",
                    "nuxt-js", "vue-router", "vuetify",
                    "primevue", "quasar",
                ],
                "angular-ecosystem": [
                    "angular-signals", "angular-standalone-components",
                    "ngrx", "angular-material", "rxjs",
                    "angular-universal", "angular-cdk",
                ],
                "svelte-ecosystem": [
                    "sveltekit", "svelte-stores", "svelte-actions",
                    "svelte-transitions",
                ],
                "meta-frameworks": [
                    "astro", "qwik", "solid-js", "htmx",
                    "alpine-js", "preact",
                ],
            },
            "css-styling": {
                "css-frameworks": [
                    "tailwind-css", "bootstrap", "bulma",
                    "material-ui", "chakra-ui", "shadcn-ui",
                    "radix-ui", "headless-ui",
                ],
                "css-in-js": [
                    "styled-components", "emotion", "vanilla-extract",
                    "css-modules", "linaria", "panda-css",
                ],
                "css-features": [
                    "css-grid", "css-flexbox", "css-container-queries",
                    "css-has-selector", "css-nesting", "css-layers",
                    "css-scroll-driven-animations", "css-view-transitions",
                ],
            },
            "state-management": {
                "client-state": [
                    "redux-toolkit", "zustand-store", "recoil",
                    "mobx", "xstate", "signals",
                    "nanostores", "valtio",
                ],
                "server-state": [
                    "tanstack-query", "swr", "apollo-client",
                    "urql", "relay",
                ],
            },
            "build-tools": {
                "bundlers": [
                    "vite", "webpack", "esbuild", "rollup",
                    "turbopack", "rspack", "parcel",
                ],
                "package-managers": [
                    "npm", "pnpm", "yarn", "bun-package-manager",
                ],
                "dev-tools": [
                    "storybook", "chromatic", "ladle",
                    "histoire", "styleguidist",
                ],
            },
        },
        "backend": {
            "web-frameworks": {
                "python-frameworks": [
                    "fastapi", "django", "flask", "starlette",
                    "litestar", "sanic", "tornado",
                ],
                "node-frameworks": [
                    "express", "nestjs", "fastify", "koa",
                    "hono", "elysia", "adonis",
                ],
                "rust-frameworks": [
                    "actix-web", "axum", "rocket", "warp",
                    "poem", "tide",
                ],
                "go-frameworks": [
                    "gin", "echo", "fiber", "chi",
                    "gorilla-mux", "buffalo",
                ],
            },
            "api-design": {
                "rest-api": [
                    "openapi-spec", "json-api", "hateoas",
                    "api-versioning", "content-negotiation",
                    "pagination-patterns", "rate-limiting",
                ],
                "graphql": [
                    "graphql-schema", "graphql-resolvers",
                    "graphql-subscriptions", "graphql-federation",
                    "apollo-server", "strawberry-graphql",
                ],
                "grpc": [
                    "protocol-buffers", "grpc-streaming",
                    "grpc-interceptors", "grpc-web",
                ],
                "websockets": [
                    "socket-io", "websocket-protocol",
                    "server-sent-events", "long-polling",
                ],
            },
            "authentication": {
                "auth-protocols": [
                    "oauth2", "oidc", "saml", "jwt-tokens",
                    "api-keys", "basic-auth", "session-auth",
                ],
                "auth-providers": [
                    "auth0", "firebase-auth", "supabase-auth",
                    "keycloak", "clerk", "nextauth",
                ],
                "authorization": [
                    "rbac", "abac", "casbin", "opa-policies",
                    "row-level-security", "multi-tenancy",
                ],
            },
        },
        "full-stack": {
            "meta-frameworks": {
                "react-full-stack": [
                    "next-js-app-router", "next-js-pages-router",
                    "remix-framework", "blitz-js",
                ],
                "vue-full-stack": [
                    "nuxt-3", "nuxt-content", "nuxt-modules",
                ],
                "multi-runtime": [
                    "astro-framework", "fresh-deno", "qwik-city",
                ],
            },
            "deployment": {
                "hosting-platforms": [
                    "vercel", "netlify", "cloudflare-pages",
                    "fly-io", "railway", "render",
                ],
                "edge-computing": [
                    "cloudflare-workers", "deno-deploy",
                    "vercel-edge-functions", "lambda-edge",
                ],
            },
        },
    },
    "data-engineering": {
        "databases": {
            "relational-databases": {
                "sql-engines": [
                    "postgresql", "mysql", "sqlite", "mariadb",
                    "cockroachdb", "yugabytedb", "tidb",
                ],
                "query-optimization": [
                    "index-strategies", "query-planning",
                    "materialized-views", "partitioning",
                    "connection-pooling", "read-replicas",
                ],
                "orm-tools": [
                    "sqlalchemy", "prisma", "drizzle-orm",
                    "typeorm", "sequelize", "django-orm",
                ],
            },
            "nosql-databases": {
                "document-stores": [
                    "mongodb", "couchdb", "firestore",
                    "amazon-documentdb", "fauna",
                ],
                "key-value-stores": [
                    "redis", "memcached", "dynamodb",
                    "etcd", "foundationdb",
                ],
                "column-stores": [
                    "cassandra", "scylladb", "hbase",
                    "clickhouse", "apache-druid",
                ],
                "graph-databases": [
                    "neo4j", "arangodb", "tigergraph",
                    "janusgraph", "amazon-neptune",
                ],
            },
            "vector-databases": {
                "purpose-built": [
                    "pinecone", "weaviate", "qdrant",
                    "milvus", "chromadb", "lancedb",
                ],
                "extensions": [
                    "pgvector", "elasticsearch-knn",
                    "opensearch-knn", "redis-vss",
                ],
            },
            "time-series-databases": {
                "tsdb-engines": [
                    "influxdb", "timescaledb", "prometheus",
                    "questdb", "victoriametrics",
                ],
            },
        },
        "data-processing": {
            "batch-processing": {
                "frameworks": [
                    "apache-spark", "apache-flink", "dask",
                    "ray-data", "polars", "duckdb",
                    "apache-beam",
                ],
                "orchestration": [
                    "apache-airflow", "prefect", "dagster",
                    "mage-ai", "temporal", "argo-workflows",
                ],
            },
            "stream-processing": {
                "event-streaming": [
                    "apache-kafka", "apache-pulsar",
                    "amazon-kinesis", "redpanda",
                ],
                "stream-compute": [
                    "kafka-streams", "flink-streaming",
                    "spark-streaming", "bytewax",
                ],
                "event-driven": [
                    "event-sourcing", "cqrs", "saga-pattern",
                    "outbox-pattern",
                ],
            },
            "data-transformation": {
                "etl-tools": [
                    "dbt", "singer-taps", "airbyte",
                    "fivetran", "stitch",
                ],
                "data-quality": [
                    "great-expectations", "soda-core",
                    "monte-carlo", "elementary",
                ],
            },
        },
        "data-analytics": {
            "business-intelligence": {
                "visualization": [
                    "tableau", "looker", "metabase",
                    "superset", "grafana", "redash",
                ],
                "notebooks": [
                    "jupyter", "observable", "hex",
                    "deepnote", "databricks-notebooks",
                ],
            },
            "data-science": {
                "python-libraries": [
                    "pandas", "numpy", "scipy",
                    "scikit-learn-library", "statsmodels",
                    "matplotlib", "seaborn", "plotly",
                ],
                "statistical-methods": [
                    "hypothesis-testing", "bayesian-inference",
                    "time-series-analysis", "causal-inference",
                    "ab-testing",
                ],
            },
        },
    },
    "devops": {
        "containerization": {
            "container-runtimes": {
                "docker-ecosystem": [
                    "dockerfile", "docker-compose", "docker-swarm",
                    "docker-buildx", "multi-stage-builds",
                    "distroless-images", "alpine-images",
                ],
                "alternative-runtimes": [
                    "podman", "containerd", "cri-o",
                    "buildah", "kaniko",
                ],
            },
            "kubernetes": {
                "core-concepts": [
                    "pods", "deployments", "services",
                    "configmaps", "secrets", "namespaces",
                    "persistent-volumes", "statefulsets",
                ],
                "advanced-k8s": [
                    "helm-charts", "kustomize", "operators",
                    "custom-resources", "admission-webhooks",
                    "network-policies", "pod-security-standards",
                ],
                "k8s-tools": [
                    "kubectl", "k9s", "lens",
                    "argo-cd", "flux-cd", "tekton",
                ],
                "service-mesh": [
                    "istio", "linkerd", "cilium",
                    "consul-connect", "envoy-proxy",
                ],
            },
        },
        "ci-cd": {
            "ci-platforms": {
                "cloud-ci": [
                    "github-actions", "gitlab-ci", "circleci",
                    "jenkins", "buildkite", "drone-ci",
                    "azure-devops", "bitbucket-pipelines",
                ],
                "ci-practices": [
                    "trunk-based-development", "feature-flags",
                    "blue-green-deployment", "canary-deployment",
                    "rolling-updates", "a-b-testing-deployment",
                ],
            },
            "infrastructure-as-code": {
                "provisioning": [
                    "terraform", "pulumi", "crossplane",
                    "cloudformation", "cdk",
                    "ansible", "salt",
                ],
                "configuration-management": [
                    "ansible-playbooks", "chef", "puppet",
                    "nix-os", "guix",
                ],
            },
        },
        "observability": {
            "monitoring": {
                "metrics": [
                    "prometheus-metrics", "grafana-dashboards",
                    "datadog", "new-relic", "dynatrace",
                    "opentelemetry-metrics",
                ],
                "logging": [
                    "elasticsearch-logging", "loki",
                    "fluentd", "logstash", "vector-logging",
                    "structured-logging",
                ],
                "tracing": [
                    "opentelemetry-tracing", "jaeger",
                    "zipkin", "tempo", "honeycomb",
                    "distributed-tracing",
                ],
                "alerting": [
                    "pagerduty", "opsgenie", "alertmanager",
                    "incident-management", "sla-monitoring",
                ],
            },
        },
        "cloud-platforms": {
            "aws": {
                "compute": [
                    "ec2", "lambda", "ecs",
                    "fargate", "eks", "lightsail",
                ],
                "storage": [
                    "s3", "ebs", "efs",
                    "glacier", "fsx",
                ],
                "networking": [
                    "vpc", "cloudfront", "route53",
                    "api-gateway-aws", "elb",
                ],
            },
            "gcp": {
                "compute": [
                    "compute-engine", "cloud-functions",
                    "cloud-run", "gke", "app-engine",
                ],
                "data": [
                    "bigquery", "cloud-storage-gcp",
                    "cloud-sql", "firestore-gcp", "bigtable",
                ],
            },
            "azure": {
                "compute": [
                    "azure-vms", "azure-functions",
                    "azure-container-instances", "aks",
                    "azure-app-service",
                ],
                "data": [
                    "azure-sql", "cosmos-db",
                    "azure-blob-storage", "azure-data-lake",
                ],
            },
        },
    },
    "security": {
        "application-security": {
            "vulnerability-scanning": {
                "sast-tools": [
                    "semgrep", "sonarqube", "bandit",
                    "codeql", "snyk-code",
                ],
                "dast-tools": [
                    "owasp-zap", "burp-suite", "nuclei",
                    "nikto",
                ],
                "sca-tools": [
                    "snyk", "dependabot", "renovate",
                    "trivy", "grype",
                ],
            },
            "secure-coding": {
                "owasp-top-ten": [
                    "injection-prevention", "broken-authentication",
                    "sensitive-data-exposure", "xxe-prevention",
                    "broken-access-control", "security-misconfiguration",
                    "xss-prevention", "insecure-deserialization",
                    "insufficient-logging", "ssrf-prevention",
                ],
                "input-validation": [
                    "sql-injection-prevention", "xss-sanitization",
                    "csrf-tokens", "content-security-policy",
                    "cors-configuration",
                ],
            },
        },
        "infrastructure-security": {
            "network-security": {
                "firewalls": [
                    "waf", "network-acl", "security-groups",
                    "zero-trust-networking",
                ],
                "encryption": [
                    "tls-ssl", "certificate-management",
                    "mutual-tls", "encryption-at-rest",
                    "key-management", "vault",
                ],
            },
            "identity-management": {
                "iam": [
                    "aws-iam", "gcp-iam", "azure-ad",
                    "sso", "mfa",
                ],
                "secrets-management": [
                    "hashicorp-vault", "aws-secrets-manager",
                    "azure-key-vault", "gcp-secret-manager",
                    "sops",
                ],
            },
        },
        "compliance": {
            "standards": {
                "frameworks": [
                    "soc2", "iso-27001", "pci-dss",
                    "hipaa", "gdpr", "ccpa",
                ],
                "audit": [
                    "audit-logging", "compliance-monitoring",
                    "policy-as-code", "drift-detection",
                ],
            },
        },
    },
    "mobile-development": {
        "cross-platform": {
            "react-native-ecosystem": {
                "core-concepts": [
                    "react-native-navigation", "expo",
                    "native-modules", "hermes-engine",
                    "react-native-reanimated", "react-native-gesture-handler",
                ],
                "libraries": [
                    "react-native-paper", "nativewind",
                    "react-native-screens", "react-native-svg",
                ],
            },
            "flutter-ecosystem": {
                "core-concepts": [
                    "flutter-widgets", "dart-language",
                    "flutter-state-management", "flutter-navigation",
                    "flutter-animations", "flutter-plugins",
                ],
                "flutter-packages": [
                    "riverpod", "bloc-pattern", "getx",
                    "flutter-hooks",
                ],
            },
            "kotlin-multiplatform": {
                "kmp-concepts": [
                    "compose-multiplatform", "kmp-shared-logic",
                    "expect-actual", "kmp-serialization",
                ],
            },
        },
        "native-development": {
            "ios": {
                "swift-ui": [
                    "swiftui-views", "swiftui-data-flow",
                    "swiftui-navigation", "swiftui-animations",
                    "combine-framework", "async-await-swift",
                ],
                "uikit": [
                    "uikit-views", "auto-layout",
                    "core-data", "uikit-collections",
                ],
            },
            "android": {
                "jetpack-compose": [
                    "compose-state", "compose-navigation",
                    "compose-theming", "compose-animations",
                ],
                "android-architecture": [
                    "mvvm-android", "room-database",
                    "hilt-di", "coroutines-android",
                    "flow-android", "workmanager",
                ],
            },
        },
    },
    "ai-agents": {
        "agent-frameworks": {
            "python-agent-frameworks": {
                "orchestration": [
                    "langchain", "llamaindex", "crewai",
                    "autogen", "pydantic-ai", "semantic-kernel",
                    "haystack", "dspy",
                ],
                "tool-use": [
                    "function-calling", "mcp-protocol",
                    "tool-registration", "structured-output",
                    "json-mode", "tool-chaining",
                ],
            },
            "agent-patterns": {
                "architectures": [
                    "react-agent-pattern", "plan-and-execute",
                    "reflexion", "tree-of-thoughts",
                    "chain-of-thought", "few-shot-prompting",
                ],
                "memory": [
                    "short-term-memory", "long-term-memory",
                    "episodic-memory", "semantic-memory",
                    "vector-store-memory", "summary-memory",
                ],
                "multi-agent": [
                    "agent-swarms", "hierarchical-agents",
                    "debate-protocols", "consensus-mechanisms",
                    "role-based-agents",
                ],
            },
        },
        "rag-systems": {
            "retrieval-pipeline": {
                "document-processing": [
                    "chunking-strategies", "recursive-splitting",
                    "semantic-chunking", "document-parsing",
                    "pdf-extraction", "table-extraction",
                ],
                "indexing": [
                    "vector-indexing", "hybrid-indexing",
                    "hierarchical-indexing", "parent-document-retrieval",
                    "multi-index-strategies",
                ],
                "retrieval-strategies": [
                    "semantic-search", "keyword-search",
                    "hybrid-search-retrieval", "reranking",
                    "query-transformation", "hyde-retrieval",
                ],
            },
            "generation-pipeline": {
                "context-assembly": [
                    "context-window-management", "context-compression",
                    "lost-in-the-middle", "citation-generation",
                ],
                "evaluation": [
                    "ragas-metrics", "faithfulness-eval",
                    "answer-relevancy", "context-precision",
                    "hallucination-detection",
                ],
            },
        },
        "coding-assistants": {
            "code-generation": {
                "tools": [
                    "github-copilot", "cursor-editor",
                    "claude-code", "cody-sourcegraph",
                    "continue-dev", "aider",
                ],
                "techniques": [
                    "code-completion", "code-refactoring",
                    "test-generation", "documentation-generation",
                    "code-review-ai", "bug-detection-ai",
                ],
            },
        },
    },
    "testing": {
        "test-frameworks": {
            "unit-testing": {
                "python-testing": [
                    "pytest", "pytest-fixtures", "pytest-parametrize",
                    "pytest-mock", "hypothesis-testing-framework",
                    "coverage-py", "mutmut",
                ],
                "javascript-testing": [
                    "jest", "vitest", "mocha",
                    "testing-library", "cypress",
                    "playwright-testing", "puppeteer",
                ],
            },
            "integration-testing": {
                "api-testing": [
                    "postman", "httpx-testing", "supertest",
                    "rest-assured", "karate-framework",
                ],
                "database-testing": [
                    "testcontainers", "factory-boy",
                    "faker-library", "database-fixtures",
                ],
            },
            "e2e-testing": {
                "browser-testing": [
                    "playwright-e2e", "cypress-e2e",
                    "selenium", "webdriverio",
                    "test-cafe",
                ],
                "mobile-testing": [
                    "appium", "detox", "maestro",
                    "espresso", "xctest",
                ],
            },
        },
        "test-practices": {
            "methodologies": {
                "approaches": [
                    "test-driven-development", "behavior-driven-development",
                    "acceptance-test-driven", "property-based-testing",
                    "mutation-testing", "snapshot-testing",
                    "contract-testing", "chaos-engineering",
                ],
            },
            "ci-testing": {
                "automation": [
                    "test-parallelization", "flaky-test-detection",
                    "test-impact-analysis", "visual-regression",
                    "accessibility-testing", "performance-testing",
                    "load-testing", "stress-testing",
                ],
            },
        },
    },
}


class GitHubTopicsGenerator(SeedGenerator):
    """Generates a feature ontology hierarchy modeled after GitHub Topics.

    Produces a deterministic taxonomy of software engineering topics
    organized in a hierarchical tree with 5-7 levels of depth. Each
    node gets a dot-separated ID (e.g., ``gh.ml.deep-learning.transformers``)
    and appropriate tags and descriptions.

    The generator produces approximately 15K-20K nodes covering:
    - Machine Learning (deep learning, NLP, RL, classical ML, MLOps)
    - Web Development (frontend, backend, full-stack)
    - Data Engineering (databases, processing, analytics)
    - DevOps (containers, CI/CD, observability, cloud)
    - Security (application, infrastructure, compliance)
    - Mobile Development (cross-platform, native)
    - AI Agents (frameworks, RAG, coding assistants)
    - Testing (frameworks, practices)
    """

    @property
    def name(self) -> str:
        """Return generator name."""
        return "GitHub Topics"

    @property
    def source_prefix(self) -> str:
        """Return ID prefix for GitHub-sourced nodes."""
        return "gh"

    def generate(self) -> list[FeatureNode]:
        """Generate the full GitHub Topics hierarchy.

        Returns:
            List of :class:`FeatureNode` instances forming the complete
            hierarchy. Root nodes have ``parent_id=None``.
        """
        nodes: list[FeatureNode] = []
        self._walk_taxonomy(_TAXONOMY, parent_id=None, level=0, nodes=nodes)
        return nodes

    def _walk_taxonomy(
        self,
        tree: dict | list,
        parent_id: str | None,
        level: int,
        nodes: list[FeatureNode],
        prefix: str = "",
    ) -> None:
        """Recursively walk the taxonomy tree, creating FeatureNode instances.

        Args:
            tree: Current level of the taxonomy (dict for branches, list for leaves).
            parent_id: ID of the parent node (None for roots).
            level: Current depth in the hierarchy.
            nodes: Accumulator list for generated nodes.
            prefix: Dot-separated ID prefix built up during recursion.
        """
        if isinstance(tree, list):
            # Leaf level: list of terminal topic names
            for topic_name in tree:
                node_id = f"{prefix}.{topic_name}" if prefix else f"gh.{topic_name}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(topic_name),
                    description=f"{self._humanize(topic_name)} in software development",
                    parent_id=parent_id,
                    level=level,
                    tags=self._generate_tags(topic_name, level),
                    metadata={"source": "github-topics", "generator": "seed"},
                )
                nodes.append(node)
        elif isinstance(tree, dict):
            for key, subtree in tree.items():
                node_id = f"{prefix}.{key}" if prefix else f"gh.{key}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(key),
                    description=f"{self._humanize(key)} domain in software engineering",
                    parent_id=parent_id,
                    level=level,
                    tags=self._generate_tags(key, level),
                    metadata={"source": "github-topics", "generator": "seed"},
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
        """Convert a slug like 'deep-learning' to 'Deep Learning'."""
        return slug.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _generate_tags(name: str, level: int) -> list[str]:
        """Generate tags for a node based on its name and level.

        Tags include the hyphenated name parts and a level indicator.
        """
        parts = name.split("-")
        tags = [p for p in parts if len(p) > 2]
        if level == 0:
            tags.append("domain")
        elif level == 1:
            tags.append("subdomain")
        elif level == 2:
            tags.append("area")
        elif level == 3:
            tags.append("topic")
        else:
            tags.append("subtopic")
        return tags
