---
name: setup-harness
description: Copy Claude Code harness into a project directory for version control. Use when user wants to set up the harness or when they say "setup harness", "copy harness", "install harness", or provide a harness path.
---

# Setup Harness Skill

Copies the Claude Code harness into project directories so it becomes part of the Git repository.

## Trigger Patterns

- User says "setup harness"
- User provides a path to claude-code-harness
- User says "copy the harness", "install harness configuration"
- User asks how to use the harness in a new project

## What This Skill Does

Copies harness files from the source to the target project:
1. Copy `.claude/` directory (excluding runtime files)
2. Optionally copy `.mcp.json`
3. Update `.gitignore` for runtime exclusions
4. Verify the setup
5. Provide next steps

## Why Copy Instead of Symlink?

- **Version Control**: `.claude/` becomes part of your repo
- **Self-Contained**: No external dependencies
- **CI/CD Ready**: Works in pipelines without the source harness
- **Project-Specific**: Customize without affecting other projects

## Usage

**Interactive Mode** (recommended):
```
User: Setup the harness
```

**Specify target path**:
```
User: Setup harness in /path/to/my-project
```

## Implementation

### Step 1: Determine Source Harness Path

The source harness is the current working directory's `.claude/` or a known location.

**Default source**: `/Users/theb/Documents/Windsurf/claude-harness-setup`

```bash
# Verify source harness exists
HARNESS_SOURCE="/Users/theb/Documents/Windsurf/claude-harness-setup"

if [ ! -d "$HARNESS_SOURCE/.claude" ]; then
    echo "Error: Harness source not found at $HARNESS_SOURCE/.claude"
    exit 1
fi

if [ ! -f "$HARNESS_SOURCE/.claude/settings.json" ] || \
   [ ! -d "$HARNESS_SOURCE/.claude/skills" ]; then
    echo "Error: Invalid harness - missing required files"
    exit 1
fi

echo "✓ Found valid harness at $HARNESS_SOURCE"
```

### Step 2: Select Target Directory

**Use AskUserQuestion** to ask where to copy the harness:

```
Question: "Where do you want to set up the Claude Code harness?"
Header: "Target Dir"
Options:
1. "Current directory" - Set up harness in the current working directory
2. "Specify path" - Provide a custom directory path

multiSelect: false
```

**Verify target directory**:
```bash
# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Target directory $TARGET_DIR does not exist"
    exit 1
fi

# Check if target is writable
if [ ! -w "$TARGET_DIR" ]; then
    echo "Error: No write permission for $TARGET_DIR"
    exit 1
fi
```

### Step 3: Handle Existing .claude Directory

```bash
if [ -e "$TARGET_DIR/.claude" ]; then
    if [ -L "$TARGET_DIR/.claude" ]; then
        echo "Found existing .claude symlink -> $(readlink $TARGET_DIR/.claude)"
        echo "Will remove symlink and copy fresh"
        # User confirmation needed
    else
        echo "Found existing .claude directory"
        echo "Will overwrite (preserving project CLAUDE.md if present)"
        # User confirmation needed
    fi
fi
```

**Use AskUserQuestion for confirmation**:
```
Question: "Existing .claude found. Overwrite with fresh copy?"
Header: "Overwrite"
Options:
1. "Yes, overwrite" - Replace with fresh harness copy
2. "No, cancel" - Abort setup

multiSelect: false
```

### Step 4: Backup Project CLAUDE.md (if exists)

```bash
PROJECT_CLAUDE_BACKUP=""
if [ -f "$TARGET_DIR/.claude/CLAUDE.md" ]; then
    PROJECT_CLAUDE_BACKUP=$(mktemp)
    cp "$TARGET_DIR/.claude/CLAUDE.md" "$PROJECT_CLAUDE_BACKUP"
    echo "✓ Backed up project CLAUDE.md"
fi
```

### Step 5: Copy Harness with Exclusions

Use `rsync` to copy while excluding runtime/state files:

