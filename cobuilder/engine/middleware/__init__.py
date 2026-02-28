"""Middleware chain package for the Attractor pipeline engine.

Exports the core middleware building blocks so call sites import from one
stable namespace::

    from cobuilder.engine.middleware import (
        Middleware, HandlerRequest, compose_middleware,
        LogfireMiddleware, TokenCountingMiddleware,
        RetryMiddleware, AuditMiddleware,
    )
"""
from __future__ import annotations

from cobuilder.engine.middleware.chain import (
    HandlerRequest,
    Middleware,
    compose_middleware,
)
from cobuilder.engine.middleware.logfire import LogfireMiddleware
from cobuilder.engine.middleware.token_counter import TokenCountingMiddleware
from cobuilder.engine.middleware.retry import RetryMiddleware
from cobuilder.engine.middleware.audit import AuditMiddleware

__all__ = [
    "Middleware",
    "HandlerRequest",
    "compose_middleware",
    "LogfireMiddleware",
    "TokenCountingMiddleware",
    "RetryMiddleware",
    "AuditMiddleware",
]
