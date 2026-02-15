# USER.md - Operator Profile

> This file captures your personal preferences, workflow habits, and project notes.
> Claude Code loads this automatically at session start via the `load-user-profile` hook.
> Edit freely — changes take effect on the next session or after compaction.

## Preferences

<!-- Tools, languages, and default choices -->
- **Package Manager**: npm
- **Language**: TypeScript / Python
- **Editor Theme**: Dark
- **Commit Style**: Conventional Commits (feat/fix/docs/chore)
- **Branch Naming**: feature/<topic>, fix/<topic>, epic/<name>

## Workflow

<!-- How you like to work with Claude Code -->
- **Autonomy Level**: Confirm before destructive actions; otherwise proceed
- **Testing**: Always run tests before marking tasks complete
- **Git**: Do not auto-commit; only commit when explicitly asked
- **Documentation**: Update docs alongside code changes
- **Error Handling**: Investigate root cause before applying fixes

## Communication Style

<!-- How Claude should talk to you -->
- **Verbosity**: Concise — skip preamble, get to the point
- **Formatting**: Use markdown; code blocks with language tags
- **Emojis**: Only when explicitly requested
- **Explanations**: Brief unless asked to elaborate
- **Tone**: Professional, direct

## Project Notes

<!-- Project-specific context that persists across sessions -->
- **Architecture**: 3-level agent hierarchy (System 3 > Orchestrator > Workers)
- **Key Repos**: claude-harness-setup (config), zenagent2 (application)
- **Deployment**: Local development; Railway for staging/production
- **Current Focus**: Epic 3 — Hindsight long-term memory integration