```bash
# Remove existing .claude (symlink or directory)
if [ -L "$TARGET_DIR/.claude" ]; then
    rm "$TARGET_DIR/.claude"
elif [ -d "$TARGET_DIR/.claude" ]; then
    rm -rf "$TARGET_DIR/.claude"
fi

# Copy with exclusions
# NOTE: learnings/ IS copied (contains useful templates)
# NOTE: validation/ IS copied (contains validation configs)
# NOTE: scripts/completion-state/ and scripts/message-bus/ MUST be copied (CLI tools)
# NOTE: Top-level message-bus/ and completion-state/ are RUNTIME dirs (excluded)
rsync -av --delete \
    --include='scripts/***' \
    --exclude='state/*' \
    --exclude='completion-state/' \
    --exclude='progress/*' \
    --exclude='worker-assignments/*' \
    --exclude='message-bus/' \
    --exclude='logs/' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='node_modules/' \
    --exclude='settings.local.json' \
    "$HARNESS_SOURCE/.claude/" "$TARGET_DIR/.claude/"

echo "✓ Copied harness to $TARGET_DIR/.claude/"
```

### Step 6: Restore Project CLAUDE.md (if backed up)

```bash
if [ -n "$PROJECT_CLAUDE_BACKUP" ] && [ -f "$PROJECT_CLAUDE_BACKUP" ]; then
    cp "$PROJECT_CLAUDE_BACKUP" "$TARGET_DIR/.claude/CLAUDE.md"
    rm "$PROJECT_CLAUDE_BACKUP"
    echo "✓ Restored project CLAUDE.md"
fi
```

### Step 7: Update .gitignore

Add runtime exclusions to the target project's `.gitignore`:

```bash
GITIGNORE="$TARGET_DIR/.gitignore"

# Check if .gitignore exists
if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
fi

# Add Claude Code runtime exclusions if not already present
if ! grep -q "Claude Code runtime files" "$GITIGNORE" 2>/dev/null; then
    cat >> "$GITIGNORE" << 'GITIGNORE_ENTRIES'

# Claude Code runtime files (not version controlled)
# Directories are kept via .gitkeep, but contents are ignored
.claude/state/*
!.claude/state/.gitkeep
.claude/completion-state/*
!.claude/completion-state/.gitkeep
.claude/progress/*
!.claude/progress/.gitkeep
.claude/worker-assignments/*
!.claude/worker-assignments/.gitkeep
.claude/message-bus/*
!.claude/message-bus/.gitkeep
.claude/logs/
.claude/*.log
.claude/settings.local.json
GITIGNORE_ENTRIES
    echo "✓ Updated .gitignore with runtime exclusions"
else
    echo "✓ Runtime exclusions already in .gitignore"
fi
```

### Step 8: Handle .mcp.json

**Use AskUserQuestion**:
```
Question: "How do you want to handle .mcp.json?"
Header: "MCP Config"
Options:
1. "Copy it (Recommended)" - Copy .mcp.json to project (can customize per-project)
2. "Keep existing" - Don't touch .mcp.json
3. "Symlink it" - Share MCP config across projects (not version controlled)

multiSelect: false
```

```bash
case "$MCP_CHOICE" in
    "copy")
        cp "$HARNESS_SOURCE/.mcp.json" "$TARGET_DIR/.mcp.json"
        echo "✓ Copied .mcp.json"
        echo "⚠ Remember to update API keys for this project"
        ;;
    "symlink")
        ln -sf "$HARNESS_SOURCE/.mcp.json" "$TARGET_DIR/.mcp.json"
        echo "✓ Symlinked .mcp.json"
        ;;
    "keep")
        echo "✓ Kept existing .mcp.json"
        ;;
esac
```

### Step 9: Create Runtime Directories

Create the excluded directories with proper structure so Claude Code works immediately:

```bash
# Create directories with .gitkeep files so git tracks them
mkdir -p "$TARGET_DIR/.claude/state"
touch "$TARGET_DIR/.claude/state/.gitkeep"

mkdir -p "$TARGET_DIR/.claude/completion-state/default"
mkdir -p "$TARGET_DIR/.claude/completion-state/history"
mkdir -p "$TARGET_DIR/.claude/completion-state/promises"
mkdir -p "$TARGET_DIR/.claude/completion-state/sessions"
touch "$TARGET_DIR/.claude/completion-state/.gitkeep"

mkdir -p "$TARGET_DIR/.claude/progress"
touch "$TARGET_DIR/.claude/progress/.gitkeep"

mkdir -p "$TARGET_DIR/.claude/worker-assignments"
touch "$TARGET_DIR/.claude/worker-assignments/.gitkeep"

mkdir -p "$TARGET_DIR/.claude/message-bus/signals"
touch "$TARGET_DIR/.claude/message-bus/.gitkeep"

echo "✓ Created runtime directories with .gitkeep files"
```

