---
name: setup-harness
description: Symlink Claude Code harness into a project directory. Use when user wants to set up the harness or when they say "setup harness", "link harness", "install harness", or provide a harness path.
---

# Setup Harness Skill

Automates symlinking the Claude Code harness into project directories.

## Trigger Patterns

- User says "setup harness"
- User provides a path to claude-code-harness
- User says "link the harness", "install harness configuration"
- User asks how to use the harness in a new project

## What This Skill Does

Creates symlinks from the project directory to the centralized harness:
1. Symlink `.claude/` directory
2. Optionally symlink `.mcp.json` (user choice)
3. Verify the setup
4. Provide next steps

## Usage

**Interactive Mode** (recommended):
```
User: Setup the harness from ~/claude-harness
```

**Specify harness path**:
```
User: Link .claude from /Users/theb/Documents/Windsurf/claude-harness-setup
```

## Implementation

### Step 1: Select Target Directory

**Use AskUserQuestion** to ask where they want to set up the harness:

```
Question: "Where do you want to set up the Claude Code harness?"
Header: "Target Dir"
Options:
1. "Current directory" - Set up harness in the current working directory
2. "Parent directory" - Set up harness in the parent of the current directory
3. "Specify custom path" - Provide a custom directory path

multiSelect: false
```

After receiving the answer:
- If "Current directory": Use `pwd` as target
- If "Parent directory": Use `$(dirname $(pwd))` as target
- If "Specify custom path": Ask for the path with a follow-up question

**Verify target directory**:
```bash
# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Target directory $TARGET_DIR does not exist"
    echo "Create it first with: mkdir -p $TARGET_DIR"
    exit 1
fi

# Check if target is writable
if [ ! -w "$TARGET_DIR" ]; then
    echo "Error: No write permission for $TARGET_DIR"
    exit 1
fi

# Change to target directory
cd "$TARGET_DIR"
```

### Step 2: Gather Additional Information

Ask the user for:
1. **Harness path**: Where is the claude-code-harness repository?
2. **MCP symlink**: Do they want to symlink `.mcp.json` or keep it separate?

**Use AskUserQuestion for harness path**:
```
Question: "Where is your claude-code-harness repository?"
Header: "Harness Path"
Options:
1. "~/claude-harness-setup" - Default location
2. "/Users/theb/Documents/Windsurf/claude-harness-setup" - Current harness location
3. "Specify custom path" - Provide a different path

multiSelect: false
```

**Use AskUserQuestion for MCP symlink**:
```
Question: "Do you want to symlink .mcp.json as well?"
Header: "MCP Config"
Options:
1. "No (Recommended)" - Keep project-specific MCP servers and API keys
2. "Yes" - Share MCP configurations across all projects

multiSelect: false
```

### Step 3: Verify Harness Path

```bash
# Check if harness directory exists
if [ ! -d "$HARNESS_PATH/.claude" ]; then
    echo "Error: $HARNESS_PATH/.claude not found"
    exit 1
fi

# Verify it's the correct harness (check for key files)
if [ ! -f "$HARNESS_PATH/.claude/CLAUDE.md" ] || \
   [ ! -d "$HARNESS_PATH/.claude/skills" ]; then
    echo "Error: Directory doesn't appear to be a valid claude-code-harness"
    exit 1
fi
```

### Step 4: Check Current Project State

```bash
# Check if .claude already exists
if [ -e ".claude" ]; then
    if [ -L ".claude" ]; then
        echo "Warning: .claude symlink already exists"
        echo "Current target: $(readlink .claude)"
        echo "Do you want to replace it? (y/n)"
        # Get user confirmation
    else
        echo "Error: .claude directory already exists (not a symlink)"
        echo "Please backup and remove it first, or choose a different location"
        exit 1
    fi
fi
```

### Step 5: Create Symlinks

