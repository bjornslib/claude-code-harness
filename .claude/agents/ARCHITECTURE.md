---
title: "Codebase Architecture (for AI Workers)"
status: active
type: architecture
last_verified: 2026-03-10
grade: authoritative
---

# Codebase Architecture (for AI Workers)

## Repository Map
- `.claude/scripts/attractor/` — Pipeline runner and worker dispatch
- `.claude/agents/` — Agent configurations (YOU ARE HERE)
- `.claude/skills/` — Skill definitions (invoked via Skill tool)
- `docs/prds/` — Product requirement documents
- `docs/sds/` — Solution design documents
- `acceptance-tests/` — Gherkin acceptance test suites

## Essential Documentation Files:
- **`CLAUDE.md`**: Contains project-specific guidelines, coding standards, architectural decisions, and development workflows that override general best practices
- **`README.md`**: High-level overview of the project, setup instructions, and key entry points
- **`ARCHITECTURE.md`**: System architecture diagrams, component relationships, and technical design overview
- **`TOC.md` or `INDEX.md`**: Table of contents linking to major documentation sections and code areas

## Architecture Documentation Components:
All essential documentation files should contain:
- Component relationships and data flows
- Dependency maps (both internal and external dependencies)
- Service boundaries and integration points
- Technology stack and framework relationships