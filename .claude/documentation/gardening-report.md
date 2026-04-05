# Harness Documentation Gardening Report

**Generated**: 2026-04-03T09:42:09
**Target**: `/Users/theb/Documents/Windsurf/cobuilder-harness/.claude`
**Mode**: EXECUTE (fixes applied)

## Summary

- **Files scanned**: 498
- **Total violations found**: 58
- **Auto-fixed**: 0
- **Remaining violations**: 58

### Before

| Severity | Count |
|----------|-------|
| Errors   | 58 |
| Warnings | 0 |
| Info     | 0 |
| Fixable  | 0 |

### After Auto-fix

| Severity | Count |
|----------|-------|
| Errors   | 58 |
| Warnings | 0 |
| Info     | 0 |

## Manual Fix Required (Doc-Debt)

These violations require human attention:

| File | Category | Severity | Message |
|------|----------|----------|---------|
| `worktrees/bubblelens-pilot/docs/ARCHITECTURE.md` | frontmatter | error | Invalid last_verified date format: '2026-02-08T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/brainstorms/bubblelens-brief.md` | frontmatter | error | Invalid type 'research'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-BUBBLELENS-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-BUBBLELENS-P1-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-BUBBLELENS-P2-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-GUARDIAN-DISPATCH-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/PRD-RUNNER-PATHFIX-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/case-dataflow/PRD-CASE-DATAFLOW-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/cobuilder-upgrade/PRD-COBUILDER-UPGRADE-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/cobuilder-upgrade/PRD-COBUILDER-UPGRADE-001.md` | frontmatter | error | Invalid last_verified date format: '2026-03-15T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/prds/contact-name-split/PRD-CONTACT-NAME-SPLIT-001.md` | frontmatter | error | Invalid type 'prd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/prds/dashboard-audit-trail/PRD-DASHBOARD-AUDIT-001.md` | frontmatter | error | Invalid last_verified date format: '2026-03-09T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/prds/sequence-progression/PRD-SEQ-PROGRESSION-001.md` | frontmatter | error | Invalid last_verified date format: '2026-03-09T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/prds/verify-check-chat-fixes/MANUAL-TESTING-GUIDE.md` | frontmatter | error | Invalid last_verified date format: '2026-03-09T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic1-scaffolding.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic2-chrome-extension.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic4-feed-ingestion.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic4-survey.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic5-metadata-enrichment.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic6-classification.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic7-persona-engine.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-BUBBLELENS-001-epic8-dashboard.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-CCCB-MIGRATION-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-COBUILDER-PLUGIN-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-DOC-GARDENER-002-typebug.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/SD-VALIDATOR-CONSOLIDATION-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/case-dataflow/SD-CASE-DATAFLOW-001-epic1-canonical-types.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/case-dataflow/SD-CASE-DATAFLOW-001-epic2-frontend-form.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/case-dataflow/SD-CASE-DATAFLOW-001-epic3-api-proxy.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/case-dataflow/SD-CASE-DATAFLOW-001-epic4-backend-alignment.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/contact-name-split/SD-CONTACT-NAME-SPLIT-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/dashboard-audit-trail/SD-DASHBOARD-AUDIT-001.md` | frontmatter | error | Invalid last_verified date format: '2026-03-11T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/dashboard-audit-trail/SD-DASHBOARD-AUDIT-FRONTEND-001.md` | frontmatter | error | Invalid last_verified date format: '2026-03-09T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/guardian-dispatch/SD-GUARDIAN-DISPATCH-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-lifecycle-launcher/SD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-lifecycle-launcher/SD-PILOT-RENAME-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-self-driving/SD-ADD-NUMBERS-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-self-driving/SD-GUARDIAN-CONSTRAINTS-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-self-driving/SD-GUARDIAN-CRUD-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-self-driving/SD-GUARDIAN-FAILURE-CTX-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/guardian-self-driving/SD-GUARDIAN-GATE-FIX-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E10-epic-orchestrators.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E10-epic-orchestrators.md` | frontmatter | error | Invalid last_verified date format: '2026-03-06T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E11-async-review.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E11-async-review.md` | frontmatter | error | Invalid last_verified date format: '2026-03-06T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E12-graduated-autonomy.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E12-graduated-autonomy.md` | frontmatter | error | Invalid last_verified date format: '2026-03-06T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E8-initiative-graph.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E8-initiative-graph.md` | frontmatter | error | Invalid last_verified date format: '2026-03-06T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E9-persistent-s3.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/harness-upgrade/SD-HARNESS-UPGRADE-001-E9-persistent-s3.md` | frontmatter | error | Invalid last_verified date format: '2026-03-06T00:00:00.000Z'. Expected YYYY-MM-DD |
| `worktrees/bubblelens-pilot/docs/sds/placeholder-hello-world.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/docs/sds/verify-check-fix/SD-VERIFY-CHECK-001.md` | frontmatter | error | Invalid type 'sd'. Must be one of: agent, architecture, command, config, guide, hook, output-style, reference, skill |
| `worktrees/bubblelens-pilot/documentation/guides/pr-environments.md` | crosslinks | error | Broken link: [Railway Environment Configuration Reference](references/environment-config.md) |
| `worktrees/bubblelens-pilot/documentation/guides/pr-environments.md` | crosslinks | error | Broken link: [Railway Variables Reference](references/variables.md) |
| `worktrees/bubblelens-pilot/documentation/guides/pr-environments.md` | crosslinks | error | Broken link: [Railway Deployment Management](../skills/railway-deployment/SKILL.md) |
| `worktrees/bubblelens-pilot/documentation/guides/pr-environments.md` | crosslinks | error | Broken link: [Railway Project Management](../skills/railway-projects/SKILL.md) |
