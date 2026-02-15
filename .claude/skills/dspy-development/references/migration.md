# DSPy Migration Guide

Breaking changes and migration patterns across major DSPy versions.

## Version Timeline

| Version | Date | Type |
|---------|------|------|
| DSPy 1.x | 2023-2024 | Original release |
| DSPy 2.0 | Mid 2024 | Incremental improvements |
| DSPy 2.6 | Late 2024 | Unified LM API, MIPROv2, async/streaming |
| DSPy 2.6.27 | June 3, 2025 | Last 2.6.x release |
| **DSPy 3.0.0** | **Aug 12, 2025** | **Major release: adapters, new optimizers, types** |
| DSPy 3.0.2 | Sep 2025 | GEPA enhancements, Citations API |
| DSPy 3.0.3 | Oct 2025 | rollout_id for cache bypassing |
| DSPy 3.0.4 | Nov 2025 | OpenAI Responses API |
| **DSPy 3.1.0** | **Jan 6, 2026** | **dspy.Reasoning, File type, Python 3.14** |
| DSPy 3.1.1 | Jan 19, 2026 | dspy.RLM, dspy.Code type |
| DSPy 3.1.2 | Jan 2026 | RLM reliability improvements |
| DSPy 3.1.3 | Feb 2026 | GEPA updates, current stable |

---

## Migration: DSPy 1.x/2.0 → 2.6

### Summary of Changes

| Area | Old (1.x/2.0) | New (2.6+) |
|------|----------------|------------|
| LM Configuration | `dspy.settings.configure(lm=lm)` | `dspy.configure(lm=lm)` |
| LM Constructor | `dspy.OpenAI()`, `dspy.Claude()`, etc. | `dspy.LM("provider/model")` |
| Context Manager | `dspy.settings.context(lm=lm)` | `dspy.context(lm=lm)` |
| MIPRO Optimizer | `from dspy.teleprompt import MIPRO` | `dspy.MIPROv2(auto="light")` |
| Assertions | `dspy.Assert` + `backtrack_handler` | `dspy.Refine` or `dspy.BestofN` |
| Suggestions | `dspy.Suggest` | `dspy.Refine` |
| Async Support | Manual wrapping | `dspy.asyncify(module)` |
| Streaming | Not supported | `dspy.streamify(module)` |
| Usage Tracking | Not available | `dspy.configure(track_usage=True)` |
| LM History | `lm.inspect_history()` | `lm.history` |
| Retriever Config | `dspy.settings.configure(rm=rm)` | `dspy.configure(rm=rm)` |

### LM Configuration

```python
# Before (1.x/2.0)
lm = dspy.OpenAI(model="gpt-4", api_key="...", max_tokens=1000)
lm = dspy.Claude(model="claude-sonnet-4-5-20250929", api_key="...")
dspy.settings.configure(lm=lm)

# After (2.6+)
lm = dspy.LM("openai/gpt-4o-mini", temperature=0.7, max_tokens=1000)
lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=2000)
dspy.configure(lm=lm)
```

### Provider String Format

| Provider | Format | Example |
|----------|--------|---------|
| OpenAI | `openai/model` | `dspy.LM("openai/gpt-4o-mini")` |
| Anthropic | `anthropic/model` | `dspy.LM("anthropic/claude-sonnet-4-5-20250929")` |
| Ollama | `ollama_chat/model` | `dspy.LM("ollama_chat/llama3.1")` |
| Azure | `azure/deployment` | `dspy.LM("azure/gpt-4")` |
| Google | `gemini/model` | `dspy.LM("gemini/gemini-pro")` |
| Together | `together_ai/model` | `dspy.LM("together_ai/meta-llama/Llama-3-8b")` |

### Assertions → Refine/BestofN

```python
# Before (1.x/2.0)
dspy.Assert(condition, "message", backtrack=backtrack_handler)
dspy.Suggest(condition, message)

# After (2.6+)
refine = dspy.Refine(signature, N=3)   # Iterative self-refinement
bon = dspy.BestofN(signature, N=5, reward_fn=metric)  # Generate N, pick best
```

