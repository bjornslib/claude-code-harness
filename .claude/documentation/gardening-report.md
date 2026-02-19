---
title: "Harness Documentation Gardening Report"
status: active
---

# Harness Documentation Gardening Report

**Generated**: 2026-02-19T19:06:13
**Target**: `/Users/theb/Documents/Windsurf/claude-harness-setup/.claude`
**Mode**: DRY-RUN (no changes)

## Summary

- **Files scanned**: 299
- **Total violations found**: 367
- **Auto-fixed**: 0
- **Remaining violations**: 367

### Before

| Severity | Count |
|----------|-------|
| Errors   | 352 |
| Warnings | 15 |
| Info     | 0 |
| Fixable  | 1 |

## Auto-fixed Violations

These violations **would be** auto-fixed with `--execute`:

| File | Category | Severity | Message |
|------|----------|----------|---------|
| `documentation/gardening-report.md` | frontmatter | warning | Missing YAML frontmatter block (---) |

## Manual Fix Required (Doc-Debt)

These violations require human attention:

| File | Category | Severity | Message |
|------|----------|----------|---------|
| `agents/backend-solutions-engineer.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/backend-solutions-engineer.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/claude-md-compliance-checker.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/claude-md-compliance-checker.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/frontend-dev-expert.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/frontend-dev-expert.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/linkedin-automation-agent.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/linkedin-automation-agent.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/solution-design-architect.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/solution-design-architect.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/tdd-test-engineer.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/tdd-test-engineer.md` | frontmatter | error | Missing required frontmatter field: status |
| `agents/validation-test-agent.md` | frontmatter | error | Missing required frontmatter field: title |
| `agents/validation-test-agent.md` | frontmatter | error | Missing required frontmatter field: status |
| `commands/development/llm-first-architecture.md` | crosslinks | error | Broken link: [ValidationDependencies, ValidationResult](
    model=model,
    deps=deps,
    system_prompt=prompt
) |
| `documentation/ADR-001-output-style-reliability.md` | naming | warning | Filename 'ADR-001-output-style-reliability.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/F4.2-cs-verify-programmatic-gate-spec.md` | naming | warning | Filename 'F4.2-cs-verify-programmatic-gate-spec.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/MESSAGE_BUS_ARCHITECTURE.md` | crosslinks | error | Broken link: [`Skill("message-bus")`](.claude/skills/message-bus/SKILL.md) |
| `documentation/MESSAGE_BUS_ARCHITECTURE.md` | crosslinks | error | Broken link: [system3-meta-orchestrator.md](.claude/output-styles/system3-meta-orchestrator.md) |
| `documentation/MESSAGE_BUS_ARCHITECTURE.md` | crosslinks | error | Broken link: [`Skill("orchestrator-multiagent")`](.claude/skills/orchestrator-multiagent/SKILL.md) |
| `documentation/NATIVE-TEAMS-EPIC1-FINDINGS.md` | naming | warning | Filename 'NATIVE-TEAMS-EPIC1-FINDINGS.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/PRD-S3-ATTRACTOR-001-testing.md` | naming | warning | Filename 'PRD-S3-ATTRACTOR-001-testing.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/PRD-S3-ATTRACTOR-002-design.md` | naming | warning | Filename 'PRD-S3-ATTRACTOR-002-design.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/SKILL-DEDUP-AUDIT.md` | naming | warning | Filename 'SKILL-DEDUP-AUDIT.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `documentation/SOLUTION-DESIGN-acceptance-testing.md` | crosslinks | error | Broken link: [login-success-dashboard.png](./evidence/AC-user-login-success.png) |
| `documentation/SOLUTION-DESIGN-acceptance-testing.md` | crosslinks | error | Broken link: [login-error.png](./evidence/AC-invalid-credentials.png) |
| `documentation/SOLUTION-DESIGN-acceptance-testing.md` | crosslinks | error | Broken link: [reset-fail.png](./evidence/AC-password-reset-complete-fail.png) |
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
| `output-styles/orchestrator.md` | frontmatter | error | Missing required frontmatter field: title |
| `output-styles/orchestrator.md` | frontmatter | error | Missing required frontmatter field: status |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [WORKERS.md](.claude/skills/orchestrator-multiagent/WORKERS.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/monitoring-commands.md](references/monitoring-commands.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [DECISION_FRAMEWORK.md](.claude/skills/system3-orchestrator/DECISION_FRAMEWORK.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/memory-context-taxonomy.md](references/memory-context-taxonomy.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [COMMUNICATION.md](.claude/skills/system3-orchestrator/COMMUNICATION.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/inter-instance-messaging.md](references/inter-instance-messaging.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [references/completion-promise-cli.md](references/completion-promise-cli.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [QUICK_REFERENCE.md](.claude/skills/system3-orchestrator/QUICK_REFERENCE.md) |
| `output-styles/system3-meta-orchestrator.md` | crosslinks | error | Broken link: [SYSTEM3_CHANGELOG.md](.claude/documentation/SYSTEM3_CHANGELOG.md) |
| `schemas/v3.9-agent-quick-reference.md` | naming | warning | Filename 'v3.9-agent-quick-reference.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `schemas/v3.9-contact-schema.md` | naming | warning | Filename 'v3.9-contact-schema.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/acceptance-test-runner/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/acceptance-test-runner/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/acceptance-test-runner/examples/validation-report.md` | crosslinks | error | Broken link: [AC-user-login-success.png](./evidence/AC-user-login-success.png) |
| `skills/acceptance-test-runner/examples/validation-report.md` | crosslinks | error | Broken link: [AC-invalid-credentials.png](./evidence/AC-invalid-credentials.png) |
| `skills/acceptance-test-runner/examples/validation-report.md` | crosslinks | error | Broken link: [AC-password-reset-request.png](./evidence/AC-password-reset-request.png) |
| `skills/acceptance-test-runner/examples/validation-report.md` | crosslinks | error | Broken link: [AC-password-reset-complete-fail.png](./evidence/AC-password-reset-complete-fail.png) |
| `skills/acceptance-test-runner/examples/validation-report.md` | crosslinks | error | Broken link: [AC-session-timeout.png](./evidence/AC-session-timeout.png) |
| `skills/acceptance-test-runner/references/report-template.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `skills/acceptance-test-runner/references/report-template.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `skills/acceptance-test-writer/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/acceptance-test-writer/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/SKILL.md` | crosslinks | error | Broken link: [security/SKILL.md](../security/SKILL.md) |
| `skills/codebase-quality/SKILL.md` | crosslinks | error | Broken link: [code-quality/SKILL.md](../code-quality/SKILL.md) |
| `skills/codebase-quality/SKILL.md` | crosslinks | error | Broken link: [documentation/SKILL.md](../documentation/SKILL.md) |
| `skills/codebase-quality/SKILL.md` | crosslinks | error | Broken link: [post-push/SKILL.md](../post-push/SKILL.md) |
| `skills/codebase-quality/code-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/code-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/documentation/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/documentation/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/documentation/SKILL.md` | crosslinks | error | Broken link: [../CLAUDE.md](../CLAUDE.md) |
| `skills/codebase-quality/post-push/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/post-push/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/security/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/security/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/codebase-quality/using-codebase-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/codebase-quality/using-codebase-quality/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/completion-promise/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/completion-promise/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/design-to-code/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/design-to-code/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/dspy-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/dspy-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/explore-first-navigation/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/explore-first-navigation/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/frontend-design/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/frontend-design/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/linkedin-campaign-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/linkedin-campaign-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/assistant-ui/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/assistant-ui/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/chrome-devtools/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/chrome-devtools/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/github/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/github/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/livekit-docs/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/livekit-docs/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/logfire/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/logfire/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/magicui/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/magicui/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/mcp-undetected-chromedriver/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/mcp-undetected-chromedriver/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/playwright/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/playwright/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-skills/shadcn/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-skills/shadcn/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-to-skill-converter/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-to-skill-converter/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/mcp-to-skill-converter/templates/registry-SKILL.md` | naming | warning | Filename 'registry-SKILL.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/message-bus/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/message-bus/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#acceptance-test-at-epic-convention) |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | crosslinks | error | Broken link: [AUTONOMOUS_MODE.md](AUTONOMOUS_MODE.md) |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | crosslinks | error | Broken link: [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) |
| `skills/orchestrator-multiagent/PREFLIGHT.md` | crosslinks | error | Broken link: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| `skills/orchestrator-multiagent/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/orchestrator-multiagent/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/orchestrator-multiagent/VALIDATION.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `skills/orchestrator-multiagent/archive/HINDSIGHT-DOCKER.md` | naming | warning | Filename 'HINDSIGHT-DOCKER.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/orchestrator-multiagent/archive/LEGACY_FEATURE_LIST.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `skills/orchestrator-multiagent/archive/LEGACY_FEATURE_LIST.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `skills/orchestrator-multiagent/archive/LEGACY_FEATURE_LIST.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md) |
| `skills/orchestrator-multiagent/archive/LEGACY_FEATURE_LIST.md` | crosslinks | error | Broken link: [FEATURE_DECOMPOSITION.md](FEATURE_DECOMPOSITION.md) |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `skills/orchestrator-multiagent/archive/STREAMLINING_PLAN.md` | crosslinks | error | Broken link: [BEADS_INTEGRATION.md](BEADS_INTEGRATION.md#at-epic-convention) |
| `skills/orchestrator-multiagent/references/message-bus-integration.md` | crosslinks | error | Broken link: [MESSAGE_BUS_ARCHITECTURE.md](../../documentation/MESSAGE_BUS_ARCHITECTURE.md) |
| `skills/orchestrator-multiagent/references/message-bus-integration.md` | crosslinks | error | Broken link: [message-bus skill](../message-bus/SKILL.md) |
| `skills/railway-central-station/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-central-station/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-database/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-database/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-deploy/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-deploy/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-deployment/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-deployment/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-domain/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-domain/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-environment/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-environment/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-metrics/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-metrics/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-new/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-new/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-projects/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-projects/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-railway-docs/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-railway-docs/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-service/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-service/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-status/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-status/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/railway-templates/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/railway-templates/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/react-best-practices/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/_sections.md` | naming | warning | Filename '_sections.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/react-best-practices/references/rules/_template.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/_template.md` | naming | warning | Filename '_template.md' doesn't follow naming conventions. Expected: kebab-case.md or UPPER_CASE.md |
| `skills/react-best-practices/references/rules/advanced-event-handler-refs.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/advanced-use-latest.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/async-api-routes.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/async-defer-await.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/async-dependencies.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/async-parallel.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/async-suspense-boundaries.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/bundle-barrel-imports.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/bundle-conditional.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/bundle-defer-third-party.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/bundle-dynamic-imports.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/bundle-preload.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/client-event-listeners.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/client-swr-dedup.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-batch-dom-css.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-cache-function-results.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-cache-property-access.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-cache-storage.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-combine-iterations.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-early-exit.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-hoist-regexp.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-index-maps.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-length-check-first.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-min-max-loop.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-set-map-lookups.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/js-tosorted-immutable.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-activity.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-animate-svg-wrapper.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-conditional-render.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-content-visibility.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-hoist-jsx.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-hydration-no-flicker.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rendering-svg-precision.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-defer-reads.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-dependencies.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-derived-state.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-lazy-state-init.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-memo.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/rerender-transitions.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/server-cache-lru.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/server-cache-react.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/server-parallel-fetching.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/react-best-practices/references/rules/server-serialization.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/research-first/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/research-first/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/s3-communicator/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/s3-communicator/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/s3-guardian/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/s3-guardian/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/s3-heartbeat/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/s3-heartbeat/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/setup-harness/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/setup-harness/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/skill-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/skill-development/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/skill-development/references/skill-creator-original.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/skill-development/references/skill-creator-original.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/system3-orchestrator/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/system3-orchestrator/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/using-tmux-for-interactive-commands/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/using-tmux-for-interactive-commands/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/website-ux-audit/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/website-ux-audit/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/website-ux-design-concepts/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/website-ux-design-concepts/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/worker-focused-execution/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/worker-focused-execution/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
| `skills/worker-focused-execution/TESTING_DETAILS.md` | crosslinks | error | Broken link: [TESTING_INFRASTRUCTURE.md](../orchestrator-multiagent/TESTING_INFRASTRUCTURE.md) |
| `skills/worktree-manager-skill/SKILL.md` | frontmatter | error | Missing required frontmatter field: title |
| `skills/worktree-manager-skill/SKILL.md` | frontmatter | error | Missing required frontmatter field: status |
