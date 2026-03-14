"""CoBuilder execution engine — Epic 1: Core Engine with Checkpoint/Resume.

Public surface for the engine package. Consumers should import from
sub-modules directly; this __init__ re-exports only the most commonly
used names.
"""
from cobuilder.engine.context import PipelineContext
from cobuilder.engine.exceptions import (
    CheckpointVersionError,
    EngineError,
    HandlerError,
    LoopDetectedError,
    NoEdgeError,
    ParseError,
    UnknownShapeError,
    ValidationError,
)
from cobuilder.engine.graph import SHAPE_TO_HANDLER, Edge, Graph, Node
from cobuilder.engine.handlers import Handler, HandlerRegistry, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus
from cobuilder.engine.parser import DotParser, parse_dot_file, parse_dot_string
from cobuilder.engine.providers import (
    LLMProfile,
    ProvidersFile,
    ResolvedLLMConfig,
    get_llm_config_for_node,
    load_providers_file,
    resolve_llm_config,
)
from cobuilder.engine.runner import EngineRunner

__all__ = [
    # Graph models
    "Graph",
    "Node",
    "Edge",
    "SHAPE_TO_HANDLER",
    # Parser
    "DotParser",
    "ParseError",
    "parse_dot_file",
    "parse_dot_string",
    # Outcome
    "Outcome",
    "OutcomeStatus",
    # Context
    "PipelineContext",
    # Handlers
    "Handler",
    "HandlerRequest",
    "HandlerRegistry",
    # Providers (Epic 1)
    "LLMProfile",
    "ProvidersFile",
    "ResolvedLLMConfig",
    "get_llm_config_for_node",
    "load_providers_file",
    "resolve_llm_config",
    # Exceptions
    "EngineError",
    "ValidationError",
    "UnknownShapeError",
    "NoEdgeError",
    "CheckpointVersionError",
    "HandlerError",
    "LoopDetectedError",
    # Runner
    "EngineRunner",
]
