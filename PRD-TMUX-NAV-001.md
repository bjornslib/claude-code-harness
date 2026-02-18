# PRD-TMUX-NAV-001: tmux-nav — Interactive tmux Session Navigator

## Overview

**Tool**: `tmux-nav`
**Language**: Go (compiled binary)
**Location**: `tools/tmux-nav/`
**Install target**: `~/.local/bin/tmux-nav` (or `$GOPATH/bin/tmux-nav`)

A fast, compiled Go CLI that enables rapid inspection and attachment to in-flight tmux sessions from within the claude-code-harness repo. Designed for iTerm2 on macOS, with graceful fallback for other terminals.

---

## Problem Statement

When multiple Claude Code orchestrators and workers are running in parallel tmux sessions, it is cumbersome to:
1. Remember which session names are active
2. Switch between them without losing context
3. Quickly "peek" at what a session is currently doing without fully attaching

A compiled Go binary provides sub-50ms startup, rich TUI, and direct shell integration — superior to Node.js scripts for a daily-driver tool.

---

## Goals

| # | Goal |
|---|------|
| G1 | List all active tmux sessions with metadata (windows, panes, attached status) |
| G2 | Show a live "peek" preview of the selected session's active pane |
| G3 | Attach to a session in the **same iTerm2 tab** when possible |
| G4 | Fall back to opening a **new iTerm2 tab** via AppleScript when not in tmux |
| G5 | Allow killing sessions from the navigator |
| G6 | Compile to a single binary with no runtime dependencies |
| G7 | Be installable with `make install` from the harness repo |

---

## Non-Goals

- Session creation (use existing tmux commands)
- Log streaming / persistent monitoring (use validation-agent monitor mode)
- Windows/Linux desktop integration (macOS/iTerm2 primary; Linux tmux-attach fallback)

---

## User Stories

**US-1** — As a developer, I want to see all active tmux sessions at a glance so I can pick one to inspect.

**US-2** — As a developer, I want to preview the last N lines of a session's output before deciding to attach, so I don't disrupt context unnecessarily.

**US-3** — As a developer using iTerm2, I want to attach to a session inside the same terminal window (using tmux CC integration), so I stay in one app.

**US-4** — As a developer not inside tmux, I want the tool to open a new iTerm2 tab and attach there automatically.

**US-5** — As a developer, I want to kill a zombie session directly from the navigator without memorising session names.

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | `tmux-nav` lists sessions within 50ms on systems with up to 20 sessions |
| AC-2 | Arrow-key selection works in the terminal TUI |
| AC-3 | Pressing `p` or `Enter` on selection shows last 30 lines of active pane |
| AC-4 | Pressing `a` attaches to session; if inside iTerm2 uses `tmux -CC attach -t <session>` |
| AC-5 | When not inside tmux, AppleScript opens a new iTerm2 tab then attaches |
| AC-6 | Pressing `k` prompts confirmation then kills the selected session |
| AC-7 | Pressing `q` or `Esc` exits cleanly |
| AC-8 | `make install` from repo root copies binary to `~/.local/bin/tmux-nav` |
| AC-9 | Binary has zero runtime dependencies beyond system tmux |

---

## Technical Design

### Architecture

```
tools/tmux-nav/
├── main.go           # Entry point, arg parsing
├── tmux/
│   └── client.go     # tmux command wrappers (list, peek, attach, kill)
├── tui/
│   └── app.go        # Bubble Tea TUI (list + preview panes)
├── iterm2/
│   └── attach.go     # iTerm2 CC detection + AppleScript new-tab fallback
├── go.mod
├── go.sum
└── Makefile
```

### Key Libraries

| Library | Purpose |
|---------|---------|
| `github.com/charmbracelet/bubbletea` | TUI framework (event loop, rendering) |
| `github.com/charmbracelet/lipgloss` | Styled output, borders, colours |
| `github.com/charmbracelet/bubbles/list` | Session list with filtering |
| `github.com/charmbracelet/bubbles/viewport` | Scrollable peek preview |

*(No gotmux or promptui — pure exec + bubbletea for maximum reliability)*

### tmux Detection

```go
// Detect if running inside tmux
os.Getenv("TMUX") != ""

// Detect if running inside iTerm2
os.Getenv("TERM_PROGRAM") == "iTerm.app"
```

### Attachment Strategy

| Context | Action |
|---------|--------|
| Inside tmux + iTerm2 | `tmux -CC attach -t <session>` (CC mode, same window) |
| Inside tmux, not iTerm2 | `tmux switch-client -t <session>` |
| Outside tmux + iTerm2 | AppleScript: open new tab → `tmux -CC attach -t <session>` |
| Outside tmux, not iTerm2 | `tmux attach -t <session>` in current terminal |

### iTerm2 AppleScript Template

```applescript
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session
      write text "tmux -CC attach -t SESSION_NAME"
    end tell
  end tell
end tell
```

### Peek Implementation

```bash
tmux capture-pane -t <session>:<window>.<pane> -p -S -30 -e
```

`-e` preserves escape codes for colour; `-S -30` captures last 30 lines.

---

## UI Layout

```
┌─ tmux-nav ─────────────────────────────────────────────────────────┐
│ Sessions (3)                    │ Preview: claude-orchestrator-A    │
│ ──────────────────────────────  │ ─────────────────────────────── │
│ ▶ claude-orchestrator-A  3w det │ [18:42:01] Task 7: running...    │
│   claude-worker-B         1w att │ [18:42:03] Writing file...       │
│   scratch                 1w det │ [18:42:05] Done.                 │
│                                 │                                   │
│ [a]ttach [p]review [k]ill [q]uit│                                   │
└────────────────────────────────────────────────────────────────────┘
```

---

## Makefile Targets

```makefile
build:
    go build -o tmux-nav ./...

install: build
    mkdir -p ~/.local/bin
    cp tmux-nav ~/.local/bin/tmux-nav
    @echo "Installed to ~/.local/bin/tmux-nav"

clean:
    rm -f tmux-nav
```

---

## Implementation Plan

| Phase | Tasks | Notes |
|-------|-------|-------|
| P1 | Go module init, project skeleton | `go mod init` |
| P2 | `tmux/client.go` — list, peek, kill | Pure exec, no lib |
| P3 | `tui/app.go` — Bubble Tea list + viewport | bubbletea + lipgloss |
| P4 | `iterm2/attach.go` — detection + AppleScript | osascript on macOS |
| P5 | Wire `main.go`, Makefile | Build + install targets |
| P6 | Repo integration | Add to .gitignore if binary, README note |

---

## Out of Scope / Future

- Session grouping by project/epic
- Persistent config file (`~/.tmux-nav.yaml`)
- Fuzzy search across sessions
- Windows (WSL) support
