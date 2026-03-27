---
title: "Install CoBuilder Harness Plugin"
status: active
type: command
last_verified: 2026-03-22
grade: reference
---

# Install CoBuilder Harness Plugin

Walk the user through installing CoBuilder step-by-step using AskUserQuestion. Do NOT just display instructions — guide them interactively.

## Step 1: Install Mode

Ask the user how they want to install:

```
AskUserQuestion({
  questions: [{
    question: "How would you like to install CoBuilder?",
    header: "Install mode",
    multiSelect: false,
    options: [
      {
        label: "Plugin marketplace (Recommended)",
        description: "Install from the bjornslib marketplace. Best for using CoBuilder in your projects."
      },
      {
        label: "Local development",
        description: "Clone the repo and load directly. Best for contributing to CoBuilder itself."
      }
    ]
  }]
})
```

## Step 2a: Marketplace Install

If the user chose marketplace:

1. Ask about scope:

```
AskUserQuestion({
  questions: [{
    question: "What scope should the plugin be installed with?",
    header: "Scope",
    multiSelect: false,
    options: [
      {
        label: "Project (Recommended)",
        description: "Shared with your team via .claude/settings.json. Checked into version control."
      },
      {
        label: "User",
        description: "Personal install across all your projects. Not shared with team."
      },
      {
        label: "Local",
        description: "Project-only, gitignored. Good for trying it out without committing."
      }
    ]
  }]
})
```

2. Run the marketplace add command:
```bash
claude plugin marketplace add bjornslib/cobuilder-harness
```

3. Run the install command with the chosen scope:
```bash
claude plugin install cobuilder-harness@bjornslib-cobuilder --scope <chosen-scope>
```

4. Proceed to Step 3.

## Step 2b: Local Development Install

If the user chose local development:

1. Ask where the harness is cloned (or should be cloned):

```
AskUserQuestion({
  questions: [{
    question: "Where is (or should) the cobuilder-harness repo be cloned?",
    header: "Harness path",
    multiSelect: false,
    options: [
      {
        label: "~/cobuilder-harness",
        description: "Default location. Will clone here if it doesn't exist."
      },
      {
        label: "Current directory",
        description: "The harness repo is the current working directory."
      }
    ]
  }]
})
```

2. If not yet cloned, run:
```bash
git clone https://github.com/bjornslib/claude-code-harness.git <chosen-path>
```

3. Install the Python package in editable mode:
```bash
pip install -e <chosen-path>
```

4. Tell the user to restart Claude Code with:
```bash
claude --plugin-dir <chosen-path>
```

5. Proceed to Step 3.

## Step 3: Pipeline Engine Setup

Ask about LLM provider configuration:

```
AskUserQuestion({
  questions: [{
    question: "Which LLM providers do you want to configure for pipeline execution?",
    header: "LLM providers",
    multiSelect: true,
    options: [
      {
        label: "DashScope (Recommended)",
        description: "Near-zero cost via Alibaba Cloud. GLM-5 and Qwen3 models. Best for development."
      },
      {
        label: "Anthropic API",
        description: "Haiku, Sonnet, Opus. Higher quality, higher cost. Needs ANTHROPIC_API_KEY."
      },
      {
        label: "Skip for now",
        description: "Configure later. Pipeline runner won't work until providers are set up."
      }
    ]
  }]
})
```

If they chose providers (not skip):
1. Copy the env example: `cp cobuilder/engine/.env.example cobuilder/engine/.env`
2. Tell them which keys to add based on their selection:
   - DashScope: `DASHSCOPE_API_KEY`
   - Anthropic: `ANTHROPIC_API_KEY`
3. Remind them to edit the file with their actual keys.

## Step 4: MCP Servers (Optional)

```
AskUserQuestion({
  questions: [{
    question: "Do you want to set up MCP server integrations? (Perplexity for research, Hindsight for memory, etc.)",
    header: "MCP setup",
    multiSelect: false,
    options: [
      {
        label: "Yes, copy template",
        description: "Copy .mcp.json.example to your project. You'll fill in API keys for each server you want."
      },
      {
        label: "Skip for now",
        description: "MCP servers are optional. Core pipeline execution works without them."
      }
    ]
  }]
})
```

If yes: `cp .mcp.json.example .mcp.json` and tell them which keys are needed.

## Step 5: Create Runtime Directories

Run automatically (no user input needed):
```bash
mkdir -p .pipelines/pipelines/signals .pipelines/pipelines/evidence
```

## Step 6: Verify

Run `/plugin` to confirm the plugin is loaded, then tell the user:

- What skills are now available (mention key ones: `cobuilder-guardian`, `research-first`, `acceptance-test-writer`)
- How to run their first pipeline: `python3 cobuilder/engine/pipeline_runner.py --dot-file <path>`
- How to get started: "Tell me what you want to build" triggers the ideation-to-execution workflow

Congratulate them on completing setup.
