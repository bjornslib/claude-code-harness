# Agent Library Improvements — BMAD-Inspired Refactor

**Date:** 2026-02-27
**Branch:** `claude/evaluate-bmad-method-goiQ2`
**Status:** In progress

## Context

After evaluating the BMAD method (10 named specialist agents across 4 phases), we identified gaps and improvement opportunities in our agent library. BMAD's key strengths we want to adopt:

- Dedicated UX Designer agent (Sally) running parallel to planning, not after
- Research-first discipline with current framework docs (context7) before any design choices
- Long-term memory integration (Hindsight reflect) to surface prior session patterns before finalising decisions
- Explicit skill invocations documented per agent so orchestrators know exactly what to reach for

## Changes

### 1. CREATE — `ux-designer` (new agent)

**BMAD equivalent:** Sally (UX Specialist)
**Gap:** We had no agent that wraps the UX pipeline.

**Skills invoked:**
- `website-ux-audit` → systematic UX/UI analysis of existing site
- `website-ux-design-concepts` → visual mockups (Stitch MCP default)
- `frontend-design` → brief for implementation handoff

**Output:** `UX_Design.md` + section reports + design brief for `frontend-dev-expert`

**Workflow position:** Runs in Phase 2 (Planning), parallel to `solution-design-architect` PRD work — not after architecture.

---

### 2. UPDATE — `solution-design-architect`

**Changes:**
- Replace hardcoded Windsurf template path → `docs/prds/` (project-relative)
- Add mandatory `research-first` invocation at task start (covers both PRD and SD modes)
- Add explicit `context7` usage within research protocol for framework/library docs
- Add `Hindsight reflect` checkpoint before finalising solution choices (surfaces prior session patterns and pitfalls)

**Rationale:** Solution design decisions should always be grounded in current docs (context7) and prior session learnings (Hindsight), not stale LLM memory.

---

### 3. UPDATE — `frontend-dev-expert`

**Add explicit skill invocations:**
- `react-best-practices` — invoke before writing any React/Next.js code
- `frontend-design` — invoke when designing new UI (not just implementing)
- `design-to-code` — invoke when translating mockup/screenshot to components
- `mcp-skills/shadcn` — invoke for shadcn/ui component patterns
- `mcp-skills/magicui` — invoke for animations, bento-grid, shimmer

---

### 4. UPDATE — `backend-solutions-engineer`

**Add explicit skill invocations:**
- `dspy-development` — invoke for any DSPy module, optimizer, or LLM pipeline work
- `research-first` — invoke before implementing unfamiliar framework/library patterns
- `mcp-skills/logfire` — invoke for observability, tracing, span management

---

### 5. UPDATE — `validation-test-agent`

**Add explicit skill invocations:**
- `acceptance-test-writer` — invoke when no acceptance tests exist yet for a PRD
- `acceptance-test-runner` — invoke to execute stored acceptance tests
- `mcp-skills/playwright` — invoke for browser automation test execution
- `mcp-skills/chrome-devtools` — invoke for console/network/performance inspection

---

## Deferred

- **Technical Writer (Paige)** — doc-gardener + orchestrator covers this; revisit if doc volume grows
- **Quick Flow Solo Dev (Barry)** — fast-track single agent for small tasks; revisit for maintenance workflows
- **Analyst (Mary)** — merged into `solution-design-architect`; split only if PRD phase becomes bottleneck
