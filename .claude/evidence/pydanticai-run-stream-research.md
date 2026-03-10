# PydanticAI run_stream() API Research Findings

## Date
March 11, 2026

## Research Query
How to use PydanticAI's `run_stream()` API for streaming responses

## Library ID Used
`/websites/ai_pydantic_dev` (5624 code snippets, Source Reputation: High, Benchmark Score: 80.25)

---

## Key Findings

### 1. Core run_stream() API

The `run_stream()` method is an async context manager that enables streaming AI responses incrementally:

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')

async def main():
    async with agent.run_stream('What is the capital of the UK?') as response:
        print(await response.get_output())
```

**Key characteristics:**
- Must be used as an async context manager (`async with`)
- Returns a `StreamedRunResult` object
- Enables real-time response display for long-running operations

---

### 2. stream_text() Method

Streams text results as an async iterable with two modes:

```python
async with agent.run_stream('What is the capital of the UK?') as response:
    async for text in response.stream_text():
        print(text)
        #> The capital of
        #> The capital of the UK is
        #> The capital of the UK is London.
```

**Parameters:**
- `delta: bool = False` - If `True`, yield each chunk of text as received; if `False` (default), yield cumulative text up to the current point
- `debounce_by: float | None = 0.1` - Group response chunks by this many seconds; `None` means no debouncing

**Important note:** Result validators are NOT called when `delta=True`.

---

### 3. stream_responses() Method

Streams structured LLM messages as an async iterable:

```python
async with agent.run_stream(user_input) as result:
    async for message, last in result.stream_responses(debounce_by=0.01):
        try:
            profile = await result.validate_response_output(
                message,
                allow_partial=not last,
            )
        except ValidationError:
            continue
        print(profile)
```

**Parameters:**
- `debounce_by: float | None = 0.1` - Optional grouping of response chunks

**Returns:** An async iterable of tuples `(ModelResponse, bool)` where the boolean indicates if this is the last message.

**Use case:** Enables processing structured outputs incrementally with debouncing to reduce validation overhead.

---

### 4. Message History Access

The `all_messages()` method provides access to conversation state:

```python
async with agent.run_stream('Tell me a joke.') as result:
    # Incomplete messages before stream finishes
    print(result.all_messages())
    # Shows only ModelRequest before completion

    async for text in result.stream_text():
        print(text)

    # Complete messages after stream finishes
    print(result.all_messages())
    # Shows both ModelRequest and ModelResponse
```

**Before completion:** Only contains the user prompt (ModelRequest)

**After completion:** Contains both request and response (ModelRequest + ModelResponse), including usage statistics and timestamp.

---

### 5. Usage Pattern Summary

| Method | Purpose | When to Use |
|--------|---------|-------------|
| `run_stream()` | Core streaming entry point | Any streaming use case |
| `stream_text()` | Text-only streaming | When you need text chunks |
| `stream_responses()` | Structured message streaming | When you need full ModelResponse objects |
| `all_messages()` | Conversation history | debugging or message tracking |
| `get_output()` | Final result | When you need the complete output |

---

### 6. Debouncing Best Practice

For long structured responses, debouncing is critical to reduce validation overhead:

```python
async with agent.run_stream(user_input) as result:
    async for message, last in result.stream_responses(debounce_by=0.01):
        # Process messages with grouped chunks
        # Reduces validation calls from per-token to per-group
```

Without debouncing, validation runs on every token. With `debounce_by=0.01`, chunks are grouped into 10ms windows.

---

### 7. Complete Example

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o', instructions='Be a helpful assistant.')

async def stream_response(prompt: str) -> str:
    full_text = []
    async with agent.run_stream(prompt) as response:
        async for text in response.stream_text():
            full_text.append(text)
    return ''.join(full_text)

# Usage
result = await stream_response("What is Python?")
```

---

## References

1. [Pydantic AI Agent API](https://ai.pydantic.dev/api/agent)
2. [Pydantic AI Result API](https://ai.pydantic.dev/api/result)
3. [Pydantic AI Examples - Stream Markdown](https://ai.pydantic.dev/examples/stream-markdown)
4. [Pydantic AI - Output Types](https://ai.pydantic.dev/output)
5. [Pydantic AI - Message History](https://ai.pydantic.dev/message-history)

---

## Research Methodology

1. **ToolSearch** - Loaded `context7` MCP tool
2. **Context7 Library ID Resolution** - Queried for `pydantic-ai` library
3. **Documentation Query** - Searched for `run_stream API streaming responses examples`
4. **Secondary Query** - Searched for `stream_text stream_output stream_responses methods`

All queries executed successfully using the `mcp__context7__query-docs` tool.

---

## Hindsight Memory Recall

Prior work recalled from `claude-harness-setup` bank:
- Pipeline processing through voice agent LiveKit, PydanticAI form_filler_agent
- Headless worker(stream-json output for JSONL emitter
- SSE stream to useFormSSE hook flow

This research builds on existing knowledge of PydanticAI use in streaming pipelines.
