"""30-day backward-compatibility shim. Expires 2026-04-11.
Real code lives at cobuilder/engine/signal_protocol.py
"""
import warnings

warnings.warn(
    "Importing from .claude/scripts/attractor/signal_protocol.py is deprecated. "
    "Use cobuilder.engine.signal_protocol instead.",
    DeprecationWarning,
    stacklevel=2,
)
from cobuilder.engine.signal_protocol import *  # noqa: F401,F403