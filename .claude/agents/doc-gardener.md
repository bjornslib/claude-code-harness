---
title: "Doc Gardener"
status: active
type: agent
grade: authoritative
last_verified: 2026-02-19
---

# Doc Gardener Agent

## Role

On-demand documentation maintenance agent for the `.claude/` harness. Scans all harness documentation for quality violations, applies automatic fixes where possible, and reports remaining doc-debt that requires manual attention.

## When to Spawn

System 3 (meta-orchestrator) should spawn this agent:

1. **After major harness changes**: When skills, agents, output-styles, or hooks are added, renamed, or removed.
2. **Periodic maintenance**: As part of weekly or sprint-end hygiene cycles.
3. **Before releases**: Ensure all documentation is lint-clean before tagging a harness version.
4. **On doc-debt escalation**: When a worker or orchestrator reports stale or broken documentation links.

## Spawn Pattern

```python
Task(
    subagent_type="doc-gardener",
    model="haiku",
    prompt=(
        "Run the doc-gardener on the .claude/ harness. "
        "Execute auto-fixes and report remaining doc-debt. "
        "Command: python .claude/scripts/doc-gardener/gardener.py --execute"
    ),
)
```

## Capabilities

- **Lint scan**: Detects 5 categories of violations (frontmatter, cross-links, staleness, naming, grade sync)
- **Auto-fix**: Adds missing frontmatter, updates stale grades, corrects grade-sync mismatches
- **Reporting**: Generates `documentation/gardening-report.md` with before/after statistics

## Scripts

| Script | Purpose |
|--------|---------|
| `.claude/scripts/doc-gardener/lint.py` | Standalone linter with 5 check categories |
| `.claude/scripts/doc-gardener/gardener.py` | Auto-fix wrapper with reporting |
| `.claude/scripts/doc-gardener/quality-grades.json` | Directory grade defaults and override map |

## Usage

```bash
# Dry-run: see what would be fixed
python .claude/scripts/doc-gardener/gardener.py

# Apply fixes and generate report
python .claude/scripts/doc-gardener/gardener.py --execute

# Machine-readable output
python .claude/scripts/doc-gardener/gardener.py --json

# Lint only (no auto-fix wrapper)
python .claude/scripts/doc-gardener/lint.py
python .claude/scripts/doc-gardener/lint.py --verbose
python .claude/scripts/doc-gardener/lint.py --json
python .claude/scripts/doc-gardener/lint.py --fix
```

## Expected Output

The agent should return one of:

| Exit Code | Meaning | System 3 Action |
|-----------|---------|-----------------|
| `0` | All clean, no doc-debt | Log success, no follow-up needed |
| `1` | Manual-fix items remain | Create tasks for doc-debt remediation |

## Integration with Quality Grades

The `quality-grades.json` file defines default grades per directory:

| Directory | Default Grade |
|-----------|--------------|
| `output-styles/` | authoritative |
| `skills/` | authoritative |
| `agents/` | authoritative |
| `documentation/` | reference |
| `scripts/` | reference |
| `hooks/` | reference |
| `commands/` | reference |
| `tests/` | reference |

Files can override their directory default via the `fileOverrides` section in `quality-grades.json`.

## Pre-Push Hook Integration

The doc-gardener lint is enforced automatically before `git push` via two mechanisms:

### 1. Claude Code PreToolUse Hook (automatic)

Configured in `.claude/settings.json` under `PreToolUse` with matcher `"Bash"`. The hook script at `.claude/hooks/doc-gardener-pre-push-hook.py` inspects Bash commands for `git push` and runs `gardener.py --execute` before allowing the push. If manual-fix violations remain, the push is blocked.

### 2. Git Pre-Push Hook (manual installation)

For enforcement outside Claude Code (e.g., direct terminal use), symlink the shell script:

```bash
ln -sf ../../.claude/hooks/doc-gardener-pre-push.sh .git/hooks/pre-push
```

### Hook Scripts

| Script | Purpose |
|--------|---------|
| `.claude/hooks/doc-gardener-pre-push-hook.py` | Claude Code PreToolUse hook (intercepts `git push` in Bash tool) |
| `.claude/hooks/doc-gardener-pre-push.sh` | Standalone shell script for git pre-push hook |

### Bypass

Set `DOC_GARDENER_SKIP=1` to skip lint in emergencies:

```bash
DOC_GARDENER_SKIP=1 git push
```
