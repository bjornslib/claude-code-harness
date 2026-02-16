#!/bin/bash
# SessionStart hook: Load MCP Skills Registry into context
# This provides 90%+ context savings compared to native MCP loading

# Get the project directory (where .claude/ lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SKILLS_REGISTRY="$PROJECT_DIR/.claude/skills/mcp-skills/SKILL.md"

# Read stdin (hook receives JSON with session info)
input=$(cat)

# Check if the registry exists
if [[ -f "$SKILLS_REGISTRY" ]]; then
  # Output the registry content as additional context
  cat "$SKILLS_REGISTRY"
else
  echo "MCP Skills Registry not found at: $SKILLS_REGISTRY"
fi
