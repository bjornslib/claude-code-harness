# Harness Documentation Gardening Report

**Generated**: 2026-02-20T13:08:46
**Target**: `/Users/theb/Documents/Windsurf/claude-harness-setup/.claude`
**Mode**: DRY-RUN (no changes)

## Summary

- **Files scanned**: 299
- **Total violations found**: 207
- **Auto-fixed**: 0
- **Remaining violations**: 207

### Before

| Severity | Count |
|----------|-------|
| Errors   | 192 |
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
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [{evidence_filename}](./evidence/{evidence_filename}) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [filename](./evidence/filename) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
| `documentation/gardening-report.md` | crosslinks | error | Broken link: [SKILL.md](SKILL.md) |
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