### Quick Migration Checklist (1.x/2.0 → 2.6)

1. [ ] Replace `dspy.OpenAI()` / `dspy.Claude()` with `dspy.LM("provider/model")`
2. [ ] Replace `dspy.settings.configure()` with `dspy.configure()`
3. [ ] Replace `dspy.settings.context()` with `dspy.context()`
4. [ ] Replace `MIPRO` with `dspy.MIPROv2`
5. [ ] Replace `dspy.Assert` / `dspy.Suggest` with `dspy.Refine` or `dspy.BestofN`
6. [ ] Replace `lm.inspect_history()` with `lm.history`
7. [ ] Add `track_usage=True` for token monitoring
8. [ ] Consider `dspy.asyncify()` for web serving
9. [ ] Consider `dspy.streamify()` for chat interfaces

---

## Migration: DSPy 2.6 → 3.0

### Breaking Changes

| Change | Details | Migration |
|--------|---------|-----------|
| **Python 3.9 dropped** | Requires 3.10+ | Upgrade Python |
| **Community retrievers removed** | External retriever integrations removed | Use custom code, Tool, or MCP integrations |
| **`dspy.Program` alias removed** | Was an alias for `dspy.Module` | Replace with `dspy.Module` |
| **Deprecated LiteLLM caching removed** | Internal caching change | Use DSPy's built-in `cache=True` on `dspy.LM()` |
| **`BaseType` renamed** | Internal type renamed to `Type` | Replace `BaseType` with `Type` |
| **Thread-safe configuration** | `dspy.configure()` has ownership model | Only first thread calls `dspy.configure()`; others use `dspy.context()` |

### New Features in 3.0

#### Adapters

Control output formatting for LM calls:

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")

# ChatAdapter (default) — field-based with [[ ## markers ]]
dspy.configure(lm=lm, adapter=dspy.ChatAdapter())

# JSONAdapter — structured JSON output
dspy.configure(lm=lm, adapter=dspy.JSONAdapter())

# XMLAdapter — XML formatting
dspy.configure(lm=lm, adapter=dspy.XMLAdapter())

# BAMLAdapter — BAML integration
dspy.configure(lm=lm, adapter=dspy.BAMLAdapter())

# Native function calling (provider-specific structured outputs)
dspy.configure(lm=lm, adapter=dspy.ChatAdapter(use_native_function_calling=True))

# Inspect what adapter sends to LM
messages = dspy.ChatAdapter().format(signature, demos, inputs)
```

#### Types System

New types for multi-modal and specialized I/O:

```python
import dspy

# Multi-modal types
class DescribeImage(dspy.Signature):
    image: dspy.Image = dspy.InputField()
    description = dspy.OutputField()

class TranscribeAudio(dspy.Signature):
    audio: dspy.Audio = dspy.InputField()
    transcript = dspy.OutputField()

# Specialized types
class AgentTask(dspy.Signature):
    task = dspy.InputField()
    history: dspy.History = dspy.InputField()        # Conversation history
    tool_calls: dspy.ToolCalls = dspy.OutputField()  # Tool invocations

# Load multi-modal inputs
img = dspy.Image.from_url("https://example.com/photo.jpg")
img = dspy.Image.from_file("local_photo.png")
audio = dspy.Audio.from_file("recording.mp3")
```

#### New Optimizers

```python
# GEPA — Reflective prompt evolution
optimizer = dspy.GEPA(metric=metric, auto="light", num_threads=32)

# SIMBA — Self-reflection optimization
optimizer = dspy.SIMBA(metric=metric, auto="light")

# ArborGRPO — RL-based weight training (requires Arbor)
from arbor import ArborProvider
optimizer = ArborGRPO(metric=metric, num_threads=8)
```

#### Module.batch (Thread-Safe)

```python
results = my_module.batch(
    inputs_list,
    num_threads=8,
    return_failed_examples=True,
    max_errors=5
)
```

#### CodeAct Module

```python
processor = dspy.CodeAct(signature, tools=[tool1, tool2])
```

#### Stable Save/Load

```python
# Save with full metadata (guaranteed 3.x forward compatibility)
optimized.save("models/my_model", save_program=True)

