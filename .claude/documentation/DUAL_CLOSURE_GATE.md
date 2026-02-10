# ADR: Dual Closure Gate — System 3 Independent Validation

**Date**: 2026-02-10
**Status**: Accepted
**Authors**: System 3 Meta-Orchestrator

## Problem Statement

Orchestrator-run validation consistently fails to catch real issues:

1. **Validation skipped entirely** — Orchestrators mark tasks complete without running acceptance tests
2. **Hollow tests** — Validation runs with mocks/stubs; features pass tests but don't actually work
3. **E2E uses fake data** — Tests use mocked APIs instead of real services
4. **Self-grading homework** — The validator teammate lives inside the orchestrator's own team, so the orchestrator controls both implementation and validation

### Root Cause

```
Previous Architecture:

System 3 (no team — tmux + Task subagents)
    └── Orchestrator (team lead of {initiative}-workers)
            ├── worker-frontend
            ├── worker-backend
            ├── worker-tester
            └── validator ← SAME TEAM as implementers (conflict of interest)
```

System 3 had no independent verification capability. It trusted whatever the orchestrator reported.

## Decision

**Split validation authority**: Orchestrators handle Level 1 (unit tests), System 3 handles Level 2+3 (API + E2E) independently.

### New Architecture

```
System 3 (TEAM LEAD of s3-{initiative}-oversight)
    ├── s3-investigator     (Explore — read-only codebase verification)
    ├── s3-prd-auditor      (solution-design-architect — PRD coverage analysis)
    ├── s3-validator        (validation-test-agent — REAL E2E, no mocks)
    ├── s3-evidence-clerk   (general-purpose/Haiku — evidence collation)
    │
    └── [tmux] → Orchestrator (team lead of {initiative}-workers)
                    ├── worker-frontend
                    ├── worker-backend
                    └── worker-tester
                    (NO validator — removed from orchestrator's team)
```

## Custom Beads Status Lifecycle

Beads accepts free-form status strings. We introduce custom statuses:

```
open → in_progress → impl_complete → s3_validating → closed
                         ↑                    │
                         └────────────────────┘
                       (s3_rejected → back to in_progress)
```

| Status | Set By | Meaning |
|--------|--------|---------|
| `open` | Planning | Task exists, not started |
| `in_progress` | Orchestrator | Worker actively implementing |
| `impl_complete` | Orchestrator | Implementation done — requesting S3 review |
| `s3_validating` | System 3 | Oversight team actively checking |
| `s3_rejected` | System 3 | Failed validation — returned to orchestrator with feedback |
| `closed` | System 3 (s3-validator only) | Validated with evidence |

## Enforcement Approach

**Instruction-based, not programmatic.** We cannot hard-block `bd close` at the CLI level (beads doesn't support ACLs). Instead:

1. **Orchestrator SKILL.md** instructs orchestrators to use `bd update --status=impl_complete` instead of `bd close`
2. **System 3 output style** instructs System 3 to manage the validation cycle
3. **Stop gate** recognizes `impl_complete` as "work remaining" for System 3 sessions
4. **Stop gate** does NOT hard-block `bd close` — enforcement is behavioral

### Why Not Programmatic Enforcement?

- Beads CLI doesn't support user-level permissions
- Git hooks could intercept `.beads/` commits, but would be brittle
- Instruction-based enforcement works well in practice: Claude Code follows SKILL.md consistently
- Adding programmatic enforcement later is possible without architectural changes

## Validation Cycle

When System 3 detects `impl_complete`:

1. Set status: `bd update <id> --status=s3_validating`
2. Dispatch 3 parallel checks:
   - **s3-investigator**: Verify files were actually modified as claimed
   - **s3-prd-auditor**: Check PRD requirement coverage
   - **s3-validator**: Run real E2E tests with real services
3. Collect all 3 reports
4. **s3-evidence-clerk**: Collate into closure report
5. Decision:
   - ALL pass → `bd close <id>` with evidence
   - ANY fail → `bd update <id> --status=in_progress` + detailed rejection feedback

## Evidence Storage

Validation artifacts are stored in `.claude/evidence/{task-id}/`:

```
.claude/evidence/
├── .gitkeep
├── {task-id}/
│   ├── closure-report.md       # Collated evidence summary
│   ├── investigation-report.md # Code change verification
│   ├── prd-coverage-matrix.md  # PRD requirement mapping
│   ├── validation-results.md   # E2E test results
│   └── screenshots/            # Visual evidence
```

## Impact on Stop Gate

| Session Type | `impl_complete` Tasks | Behavior |
|-------------|----------------------|----------|
| System 3 | Present | BLOCKED — must run validation cycle |
| System 3 | None | PASS (normal exit) |
| Orchestrator | Present | PASS — impl_complete means "handed off to S3" |
| Worker | N/A | PASS (workers don't see bead statuses) |

## Consequences

### Positive
- Independent validation eliminates "self-grading homework" problem
- Evidence artifacts provide auditable validation trail
- Orchestrators can continue working while S3 validates in parallel
- Rejections include specific, actionable feedback

### Negative
- Validation cycle adds latency (3 parallel workers + collation)
- System 3 requires more context for oversight team management
- Custom statuses require all documentation to be updated
- First implementation is instruction-based (not enforceable by tooling)

### Neutral
- Beads status strings are free-form — no schema changes needed
- Stop gate changes are additive (no breaking changes)
- Message bus protocol unchanged (just new message types)

## Related Documents

- `.claude/output-styles/system3-meta-orchestrator.md` — Oversight team management section
- `.claude/skills/orchestrator-multiagent/SKILL.md` — Implementation Complete Handoff section
- `.claude/skills/system3-orchestrator/references/oversight-team.md` — Worker spawn commands
- `.claude/hooks/unified_stop_gate/work_exhaustion_checker.py` — Status recognition
