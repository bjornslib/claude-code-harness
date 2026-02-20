---
title: "PRD-S3-AUTONOMY-001: Agent Autonomy & Observability Expansion"
status: draft
type: prd
last_verified: 2026-02-17
grade: B
related_beads: []
---

# PRD-S3-AUTONOMY-001: Agent Autonomy & Observability Expansion

**Author**: System 3 Meta-Orchestrator
**Date**: 2026-02-17
**Status**: APPROVED WITH CHANGES — Reviewed 2026-02-17
**Branch**: system3-with-claws
**Repositories**: claude-harness-setup (harness), zenagent3/zenagent/agencheck (application)

## Problem Statement

Our 3-level agent hierarchy (System 3 → Orchestrator → Worker) can write and deploy code but lacks the feedback loops to **observe, validate, and maintain** its own work autonomously. Agents are blind to runtime behavior (logs, traces, deployment health), documentation rots without detection, test specifications exist as markdown but are never executed by agents, and validation is single-pass rather than continuous.

These gaps limit autonomous operation to ~2-hour sprints. To reach 6+ hour autonomous sessions (the OpenAI benchmark), agents need closed-loop feedback: implement → deploy → observe → validate → fix → maintain.

## Research Basis

This PRD synthesizes findings from:
- **OpenAI Harness Engineering** (2026-02): AGENTS.md pattern, doc-gardening agents, agent-legible observability, mechanical enforcement of golden principles, ephemeral observability per worktree
- **Hindsight Memory Banks**: System 3 private bank (orchestration patterns, anti-patterns) and project bank (documentation fragmentation, validation gaps, missing observability contracts)
- **Codebase Audit**: zenagent3/zenagent/agencheck — 1,456 markdown files across 3 fragmented systems, Logfire 4.17.0 installed but not agent-accessible, 335 catalogued test files with unenforced test-as-markdown pattern
- **External Research**: Logfire MCP server, Railway PR preview environments, Claude Agent SDK for programmatic validation, Anthropic Python SDK (Sonnet 4.5), Ralph Wiggum review patterns

## Success Criteria

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Autonomous session duration | ~2 hours | 6+ hours | Session timestamps in Hindsight |
| Agent self-debugging capability | None | Agents query Logfire traces | Logfire MCP tool usage count |
| Documentation findability | Scan 4 directories blindly | Single INDEX.md + quality-grades.json | Agent navigation time |
| Test spec execution rate | 0% (specs exist, never executed) | 80%+ of browser specs run per epic | Test report files generated |
| Validation gate strength | Single-pass (trust self-report) | Triple-gate (teammate + cs-verify + programmatic) | cs-verify rejection rate |
| Doc staleness | Unknown (no tracking) | 0 files >90 days without review | docs/lint.py violations |
| Output style context load | 2,507 lines auto-loaded | ~1,950 lines auto-loaded | Line count |

---

## Epic 1: Agent-Legible Observability

**Goal**: Give agents the ability to query their own runtime behavior — traces, errors, metrics — so they can self-debug and validate deployment health.

### F1.1: Logfire MCP Server Integration

**Description**: Add the official Pydantic Logfire MCP server to `.mcp.json` in both repositories, enabling agents to query OpenTelemetry traces and metrics collected by our existing Logfire 4.17.0 installation.

**Acceptance Criteria**:
- [ ] Logfire MCP server configured in `.mcp.json` with `LOGFIRE_READ_TOKEN`
- [ ] Agent can invoke `find_exceptions_in_traces` and get results from agencheck services
- [ ] Agent can invoke `run_sql_query` against Logfire trace data
- [ ] Documentation added to `docs/guides/observability.md` describing available tools
- [ ] Smoke test: Agent queries "exceptions in last hour for eddy-validate" and gets structured results

**Technical Notes**:
- Server: Python package `logfire-mcp` on PyPI (v0.8.0+). Run via `uvx logfire-mcp@latest` or `pip install logfire-mcp`
- Pydantic also offers a hosted remote MCP server (preferred for production)
- Available tools: `find_exceptions_in_file`, `arbitrary_query`, `logfire_link`
- Requires read-only Logfire API token (generate from Logfire dashboard)
- No code changes to agencheck services — Logfire already instrumented
- Add to MCP skills wrapper for progressive disclosure

**Risk**: Logfire read token may have rate limits. Mitigation: cache frequent queries.

### F1.2: Structured Log Schema Standardization

**Description**: Standardize log output across all 4 backend services (main orchestrator, eddy-validate, user-chat, deep-research) to use a consistent JSON schema that agents can parse.

