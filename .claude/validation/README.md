# Validation Evidence Directory

This directory stores evidence from validation-agent runs.

## Structure

| Directory | Purpose |
|-----------|---------|
| `screenshots/` | Browser screenshots from E2E tests |
| `logs/` | Test output logs |
| `evidence/` | General evidence artifacts (JSON, API responses) |

## Naming Convention

Evidence files follow: `<task-id>_<timestamp>_<type>.<ext>`
- Example: `agencheck-xyz_20260112_120000_unit-tests.log`
- Example: `agencheck-xyz_20260112_120100_e2e-screenshot.png`
