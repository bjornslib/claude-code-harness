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

### Step 1: Gather Information

Ask the user for:
1. **Harness path**: Where is the claude-code-harness repository?
2. **MCP symlink**: Do they want to symlink `.mcp.json` or keep it separate?

**Example questions**:
```
What is the path to your claude-code-harness repository?
(e.g., ~/claude-harness or /path/to/claude-harness-setup)

Do you want to symlink .mcp.json as well?
- Yes: Share MCP server configurations across projects
- No: Keep project-specific MCP servers (recommended if you need custom API keys)
```

### Step 2: Verify Harness Path

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

### Step 3: Check Current Project State

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

### Step 4: Create Symlinks

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

### Step 5: Verify Setup

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

### Step 6: Provide Next Steps

```
✓ Harness setup complete!

Next steps:
1. Launch Claude Code: claude
2. Verify configuration: cat .claude/CLAUDE.md
3. Start working:
   - System 3: ccsystem3
   - Orchestrator: launchorchestrator [epic-name]
   - Worker: launchcc (in tmux session)

Configuration:
  .claude -> $HARNESS_ABS/.claude
  [.mcp.json -> $HARNESS_ABS/.mcp.json] (if symlinked)

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
User: Setup the harness from ~/claude-harness