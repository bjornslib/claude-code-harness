# Claude Code Harness Setup

A complete configuration framework for multi-agent AI orchestration using Claude Code. This repository provides skills, hooks, and orchestration tools for building sophisticated AI-powered development workflows.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for MCP servers)
- Git
- Anthropic API key

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/faie-group/claude-harness-setup.git
   cd claude-harness-setup
   ```

2. **Install Python dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Configure environment variables**
   ```bash
   cp .mcp.json.example .mcp.json
   # Edit .mcp.json and add your API keys
   ```

4. **Run tests to verify setup**
   ```bash
   pytest tests/ -v
   ```

### MCP Server Setup

This harness uses several MCP (Model Context Protocol) servers:

| Server | Purpose | Required Env Var |
|--------|---------|------------------|
| `sequential-thinking` | Multi-step reasoning | None |
| `context7` | Framework documentation | None |
| `perplexity` | Web research | `PERPLEXITY_API_KEY` |
| `brave-search` | Web search | `BRAVE_API_KEY` |
| `serena` | IDE assistant patterns | None |
| `hindsight` | Long-term memory | None (local HTTP) |
| `logfire-mcp` | Observability queries | `LOGFIRE_READ_TOKEN` |

## Architecture

### 3-Level Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: META-ORCHESTRATOR                                         │
│  Role: Strategic planning, OKR tracking, business validation        │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 2: ORCHESTRATOR                                              │
│  Role: Feature coordination, worker delegation via native teams     │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: WORKERS (native teammates via Agent Teams)                │
│  Specialists: frontend-dev-expert, backend-solutions-engineer,      │
│               tdd-test-engineer, solution-architect                 │
│  Role: Implementation, testing, focused execution                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Higher levels coordinate; lower levels implement.

### Directory Structure

```
.claude/
├── CLAUDE.md                     # Configuration directory documentation
├── settings.json                 # Core settings (hooks, permissions)
├── output-styles/                # Automatically loaded agent behaviors
├── skills/                       # Explicitly invoked agent skills
├── hooks/                        # Lifecycle event handlers
├── scripts/                      # CLI utilities
├── commands/                     # Slash commands
└── documentation/                # Architecture decisions and guides

cobuilder/
├── engine/                       # Pipeline runner and handlers
├── templates/                    # DOT pipeline templates
├── repomap/                      # Codebase intelligence
└── worktrees/                    # Worktree management
```

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ -v --cov=cobuilder --cov-report=term-missing
```

### Coverage Requirements
- Minimum coverage: **90%**
- CI enforces this on all PRs

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Architecture overview
- Setup steps
- Testing guidelines
- Code style requirements
- Template creation

## License

MIT License - Copyright (c) 2026 FAIE Group

See [LICENSE](LICENSE) for full text.