**Acceptance Criteria**:
- [ ] Log schema document in `docs/design/log-schema.md`
- [ ] All services emit logs with fields: `event_type`, `service`, `status`, `duration_ms`, `correlation_id`
- [ ] LLM calls include `tokens_used.input` and `tokens_used.output` fields
- [ ] Agent can query Logfire for "total tokens used by eddy-validate in last hour"

**Technical Notes**:
- Logfire already collects structured data; this is about adding consistent custom attributes
- Requires code changes in each service's logging setup (4 files)
- Token tracking requires instrumenting OpenAI/Anthropic client calls

### F1.3: Observability Integration in Orchestrator Workflow

**Description**: Add a post-deployment observability check to the orchestrator validation flow, making it a standard step after code deployment.

**Acceptance Criteria**:
- [ ] Orchestrator-multiagent SKILL.md includes "Level 4: Deploy Health" validation step
- [ ] Orchestrators query Logfire after deployment for: new exceptions, latency regressions, error rate changes
- [ ] If anomalies detected: orchestrator creates follow-up task before closing epic
- [ ] Template query added to orchestrator skill references

---

## Epic 2: Documentation Centralization & Governance

**Goal**: Consolidate 1,456 fragmented documentation files into a centralized, indexed, machine-readable system with programmatic quality enforcement.

### F2.1: Documentation Structure & Index (zenagent3)

**Description**: Create the target documentation structure in `zenagent3/zenagent/agencheck/docs/` with a ~100-line `INDEX.md` and machine-readable `quality-grades.json`.

**Acceptance Criteria**:
- [ ] `docs/INDEX.md` exists with ~100 lines, serving as table of contents
- [ ] `docs/quality-grades.json` tracks every doc's status, grade, last_verified date
- [ ] Directory structure: `prd/`, `design/`, `architecture/`, `guides/`, `plans/`, `tests/`, `archive/`
- [ ] Every markdown file has frontmatter: `title`, `status`, `type`, `last_verified`, `grade`
- [ ] Agent can read INDEX.md and navigate to any document in 1 hop

**Technical Notes**:
- Inspired by OpenAI's AGENTS.md pattern but adapted for our dual-repo setup
- INDEX.md focuses on active/relevant docs only; archive is discoverable but not prominent
- quality-grades.json enables programmatic staleness checking

### F2.2: Documentation Migration Script

**Description**: Create a Python migration script that moves files from the 3 current systems into the new structure, adding frontmatter where missing.

**Acceptance Criteria**:
- [ ] Migration script handles: `documentation/prds/` + `documentation/prd/` + `.taskmaster/docs/` → `docs/prd/`
- [ ] `documentation/solution_designs/` → `docs/design/solution/`
- [ ] `documentation/scratch-pads/` (798 files) → `docs/archive/scratch-pads/`
- [ ] Naming normalization (hyphens vs underscores standardized)
- [ ] Script is idempotent (safe to run multiple times)
- [ ] `--dry-run` mode shows what would be moved without moving
- [ ] Script detects and warns about absolute path references (`/Users/...`)
- [ ] Script validates cross-references after migration
- [ ] Rollback script provided (`docs/rollback-migration.sh`)
- [ ] Git history preserved (use `git mv` where possible)
- [ ] Post-migration: `docs/lint.py --full` passes with 0 violations

**Migration Phases** (progressive, not all-at-once):
1. Phase 1: Active PRDs (~50 files) + INDEX.md + quality-grades.json
2. Phase 2: Solution designs (~100 files)
3. Phase 3: Guides/plans (~200 files)
4. Phase 4: Scratch-pads archive (798 files, low-touch move)
5. Phase 5: Remaining files (~300 files)

**Technical Notes**:
- Must handle duplicate directory names (`prd/` vs `prds/`, `handoff/` vs `handoffs/`)
- Scratch-pads are archived, not deleted
- .taskmaster/docs/ may need symlinks for TaskMaster compatibility
- Test migration on a branch first; keep old directories for 2 weeks before deleting

### F2.3: Documentation Linter

**Description**: Create a standalone Python linter (`docs/lint.py`) that mechanically enforces documentation structure, freshness, and cross-link integrity.

**Acceptance Criteria**:
- [ ] Checks: frontmatter presence, cross-link validity, PRD-bead sync, quality-grades accuracy, staleness (>90 days), naming conventions, orphaned files
- [ ] Exit code 0 = all pass, exit code 1 = violations found
- [ ] `--changed-only` flag for pre-commit hook usage
- [ ] `--full` flag for complete scan with report output
- [ ] Output: human-readable violation list AND machine-readable JSON
- [ ] Integrated as pre-commit hook in `.claude/hooks/`