```bash
# Get absolute path to harness
HARNESS_ABS=$(cd "$HARNESS_PATH" && pwd)

# Create .claude symlink
ln -s "$HARNESS_ABS/.claude" .claude

echo "✓ Created .claude symlink"
echo "  .claude -> $HARNESS_ABS/.claude"

# Optionally create .mcp.json symlink
if [ "$SYMLINK_MCP" = "yes" ]; then
    if [ -e ".mcp.json" ]; then
        echo "Warning: .mcp.json already exists"
        # Handle existing file
    else
        ln -s "$HARNESS_ABS/.mcp.json" .mcp.json
        echo "✓ Created .mcp.json symlink"
        echo "  .mcp.json -> $HARNESS_ABS/.mcp.json"
    fi
fi
```

### Step 6: Verify Setup

```bash
# Check if symlinks are valid
if [ -L ".claude" ] && [ -d ".claude" ]; then
    echo "✓ .claude symlink is valid"
else
    echo "✗ .claude symlink verification failed"
fi

# Test hook access
if [ -f ".claude/settings.json" ]; then
    echo "✓ Can access harness configuration"
else
    echo "✗ Cannot access harness configuration"
fi

# Check permissions
if [ -x ".claude/scripts/message-bus/mb-init" ]; then
    echo "✓ Scripts are executable"
else
    echo "⚠ Warning: Some scripts may not be executable"
    echo "  Run: chmod +x $HARNESS_ABS/.claude/scripts/**/*"
fi
```

### Step 7: Setup Shell Functions

**Use AskUserQuestion to ask about shell configuration**:
```
Question: "Do you want to add the Claude Code launch functions to your shell?"
Header: "Shell Setup"
Options:
1. "Yes, add to ~/.zshrc (Recommended)" - Add ccsystem3, ccorch, launchcc functions
2. "No, I'll configure manually" - Skip shell setup

multiSelect: false
```

If user selects "Yes", add these functions to `~/.zshrc`:

```bash
# Check if functions already exist
if grep -q "function ccsystem3" ~/.zshrc 2>/dev/null; then
    echo "⚠ Shell functions already exist in ~/.zshrc"
    echo "  Skipping to avoid duplicates"
else
    cat >> ~/.zshrc << 'SHELL_FUNCTIONS'

# Claude Code Harness - Launch Functions
# Added by setup-harness skill

# Helper: Derive project bank name from current directory
function _derive_project_bank {
    basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g' | sed 's/ /-/g'
}

# Launch Claude Code with full permissions (for workers in tmux)
function launchcc {
    claude --chrome --dangerously-skip-permissions "$@"
}

# Launch as Orchestrator (Level 2)
function ccorch {
    export CLAUDE_SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
    export CLAUDE_PROJECT_BANK="$(_derive_project_bank)"
    export CLAUDE_OUTPUT_STYLE=orchestrator
    export CLAUDE_ENFORCE_BO=false
    export CLAUDE_MAX_ITERATIONS=5

    echo "🆔 Session ID: $CLAUDE_SESSION_ID"
    echo "🧠 Project Bank: $CLAUDE_PROJECT_BANK"
    claude --chrome --dangerously-skip-permissions "$@"
}

# Launch as System 3 Meta-Orchestrator (Level 1)
function ccsystem3 {
    export CLAUDE_SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
    export CLAUDE_PROJECT_BANK="$(_derive_project_bank)"
    export CLAUDE_ENFORCE_PROMISE=true
    export CLAUDE_ENFORCE_BO=true
    export CLAUDE_OUTPUT_STYLE=system3
    export CLAUDE_MAX_ITERATIONS=25

    echo "🆔 Session ID: $CLAUDE_SESSION_ID"
    echo "🧠 Project Bank: $CLAUDE_PROJECT_BANK"
    claude --chrome --dangerously-skip-permissions "$@"
}
SHELL_FUNCTIONS

    echo "✓ Added shell functions to ~/.zshrc"
    echo "  Run 'source ~/.zshrc' to activate"
fi
```

**Environment Variables Set by Launch Functions:**

