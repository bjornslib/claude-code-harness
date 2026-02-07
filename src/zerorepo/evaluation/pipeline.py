"""Evaluation pipeline orchestration.

This module will implement the end-to-end evaluation pipeline that
chains the three stages together:
1. Localisation - match benchmark tasks to candidate functions
2. Semantic validation - LLM-based assessment of candidates
3. Test execution - sandbox-based ground-truth testing

The pipeline supports configurable stage skipping, parallel execution,
result caching, and progress reporting.
"""
