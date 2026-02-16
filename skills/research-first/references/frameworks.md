# Frameworks and Libraries Reference

Complete list of frameworks and libraries that should trigger the research-first skill.

## Frontend

| Framework | context7 ID | Common Queries |
|-----------|-------------|----------------|
| React | `/facebook/react` | hooks, context, state, rendering, effects |
| Next.js | `/vercel/next.js` | app router, server components, API routes, middleware |
| Tailwind CSS | `/tailwindlabs/tailwindcss` | utilities, config, plugins, responsive |
| Zustand | `/pmndrs/zustand` | stores, slices, middleware, persist |
| @assistant-ui | `/assistant-ui/assistant-ui` | chat components, runtime, messages |
| React Query | `/tanstack/query` | queries, mutations, cache, infinite |
| Framer Motion | `/framer/motion` | animations, gestures, layout |
| Radix UI | `/radix-ui/primitives` | primitives, accessibility, composition |
| shadcn/ui | `/shadcn/ui` | components, theming, installation |

## Backend (Python)

| Framework | context7 ID | Common Queries |
|-----------|-------------|----------------|
| FastAPI | `/tiangolo/fastapi` | routes, dependencies, middleware, security |
| PydanticAI | `/pydantic/pydantic-ai` | agents, tools, structured output, streaming |
| pydantic-graph | `/pydantic/pydantic-graph` | workflows, state, nodes, edges |
| LlamaIndex | `/run-llama/llama_index` | indexing, retrieval, agents, tools |
| Pydantic | `/pydantic/pydantic` | models, validation, serialization |
| SQLAlchemy | `/sqlalchemy/sqlalchemy` | ORM, queries, sessions, migrations |
| Alembic | `/sqlalchemy/alembic` | migrations, revisions, autogenerate |
| Celery | `/celery/celery` | tasks, workers, scheduling, results |
| Redis (Python) | `/redis/redis-py` | caching, pubsub, streams |

## Database

| Technology | context7 ID | Common Queries |
|------------|-------------|----------------|
| Supabase | `/supabase/supabase` | auth, realtime, storage, edge functions |
| PostgreSQL | `/postgres/postgres` | queries, indexes, functions, triggers |
| Prisma | `/prisma/prisma` | schema, queries, migrations, relations |
| Drizzle | `/drizzle-team/drizzle-orm` | schema, queries, migrations |

## Voice & Real-Time

| Framework | context7 ID | Common Queries |
|-----------|-------------|----------------|
| LiveKit | `/livekit/livekit` | rooms, tracks, agents, voice |
| LiveKit Agents | `/livekit/agents` | voice agents, STT, TTS, pipelines |
| Twilio | `/twilio/twilio-python` | calls, SMS, webhooks |
| WebRTC | N/A (use Perplexity) | connections, streams, signaling |

## Testing

| Framework | context7 ID | Common Queries |
|-----------|-------------|----------------|
| Pytest | `/pytest-dev/pytest` | fixtures, markers, parametrize, mocking |
| Jest | `/jestjs/jest` | mocks, snapshots, async, coverage |
| Playwright | `/microsoft/playwright` | selectors, actions, assertions, fixtures |
| React Testing Library | `/testing-library/react-testing-library` | queries, events, async |

## Infrastructure & DevOps

| Tool | context7 ID | Common Queries |
|------|-------------|----------------|
| Docker | `/docker/docs` | compose, volumes, networks, build |
| Vercel | `/vercel/vercel` | deployment, environment, edge |
| GitHub Actions | `/actions/toolkit` | workflows, actions, secrets |

## AI & ML

| Framework | context7 ID | Common Queries |
|-----------|-------------|----------------|
| Anthropic SDK | `/anthropic/anthropic-sdk-python` | messages, tools, streaming |
| OpenAI SDK | `/openai/openai-python` | chat, embeddings, assistants |
| LangChain | `/langchain-ai/langchain` | chains, agents, memory, tools |
| FAISS | N/A (use Perplexity) | indexes, search, GPU |
| Transformers | `/huggingface/transformers` | models, tokenizers, pipelines |

## MCP (Model Context Protocol)

| Component | context7 ID | Common Queries |
|-----------|-------------|----------------|
| MCP SDK | `/modelcontextprotocol/sdk` | servers, tools, resources |
| MCP Specification | `/modelcontextprotocol/specification` | protocol, messages, types |

## Trigger Keywords by Category

### Uncertainty Phrases
- "how do I"
- "what's the best way"
- "should I"
- "is this right"
- "is this the correct approach"
- "not sure if"
- "wondering if"
- "would it be better to"

### Implementation Phrases
- "implement"
- "build"
- "create"
- "add feature"
- "set up"
- "configure"
- "integrate"

### Problem Phrases
- "not working"
- "deprecated"
- "version mismatch"
- "breaking change"
- "migration"
- "upgrade"

### Design Phrases
- "architecture"
- "design pattern"
- "best practice"
- "recommended approach"
- "trade-offs"
- "alternatives"

## Version-Sensitive Frameworks

These frameworks have frequent breaking changes. ALWAYS research before using:

| Framework | Why |
|-----------|-----|
| Next.js | App Router vs Pages Router, frequent API changes |
| React | React 18/19 concurrent features, hooks evolution |
| PydanticAI | New framework, rapid development |
| Supabase | Auth v2 changes, realtime updates |
| Tailwind | v3 vs v4 differences |
| LiveKit Agents | Python agents SDK evolving |

## context7 Query Tips

### Resolving Library IDs

```python
# First, resolve the library ID
mcp__context7__resolve-library-id(
    libraryName="next.js",
    query="app router server components"
)
```

### Querying Documentation

```python
# Then query with specific question
mcp__context7__query-docs(
    libraryId="/vercel/next.js",
    query="how to use server actions with forms"
)
```

### Common Query Patterns

| Need | Query Format |
|------|--------------|
| API usage | "[feature] API example" |
| Migration | "migrate from [old] to [new]" |
| Best practice | "[feature] best practices" |
| Troubleshooting | "[error] solution" |
| Configuration | "[feature] configuration options" |
