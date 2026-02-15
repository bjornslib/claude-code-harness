# Migration Guide: DSPy 1.x/2.0 to DSPy 2.6+

Breaking changes and migration patterns for updating to DSPy 2.6.

## Summary of Changes

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

## LM Configuration

### Before (1.x/2.0)

```python
import dspy

# Per-provider constructors (DEPRECATED)
lm = dspy.OpenAI(model="gpt-4", api_key="...", max_tokens=1000)
lm = dspy.Claude(model="claude-sonnet-4-5-20250929", api_key="...")
lm = dspy.OllamaLocal(model="llama3.1", base_url="http://localhost:11434")
lm = dspy.HFModel(model="meta-llama/Llama-3-8B")

# Old configuration
dspy.settings.configure(lm=lm)

# Old context manager
with dspy.settings.context(lm=other_lm):
    result = module(input=x)

# Old history inspection
lm.inspect_history(n=5)
```

### After (2.6+)

```python
import dspy

# Unified constructor for ALL providers
lm = dspy.LM("openai/gpt-4o-mini", temperature=0.7, max_tokens=1000)
lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=2000)
lm = dspy.LM("ollama_chat/llama3.1", api_base="http://localhost:11434")

# New configuration
dspy.configure(lm=lm)

# New context manager
with dspy.context(lm=other_lm):
    result = module(input=x)

# New history access (property, not method)
print(lm.history)  # List of {prompt, response, usage, ...}

# Token usage tracking (new feature)
dspy.configure(lm=lm, track_usage=True)
result = module(input=x)
print(result.get_lm_usage())  # Token counts per provider

# Caching (enabled by default, disable with)
lm = dspy.LM("openai/gpt-4o-mini", cache=False)
```

### Provider String Format

The `dspy.LM()` constructor uses LiteLLM's provider string format:

| Provider | Format | Example |
|----------|--------|---------|
| OpenAI | `openai/model` | `dspy.LM("openai/gpt-4o-mini")` |
| Anthropic | `anthropic/model` | `dspy.LM("anthropic/claude-sonnet-4-5-20250929")` |
| Ollama | `ollama_chat/model` | `dspy.LM("ollama_chat/llama3.1")` |
| Azure | `azure/deployment` | `dspy.LM("azure/gpt-4")` |
| Google | `gemini/model` | `dspy.LM("gemini/gemini-pro")` |
| Together | `together_ai/model` | `dspy.LM("together_ai/meta-llama/Llama-3-8b")` |
| Anyscale | `anyscale/model` | `dspy.LM("anyscale/meta-llama/Llama-3-8b")` |

## Optimizer Changes

### MIPRO to MIPROv2

```python
# Before (1.x/2.0)
from dspy.teleprompt import MIPRO

optimizer = MIPRO(
    metric=metric,
    num_candidates=10,
    init_temperature=1.0
)
optimized = optimizer.compile(
    student=module,
    trainset=trainset,
    valset=valset,
    num_trials=100
)

# After (2.6+)
# Easy way (recommended)
tp = dspy.MIPROv2(metric=metric, auto="medium")
optimized = tp.compile(module, trainset=trainset)

# Full control
tp = dspy.MIPROv2(
    metric=metric,
    num_candidates=10,
    num_threads=8,
    max_errors=5
)
optimized = tp.compile(
    module,
    trainset=trainset,
    max_bootstrapped_demos=2,
    max_labeled_demos=2,
    num_trials=50
)
```

### MIPROv2 Auto Modes

New in 2.6: `auto` parameter for easy optimization scaling.

| Mode | Trials | Time | Best For |
|------|--------|------|----------|
| `"light"` | ~10-20 | 30s-2min | Quick iteration, prototyping |
| `"medium"` | ~50-100 | 5-15min | Production optimization |
| `"heavy"` | ~200+ | 30min-2hrs | Maximum quality |

### Teacher-Student (New in 2.6)

```python
# New: Use expensive LM to teach cheap LM
teacher = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
student = dspy.LM("openai/gpt-4o-mini")

dspy.configure(lm=student)
tp = dspy.MIPROv2(
    metric=metric,
    auto="medium",
    teacher_settings=dict(lm=teacher),
    prompt_model=teacher
)
optimized = tp.compile(module, trainset=trainset)
```

