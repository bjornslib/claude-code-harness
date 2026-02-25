# Claude Code Harness

A centralized, reusable configuration framework for multi-agent AI orchestration with Claude Code. Maintain one harness, use it across all your projects via symlinks.

**📖 Quick Navigation**:
- 🚀 **New here?** Start with the [Quick Start](#-quick-start) section below
- 📘 **Setting up?** See [SETUP_GUIDE.md](./SETUP_GUIDE.md) for step-by-step instructions
- 🏗️ **Understanding the system?** Check [ARCHITECTURE.md](./ARCHITECTURE.md) for visual diagrams
- ⚙️ **Technical details?** Read [CLAUDE.md](./CLAUDE.md) for complete reference

## 🎯 Concept

Instead of duplicating `.claude/` configuration in every project, maintain it once in this repository and symlink it into your project directories. This gives you:

- ✅ **Single source of truth** - Update orchestration patterns once, apply everywhere
- ✅ **Version control** - Track changes to your AI workflow configurations
- ✅ **Consistent behavior** - Same agent hierarchy across all projects
- ✅ **Easy updates** - Pull latest improvements without manual copying

## 🏗️ Architecture

This harness provides a 3-level agent hierarchy for sophisticated multi-agent development:

```
System 3 (Meta-Orchestrator)
    ↓
Orchestrators (Feature coordination)
    ↓
Workers (Implementation)
```

**Key Components**:
- **Output Styles**: Auto-loaded agent behaviors (system3, orchestrator)
- **Skills**: 20+ specialized capabilities (orchestration, testing, design, etc.)
- **Hooks**: Lifecycle automation (session start, stop gates, validation)
- **MCP Integration**: 9+ MCP servers with progressive disclosure wrappers
- **Task Master**: PRD → Task decomposition and tracking

**📖 Documentation**:
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Visual diagrams and system flows
- [CLAUDE.md](./CLAUDE.md) - Complete technical reference
- [SETUP_GUIDE.md](./SETUP_GUIDE.md) - Quick setup and troubleshooting

## 🚀 Quick Start

### Step 1: Clone and Configure

1. **Clone this repository** (one-time setup):
   ```bash
   git clone https://github.com/bjornslib/claude-code-harness.git ~/claude-harness
   cd ~/claude-harness
   ```

2. **Configure MCP servers with your API keys**:
   ```bash
   cp .mcp.json.example .mcp.json
   # Edit .mcp.json with your API keys:
   # - ANTHROPIC_API_KEY
   # - PERPLEXITY_API_KEY
   # - BRAVE_API_KEY
   # - GITHUB_PERSONAL_ACCESS_TOKEN (in .claude/skills/mcp-skills/github/mcp-config.json)
   ```

   **Required API keys**:
   - **Anthropic API**: For Task Master and agent operations - [Get API key](https://console.anthropic.com/settings/keys)
   - **Perplexity API**: For research and web queries - [Get API key](https://www.perplexity.ai/settings/api)
   - **Brave Search API**: For web search capabilities - [Get API key](https://brave.com/search/api/)
   - **GitHub Token**: For GitHub MCP skill (optional) - [Create token](https://github.com/settings/tokens)

### Step 2: Link into Your Project

#### Option A: Automated Setup (Recommended)

From your project directory:

```bash
claude
```

Then use the slash command:

```
/setup-harness ~/claude-harness
```

The command will:
1. Verify the harness directory exists
2. Create the `.claude` symlink in your project
3. Optionally symlink `.mcp.json` (if you want shared MCP servers)
4. Verify the setup

#### Option B: Manual Setup

1. **Symlink into your project**:
   ```bash
   cd /path/to/your/project
   ln -s ~/claude-harness/.claude .claude
   ```

2. **Choose MCP configuration approach**:

   **Option 1: Symlink** (share MCP servers across all projects):
   ```bash
   ln -s ~/claude-harness/.mcp.json .mcp.json
   ```

   **Option 2: Copy** (customize per project):
   ```bash
   cp ~/claude-harness/.mcp.json .mcp.json
   # Then customize for this project
   ```

3. **Verify setup**:
   ```bash
   ls -la .claude  # Should show symlink arrow
   claude          # Launch Claude Code
   ```

## 📁 What Gets Symlinked?

### The `.claude` Directory

When you symlink `.claude`, your project gets access to:

```
.claude/
├── output-styles/          # Auto-loaded agent behaviors
├── skills/                 # 20+ capabilities (orchestration, TDD, etc.)
├── hooks/                  # Lifecycle automation
├── scripts/                # CLI utilities (completion-state)
├── commands/               # Slash commands
├── documentation/          # Architecture guides
├── settings.json           # Core configuration
└── CLAUDE.md              # This directory's documentation
```

### The `.mcp.json` File (Optional)

Symlink this if you want shared MCP server configurations across projects:
- sequential-thinking
- task-master-ai
- context7
- perplexity-ask
- brave-search
- serena
- hindsight
- beads

**When NOT to symlink `.mcp.json`**:
- Your project needs different API keys
- You need project-specific MCP servers
- You want to control MCP servers independently

## 🔧 Project-Specific Customization

Even with symlinked `.claude`, you can customize per-project:

### 1. Local Settings Override

Create `.claude/settings.local.json` in your project (this won't affect the harness):

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

### 2. Project-Specific MCP Servers

Copy `.mcp.json` instead of symlinking it, then add your project's servers:

```json
{
  "mcpServers": {
    "project-specific-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["my-project-mcp-server"]
    }
  }
}
```

### 3. Additional Skills

Place project-specific skills in your project root:

```
your-project/
├── .claude/              # Symlink to harness
├── .claude-local/        # Project-specific additions
│   └── skills/
│       └── custom-skill/
└── your-code/
```

Then reference with `Skill("custom-skill")`.

## 🔄 Updating the Harness

When improvements are made to the harness:

```bash
cd ~/claude-harness
git pull
```

All projects using the symlink immediately get the updates. No manual copying needed.

## 🎮 Using the Harness

### Launch Commands

| Level | Command | Purpose |
|-------|---------|---------|
| System 3 | `ccsystem3` | Meta-orchestrator for strategic planning |
| Orchestrator | `launchorchestrator [epic]` | Feature coordination |
| Worker | `launchcc` | Implementation in tmux session |

### Common Workflows

**Start a new feature**:
```bash
ccsystem3
# In System 3 session: Define OKRs, spawn orchestrator
```

**Work on existing tasks**:
```bash
launchorchestrator feature-auth
# Orchestrator delegates to workers via tmux
```

**Implement a specific task**:
```bash
# In tmux session
launchcc
# Worker executes, reports completion
```

## 📋 Prerequisites

- **Claude Code CLI** installed (`claude`)
- **Git** for version control
- **tmux** for worker session management (optional but recommended)
- **Node.js** for Task Master and MCP servers
- **Python 3.8+** for hooks and scripts

### Installing Dependencies

**macOS**:
```bash
brew install tmux node python
npm install -g task-master-ai
```

**Linux**:
```bash
sudo apt install tmux nodejs python3 python3-pip
npm install -g task-master-ai
```

## ⚠️ Important Notes

### API Keys

This repository provides `.mcp.json.example` as a template. You must create your own `.mcp.json` with your API keys:

**Setup**:
1. Copy the example: `cp .mcp.json.example .mcp.json`
2. Add your API keys for:
   - Anthropic API (required for Task Master)
   - Perplexity API (required for research)
   - Brave Search API (required for web search)
   - GitHub Token (optional, for GitHub skill)
3. Never commit `.mcp.json` to version control (already in `.gitignore`)

**Security best practices**:
- Keep API keys in `.mcp.json` which is gitignored
- Use environment variables for CI/CD
- Rotate keys regularly
- Use project-specific keys when possible

### Symlink Compatibility

**Works great with**:
- Git (symlinks are tracked)
- macOS, Linux
- VSCode, Cursor, Windsurf
- Claude Code CLI

**Potential issues**:
- Windows (use WSL or Git Bash)
- Some deployment systems (may need to resolve symlinks)
- Cloud sync tools (Dropbox, etc.) may not handle symlinks well

## 🧪 Testing

Run harness tests:

```bash
cd ~/claude-harness

# Test hooks
pytest .claude/tests/hooks/

# Test completion state
pytest .claude/tests/completion-state/

# Test stop gate
pytest .claude/hooks/unified_stop_gate/tests/
```

## 📚 Documentation

### Main Documentation

- **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** - Quick setup reference and troubleshooting
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Visual diagrams showing symlink concept, agent hierarchy, and system flows
- **[CLAUDE.md](./CLAUDE.md)** - Complete technical architecture and configuration reference

### Additional References

- [.claude/TM_COMMANDS_GUIDE.md](./.claude/TM_COMMANDS_GUIDE.md) - Task Master slash commands
- [.claude/documentation/ADR-001-output-style-reliability.md](./.claude/documentation/ADR-001-output-style-reliability.md) - Output styles vs skills

## 🤝 Contributing

This harness is designed to evolve with your team's needs:

1. Make improvements in the central harness repo
2. Test across your projects
3. Commit and push
4. All projects get the updates via symlink

**Contribution workflow**:
```bash
cd ~/claude-harness
git checkout -b feature/new-skill
# Make changes
git add .
git commit -m "Add new orchestration skill"
git push origin feature/new-skill
# Create PR
```

## 🐛 Troubleshooting

For detailed troubleshooting, see [SETUP_GUIDE.md](./SETUP_GUIDE.md#troubleshooting).

**Quick fixes**:

```bash
# Symlink not working
rm .claude && ln -s ~/claude-harness/.claude .claude

# Scripts not executable
chmod +x ~/claude-harness/.claude/scripts/**/*
chmod +x ~/claude-harness/.claude/hooks/**/*

```

## 📄 License

MIT License - Use freely in your projects

## 🙏 Acknowledgments

Built with:
- [Claude Code](https://claude.ai/code) by Anthropic
- [Task Master AI](https://github.com/taskmaster-ai/taskmaster) for task decomposition
- [Beads](https://github.com/beads-dev/beads) for issue tracking
- Multiple MCP servers for enhanced capabilities

---

**Questions or issues?** Open an issue in this repository or consult the [CLAUDE.md](./CLAUDE.md) documentation.