**Risk Assessment**: The linter must be lightweight (no external dependencies) and fast (<5 seconds for full scan). Heavy linters slow down commits and get disabled.

### F2.4: Doc-Gardener Remediation

**Description**: System 3 idle-time task that reads lint violations and opens fix-up PRs or creates beads for manual fixes.

**Acceptance Criteria**:
- [ ] System 3 can run `docs/lint.py --full --json` and parse violations
- [ ] For auto-fixable violations (broken links, missing frontmatter): agent creates fix commit
- [ ] For manual-fix violations (stale content): agent creates bead with `tag: doc-debt`
- [ ] Weekly report stored in `docs/GARDENING_REPORT.md`

---

## Epic 3: Test-as-Markdown Enforcement with Claude in Chrome

**Goal**: Activate the existing test-catalogue pattern by wiring markdown test specifications into the orchestrator validation flow, executed via Claude in Chrome.

### F3.1: Test Spec Standard Format

**Description**: Define a standard markdown format for browser test specifications that Claude in Chrome agents can execute.

**Acceptance Criteria**:
- [ ] Standard frontmatter: `title`, `type` (e2e-browser|api|visual), `service`, `port`, `prerequisites`
- [ ] Step format: numbered steps with action verbs (Navigate, Click, Fill, Wait, Assert)
- [ ] Evidence section: what screenshots/outputs to capture
- [ ] At least 5 existing test guides converted to standard format
- [ ] Format documented in `docs/tests/TEST_SPEC_FORMAT.md`

**Technical Notes**:
- Building on existing patterns: `epic9-TEST-GUIDE.md`, `MANUAL_TESTING_GUIDE.md`, `AG_UI_TESTING_IMPLEMENTATION_GUIDE.md`
- Claude in Chrome tools: `navigate`, `find`, `form_input`, `computer`, `read_page`, `upload_image`
- Specs are human-readable AND machine-executable (dual-use)

### F3.2: Browser Validation Integration

**Description**: Wire test spec execution into the orchestrator validation flow as a standard step.

**Acceptance Criteria**:
- [ ] Orchestrator validation includes "Level 3: Browser E2E" step
- [ ] Step reads test spec markdown, delegates to validation agent with Claude in Chrome access
- [ ] Agent follows steps literally, captures screenshots as evidence
- [ ] Results written to `docs/tests/reports/{date}-{spec-id}.md`
- [ ] Epic closure blocked unless at least one browser test spec passes

**Additional Acceptance Criteria**:
- [ ] Chrome health check at validation start: verify extension is connected before attempting browser tests
- [ ] If Chrome disconnects mid-session, fail gracefully and flag remaining tests as incomplete

**Risk Assessment**: Claude in Chrome requires Chrome to be open with the extension connected. This is an external dependency. Mitigation: Gate check at start verifies connectivity. If Chrome unavailable, skip browser tests but flag as incomplete.

### F3.3: Test Catalogue Sync

**Description**: Ensure the existing `tests/catalogue/` system stays synchronized with the new test spec format, and that `component_test_map.json` reflects browser test coverage.

**Acceptance Criteria**:
- [ ] `component_test_map.json` includes browser test spec mappings
- [ ] `COVERAGE_GAP_REPORT.md` updated to track browser test coverage
- [ ] Agent can query: "Which components have browser tests?" and get a structured answer

---

## Epic 4: On-Demand Validation Teammate Integration

**Goal**: Replace ephemeral validation subagents with an on-demand validation teammate pattern in the System 3 team, creating a structured validation workflow with triple-gate verification.

### F4.1: On-Demand Validation Teammate Pattern

**Description**: Define a structured pattern for System 3 to spawn validation teammates on-demand when verification is needed, using native Agent Teams.

**Acceptance Criteria**:
- [ ] System 3 can spawn `s3-validator` on-demand when validation is needed via `TeamCreate` + `Task`
- [ ] `s3-validator` handles validation request via its initial prompt (acceptance criteria, evidence, worktree path)
- [ ] `s3-validator` has access to Claude in Chrome tools for browser validation
- [ ] `s3-validator` reports results via `SendMessage` to team-lead and exits gracefully
- [ ] System 3 can spawn MULTIPLE validators in parallel for different tasks
- [ ] Documented pattern for reusing validators across multiple validations within one session
- [ ] Documented in system3-orchestrator SKILL.md