## Assertions to Refine/BestofN

### Before (1.x/2.0)

```python
import dspy
from dspy.primitives.assertions import assert_transform_module, backtrack_handler

class ValidatedQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.qa = dspy.ChainOfThought("question -> answer: float")

    def forward(self, question):
        answer = self.qa(question=question).answer

        # Assert: if fails, backtracks and retries
        dspy.Assert(
            isinstance(float(answer), float),
            "Answer must be a number",
            backtrack=backtrack_handler
        )
        return dspy.Prediction(answer=answer)

# Also had dspy.Suggest (soft version)
dspy.Suggest(condition, message)
```

### After (2.6+)

```python
import dspy

# Option 1: dspy.Refine (iterative self-refinement)
refine = dspy.Refine(
    dspy.Signature("question -> answer"),
    N=3  # Up to 3 refinement rounds
)
result = refine(question="What is 15% of 80?")

# Option 2: dspy.BestofN (generate N, pick best)
bon = dspy.BestofN(
    dspy.Signature("question -> answer"),
    N=5,
    reward_fn=my_quality_metric
)
result = bon(question="What is 15% of 80?")
```

**Migration guidance:**
- `dspy.Assert` with backtracking → `dspy.Refine` (same iterative improvement concept)
- `dspy.Suggest` (soft guidance) → `dspy.Refine` with low N
- Validation loops → `dspy.BestofN` with quality metric

## Async and Streaming (New in 2.6)

### Async (New)

```python
# No equivalent in 1.x/2.0

# 2.6+: Wrap any module for async
cot = dspy.ChainOfThought("question -> answer")
async_cot = dspy.asyncify(cot)

result = await async_cot(question="What is DSPy?")
```

### Streaming (New)

```python
# No equivalent in 1.x/2.0

# 2.6+: Stream tokens from any module
cot = dspy.ChainOfThought("question -> answer")
stream_cot = dspy.streamify(cot)

for chunk in stream_cot(question="Explain quantum computing"):
    print(chunk, end="")
```

## Per-Call Configuration (New in 2.6)

```python
# No equivalent in 1.x/2.0

# 2.6+: Override config per call
predictor = dspy.Predict("question -> answer")

# Default temperature
result = predictor(question="What is 2+2?")

# Override for this call only
result = predictor(
    question="Write a creative poem",
    config={"temperature": 1.0, "max_tokens": 500}
)
```

## Quick Migration Checklist

1. [ ] Replace `dspy.OpenAI()` / `dspy.Claude()` / etc. with `dspy.LM("provider/model")`
2. [ ] Replace `dspy.settings.configure(lm=lm)` with `dspy.configure(lm=lm)`
3. [ ] Replace `dspy.settings.context(lm=lm)` with `dspy.context(lm=lm)`
4. [ ] Replace `from dspy.teleprompt import MIPRO` with `dspy.MIPROv2`
5. [ ] Replace `dspy.Assert` / `dspy.Suggest` with `dspy.Refine` or `dspy.BestofN`
6. [ ] Replace `lm.inspect_history()` with `lm.history`
7. [ ] Add `track_usage=True` to `dspy.configure()` for token monitoring
8. [ ] Consider `dspy.asyncify()` for web serving
9. [ ] Consider `dspy.streamify()` for chat interfaces
10. [ ] Use `auto="light"` with MIPROv2 as starting optimization

## Backward Compatibility

DSPy 2.6 maintains some backward compatibility:
- `dspy.settings.configure()` still works but is deprecated
- `dspy.Predict`, `dspy.ChainOfThought`, `dspy.ReAct` are unchanged
- `dspy.Module`, `dspy.Signature`, `dspy.Example` are unchanged
- `BootstrapFewShot`, `COPRO`, `BootstrapFinetune` are unchanged
- `dspy.Retrieve` and retriever integrations are unchanged

**Will break in future versions:**
- Per-provider LM constructors (`dspy.OpenAI`, `dspy.Claude`, etc.)
- `dspy.settings.configure()` (use `dspy.configure()`)
- `dspy.Assert` and `dspy.Suggest` (use `dspy.Refine` / `dspy.BestofN`)
- Old MIPRO (use MIPROv2)
