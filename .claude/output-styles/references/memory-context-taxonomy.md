# Memory Context Taxonomy Reference

> Extracted from `system3-meta-orchestrator.md` to reduce output style context size.
> This is lookup/reference material for Hindsight memory bank contexts.

---

## Private Bank: `system3-orchestrator`

| Context | Purpose |
|---------|---------|
| `system3-patterns` | **Validated** orchestration patterns (passed process supervision) |
| `system3-anti-patterns` | Failed approaches (failed process supervision) |
| `system3-capabilities` | Capability confidence levels per domain |
| `system3-narrative` | GEO chains (Goal-Experience-Outcome) |
| `system3-active-goals` | Current initiatives and next steps |
| `system3-prd-tracking` | **Active initiative goals**, acceptance criteria, and outcome records |
| `system3-okr-tracking` | Active Business Epics, Key Result status, verification attempts |
| `system3-decisions` | Autonomous decisions with reasoning and reversibility |

**Note:** The private bank (`system3-orchestrator`) is exclusively for YOUR meta-orchestration wisdom. Only System 3 reads/writes this bank.

## Project Bank: `$CLAUDE_PROJECT_BANK`

| Context | Purpose |
|---------|---------|
| `project` | Core project knowledge |
| `patterns` | Development patterns (backend, frontend, etc.) |
| `architecture` | Solution designs and decisions |
| `bugs` | Root causes and prevention strategies |
| `deployment` | Infrastructure patterns |
| `roadmap` | Strategic Themes, long-term business direction |

**Note:** The project bank ID is derived from your current directory name (e.g., `dspy-preemploymentdirectory-poc`). Access via `os.environ.get("CLAUDE_PROJECT_BANK")`.

## Memory Contexts for OKR Tracking

| Context | Bank | Purpose |
|---------|------|---------|
| `system3-okr-tracking` | Private | Active Business Epics, Key Result status, verification attempts |
| `system3-prd-tracking` | Private | PRD-extracted goals (existing context) |
| `roadmap` | Shared | Strategic Themes, long-term business direction |
