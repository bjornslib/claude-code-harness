# mcp-to-skill-converter

A Claude Skill that converts MCP servers into Claude Skills with 90%+ context savings.

## Why This Exists

MCP servers are great but load all tool definitions into context at startup. With 20+ tools, that's 30-50k tokens gone before Claude does any work.

This converter applies the "progressive disclosure" pattern to any MCP server:
- **Startup**: ~100 tokens (just metadata)
- **When used**: ~5k tokens (full instructions)
- **Executing**: 0 tokens (runs externally)

## Quick Start

All commands run from project root:

```bash
# List available MCP servers
python .claude/skills/mcp-to-skill-converter/mcp_to_skill.py --list

# Convert a single server (auto-outputs to mcp-skills/)
python .claude/skills/mcp-to-skill-converter/mcp_to_skill.py --name github

# Convert ALL compatible servers
python .claude/skills/mcp-to-skill-converter/mcp_to_skill.py --all
```

## Features

### List Servers (`--list`)

Shows all MCP servers in your `.mcp.json` with compatibility status:

```
📄 Servers in: /path/to/.mcp.json

Name                      Type       Compatible   Command
--------------------------------------------------------------------------------
github                    stdio      ✅ Yes        npx
context7                  stdio      ✅ Yes        npx
livekit-docs              http       ❌ No         https://...

📊 Total: 16 servers, 14 compatible
```

### Convert Single Server (`--name`)

```bash
python .claude/skills/mcp-to-skill-converter/mcp_to_skill.py --name github
```

Creates `.claude/skills/mcp-skills/github/` with:
- `SKILL.md` - Instructions for Claude
- `executor.py` - Handles MCP calls dynamically
- `mcp-config.json` - Server configuration
- `package.json` - Dependencies

### Batch Convert (`--all`)

```bash
python .claude/skills/mcp-to-skill-converter/mcp_to_skill.py --all
```

Converts all compatible (stdio) servers, creating a subdirectory for each.

### Auto-Discovery

The converter automatically finds `.mcp.json` by searching:
1. Current directory
2. Parent directories (like git does)

Or specify explicitly:
```bash
python mcp_to_skill.py --mcp-json /path/to/.mcp.json --name github --output-dir ./skills
```

### Legacy Mode

Still supports individual config files:
```bash
python mcp_to_skill.py --mcp-config github.json --output-dir ./skills/github
```

## CLI Reference

| Option | Description |
|--------|-------------|
| `--list` | List all servers with compatibility info |
| `--name NAME` | Convert specific server by name |
| `--all` | Convert all compatible servers |
| `--output-dir PATH` | Output directory for generated skill(s) |
| `--mcp-json PATH` | Path to .mcp.json (auto-discovers if not specified) |
| `--mcp-config PATH` | [Legacy] Direct MCP config JSON file |

## Context Savings

| Scenario | Native MCP | As Skill | Savings |
|----------|------------|----------|---------|
| Idle | 30-50k tokens | ~100 tokens | 99%+ |
| Active | 30-50k tokens | ~5k tokens | 85%+ |
| Executing | 30-50k tokens | 0 tokens | 100% |

## Server Compatibility

| Type | Compatible | Notes |
|------|------------|-------|
| `stdio` | ✅ Yes | Standard input/output protocol |
| `http` | ❌ No | Different protocol, requires HTTP client |
| `sse` | ❌ No | Server-sent events, different transport |

## How It Works

```
┌─────────────────────────────────────┐
│ .mcp.json                           │
│ (Your existing MCP configuration)   │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ mcp_to_skill.py                     │
│ - Reads .mcp.json                   │
│ - Introspects MCP server            │
│ - Generates Skill structure         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Generated Skill                     │
│ ├── SKILL.md (100 tokens)           │
│ ├── executor.py (dynamic calls)     │
│ └── config files                    │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Claude                              │
│ - Loads metadata only               │
│ - Full docs when needed             │
│ - Calls executor for tools          │
└─────────────────────────────────────┘
```

## Testing Generated Skills

Use the central executor from project root:

```bash
# List tools
python .claude/skills/mcp-skills/executor.py --skill <skill-name> --list

# Describe a tool
python .claude/skills/mcp-skills/executor.py --skill <skill-name> --describe tool_name

# Call a tool
python .claude/skills/mcp-skills/executor.py --skill <skill-name> --call '{"tool": "tool_name", "arguments": {...}}'
```

## Requirements

```bash
pip install mcp
```

Python 3.8+ required.

## Troubleshooting

### "mcp package not found"
```bash
pip install mcp
```

### "Server not found"
Run `--list` to see available server names.

### "Type not supported"
Only `stdio` servers can be converted. HTTP/SSE servers use different protocols.

### "Could not find .mcp.json"
Use `--mcp-json` to specify the path explicitly.

## Credits

Inspired by:
- [playwright-skill](https://github.com/lackeyjb/playwright-skill) by @lackeyjb
- [Anthropic Skills](https://www.anthropic.com/news/skills) framework
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

MIT