### Step 10: Verify Setup

```bash
echo ""
echo "=== Verification ==="

# Check key files exist
[ -f "$TARGET_DIR/.claude/settings.json" ] && echo "✓ settings.json" || echo "✗ settings.json missing"
[ -d "$TARGET_DIR/.claude/skills" ] && echo "✓ skills/" || echo "✗ skills/ missing"
[ -d "$TARGET_DIR/.claude/hooks" ] && echo "✓ hooks/" || echo "✗ hooks/ missing"
[ -d "$TARGET_DIR/.claude/output-styles" ] && echo "✓ output-styles/" || echo "✗ output-styles/ missing"

# Check scripts are executable
if [ -x "$TARGET_DIR/.claude/scripts/message-bus/mb-init" 2>/dev/null ]; then
    echo "✓ Scripts are executable"
else
    echo "⚠ Making scripts executable..."
    find "$TARGET_DIR/.claude/scripts" -type f -name "*.sh" -exec chmod +x {} \;
    find "$TARGET_DIR/.claude/scripts" -type f -name "mb-*" -exec chmod +x {} \;
fi
```

### Step 11: Provide Next Steps

```
✓ Harness setup complete!

Copied to: $TARGET_DIR/.claude/

What was copied:
  - settings.json (Claude Code configuration)
  - skills/ (21 skills including orchestrator-multiagent)
  - hooks/ (lifecycle automation)
  - output-styles/ (orchestrator, system3)
  - scripts/ (message-bus, utilities)

Runtime directories created (gitignored, with .gitkeep):
  - state/, progress/, worker-assignments/
  - completion-state/ (with subdirs: default/, history/, promises/, sessions/)
  - message-bus/ (with subdirs: signals/)

Next steps:
1. Customize .claude/CLAUDE.md for your project
2. Review .mcp.json API keys
3. Commit the .claude/ directory to git
4. Launch Claude Code:
   - System 3: ccsystem3
   - Orchestrator: ccorch
   - Worker: launchcc

To update harness later:
  Run /setup-harness again (will preserve your CLAUDE.md)
```

## Files Copied vs Excluded

### Copied (version controlled)
- `settings.json` - Core configuration
- `skills/` - All skill definitions
- `hooks/` - Lifecycle hooks
- `output-styles/` - Agent behavior definitions
- `scripts/` - CLI utilities
- `commands/` - Slash commands
- `schemas/` - JSON schemas
- `tests/` - Hook tests
- `utils/` - Utility scripts
- `agents/` - Agent configurations
- `documentation/` - Architecture docs
- `validation/` - Validation agent configs
- `learnings/` - Multi-agent coordination guides (coordination.md, decomposition.md, failures.md)
- `TM_COMMANDS_GUIDE.md` - Task Master reference

### Excluded (runtime, gitignored)
- `state/*` - Runtime state files (directory kept with .gitkeep)
- `completion-state/*` - Session completion tracking (subdirs created: default/, history/, promises/, sessions/)
- `progress/*` - Session progress files (directory kept with .gitkeep)
- `worker-assignments/*` - Worker task assignments (directory kept with .gitkeep)
- `message-bus/*` - Inter-instance messaging (subdirs created: signals/)
- `logs/` - Log files
- `settings.local.json` - Local overrides

## Error Handling

**Source harness not found**:
```
Error: Harness source not found at /path/.claude
Please ensure the claude-harness-setup repository exists
```

**Target not writable**:
```
Error: No write permission for /path/to/project
Check directory permissions or run with appropriate access
```

**rsync not available**:
```bash
# Fallback to cp if rsync unavailable
if ! command -v rsync &> /dev/null; then
    cp -R "$HARNESS_SOURCE/.claude" "$TARGET_DIR/.claude"
    # Manual cleanup of excluded directories
    rm -rf "$TARGET_DIR/.claude/state"
    rm -rf "$TARGET_DIR/.claude/completion-state"
    # ... etc
fi
```

## Example Interaction

```
User: Setup harness in /Users/theb/Documents/Windsurf/DSPY_PreEmploymentDirectory_PoC