**Technical Notes**:
- The validator is a Sonnet-class agent with both code and browser capabilities
- Claude Code teammates exit when their work queue is empty — they do NOT "wait idle"
- Pattern: spawn per-request → validate → report via SendMessage → exit
- For multiple validations: spawn fresh validator per task (cheap, reliable)
- This ENHANCES the current oversight team pattern with standardized message protocol

### F4.2: Programmatic cs-verify Gate (Anthropic SDK)

**Description**: Update the `cs-verify` completion-state script to invoke Claude Sonnet 4.5 via the Anthropic Python SDK as a programmatic validation gate.

**Acceptance Criteria**:
- [ ] `cs-verify` script calls Anthropic Messages API with Sonnet 4.5 model
- [ ] Input: promise summary, acceptance criteria, proof provided
- [ ] Output: JSON verdict (PASS/FAIL), reasoning, confidence score
- [ ] If verdict=FAIL: verification rejected, session cannot end
- [ ] Cost tracking: log tokens used per validation call
- [ ] Fallback: if API unavailable, warn but don't block (graceful degradation)

**Technical Notes**:
- Uses `anthropic` Python package (already available in environment)
- Model: `claude-sonnet-4-5-20250929`
- Cost: ~$0.01-0.03 per validation call
- This creates the third gate in the triple-gate validation:
  - Gate 1: Session self-reports completion
  - Gate 2: s3-validator teammate independently verifies
  - Gate 3: cs-verify calls Sonnet 4.5 as programmatic judge

**Risk Assessment**: API latency (~2-5 seconds per call). Acceptable for completion verification. Fallback to warn-only mode if API is down.

### F4.3: Validation Request Protocol

**Description**: Define the message format for System 3 → s3-validator communication.

**Acceptance Criteria**:
- [ ] Standard message format documented
- [ ] Includes: task_id, acceptance_criteria (list), claimed_evidence, worktree_path, validation_type (code|browser|both)
- [ ] Response format: verdict, evidence_collected, test_results, screenshots (if browser), reasoning
- [ ] System 3 can correlate requests and responses by task_id

---

## Epic 5: Output Style & Context Optimization

**Goal**: Reduce auto-loaded context from 15,536 lines to under 10,000 lines while maintaining behavioral reliability.

### F5.1: system3-meta-orchestrator.md Streamlining

**Description**: Reduce the System 3 output style from 2,507 lines to ~1,950 lines by extracting reference-only material while preserving all behavioral content.

**Acceptance Criteria**:
- [ ] Output style reduced to ~1,950 lines (22% reduction)
- [ ] ALL behavioral content retained: Iron Laws, decision framework, spawn patterns, monitoring protocols, OKR framework, momentum maintenance
- [ ] Only reference/lookup content extracted: command tables, message format specs, memory taxonomy, completion promise CLI reference
- [ ] Extracted sections moved to `references/` directory within system3-orchestrator skill
- [ ] Remaining content covers: session initialization, Iron Laws, decision framework, momentum maintenance, core spawn patterns
- [ ] No behavioral regression: System 3 still follows all protocols
- [ ] Progressive disclosure: reference sections loaded on-demand via skill invocation

**Sections Safe to Extract** (~550 lines of reference-only content):
| Section | Lines | Move To | Why Safe |
|---------|-------|---------|----------|
| Completion Promise CLI Reference | ~200 | `references/completion-promise.md` (exists) | Lookup table, not behavioral |
| Inter-Instance Messaging commands | ~150 | `references/message-bus-usage.md` | Command reference, not behavioral |
| Memory Context Taxonomy | ~100 | `references/memory-taxonomy.md` | Classification table, not behavioral |
| Monitoring command examples | ~100 | Inline in `references/monitoring-patterns.md` | Examples, not protocol |

**Sections That MUST STAY** (~1,950 lines of behavioral content):
- Iron Laws (all 4) — non-negotiable behavioral rules
- Decision Framework — real-time decision-making protocol
- Spawn patterns (tmux) — without these, orchestrators silently fail
- Monitoring protocols (dual-layer) — without these, orchestrators are unmonitored
- OKR framework — without this, business outcomes aren't tracked
- Momentum maintenance — without this, sessions stop prematurely
- Oversight team protocol — without this, validation is skipped
- PRD Workshop — without this, PRDs aren't created before implementation

**Risk Assessment**: Output styles are 100% reliable (auto-loaded). Skills are ~85% reliable (require invocation). The reviewer confirmed ~75-80% of content is behavioral. Moving behavioral content to skills causes System 3 to "forget" protocols when skills aren't invoked. Mitigation: conservative extraction (reference-only content), add skill auto-invoke in session init to pre-load critical references.

