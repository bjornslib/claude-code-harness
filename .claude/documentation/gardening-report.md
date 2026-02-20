# Harness Documentation Gardening Report

**Generated**: 2026-02-19T21:07:20
**Target**: `/Users/theb/Documents/Windsurf/claude-harness-setup/.claude`
**Mode**: EXECUTE (fixes applied)

## Summary

- **Files scanned**: 299
- **Total violations found**: 355
- **Auto-fixed**: 154
- **Remaining violations**: 201

### Before

| Severity | Count |
|----------|-------|
| Errors   | 187 |
| Warnings | 168 |
| Info     | 0 |
| Fixable  | 154 |

### After Auto-fix

| Severity | Count |
|----------|-------|
| Errors   | 187 |
| Warnings | 14 |
| Info     | 0 |

## Auto-fixed Violations

These violations were automatically remediated:

| File | Category | Severity | Message |
|------|----------|----------|---------|
| `commands/check-messages.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/development/llm-first-architecture.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/development/testing-protocol.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/help/list-commands.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/help/quick-reference.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/integration/serena-mcp.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/management/task-csv.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/o3-pro.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/parallel/cleanup.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/parallel/setup.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/parallel/status.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/parallel-solutioning.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/add-dependency/add-dependency.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/add-subtask/add-subtask.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/add-subtask/convert-task-to-subtask.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/add-task/add-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/analyze-complexity/analyze-complexity.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/clear-subtasks/clear-all-subtasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/clear-subtasks/clear-subtasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/complexity-report/complexity-report.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/expand/expand-all-tasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/expand/expand-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/fix-dependencies/fix-dependencies.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/generate/generate-tasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/help.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/init/init-project-quick.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/init/init-project.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/learn.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/list/list-tasks-by-status.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/list/list-tasks-with-subtasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/list/list-tasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/models/setup-models.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/models/view-models.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/next/next-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/parse-prd/parse-prd-with-research.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/parse-prd/parse-prd.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/remove-dependency/remove-dependency.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/remove-subtask/remove-subtask.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/remove-task/remove-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-cancelled.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-deferred.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-done.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-in-progress.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-pending.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/set-status/to-review.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/setup/install-taskmaster.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/setup/quick-install-taskmaster.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/show/show-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/status/project-status.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/sync-readme/sync-readme.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/tm-main.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/update/update-single-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/update/update-task.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/update/update-tasks-from-id.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/utils/analyze-project.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/validate-dependencies/validate-dependencies.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/workflows/auto-implement-tasks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/workflows/command-pipeline.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/tm/workflows/smart-workflow.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/use-codex-support.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/website-upgraded.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/workflow/completion-protocol.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/workflow/processes.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `commands/workflow/research-colleagues.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/acceptance-test-runner/examples/validation-report.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/acceptance-test-runner/references/chrome-mcp-actions.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/acceptance-test-runner/references/report-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/acceptance-test-writer/references/action-catalog.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/acceptance-test-writer/references/schemas.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/completion-promise/verify-prompt-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/examples/workflow-matrix-interaction-design.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/examples/workflow-matrix-prd.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/references/brief-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/references/implementation-rules.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/references/jsonc-schema.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/references/research-workflow.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/references/shadcn-patterns.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/templates/brief-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/templates/interaction-design.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/design-to-code/templates/prd.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/dspy-development/README.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/dspy-development/references/examples.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/dspy-development/references/migration.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/dspy-development/references/modules.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/dspy-development/references/optimizers.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/explore-first-navigation/examples/architecture-exploration.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/explore-first-navigation/references/explore-prompts.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/explore-first-navigation/references/parallel-patterns.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/examples/campaign-brief-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/examples/message-examples.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/guides.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/phases/phase-1-enrichment.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/phases/phase-2-message-crafting.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/phases/phase-3-quality-assurance.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/phases/phase-4-scale.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/phases/phase-5-finalize.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/linkedin-campaign-development/references/troubleshooting.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/mcp-to-skill-converter/README.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/message-bus/monitor-prompt-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/multilead-add-lead-skill/README.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/ORCHESTRATOR_INITIALIZATION_TEMPLATE.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/REFERENCE.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/VALIDATION.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/WORKERS.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/WORKFLOWS.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/ZEROREPO.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/archive/HINDSIGHT-DOCKER.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/archive/LEGACY_FEATURE_LIST.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/references/hindsight-integration.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/orchestrator-multiagent/references/message-bus-integration.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/railway-common/references/environment-config.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/railway-common/references/monorepo.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/railway-common/references/railpack.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/railway-common/references/variables.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/react-best-practices/references/react-performance-guidelines.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/research-first/examples/architecture-decision.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/research-first/examples/fastapi-validation.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/research-first/examples/react-hook-research.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/research-first/references/frameworks.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/s3-guardian/references/gherkin-test-patterns.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/s3-guardian/references/guardian-workflow.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/s3-guardian/references/monitoring-patterns.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/s3-guardian/references/validation-scoring.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/COMMUNICATION.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/DECISION_FRAMEWORK.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/HINDSIGHT_INTEGRATION.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/IDLE_BEHAVIOR.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/QUICK_REFERENCE.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/README.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/examples/orchestrator-prompt.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/examples/wisdom-injection-template.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/completion-promise-cli.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/inter-instance-messaging.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/memory-context-taxonomy.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/monitoring-commands.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/okr-tracking.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/oversight-team.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/post-orchestration.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/prd-extraction.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/spawn-workflow.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/system3-mcp-daemon.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/tmux-commands.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/troubleshooting.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/system3-orchestrator/references/validation-workflow.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/website-ux-audit/examples/EXAMPLES.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/website-ux-audit/references/CHECKLIST.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worker-focused-execution/TESTING_DETAILS.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worker-focused-execution/VOTING_DETAILS.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worktree-manager-skill/EXAMPLES.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worktree-manager-skill/OPERATIONS.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worktree-manager-skill/REFERENCE.md` | frontmatter | warning | Missing YAML frontmatter block (---) |
| `skills/worktree-manager-skill/TROUBLESHOOTING.md` | frontmatter | warning | Missing YAML frontmatter block (---) |

## Manual Fix Required (Doc-Debt)

These violations require human attention:

| File | Category | Severity | Message |
|------|----------|----------|---------|
| `commands/development/llm-first-architecture.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/ADR-001-output-style-reliability.md` | naming | warning | Filename 'ADR-001-output-style-reliability.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/F4.2-cs-verify-programmatic-gate-spec.md` | naming | warning | Filename 'F4.2-cs-verify-programmatic-gate-spec.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/NATIVE-TEAMS-EPIC1-FINDINGS.md` | naming | warning | Filename 'NATIVE-TEAMS-EPIC1-FINDINGS.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/PRD-S3-ATTRACTOR-001-testing.md` | naming | warning | Filename 'PRD-S3-ATTRACTOR-001-testing.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/PRD-S3-ATTRACTOR-002-design.md` | naming | warning | Filename 'PRD-S3-ATTRACTOR-002-design.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/SKILL-DEDUP-AUDIT.md` | naming | warning | Filename 'SKILL-DEDUP-AUDIT.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/SOLUTION-DESIGN-acceptance-testing.md` | naming | warning | Filename 'SOLUTION-DESIGN-acceptance-testing.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/UPDATE-validation-agent-integration.md` | naming | warning | Filename 'UPDATE-validation-agent-integration.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-success-dashboard.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-error.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [reset-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-success-dashboard.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-error.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [reset-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-success-dashboard.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-error.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [reset-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [WORKERS.md](.claude/skills/orchestrator-multiagent/WORKERS.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [DECISION_FRAMEWORK.md](.claude/skills/system3-orchestrator/DECISION_FRAMEWORK.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [COMMUNICATION.md](.claude/skills/system3-orchestrator/COMMUNICATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/inter-instance-messaging.md](references/inter-instance-messaging.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/completion-promise-cli.md](references/completion-promise-cli.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [QUICK_REFERENCE.md](.claude/skills/system3-orchestrator/QUICK_REFERENCE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SYSTEM3_CHANGELOG.md](.claude/documentation/SYSTEM3_CHANGELOG.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-user-login-success.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-invalid-credentials.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-request.png](./evidence/AC-password-reset-request.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-complete-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-session-timeout.png](./evidence/AC-session-timeout.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [security/SKILL.md](../security/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [code-quality/SKILL.md](../code-quality/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [documentation/SKILL.md](../documentation/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [post-push/SKILL.md](../post-push/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#acceptance-test-at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [FEATURE_DECOMPOSITION.md](FEATURE_DECOMPOSITION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [message-bus skill](../message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TESTING_INFRASTRUCTURE.md](../orchestrator-multiagent/TESTING_INFRASTRUCTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [.claude/documentation/](./claude/documentation/) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [ZEROREPO.md](ZEROREPO.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-success-dashboard.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [login-error.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [reset-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Screenshot](url) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Screenshot](url) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Screenshots](url) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Railway Environment Configuration Reference](references/environment-config.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Railway Variables Reference](references/variables.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [WORKERS.md](.claude/skills/orchestrator-multiagent/WORKERS.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [DECISION_FRAMEWORK.md](.claude/skills/system3-orchestrator/DECISION_FRAMEWORK.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [COMMUNICATION.md](.claude/skills/system3-orchestrator/COMMUNICATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [QUICK_REFERENCE.md](.claude/skills/system3-orchestrator/QUICK_REFERENCE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SYSTEM3_CHANGELOG.md](.claude/documentation/SYSTEM3_CHANGELOG.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-user-login-success.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-invalid-credentials.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-request.png](./evidence/AC-password-reset-request.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-complete-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-session-timeout.png](./evidence/AC-session-timeout.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [security/SKILL.md](../security/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [code-quality/SKILL.md](../code-quality/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [documentation/SKILL.md](../documentation/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [post-push/SKILL.md](../post-push/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [message-bus SKILL.md](../message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#acceptance-test-at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [message-bus skill](../message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [FEATURE_DECOMPOSITION.md](FEATURE_DECOMPOSITION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TESTING_INFRASTRUCTURE.md](../orchestrator-multiagent/TESTING_INFRASTRUCTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Gap Analysis (Uber-Epic)](work-history-mvp-gap-analysis.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [Phase 2: Contact Intelligence](work-history-phase2-contact-intelligence.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [WORKERS.md](.claude/skills/orchestrator-multiagent/WORKERS.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [DECISION_FRAMEWORK.md](.claude/skills/system3-orchestrator/DECISION_FRAMEWORK.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [COMMUNICATION.md](.claude/skills/system3-orchestrator/COMMUNICATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/inter-instance-messaging.md](references/inter-instance-messaging.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/completion-promise-cli.md](references/completion-promise-cli.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [QUICK_REFERENCE.md](.claude/skills/system3-orchestrator/QUICK_REFERENCE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SYSTEM3_CHANGELOG.md](.claude/documentation/SYSTEM3_CHANGELOG.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-user-login-success.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-invalid-credentials.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-request.png](./evidence/AC-password-reset-request.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-complete-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-session-timeout.png](./evidence/AC-session-timeout.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [security/SKILL.md](../security/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [code-quality/SKILL.md](../code-quality/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [documentation/SKILL.md](../documentation/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [post-push/SKILL.md](../post-push/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#acceptance-test-at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [FEATURE_DECOMPOSITION.md](FEATURE_DECOMPOSITION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [message-bus skill](../message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TESTING_INFRASTRUCTURE.md](../orchestrator-multiagent/TESTING_INFRASTRUCTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [WORKERS.md](.claude/skills/orchestrator-multiagent/WORKERS.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [DECISION_FRAMEWORK.md](.claude/skills/system3-orchestrator/DECISION_FRAMEWORK.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [COMMUNICATION.md](.claude/skills/system3-orchestrator/COMMUNICATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/inter-instance-messaging.md](references/inter-instance-messaging.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [references/completion-promise-cli.md](references/completion-promise-cli.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [QUICK_REFERENCE.md](.claude/skills/system3-orchestrator/QUICK_REFERENCE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SYSTEM3_CHANGELOG.md](.claude/documentation/SYSTEM3_CHANGELOG.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-user-login-success.png](./evidence/AC-user-login-success.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-invalid-credentials.png](./evidence/AC-invalid-credentials.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-request.png](./evidence/AC-password-reset-request.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-password-reset-complete-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AC-session-timeout.png](./evidence/AC-session-timeout.png) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [security/SKILL.md](../security/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [code-quality/SKILL.md](../code-quality/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [documentation/SKILL.md](../documentation/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [post-push/SKILL.md](../post-push/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#acceptance-test-at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [FEATURE_DECOMPOSITION.md](FEATURE_DECOMPOSITION.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#at-epic-convention) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [message-bus skill](../message-bus/SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [TESTING_INFRASTRUCTURE.md](../orchestrator-multiagent/TESTING_INFRASTRUCTURE.md) |
| `schemas/v3.9-agent-quick-reference.md` | naming | warning | Filename 'v3.9-agent-quick-reference.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `schemas/v3.9-contact-schema.md` | naming | warning | Filename 'v3.9-contact-schema.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/acceptance-test-runner/references/report-template.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `skills/acceptance-test-runner/references/report-template.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | naming | warning | Filename 'registry-SKILL.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/orchestrator-multiagent/archive/HINDSIGHT-DOCKER.md` | naming | warning | Filename 'HINDSIGHT-DOCKER.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `skills/react-best-practices/references/rules/_sections.md` | naming | warning | Filename '_sections.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/react-best-practices/references/rules/_template.md` | naming | warning | Filename '_template.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
