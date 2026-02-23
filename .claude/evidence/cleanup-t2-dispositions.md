# Task 2: Cross-Reference Analysis Dispositions

Analysis date: 2026-02-24
Branch: feat/claude-dir-cleanup

## Hooks NOT in settings.json

| File | References Found | Disposition | Reason |
|------|-----------------|-------------|--------|
| hooks/completion-gate.py | 3 | KEEP | Referenced by validation-test-agent.md, completion-promise/SKILL.md, SYSTEM3_CHANGELOG.md |
| hooks/completion-gate.sh | 0 | DELETE | Only self-reference, not in settings.json |
| hooks/context-preserver-hook.py | 2 | KEEP | Referenced by context-reinjector-hook.py, hindsight-memory-flush.py |
| hooks/context-reinjector-hook.py | 1 | KEEP | Documented in NATIVE-TEAMS-EPIC1-FINDINGS.md as needing update |
| hooks/decision-time-guidance-hook.py | 2 | KEEP | Referenced by DECISION_TIME_GUIDANCE.md, decision-guidance-hook-config.json |
| hooks/test-stop-gate.sh | 3 | KEEP | Test infrastructure referenced by STOP_GATE_CONSOLIDATION.md |

## Utils

| File | References Found | Disposition | Reason |
|------|-----------------|-------------|--------|
| utils/advisory-report.sh | 0 | DELETE | Only self-references, orphaned cluster |
| utils/commit-range.sh | 0 | DELETE | Only self-references, orphaned cluster |
| utils/doc-cleanup.sh | 0 | DELETE | Only self-references, orphaned cluster (sources document-lifecycle.sh) |
| utils/document-lifecycle.sh | 0 | DELETE | Only referenced by other orphaned utils in same cluster |

## Commands

| File | References Found | Disposition | Reason |
|------|-----------------|-------------|--------|
| commands/o3-pro.md | 0 file refs | KEEP | Active slash command (auto-discovered from commands/) |
| commands/use-codex-support.md | 0 file refs | KEEP | Active slash command (auto-discovered from commands/) |
| commands/website-upgraded.md | 0 file refs | KEEP | Active slash command (auto-discovered from commands/) |
| commands/parallel-solutioning.md | 0 file refs | KEEP | Active slash command (auto-discovered from commands/) |
| commands/check-messages.md | 2 | KEEP | Active slash command, referenced by message-bus/SKILL.md and MESSAGE_BUS_ARCHITECTURE.md |

## Summary

- **Investigated**: 15 files
- **Kept**: 10 files
- **Deleted**: 5 files
