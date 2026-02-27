"""Library documentation hierarchy generator for ontology seed data.

Generates feature ontology nodes modeled after popular library API
documentation hierarchies (scikit-learn, React, Django, TensorFlow, etc.).
Deterministic -- no API calls.

Implements Task 2.1.2 of PRD-RPG-P2-001.
"""

from __future__ import annotations

from cobuilder.repomap.ontology.models import FeatureNode
from cobuilder.repomap.ontology.scrapers.base import SeedGenerator

# ---------------------------------------------------------------------------
# Library API hierarchies
# ---------------------------------------------------------------------------
# Each library maps: {module: {submodule: {class_or_func: [methods/params]}}}

_LIBRARIES: dict[str, dict] = {
    "scikit-learn": {
        "sklearn-preprocessing": {
            "scalers": {
                "standard-scaler": [
                    "fit", "transform", "fit-transform",
                    "inverse-transform", "partial-fit",
                    "get-params", "set-params",
                ],
                "min-max-scaler": [
                    "fit", "transform", "fit-transform",
                    "inverse-transform", "partial-fit",
                    "data-range", "feature-range",
                ],
                "robust-scaler": [
                    "fit", "transform", "fit-transform",
                    "quantile-range", "centering",
                ],
                "max-abs-scaler": ["fit", "transform", "fit-transform"],
                "normalizer": ["fit", "transform", "norm-options"],
            },
            "encoders": {
                "one-hot-encoder": [
                    "fit", "transform", "categories",
                    "drop-options", "sparse-output",
                    "handle-unknown", "min-frequency",
                ],
                "label-encoder": [
                    "fit", "transform", "inverse-transform",
                    "classes-attribute",
                ],
                "ordinal-encoder": [
                    "fit", "transform", "categories",
                    "handle-unknown", "unknown-value",
                ],
                "target-encoder-sklearn": [
                    "fit", "transform", "smooth",
                    "target-type",
                ],
            },
            "imputers": {
                "simple-imputer": [
                    "strategy-options", "fill-value",
                    "missing-values", "add-indicator",
                ],
                "knn-imputer": [
                    "n-neighbors", "weights",
                    "metric", "missing-values",
                ],
                "iterative-imputer": [
                    "estimator", "max-iter",
                    "initial-strategy", "imputation-order",
                ],
            },
        },
        "sklearn-model-selection": {
            "splitters": {
                "k-fold": [
                    "n-splits", "shuffle", "random-state",
                    "split-method", "get-n-splits",
                ],
                "stratified-k-fold": [
                    "n-splits", "shuffle", "random-state",
                    "split-method",
                ],
                "time-series-split": [
                    "n-splits", "max-train-size",
                    "test-size", "gap",
                ],
                "group-k-fold": ["n-splits", "split-method"],
                "leave-one-out": ["split-method", "get-n-splits"],
            },
            "search": {
                "grid-search-cv": [
                    "param-grid", "scoring", "cv",
                    "refit", "n-jobs", "verbose",
                    "best-params", "best-score", "cv-results",
                ],
                "randomized-search-cv": [
                    "param-distributions", "n-iter",
                    "scoring", "cv", "random-state",
                ],
                "halving-grid-search": [
                    "factor", "resource", "min-resources",
                    "aggressive-elimination",
                ],
            },
            "metrics": {
                "classification-metrics": [
                    "accuracy-score", "precision-score",
                    "recall-score", "f1-score",
                    "roc-auc-score", "confusion-matrix",
                    "classification-report",
                ],
                "regression-metrics": [
                    "mean-squared-error", "mean-absolute-error",
                    "r2-score", "mean-absolute-percentage-error",
                    "median-absolute-error",
                ],
                "clustering-metrics": [
                    "silhouette-score", "adjusted-rand-index",
                    "normalized-mutual-info", "calinski-harabasz",
                ],
            },
        },
        "sklearn-ensemble": {
            "forest-models": {
                "random-forest-classifier": [
                    "n-estimators", "max-depth", "min-samples-split",
                    "min-samples-leaf", "max-features",
                    "bootstrap", "oob-score", "feature-importances",
                ],
                "random-forest-regressor": [
                    "n-estimators", "max-depth", "criterion",
                    "min-samples-split",
                ],
                "extra-trees-classifier": [
                    "n-estimators", "max-depth", "max-features",
                ],
            },
            "boosting-models": {
                "gradient-boosting-classifier": [
                    "n-estimators", "learning-rate", "max-depth",
                    "subsample", "loss-function",
                ],
                "gradient-boosting-regressor": [
                    "n-estimators", "learning-rate", "max-depth",
                    "alpha-quantile",
                ],
                "hist-gradient-boosting": [
                    "max-iter", "max-depth", "learning-rate",
                    "early-stopping", "categorical-features",
                ],
                "adaboost-classifier": [
                    "n-estimators", "learning-rate",
                    "algorithm-option",
                ],
            },
            "voting-stacking": {
                "voting-classifier": [
                    "estimators", "voting-type", "weights",
                ],
                "stacking-classifier": [
                    "estimators", "final-estimator", "cv",
                    "stack-method",
                ],
                "bagging-classifier": [
                    "estimator", "n-estimators",
                    "max-samples", "max-features",
                ],
            },
        },
        "sklearn-pipeline": {
            "pipeline-tools": {
                "pipeline-class": [
                    "steps", "memory", "verbose",
                    "fit", "predict", "score",
                    "set-params", "get-params",
                ],
                "column-transformer": [
                    "transformers", "remainder",
                    "sparse-threshold", "n-jobs",
                ],
                "feature-union": [
                    "transformer-list", "n-jobs",
                    "transformer-weights",
                ],
                "function-transformer": [
                    "func", "inverse-func", "validate",
                ],
            },
        },
    },
    "react": {
        "react-core": {
            "hooks": {
                "state-hooks": [
                    "use-state", "use-reducer", "use-sync-external-store",
                ],
                "effect-hooks": [
                    "use-effect", "use-layout-effect",
                    "use-insertion-effect",
                ],
                "ref-hooks": [
                    "use-ref", "use-imperative-handle",
                ],
                "context-hooks": [
                    "use-context",
                ],
                "performance-hooks": [
                    "use-memo", "use-callback", "use-transition",
                    "use-deferred-value",
                ],
                "react-19-hooks": [
                    "use-action-state", "use-form-status",
                    "use-optimistic", "use-hook",
                ],
            },
            "components": {
                "component-types": [
                    "function-components", "server-components",
                    "client-components", "error-boundaries",
                    "suspense-boundaries", "portals",
                ],
                "component-patterns": [
                    "controlled-components", "uncontrolled-components",
                    "higher-order-components", "render-props",
                    "compound-components", "headless-components",
                ],
            },
            "rendering": {
                "rendering-strategies": [
                    "client-side-rendering", "server-side-rendering",
                    "static-site-generation", "incremental-static-regeneration",
                    "streaming-ssr", "partial-prerendering",
                ],
                "reconciliation": [
                    "virtual-dom", "fiber-architecture",
                    "concurrent-rendering", "batched-updates",
                    "selective-hydration",
                ],
            },
        },
        "react-ecosystem": {
            "routing": {
                "react-router-lib": [
                    "browser-router", "route-matching",
                    "nested-routes", "route-loaders",
                    "route-actions", "error-routes",
                ],
                "next-router": [
                    "app-router", "pages-router",
                    "dynamic-routes", "catch-all-routes",
                    "middleware", "parallel-routes",
                    "intercepting-routes",
                ],
            },
            "state-libraries": {
                "redux-ecosystem": [
                    "redux-store", "redux-slices",
                    "redux-thunk", "rtk-query",
                    "redux-selectors", "redux-middleware",
                ],
                "zustand-lib": [
                    "zustand-create", "zustand-middleware",
                    "zustand-devtools", "zustand-persist",
                    "zustand-immer",
                ],
                "tanstack-query-lib": [
                    "use-query", "use-mutation",
                    "query-client", "query-keys",
                    "infinite-queries", "prefetching",
                    "optimistic-updates",
                ],
            },
            "form-libraries": {
                "react-hook-form-lib": [
                    "register", "handle-submit",
                    "form-state", "validation",
                    "field-arrays", "watch",
                ],
                "formik": [
                    "formik-form", "formik-field",
                    "validation-schema", "form-helpers",
                ],
            },
        },
    },
    "django": {
        "django-core": {
            "models": {
                "field-types": [
                    "char-field", "text-field", "integer-field",
                    "float-field", "boolean-field", "date-field",
                    "datetime-field", "json-field", "uuid-field",
                    "foreign-key", "many-to-many", "one-to-one",
                    "file-field", "image-field",
                ],
                "querysets": [
                    "filter", "exclude", "annotate",
                    "aggregate", "values", "values-list",
                    "select-related", "prefetch-related",
                    "defer", "only", "raw-queries",
                    "f-expressions", "q-objects",
                ],
                "managers": [
                    "default-manager", "custom-manager",
                    "manager-methods", "queryset-as-manager",
                ],
            },
            "views": {
                "function-views": [
                    "request-object", "response-object",
                    "http-methods", "decorators",
                ],
                "class-based-views": [
                    "template-view", "list-view", "detail-view",
                    "create-view", "update-view", "delete-view",
                    "form-view", "mixin-classes",
                ],
                "api-views": [
                    "drf-api-view", "drf-viewset",
                    "drf-serializers", "drf-permissions",
                    "drf-authentication", "drf-pagination",
                    "drf-filtering", "drf-throttling",
                ],
            },
            "templates": {
                "template-features": [
                    "template-tags", "template-filters",
                    "template-inheritance", "includes",
                    "context-processors", "custom-tags",
                ],
            },
            "forms": {
                "form-handling": [
                    "form-class", "model-form",
                    "form-validation", "formsets",
                    "inline-formsets", "form-widgets",
                ],
            },
        },
        "django-ecosystem": {
            "middleware": {
                "built-in-middleware": [
                    "security-middleware", "session-middleware",
                    "authentication-middleware", "csrf-middleware",
                    "common-middleware", "gzip-middleware",
                ],
                "custom-middleware": [
                    "process-request", "process-response",
                    "process-exception", "async-middleware",
                ],
            },
            "admin": {
                "admin-features": [
                    "model-admin", "inline-admin",
                    "admin-actions", "admin-filters",
                    "admin-search", "admin-custom-views",
                ],
            },
            "django-channels": {
                "websocket-features": [
                    "consumers", "routing-channels",
                    "channel-layers", "async-consumers",
                    "websocket-groups",
                ],
            },
        },
    },
    "tensorflow": {
        "tf-core": {
            "tensors": {
                "tensor-ops": [
                    "tensor-creation", "tensor-manipulation",
                    "tensor-math", "tensor-indexing",
                    "broadcasting", "gradient-tape",
                ],
            },
            "keras-api": {
                "layers": [
                    "dense-layer", "conv2d-layer", "lstm-layer",
                    "attention-layer", "embedding-layer",
                    "dropout-layer", "batch-normalization",
                    "layer-normalization", "multi-head-attention",
                ],
                "models": [
                    "sequential-model", "functional-api",
                    "model-subclassing", "model-compile",
                    "model-fit", "model-evaluate",
                    "model-save-load", "callbacks",
                ],
                "optimizers": [
                    "adam-optimizer", "sgd-optimizer",
                    "rmsprop", "adagrad",
                    "learning-rate-schedules",
                ],
                "losses": [
                    "cross-entropy-loss", "mse-loss",
                    "huber-loss", "focal-loss",
                    "custom-loss-functions",
                ],
            },
        },
        "tf-ecosystem": {
            "tf-data": {
                "data-pipeline": [
                    "tf-dataset", "tf-map", "tf-batch",
                    "tf-shuffle", "tf-prefetch",
                    "tf-interleave", "tf-from-generator",
                    "tfrecords",
                ],
            },
            "tf-serving": {
                "deployment": [
                    "saved-model-format", "tf-lite",
                    "tf-js", "tf-serving-api",
                    "signature-defs",
                ],
            },
            "tf-hub": {
                "model-hub": [
                    "pretrained-models", "feature-extraction",
                    "fine-tuning-tf", "model-registry",
                ],
            },
        },
    },
    "pytorch": {
        "torch-core": {
            "tensors": {
                "tensor-operations": [
                    "tensor-creation-torch", "tensor-indexing-torch",
                    "tensor-math-torch", "autograd",
                    "backward-pass", "gradient-accumulation",
                    "no-grad-context", "inference-mode",
                ],
            },
            "nn-module": {
                "layers-torch": [
                    "linear-layer", "conv2d-torch", "lstm-torch",
                    "transformer-encoder", "transformer-decoder",
                    "multi-head-attention-torch", "embedding-torch",
                    "batch-norm-torch", "layer-norm-torch",
                    "group-norm", "dropout-torch",
                ],
                "model-building": [
                    "sequential-torch", "module-list",
                    "module-dict", "parameter-registration",
                    "forward-method", "custom-modules",
                ],
            },
            "optimization": {
                "optimizers-torch": [
                    "adam-torch", "adamw-torch", "sgd-torch",
                    "lr-scheduler", "cosine-annealing",
                    "one-cycle-lr", "warmup-scheduler",
                ],
            },
            "data-loading": {
                "dataset-tools": [
                    "torch-dataset", "dataloader",
                    "sampler", "collate-fn",
                    "distributed-sampler", "iterable-dataset",
                ],
            },
        },
        "torch-ecosystem": {
            "distributed-training": {
                "parallelism": [
                    "data-parallel", "distributed-data-parallel",
                    "fsdp", "pipeline-parallel",
                    "tensor-parallel", "deepspeed",
                    "megatron-lm",
                ],
            },
            "torch-compile": {
                "compilation": [
                    "torch-dynamo", "torch-inductor",
                    "export-api", "aot-autograd",
                ],
            },
            "huggingface": {
                "transformers-lib": [
                    "auto-model", "auto-tokenizer",
                    "trainer-api", "pipeline-api",
                    "model-hub-hf", "datasets-lib",
                    "peft-library", "trl-library",
                    "accelerate-library",
                ],
            },
        },
    },
    "fastapi-lib": {
        "fastapi-core": {
            "routing": {
                "route-handlers": [
                    "path-operations", "path-parameters",
                    "query-parameters", "request-body",
                    "response-model", "status-codes",
                    "dependencies-fastapi", "background-tasks",
                ],
                "advanced-routing": [
                    "api-router", "route-prefix",
                    "tags", "include-router",
                    "websocket-routes", "lifespan-events",
                ],
            },
            "validation": {
                "pydantic-integration": [
                    "base-model-fastapi", "field-validation",
                    "custom-validators", "nested-models",
                    "discriminated-unions-fastapi",
                    "computed-fields",
                ],
                "request-validation": [
                    "body-validation", "query-validation",
                    "header-validation", "cookie-validation",
                    "file-upload", "form-data",
                ],
            },
            "middleware-fastapi": {
                "middleware-types": [
                    "cors-middleware", "gzip-middleware-fastapi",
                    "trusted-host", "https-redirect",
                    "custom-middleware-fastapi",
                ],
            },
        },
        "fastapi-ecosystem": {
            "security-fastapi": {
                "auth-methods": [
                    "oauth2-fastapi", "jwt-fastapi",
                    "api-key-security", "http-basic",
                    "dependencies-security",
                ],
            },
            "database-fastapi": {
                "orm-integration": [
                    "sqlalchemy-fastapi", "tortoise-orm",
                    "sqlmodel", "database-sessions",
                    "async-database",
                ],
            },
            "testing-fastapi": {
                "test-tools": [
                    "test-client", "async-test-client",
                    "dependency-overrides", "test-database",
                ],
            },
        },
    },
}