### F5.2: Skill Deduplication Audit

**Description**: Audit all 40 skills for content that duplicates the output style or other skills, and consolidate.

**Acceptance Criteria**:
- [ ] Audit report identifying duplicated content across skills
- [ ] Deduplicated skills: single source of truth for each pattern
- [ ] Total skill line count reduced by at least 20%
- [ ] No broken cross-references after consolidation

---

## Epic 6: Railway PR Preview Environments

**Goal**: Enable per-PR isolated deployment environments for automated validation against real infrastructure.

### F6.1: Railway PR Deploy Configuration

**Description**: Enable and configure Railway PR preview environments for the agencheck project.

**Acceptance Criteria**:
- [ ] PR deploys enabled in Railway project settings
- [ ] `railway.toml` updated with `[environments.pr]` sections for all services
- [ ] Each PR gets: backend (8000) + frontend (3000) + isolated database
- [ ] PR environments auto-tear-down on merge/close
- [ ] Health check endpoints verified per PR environment
- [ ] Documentation in `docs/guides/pr-environments.md`

**Prerequisites**:
- [ ] Verify current Railway plan supports PR preview environments
- [ ] Confirm monorepo vs separate service compatibility

**Technical Notes**:
- Uses existing Railway skills (no MCP server needed)
- Cost: ~$10-15/month for 5 active PRs (within Pro plan budget)
- Database: Railway auto-provisions separate instances per environment
- CORS: Must whitelist `*.railway.app` in backend configuration

### F6.2: Agent-Driven PR Validation

**Description**: Enable orchestrators to discover and test against PR preview environments.

**Acceptance Criteria**:
- [ ] Orchestrator can query Railway skill for PR environment URL
- [ ] Orchestrator can run API health checks against PR environment
- [ ] Orchestrator can delegate browser testing to Claude in Chrome against PR URL
- [ ] Validation results linked to PR via GitHub comment (using github skill)

---

## Non-Goals

- **New MCP servers for Railway**: Existing 13 Railway skills cover 90% of needs
- **Playwright MCP**: Claude in Chrome is the preferred browser automation tool
- **Full scratch-pad analysis**: Archive the 798 files; don't analyze each one
- **Cross-model review loops**: Same-model validation (Sonnet) is sufficient for now
- **Production deployment automation**: Agents propose; humans approve deployments to production

## Dependencies

| Dependency | Required For | Status |
|-----------|-------------|--------|
| Logfire read token | Epic 1 (F1.1) | Need to generate from dashboard |
| Anthropic API key | Epic 4 (F4.2) | Available in environment |
| Chrome + extension | Epic 3 (F3.2), Epic 4 (F4.1) | External dependency, gate-checked |
| Railway Pro plan | Epic 6 | Already active |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Output style streamlining causes behavioral regression | Medium | High | Keep Iron Laws in output style; extensive testing before rollout |
| Logfire rate limits block agent queries | Low | Medium | Cache frequent queries; batch requests |
| On-demand s3-validator fails to report | Low | Medium | SendMessage timeout detection; spawn replacement validator |
| Doc migration breaks existing TaskMaster integration | Medium | Medium | Symlinks for .taskmaster/docs/ compatibility |
| cs-verify API call adds latency to session end | Low | Low | Acceptable 2-5s; fallback to warn-only |
| Chrome extension unavailable for browser tests | Medium | Medium | Gate check; degrade gracefully, flag incomplete |

## Estimated Effort

| Epic | Effort | Team |
|------|--------|------|
| Epic 1: Observability | 1-2 days | 1 orchestrator (backend) |
| Epic 2: Documentation | 2-3 days | 1 orchestrator (scripts + migration) |
| Epic 3: Test Enforcement | 1-2 days | 1 orchestrator (frontend + specs) |
| Epic 4: Validation Service | 1-2 days | 1 orchestrator (harness + scripts) |
| Epic 5: Context Optimization | 1 day | System 3 direct (planning/docs, not code) |
| Epic 6: Railway PR Envs | 0.5 days | 1 orchestrator (config) |
| **Total** | **7-10 days** | **Parallelizable to ~4 days** |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-17 | Initial draft from System 3 research synthesis |
| 0.2 | 2026-02-17 | Post-review corrections: output style target 800→1,950 lines, persistent teammate→on-demand pattern, Logfire MCP corrected to PyPI package, doc migration phasing added, Chrome health check added, Railway prerequisite added |
