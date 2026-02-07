"""Metrics computation for the evaluation pipeline.

This module will implement aggregate metric calculations including:
- Pass rate, voting rate, and localisation rate
- Coverage metrics (fraction of categories with passing tests)
- Novelty metrics (categories outside reference taxonomy)
- Weighted scoring combining multiple metric dimensions
- Per-difficulty and per-category breakdowns
"""
