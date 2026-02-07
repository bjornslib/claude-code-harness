"""Harvest test functions from reference projects for the RepoCraft benchmark.

This script will crawl reference project test suites to extract
individual test functions and their metadata for use as benchmark tasks.
The harvesting process:
1. Clone or access reference project repositories
2. Parse test files to extract individual test functions
3. Resolve imports, fixtures, and auxiliary code dependencies
4. Classify tasks by difficulty based on complexity heuristics
5. Output structured BenchmarkTask entries to the tasks directory
"""
