---
title: "Architecture Exploration"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Example: Full Architecture Exploration

This example demonstrates a complete architecture exploration workflow.

---

## Scenario

User asks: "Help me understand how this codebase is structured"

---

## Step 1: Initial Architecture Map

```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Map the high-level architecture of this codebase
Thoroughness: very thorough

ANALYZE:
1. Directory structure - what are the main directories and their purposes?
2. Layer organization - frontend, backend, shared, infrastructure
3. Entry points - where does execution start?
4. Key configuration files

RETURN:
{
  "structure": {
    "directories": [
      {"name": "app/", "purpose": "Frontend Next.js application"},
      {"name": "api/", "purpose": "Backend FastAPI services"}
    ],
    "layers": ["frontend", "backend", "shared"],
    "entry_points": [
      {"file": "api/main.py", "type": "backend"},
      {"file": "app/page.tsx", "type": "frontend"}
    ],
    "config": ["pyproject.toml", "package.json", ".env.example"]
  }
}

MAX OUTPUT: 600 tokens"""
)
```

---

## Step 2: Parallel Layer Deep-Dive

```python
# Launch simultaneously
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Deep-dive into frontend architecture

ANALYZE:
1. Component organization (atomic design? feature-based?)
2. State management (Redux? Context? Zustand?)
3. Routing structure
4. API integration patterns

RETURN:
{
  "layer": "frontend",
  "component_pattern": "...",
  "state_management": "...",
  "routing": "...",
  "api_integration": "..."
}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Deep-dive into backend architecture

ANALYZE:
1. Route organization
2. Service layer structure
3. Database access patterns
4. External integrations

RETURN:
{
  "layer": "backend",
  "route_pattern": "...",
  "services": "...",
  "database": "...",
  "integrations": "..."
}"""
)
```

---

## Step 3: Cross-Cutting Concerns

```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Identify cross-cutting concerns

FIND:
1. Authentication/authorization patterns
2. Error handling approach
3. Logging and monitoring
4. Testing strategy

RETURN:
{
  "auth": {"pattern": "...", "files": [...]},
  "errors": {"pattern": "...", "files": [...]},
  "logging": {"pattern": "...", "files": [...]},
  "testing": {"pattern": "...", "coverage": "..."}
}"""
)
```

---

## Step 4: Aggregate Results

After receiving all exploration results, the orchestrator combines them:

```python
architecture_summary = {
    "overview": initial_map["structure"],
    "frontend": frontend_result,
    "backend": backend_result,
    "cross_cutting": cross_cutting_result,
    "key_insights": [
        "Frontend uses Next.js with App Router",
        "Backend is FastAPI with MCP tool pattern",
        "Authentication via Clerk integration",
        "Testing uses pytest + Jest"
    ]
}
```

---

## Step 5: Targeted Read (Only After Exploration)

Based on exploration findings, read specific key files:

```python
# Only now do we use Read - for specific, targeted files
Read(file_path="api/main.py")  # Identified as key entry point
Read(file_path="app/page.tsx")  # Identified as frontend entry
```

---

## Result

The orchestrator now has:
- Complete architecture understanding (~800 tokens of compressed knowledge)
- Key file paths for targeted reading
- Pattern recognition across layers
- **Main context preserved for implementation work**

---

## Context Usage Comparison

| Approach | Tokens Used | Information Quality |
|----------|-------------|---------------------|
| Direct Glob + Read (10 files) | ~5,000 | Raw, needs parsing |
| Explore agents (4 parallel) | ~800 | Structured, analyzed |

**Savings: 84%**
