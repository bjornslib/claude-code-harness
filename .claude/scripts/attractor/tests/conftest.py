"""Pytest configuration for attractor unit tests."""
from __future__ import annotations

import sys
import os

import pytest

# Ensure the attractor package root is on the Python path
# so tests can import gchat_adapter, channel_bridge, channel_adapter, etc.
_ATTRACTOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ATTRACTOR_DIR not in sys.path:
    sys.path.insert(0, _ATTRACTOR_DIR)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end integration test requiring real Agent SDK calls (deselect with '-m \"not e2e\"')",
    )
