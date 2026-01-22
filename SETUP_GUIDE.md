# Quick Setup Guide

This guide helps you set up the Claude Code Harness in any project.

## For First-Time Setup

### 1. Get the Harness

```bash
cd ~
git clone https://github.com/bjornslib/claude-code-harness.git
cd claude-code-harness
```

### 2. Configure API Keys

```bash
# Copy the example configuration
cp .mcp.json.example .mcp.json

# Edit with your API keys
# You need:
# - Anthropic API Key: https://console.anthropic.com/settings/keys
# - Perplexity API Key: https://www.perplexity.ai/settings/api
# - Brave Search API Key: https://brave.com/search/api/
# - GitHub Token (optional): https://github.com/settings/tokens

nano .mcp.json
```

### 3. Update GitHub MCP Skill (Optional)

If you want to use the GitHub skill:

```bash
nano .claude/skills/mcp-skills/github/mcp-config.json
# Replace "your-github-personal-access-token-here" with your actual token
```

### 4. Make Scripts Executable

```bash
chmod +x .claude/scripts/message-bus/*
chmod +x .claude/scripts/completion-state/*
chmod +x .claude/hooks/*.sh
chmod +x .claude/hooks/**/*.py
chmod +x .claude/skills/setup-harness/setup.py
```

## For Each New Project

### Option 1: Using the Setup Command (Easiest)

```bash
cd /path/to/your/project
claude
```

Then in Claude Code:
```
/setup-harness ~/claude-code-harness
```

### Option 2: Manual Symlink

```bash
cd /path/to/your/project
ln -s ~/claude-code-harness/.claude .claude

# Choose one:
ln -s ~/claude-code-harness/.mcp.json .mcp.json  # Share MCP config
# OR
cp ~/claude-code-harness/.mcp.json .mcp.json     # Project-specific MCP config
```

### Option 3: Using the Python Script

```bash
cd /path/to/your/project
python ~/claude-code-harness/.claude/skills/setup-harness/setup.py ~/claude-code-harness --mcp
```

## Verify Setup

```bash
# Check symlink
ls -la .claude

# Should show:
# .claude -> /Users/yourusername/claude-code-harness/.claude

# Test access
cat .claude/CLAUDE.md

# Launch Claude Code
claude
```

## Update the Harness

When improvements are made to the harness:

```bash
cd ~/claude-code-harness
git pull
```

All projects using the symlink automatically get the updates!

## Troubleshooting

### Symlink not working

```bash
# Remove broken symlink
rm .claude

# Recreate
ln -s ~/claude-code-harness/.claude .claude
```

### Permission denied

```bash
chmod +x ~/claude-code-harness/.claude/scripts/**/*
chmod +x ~/claude-code-harness/.claude/hooks/**/*
```

### Can't find harness

```bash
# Find where you cloned it
find ~ -name "claude-code-harness" -type d 2>/dev/null
```

### MCP servers not working

```bash
# Check if .mcp.json has valid API keys
cat .mcp.json

# Verify paths are correct
# Verify API keys are not placeholder values
```

## Launch Commands

Once setup is complete:

| Command | Purpose |
|---------|---------|
| `claude` | Launch standard Claude Code |
| `ccsystem3` | Launch System 3 meta-orchestrator |
| `launchorchestrator [epic]` | Launch orchestrator in worktree |
| `launchcc` | Launch worker (in tmux session) |

## Additional Configuration

### Project-Specific Overrides

Create `.claude/settings.local.json` in your project (doesn't affect harness):

```json
{
  "permissions": {
    "allow": [
      "Bash(npm:*)",
      "Bash(python:*)"
    ]
  }
}
```

### Custom Skills

Place project-specific skills in `.claude-local/skills/` in your project root.

## Documentation

- [README.md](./README.md) - Full repository documentation
- [CLAUDE.md](./CLAUDE.md) - Architecture and configuration reference
- [.claude/TM_COMMANDS_GUIDE.md](./.claude/TM_COMMANDS_GUIDE.md) - Task Master commands
- [.claude/documentation/](./claude/documentation/) - Architecture decisions and guides

## Support

- 🐛 **Issues**: https://github.com/bjornslib/claude-code-harness/issues
- 📖 **Docs**: Check the documentation folder
- 💬 **Questions**: Open a GitHub discussion
