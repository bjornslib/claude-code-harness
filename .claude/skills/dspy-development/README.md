# DSPy — At a Glance

> Personal quick-reference for DSPy (Declarative Language Model Programming).
> For detailed docs, see `SKILL.md` and `references/`.

## What is DSPy?

DSPy is a framework by Stanford NLP for **programming** (not prompting) language models. Instead of writing prompts by hand, you define signatures (input → output contracts), compose modules, and let optimizers automatically find the best prompts, few-shot examples, and even model weights.

**Think of it as**: PyTorch for LM programming. Define your architecture, define your loss function (metric), and let the framework optimize.

## Core Mental Model

```
Signature  →  Module  →  Optimizer  →  Optimized Program
(what)        (how)      (improve)     (deploy)
```

1. **Signature**: What the LM should do (`"question -> answer"`)
2. **Module**: How to do it (`Predict`, `ChainOfThought`, `ReAct`, `RLM`)
3. **Optimizer**: Improve it automatically (`MIPROv2`, `GEPA`, `BootstrapFewShot`)
4. **Program**: Deploy the optimized result (`.save()` / `.load()`)

## Quick Start

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=1000)
dspy.configure(lm=lm)

# Simple prediction
qa = dspy.Predict("question -> answer")
result = qa(question="What is the capital of France?")

# With reasoning
cot = dspy.ChainOfThought("question -> answer")
result = cot(question="If 3x + 7 = 22, what is x?")
print(result.rationale)  # Step-by-step reasoning
print(result.answer)     # "5"
```

## Module Cheat Sheet

| Module | Use When | Key Feature |
|--------|----------|-------------|
| `dspy.Predict` | Simple tasks | Fast, direct |
| `dspy.ChainOfThought` | Complex reasoning | Auto-generates rationale |
| `dspy.ProgramOfThought` | Math, data transforms | Generates + executes code |
| `dspy.ReAct` | Tool-using agents | Think → Act → Observe loop |
| `dspy.RLM` | Documents > context window | Sandboxed Python REPL exploration |
| `dspy.CodeAct` | Dynamic code + tools | Code generation + execution |
| `dspy.TypedPredictor` | Structured output | Returns Pydantic models |
| `dspy.Refine` | Quality-critical output | Iterative self-improvement |
| `dspy.BestofN` | High-stakes decisions | Generate N, pick best |

## Optimizer Cheat Sheet

| Optimizer | Data Needed | Speed | Best For |
|-----------|-------------|-------|----------|
| `BootstrapFewShot` | 10-50 | Fast | First try |
| `dspy.MIPROv2(auto="light")` | 20-50 | Fast | **Default choice** |
| `dspy.MIPROv2(auto="medium")` | 50-200 | Medium | Production |
| `dspy.GEPA` | 20-100 | Medium | Agentic tasks, feedback-rich |
| `dspy.SIMBA` | 20-100 | Medium | Self-reflection tasks |
| `ArborGRPO` | 100+ | Slow | RL weight training |

## Key Patterns

### Custom Module (PyTorch-style)

```python
class RAG(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        passages = self.retrieve(question).passages
        return self.generate(context="\n".join(passages), question=question)
```

### Structured Output

```python
from pydantic import BaseModel, Field

class Person(BaseModel):
    name: str = Field(description="Full name")
    age: int

class Extract(dspy.Signature):
    text = dspy.InputField()
    person: Person = dspy.OutputField()

extractor = dspy.TypedPredictor(Extract)
```

### Optimization Loop

```python
# 1. Define metric
def metric(example, pred, trace=None):
    return example.answer.lower() == pred.answer.lower()

# 2. Optimize
tp = dspy.MIPROv2(metric=metric, auto="light")
optimized = tp.compile(my_module, trainset=trainset)

# 3. Evaluate
from dspy.evaluate import Evaluate
score = Evaluate(devset=testset, metric=metric)(optimized)

# 4. Save
optimized.save("models/v1", save_program=True)
```

### Multi-Modal (3.0+)

```python
class DescribeImage(dspy.Signature):
    image: dspy.Image = dspy.InputField()
    description = dspy.OutputField()

result = dspy.Predict(DescribeImage)(
    image=dspy.Image.from_file("photo.jpg")
)
```

### Long Documents with RLM (3.1+)

```python
rlm = dspy.RLM("context, query -> answer", max_iterations=20)
result = rlm(context=massive_doc, query="What was Q3 revenue?")
# LM writes Python to peek/grep/partition, uses llm_query() for sub-calls
```

### Adapters (3.0+)

```python
dspy.configure(lm=lm, adapter=dspy.ChatAdapter())   # Default
dspy.configure(lm=lm, adapter=dspy.JSONAdapter())    # JSON output
dspy.configure(lm=lm, adapter=dspy.XMLAdapter())     # XML output
```

### Async + Streaming

```python
async_qa = dspy.asyncify(my_module)
result = await async_qa(question="...")

stream_qa = dspy.streamify(my_module)
for chunk in stream_qa(question="..."):
    print(chunk, end="")
```

### Batch Processing (3.0+)

```python
results = my_module.batch(inputs_list, num_threads=8)
```

## Version at a Glance

| Feature | Since |
|---------|-------|
| Unified `dspy.LM()` | 2.6 |
| `MIPROv2`, `asyncify`, `streamify` | 2.6 |
| Adapters, GEPA, SIMBA, ArborGRPO, types | 3.0 |
| `Module.batch`, `CodeAct`, MLflow | 3.0 |
| `dspy.Reasoning`, `dspy.RLM` | 3.1 |

**Current stable**: DSPy 3.1.3 (Feb 2026) | **Python**: 3.10+

## Resources

| Resource | URL |
|----------|-----|
| Docs | https://dspy.ai |
| Learning Path | https://dspy.ai/learn/ |
| GitHub | https://github.com/stanfordnlp/dspy |
| Discord | https://discord.gg/XCGy2WDCQB |
| RLM Paper | arXiv:2512.24601 |

## File Map

```
dspy-development/
├── README.md              ← You are here (quick reference)
├── SKILL.md               ← Core skill with triggers and key patterns
└── references/
    ├── modules.md         ← Complete module API and usage patterns
    ├── optimizers.md      ← All optimizers with metrics and evaluation
    ├── examples.md        ← Production examples (RAG, agents, RLM, etc.)
    └── migration.md       ← Breaking changes across versions
```
