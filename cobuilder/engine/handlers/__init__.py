"""Handler implementations for Attractor DOT pipeline node shapes.

Each handler corresponds to one or more DOT node shapes and implements the
``Handler`` protocol defined in ``base.py``.  The ``HandlerRegistry`` maps
shapes to handler instances at startup.

Importing this package registers nothing automatically; the registry must be
explicitly populated (typically by ``EngineRunner`` at startup).

Public re-exports for convenience:
"""
from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.handlers.registry import HandlerRegistry

__all__ = [
    "Handler",
    "HandlerRequest",
    "HandlerRegistry",
]
