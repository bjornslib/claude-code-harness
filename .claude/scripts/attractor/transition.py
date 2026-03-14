"""30-day backward-compatibility shim. Expires 2026-04-11.
Real code lives at cobuilder/engine/transition.py
"""
import warnings

warnings.warn(
    "Importing from .claude/scripts/attractor/transition.py is deprecated. "
    "Use cobuilder.engine.transition instead.",
    DeprecationWarning,
    stacklevel=2,
)
from cobuilder.engine.transition import *  # noqa: F401,F403