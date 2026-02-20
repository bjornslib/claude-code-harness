---
title: "List Commands"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# Project Commands Reference

## Available Slash Commands

### Essential Integration
**`/project:integration/serena-mcp`** - Complete Serena MCP setup and semantic code navigation
- Usage: `/project:integration/serena-mcp [setup|troubleshoot|patterns]`
- Essential for all coding work with semantic analysis

**`/project:integration/o3-pro`** - Advanced O3-Pro workflows and monitoring protocols  
- Usage: `/project:integration/o3-pro [launch|monitor|extract|cleanup]`
- For complex reasoning tasks requiring deep analysis

### Workflow Management
**`/project:workflow/processes`** - Complete development workflows and research protocols
- Usage: `/project:workflow/processes [research|implementation|testing]`
- Comprehensive development discipline patterns

**`/project:workflow/completion-protocol`** - Detailed task completion steps and webhook requirements
- Usage: `/project:workflow/completion-protocol [steps|webhook|validation]` 
- Critical for proper task completion

**`/project:workflow/research-colleagues`** - Perplexity and Brave Search collaboration patterns
- Usage: `/project:workflow/research-colleagues [perplexity|brave|both]`
- Essential research workflows with AI colleagues

### Development Discipline  
**`/project:development/llm-first-architecture`** - LLM-first design principles and anti-patterns
- Usage: `/project:development/llm-first-architecture [principles|patterns|anti-patterns]`
- Core architectural philosophy for agent-centric development

**`/project:development/testing-protocol`** - Comprehensive testing requirements and validation
- Usage: `/project:development/testing-protocol [unit|integration|validation]`
- Complete testing discipline and quality assurance

### Task Management
**`/project:management/task-csv`** - Complete CSV task management commands and workflows
- Usage: `/project:management/task-csv [query|update|create|examples]`
- Master task management with semantic metadata

### Help & Discovery
**`/project:help/quick-reference`** - Common command patterns and shortcuts
- Usage: `/project:help/quick-reference [daily|emergency|patterns]`  
- Quick access to frequently used workflows

## Command Usage Patterns

### Tab Autocomplete
```bash
/project:<TAB>              # Discover all namespaces
/project:integration/<TAB>  # Discover integration commands
/project:workflow/<TAB>     # Discover workflow commands
```

### Command Arguments
```bash
/project:integration/serena-mcp setup     # Setup with specific mode
/project:workflow/research-colleagues both # Research with both colleagues
/project:help/quick-reference daily       # Daily workflow patterns
```

### Command Chaining
```bash
# Research then implement with LLM-first principles
/project:workflow/research-colleagues | /project:development/llm-first-architecture

# Setup Serena then manage tasks
/project:integration/serena-mcp setup | /project:management/task-csv query

# Complete workflow: research → develop → test → complete
/project:workflow/research-colleagues | /project:development/llm-first-architecture | /project:development/testing-protocol | /project:workflow/completion-protocol
```

## Getting Help
- **This command**: `/project:help/list-commands` - Master command reference
- **Quick patterns**: `/project:help/quick-reference` - Common workflows  
- **Tab completion**: Use `<TAB>` after any `/project:` prefix for discovery
- **Command arguments**: Most commands accept arguments for specific modes or focus areas

## Command Development
To add new commands:
1. Create `.md` file in appropriate `.claude/commands/` subdirectory
2. Use clear, descriptive naming with kebab-case
3. Include usage examples and argument descriptions
4. Update this list-commands reference

**🚀 This native slash command system provides modular, discoverable workflows that leverage Claude Code's built-in capabilities.**