# Load
loaded = dspy.ChainOfThought("question -> answer")
loaded.load("models/my_model.json")
```

#### MLflow Integration

```python
import mlflow
mlflow.dspy.autolog()  # Automatic tracking of DSPy programs
```

### Quick Migration Checklist (2.6 → 3.0)

1. [ ] Upgrade Python to 3.10+
2. [ ] Replace `dspy.Program` with `dspy.Module`
3. [ ] Replace `BaseType` with `Type` (if used internally)
4. [ ] Replace community retrievers with custom code or MCP/Tool integrations
5. [ ] Review thread safety — ensure `dspy.configure()` called from main thread only
6. [ ] Install Deno if using `ProgramOfThought`, `RLM`, or `CodeAct`
7. [ ] Consider adding adapters for better output control
8. [ ] Consider multi-modal types for image/audio tasks
9. [ ] Use `save_program=True` for guaranteed save compatibility
10. [ ] Try GEPA optimizer for agentic or feedback-rich tasks

---

## Migration: DSPy 3.0 → 3.1

### New Features (No Breaking Changes)

| Feature | Version | Description |
|---------|---------|-------------|
| `dspy.Reasoning` | 3.1.0 | Type for native reasoning model outputs (o1, o3) |
| `dspy.File` | 3.1.0 | Type for file attachments |
| `dspy.RLM` | 3.1.1 | Recursive Language Model for long-context processing |
| `dspy.Code` | 3.1.1 | Type for code blocks |
| Python 3.14 support | 3.1.0 | Official compatibility |

### Using dspy.Reasoning (3.1+)

```python
import dspy

lm = dspy.LM("openai/o3-mini")
dspy.configure(lm=lm)

class MathSolver(dspy.Signature):
    problem = dspy.InputField()
    reasoning: dspy.Reasoning = dspy.InputField()  # Native CoT from reasoning models
    answer = dspy.OutputField()

solver = dspy.Predict(MathSolver)
result = solver(problem="Find all primes p where p^2 + 2 is also prime")
```

### Using dspy.RLM (3.1.1+)

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

# Requires Deno runtime for sandboxed code execution
rlm = dspy.RLM(
    "context, query -> answer",
    max_iterations=20,
    max_llm_calls=10,
    max_output_chars=50000
)

result = rlm(context=massive_document, query="What was Q3 revenue?")
```

---

## Backward Compatibility Summary

### Still Works in 3.x (from 2.6)

- `dspy.configure()` and `dspy.context()` — unchanged
- `dspy.Predict`, `dspy.ChainOfThought`, `dspy.ReAct` — unchanged
- `dspy.Module`, `dspy.Signature`, `dspy.Example` — unchanged
- `BootstrapFewShot`, `COPRO`, `BootstrapFinetune` — unchanged
- `dspy.MIPROv2` — enhanced but backward compatible
- `dspy.Refine`, `dspy.BestofN` — unchanged
- `dspy.asyncify()`, `dspy.streamify()` — unchanged
- `dspy.Retrieve` — unchanged (but community integrations removed)

### Deprecated (Works but Will Break)

- Per-provider LM constructors (`dspy.OpenAI`, `dspy.Claude`) — use `dspy.LM()`
- `dspy.settings.configure()` — use `dspy.configure()`
- Old MIPRO — use MIPROv2
- `dspy.Assert` / `dspy.Suggest` — use `dspy.Refine` / `dspy.BestofN`

### Removed in 3.0

- `dspy.Program` alias — use `dspy.Module`
- Community retrievers — use custom code or MCP
- Deprecated LiteLLM caching — use `cache=True` on `dspy.LM()`
- Python 3.9 support — requires 3.10+
- `BaseType` — renamed to `Type`
