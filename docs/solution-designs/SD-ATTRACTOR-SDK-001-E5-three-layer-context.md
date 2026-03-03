# SD-ATTRACTOR-SDK-001-E5: Three-Layer Context Injection

**PRD**: GAP-PRD-ATTRACTOR-SDK-001
**Epic**: 5 — Three-Layer Context Injection
**Priority**: P2 (optimization on top of stable SDK pipeline)
**Depends on**: Epic 4 (stable SDK pipeline)
**Design Influence**: [Gastown Three-Layer Context Pattern](../references/gastown-comparison.md#priority-3-three-layer-context-injection)

---

## 1. Problem

Workers currently receive context as a single prompt blob — role identity, task details, acceptance criteria, and SD content are all mixed into one `system_prompt` + `prompt` construction. This creates:

1. **Prompt caching inefficiency**: Anthropic caches identical system prompts (~90% cost reduction). But since our system_prompt includes per-node task details, it changes every node, breaking the cache.
2. **Role/task entanglement**: Changing implementation rules (role) requires editing the same code that constructs task context. These concerns should be separate.
3. **No reuse of existing agent definitions**: We already define specialist agents in `.claude/agents/` (backend-solutions-engineer, frontend-dev-expert, etc.) but `worker_backend.py` hardcodes its own persona strings — duplicating definitions.
4. **Token waste on identity**: Node ID, pipeline ID, runner ID are passed in the prompt, consuming context tokens. These could be zero-cost env vars.

## 2. Design

### 2.1 Three-Layer Model

```
Layer 1: ROLE (What kind of agent am I?)
  → Source: .claude/agents/{worker_type}.md
  → Delivery: ClaudeAgentOptions(system_prompt=...)
  → Stability: Same across ALL nodes of this worker type → prompt caching
  → Content: Persona, behavioral rules, tool constraints

Layer 1.5: SKILLS DIGEST (What patterns should I follow?)
  → Source: Pre-computed from .claude/skills/*/SKILL.md (filtered per worker type)
  → Delivery: Appended to system_prompt (after role definition)
  → Stability: Same across ALL nodes of this worker type → prompt caching
  → Content: Relevant skill patterns, workflow guides, best practices
  → Why: setting_sources=None disables the Skill tool. Skills are orchestration-level
    tools, but workers still need the PATTERNS those skills encode. The runner
    pre-computes a digest of relevant skills and injects it into the system_prompt.

Layer 2: TASK (What should I do right now?)
  → Source: DOT node attributes + SD document
  → Delivery: query(prompt=...) parameter
  → Stability: Changes per node
  → Content: Acceptance criteria, SD section, target directory, Seance context

Layer 3: IDENTITY (Which specific instance am I?)
  → Source: Pipeline runtime state
  → Delivery: ClaudeAgentOptions(env={...})
  → Stability: Changes per spawn
  → Content: WORKER_NODE_ID, PIPELINE_ID, RUNNER_ID, PRD_REF
  → Cost: Zero context tokens — env vars are invisible to the model
```

### 2.2 Leveraging Existing Agent Definitions

The `.claude/agents/` directory already contains specialist agent definitions. Instead of hardcoding `WORKER_ROLES` in `worker_backend.py`, read from these files:

```python
import os
from pathlib import Path

AGENTS_DIR = Path(".claude/agents")

def load_worker_role(worker_type: str) -> str:
    """Load role definition from existing .claude/agents/ definitions.

    Falls back to a minimal default if the agent file doesn't exist.
    The agent .md file content becomes the system_prompt — stable per
    worker type, enabling Anthropic prompt caching.
    """
    agent_file = AGENTS_DIR / f"{worker_type}.md"
    if agent_file.exists():
        content = agent_file.read_text()
        # Strip frontmatter if present
        if content.startswith("---"):
            _, _, content = content.partition("---")[2].partition("---")
        return content.strip()

    # Fallback for unknown types
    return (
        f"You are a specialist agent ({worker_type}). "
        "You implement features directly — no delegation or orchestration."
    )
```

**Benefits**:
- Single source of truth for agent personas
- Agent definitions are version-controlled and reviewed
- Changes to agent behavior propagate to all pipeline workers automatically
- No code change needed to add new worker types — just add `.claude/agents/new-type.md`

### 2.3 Skills Digest (Layer 1.5)

Workers run with `setting_sources=None`, which disables the `Skill` tool entirely — `.claude/skills/` files are not discovered. However, workers still need the **patterns** encoded in skills (research workflows, testing discipline, design rules, etc.).

The Skills Digest solves this by pre-computing relevant skill content at spawn time:

```python
SKILLS_DIR = Path(".claude/skills")

# Worker type → list of skill directories to include in digest
WORKER_SKILL_DIGESTS: dict[str, list[str]] = {
    "backend-solutions-engineer": [
        "research-first",           # Framework research patterns
        "dspy-development",         # DSPy module patterns (if applicable)
    ],
    "frontend-dev-expert": [
        "react-best-practices",     # React/Next.js performance rules
        "frontend-design",          # UI design quality standards
        "design-to-code",           # Mockup-to-component translation
    ],
    "tdd-test-engineer": [
        "test-driven-development",  # TDD discipline (red/green/refactor)
    ],
    "validation-reviewer": [
        "acceptance-test-runner",   # Acceptance test execution patterns
    ],
}


def build_skills_digest(worker_type: str) -> str:
    """Pre-compute skill content for a worker type (Layer 1.5).

    Reads relevant SKILL.md files and concatenates them into a digest
    that is appended to the system_prompt. This gives workers access
    to skill patterns without requiring the Skill tool or filesystem
    settings.

    The digest is stable per worker type → benefits from prompt caching.
    """
    skill_names = WORKER_SKILL_DIGESTS.get(worker_type, [])
    if not skill_names:
        return ""

    sections = []
    for skill_name in skill_names:
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text()
            # Strip frontmatter
            if content.startswith("---"):
                _, _, content = content.partition("---")[2].partition("---")
            sections.append(
                f"## Skill: {skill_name}\n\n{content.strip()}"
            )

    if not sections:
        return ""

    return (
        "\n\n# SKILLS DIGEST\n"
        "The following skill patterns are pre-loaded for your worker type. "
        "Follow these patterns during implementation.\n\n"
        + "\n\n---\n\n".join(sections)
    )
```

**Why this works**:
- Workers get the exact same skill guidance that orchestrator-level agents use
- No filesystem dependency at runtime — content is pre-computed
- No hook/plugin/MCP leakage from `setting_sources`
- Stable per worker type → prompt caching still applies (Layer 1 + 1.5 together)
- Runner/guardian (which HAS full skill access) does the pre-computation

**Why not `setting_sources=["project"]`?**
Loading project settings gives workers skills BUT also inherits:
- Stop gate hooks (would block normal worker completion)
- Orchestrator-detector hooks (would confuse worker identity)
- All MCP servers from `.mcp.json` (5K-12K token overhead)
- Output styles (would override worker's focused persona)
- Plugins (beads, code-review — unnecessary for leaf workers)

There is no selective "load just skills" option in the SDK.

### 2.4 MCP Tool Configuration per Worker Type

Extend the existing `WORKER_MCP_SERVERS` config (from E1) into a central registry:

```python
# worker_config.py — central worker type configuration

@dataclass
class WorkerTypeConfig:
    """Configuration for a worker type."""
    role_source: str  # Path to .claude/agents/{type}.md
    allowed_tools: list[str]
    mcp_servers: dict[str, dict]
    default_model: str = "claude-sonnet-4-6"
    max_turns: int = 100
    timeout_seconds: int = 1800

WORKER_CONFIGS: dict[str, WorkerTypeConfig] = {
    "backend-solutions-engineer": WorkerTypeConfig(
        role_source=".claude/agents/backend-solutions-engineer.md",
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
        mcp_servers={
            "serena": {"command": "serena-mcp", "args": []},
            "context7": {"command": "npx", "args": ["-y", "@context7/mcp"]},
            "perplexity": {"command": "npx", "args": ["-y", "server-perplexity-ask"]},
            "brave-search": {"command": "npx", "args": ["-y", "@anthropic/mcp-brave-search"]},
        },
    ),
    "frontend-dev-expert": WorkerTypeConfig(
        role_source=".claude/agents/frontend-dev-expert.md",
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
        mcp_servers={
            "serena": {"command": "serena-mcp", "args": []},
            "context7": {"command": "npx", "args": ["-y", "@context7/mcp"]},
        },
    ),
    "tdd-test-engineer": WorkerTypeConfig(
        role_source=".claude/agents/tdd-test-engineer.md",
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        mcp_servers={
            "serena": {"command": "serena-mcp", "args": []},
            "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
        },
    ),
    "validation-reviewer": WorkerTypeConfig(
        role_source=".claude/agents/validation-reviewer.md",
        allowed_tools=["Read", "Bash", "Glob", "Grep"],  # NO Edit/Write
        mcp_servers={
            "serena": {"command": "serena-mcp", "args": []},
            "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
        },
        max_turns=60,
        timeout_seconds=300,
    ),
}
```

### 2.4 Updated spawn_worker_sdk()

```python
async def spawn_worker_sdk(
    node_id: str,
    worker_type: str,
    task_prompt: str,  # Layer 2: TASK (per-node)
    target_dir: str,
    pipeline_id: str = "",
    runner_id: str = "",
    prd_ref: str = "",
    additional_context: str = "",  # Seance context (E4)
) -> WorkerResult:
    """Spawn worker with three-layer context injection + skills digest."""

    config = WORKER_CONFIGS.get(worker_type, WORKER_CONFIGS["backend-solutions-engineer"])

    # Layer 1: ROLE — stable per worker type (prompt caching)
    role_content = load_worker_role(worker_type)

    # Layer 1.5: SKILLS DIGEST — pre-computed skill patterns (also stable per type)
    skills_digest = build_skills_digest(worker_type)

    # Combined system_prompt: ROLE + SKILLS DIGEST (stable per worker type → cached)
    system_prompt = role_content + skills_digest

    # Layer 3: IDENTITY — zero token cost
    identity_env = {
        "WORKER_NODE_ID": node_id,
        "PIPELINE_ID": pipeline_id,
        "RUNNER_ID": runner_id,
        "PRD_REF": prd_ref,
    }
    clean_env = {
        k: v for k, v in os.environ.items()
        if k not in ("CLAUDECODE", "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
    }
    clean_env.update(identity_env)

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,       # Layer 1: ROLE
        allowed_tools=config.allowed_tools,
        permission_mode="bypassPermissions",
        model=config.default_model,
        cwd=str(target_dir),
        max_turns=config.max_turns,
        setting_sources=None,
        mcp_servers=config.mcp_servers,
        env=clean_env,                     # Layer 3: IDENTITY
    )

    # Layer 2: TASK — per-node context in prompt parameter
    full_prompt = task_prompt
    if additional_context:
        full_prompt += f"\n\n{additional_context}"

    # ... rest of spawn logic (same as E1)
```

## 3. Testing

- **Unit test**: `load_worker_role()` reads from `.claude/agents/` correctly
- **Unit test**: `load_worker_role()` strips frontmatter
- **Unit test**: `load_worker_role()` falls back for unknown types
- **Unit test**: Identity env vars are set in `ClaudeAgentOptions.env`
- **Unit test**: System prompt is identical across nodes of same type (caching)
- **Integration test**: Worker spawned with three-layer context completes successfully
- **Cost test**: Compare token usage with vs without prompt caching (same system_prompt)

## 4. Files Changed

| File | Change |
|------|--------|
| `worker_backend.py` | Replace hardcoded `WORKER_ROLES` with `load_worker_role()` from `.claude/agents/` |
| `worker_config.py` | **NEW** — Central `WorkerTypeConfig` registry |
| `spawn_runner.py` | Pass identity env vars (node_id, pipeline_id, runner_id) |
| `.claude/agents/validation-reviewer.md` | **NEW** — Validation worker agent definition (moved from E4 inline) |
| `tests/test_worker_config.py` | **NEW** — unit tests |

## 5. Open Questions

1. **Should workers read their own identity from env vars?** Workers could use `os.environ["WORKER_NODE_ID"]` for logging and signal writing instead of receiving it in the prompt. This saves tokens but requires workers to know about the env var convention. Recommendation: yes, use env vars for identity — it's a stable, zero-cost channel.

2. **How much of .claude/agents/*.md should be the system_prompt?** Some agent definitions include tool examples, common patterns, and contextual guidance that may not be relevant for pipeline workers. Consider a `## Pipeline Worker Role` section in each agent file that is extracted as the system_prompt, with the rest available for reference. Alternatively, keep it simple: the entire file is the system_prompt.

3. **Should this epic also formalize the MCP research task?** AC-1.8 (E1) requires researching MCP tool needs per worker type. E5 could be where the research results are formalized into `WORKER_CONFIGS`. Recommendation: E1 does initial research and populates a minimal config; E5 formalizes it into the registry pattern.