class LibraryDocsGenerator(SeedGenerator):
    """Generates feature ontology nodes from library API documentation structures.

    Produces a deterministic hierarchy modeled after popular library APIs
    (scikit-learn, React, Django, TensorFlow, PyTorch, FastAPI). Each
    node gets an ID prefixed with ``lib.{library-name}``.

    The generator produces approximately 8K-12K nodes covering:
    - scikit-learn (preprocessing, model selection, ensemble, pipeline)
    - React (hooks, components, rendering, routing, state)
    - Django (models, views, templates, forms, admin)
    - TensorFlow (tensors, Keras layers/models, data pipeline)
    - PyTorch (tensors, nn.Module, distributed training, HuggingFace)
    - FastAPI (routing, validation, middleware, security)
    """

    @property
    def name(self) -> str:
        """Return generator name."""
        return "Library Docs"

    @property
    def source_prefix(self) -> str:
        """Return ID prefix for library-sourced nodes."""
        return "lib"

    def generate(self) -> list[FeatureNode]:
        """Generate the full library documentation hierarchy.

        Returns:
            List of :class:`FeatureNode` instances forming the hierarchy.
        """
        nodes: list[FeatureNode] = []
        for lib_name, lib_tree in _LIBRARIES.items():
            lib_id = f"lib.{lib_name}"
            lib_node = FeatureNode(
                id=lib_id,
                name=self._humanize(lib_name),
                description=f"{self._humanize(lib_name)} library API documentation hierarchy",
                parent_id=None,
                level=0,
                tags=[lib_name, "library", "api"],
                metadata={"source": "library-docs", "generator": "seed", "library": lib_name},
            )
            nodes.append(lib_node)
            self._walk_tree(
                lib_tree,
                parent_id=lib_id,
                level=1,
                nodes=nodes,
                prefix=lib_id,
                library=lib_name,
            )
        return nodes

    def _walk_tree(
        self,
        tree: dict | list,
        parent_id: str,
        level: int,
        nodes: list[FeatureNode],
        prefix: str,
        library: str,
    ) -> None:
        """Recursively walk a library's API tree creating FeatureNode instances."""
        if isinstance(tree, list):
            for item_name in tree:
                node_id = f"{prefix}.{item_name}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(item_name),
                    description=f"{self._humanize(item_name)} in {self._humanize(library)}",
                    parent_id=parent_id,
                    level=level,
                    tags=[item_name.split("-")[0], library],
                    metadata={"source": "library-docs", "generator": "seed", "library": library},
                )
                nodes.append(node)
        elif isinstance(tree, dict):
            for key, subtree in tree.items():
                node_id = f"{prefix}.{key}"
                node = FeatureNode(
                    id=node_id,
                    name=self._humanize(key),
                    description=f"{self._humanize(key)} module in {self._humanize(library)}",
                    parent_id=parent_id,
                    level=level,
                    tags=[key.split("-")[0], library],
                    metadata={"source": "library-docs", "generator": "seed", "library": library},
                )
                nodes.append(node)
                self._walk_tree(
                    subtree,
                    parent_id=node_id,
                    level=level + 1,
                    nodes=nodes,
                    prefix=node_id,
                    library=library,
                )

    @staticmethod
    def _humanize(slug: str) -> str:
        """Convert a slug to human-readable title."""
        return slug.replace("-", " ").replace("_", " ").title()
