"""30-day backward-compatibility shim. Expires 2026-04-11.
Real code lives at cobuilder/engine/parser.py
"""
import warnings

warnings.warn(
    "Importing from .claude/scripts/attractor/parser.py is deprecated. "
    "Use cobuilder.engine.parser instead.",
    DeprecationWarning,
    stacklevel=2,
)
from cobuilder.engine.parser import *  # noqa: F401,F403