| Variable | Purpose | Set By |
|----------|---------|--------|
| `CLAUDE_SESSION_ID` | Unique session identifier for completion tracking | All functions |
| `CLAUDE_PROJECT_BANK` | Hindsight memory bank (derived from directory name) | ccorch, ccsystem3 |
| `CLAUDE_OUTPUT_STYLE` | Output style to load (orchestrator/system3) | ccorch, ccsystem3 |
| `CLAUDE_ENFORCE_BO` | Enforce business outcome validation | ccsystem3 only |
| `CLAUDE_ENFORCE_PROMISE` | Enforce completion promise tracking | ccsystem3 only |
| `CLAUDE_MAX_ITERATIONS` | Max agentic turns before pause | All functions |

### Step 8: Provide Next Steps

```
✓ Harness setup complete!

Configuration:
  .claude -> $HARNESS_ABS/.claude
  [.mcp.json -> $HARNESS_ABS/.mcp.json] (if symlinked)
  [Shell functions added to ~/.zshrc] (if selected)

Next steps:
1. Reload shell: source ~/.zshrc
2. Launch Claude Code:
   - System 3 (strategic): ccsystem3
   - Orchestrator (feature): ccorch
   - Worker (implementation): launchcc
3. Verify configuration: cat .claude/CLAUDE.md

Launch Commands:
  ccsystem3    - Meta-orchestrator with completion promises
  ccorch       - Feature orchestrator with worker delegation
  launchcc     - Worker in tmux session

Environment (auto-set by launch commands):
  CLAUDE_SESSION_ID    - Unique per session
  CLAUDE_PROJECT_BANK  - Derived from directory name (e.g., "my-project")
  CLAUDE_OUTPUT_STYLE  - system3 or orchestrator

To update the harness:
  cd $HARNESS_ABS && git pull

Documentation:
  - README.md: $HARNESS_ABS/README.md
  - Architecture: .claude/CLAUDE.md
  - Task Master: .claude/TM_COMMANDS_GUIDE.md
```

## Error Handling

### Common Issues

**1. Symlink already exists**:
- Show current target
- Ask user if they want to replace it
- If yes: `rm .claude && ln -s ...`

**2. Directory already exists (not symlink)**:
- Warn user
- Suggest backing up existing directory
- Offer to rename: `mv .claude .claude.backup`

**3. Harness path invalid**:
- Verify path exists
- Check for key files (.claude/CLAUDE.md, etc.)
- Suggest correct path format

**4. Permission issues**:
- Check if scripts are executable
- Provide chmod command if needed
- Verify user has write access to project directory

**5. Relative vs absolute paths**:
- Always convert to absolute path with `cd && pwd`
- Symlinks should use absolute paths for reliability

## Safety Checks

Before creating symlinks:
- [ ] Harness path exists and is valid
- [ ] Harness contains .claude/CLAUDE.md
- [ ] Harness contains .claude/skills/
- [ ] Project directory is writable
- [ ] No conflicting .claude directory (or user confirmed replacement)
- [ ] Paths are absolute (not relative)

## Example Interaction

```
User: Setup the harness
Assistant: I'll help you set up the Claude Code harness.

Where do you want to set up the harness?
1. Current directory (/Users/theb/Documents/Windsurf/my-project)
2. Parent directory (/Users/theb/Documents/Windsurf)
3. Specify custom path

User: Current directory

Assistant: [Verifies target directory exists and is writable]
✓ Target directory is valid

Where is your claude-code-harness repository?
1. ~/claude-harness-setup
2. /Users/theb/Documents/Windsurf/claude-harness-setup
3. Specify custom path

User: Option 2

Assistant: [Checks ~/claude-harness/.claude exists]
✓ Found valid harness at /Users/theb/Documents/Windsurf/claude-harness-setup

Do you want to symlink .mcp.json as well?
1. No (Recommended) - Keep project-specific MCP servers and API keys
2. Yes - Share MCP configurations across all projects

User: No, keep it separate

Assistant: [Creates symlinks]
✓ Created .claude symlink
  .claude -> /Users/theb/Documents/Windsurf/claude-harness-setup/.claude

✓ Harness setup complete\!

Next steps:
1. Launch Claude Code: claude
2. Verify configuration: cat .claude/CLAUDE.md
3. Start working:
   - System 3: ccsystem3
   - Orchestrator: launchorchestrator [epic-name]
   - Worker: launchcc (in tmux session)
```
