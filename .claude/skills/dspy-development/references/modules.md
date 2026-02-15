# DSPy Modules (DSPy 2.6+)

Complete guide to DSPy's built-in modules for language model programming.

## Module Basics

DSPy modules are composable building blocks inspired by PyTorch's NN modules:
- Have learnable parameters (prompts, few-shot examples)
- Can be composed using Python control flow
- Generalized to handle any signature
- Optimizable with DSPy optimizers

### Base Module Pattern

```python
import dspy

class CustomModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict("input -> output")

    def forward(self, input):
        result = self.predictor(input=input)
        return result
```

## Core Modules

### dspy.Predict

**Basic prediction module** - Makes LM calls without reasoning steps.

```python
import dspy

# Configure LM (DSPy 2.6 unified API)
lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Inline signature
qa = dspy.Predict("question -> answer")
result = qa(question="What is 2+2?")

# Class signature
class QA(dspy.Signature):
    """Answer questions concisely."""
    question = dspy.InputField()
    answer = dspy.OutputField(desc="short, factual answer")

qa = dspy.Predict(QA)
result = qa(question="What is the capital of France?")
print(result.answer)  # "Paris"

# Per-call config override
result = qa(question="Explain gravity", config={"temperature": 0.7})
```

**When to use:**
- Simple, direct predictions
- No reasoning steps needed
- Fast responses required

### dspy.ChainOfThought

**Step-by-step reasoning** - Generates rationale before answer.

**Parameters:**
- `signature`: Task signature
- `rationale_field`: Custom reasoning field (optional)

```python
# Basic usage
cot = dspy.ChainOfThought("question -> answer")
result = cot(question="If I have 5 apples and give away 2, how many remain?")
print(result.rationale)  # "Let's think step by step..."
print(result.answer)     # "3"

# Custom rationale field
cot = dspy.ChainOfThought(
    signature="problem -> solution",
    rationale_field=dspy.OutputField(
        prefix="Reasoning: Let's break this down step by step to"
    )
)
```

**When to use:**
- Complex reasoning tasks
- Math word problems
- Logical deduction
- Quality > speed

**Performance:**
- ~2x slower than Predict
- Significantly better accuracy on reasoning tasks

### dspy.ProgramOfThought

**Code-based reasoning** - Generates and executes Python code.

```python
pot = dspy.ProgramOfThought("question -> answer")

result = pot(question="What is 15% of 240?")
# Internally generates: answer = 240 * 0.15
print(result.answer)  # 36.0

result = pot(question="If a train travels 60 mph for 2.5 hours, how far does it go?")
# Generates: distance = 60 * 2.5
print(result.answer)  # 150.0
```

**When to use:**
- Arithmetic calculations
- Symbolic math
- Data transformations
- Deterministic computations

### dspy.ReAct

**Reasoning + Acting** - Agent that uses tools iteratively.

```python
# Define tools
def search_wikipedia(query: str) -> str:
    """Search Wikipedia for information."""
    return search_results

def calculate(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression, {"__builtins__": {}}, {})

# Create ReAct agent
class ResearchQA(dspy.Signature):
    """Answer questions using available tools."""
    question = dspy.InputField()
    answer = dspy.OutputField()

react = dspy.ReAct(ResearchQA, tools=[search_wikipedia, calculate])

# Agent decides which tools to use
result = react(question="How old was Einstein when he published special relativity?")
# 1. Thinks: "Need birth year and publication year"
# 2. Acts: search_wikipedia("Albert Einstein")
# 3. Acts: calculate("1905 - 1879")
# 4. Returns: "26 years old"
```

**When to use:**
- Multi-step research tasks
- Tool-using agents
- Complex information retrieval
- Tasks requiring multiple API calls

**Best practices:**
- Keep tool descriptions clear and specific
- Limit to 5-7 tools (too many = confusion)
- Provide tool usage examples in docstrings

### dspy.MultiChainComparison

**Generate multiple outputs and compare** - Self-consistency pattern.

```python
mcc = dspy.MultiChainComparison("question -> answer", M=5)

result = mcc(question="What is the capital of France?")
# Generates 5 candidate answers, compares and selects most consistent
print(result.answer)  # "Paris"
```

**Parameters:**
- `M`: Number of candidates to generate (default: 5)
- `temperature`: Sampling temperature for diversity

**When to use:**
- High-stakes decisions
- Ambiguous questions
- When single answer may be unreliable

## DSPy 2.6+ Modules

### dspy.Refine

**Iterative self-refinement** - Generates an initial output, then iteratively improves it. Replaces the old `dspy.Assert` / `dspy.Suggest` pattern for quality enforcement.

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

class WriteEmail(dspy.Signature):
    """Write a professional email."""
    topic = dspy.InputField()
    email = dspy.OutputField(desc="professional, concise email")

# Refine generates, then iteratively improves
refine = dspy.Refine(WriteEmail, N=3)  # Up to 3 refinement rounds

result = refine(topic="Request for project status update")
print(result.email)
# Output is iteratively refined for quality
```

**Parameters:**
- `signature`: Task signature
- `N`: Maximum refinement iterations (default: 3)

**When to use:**
- Quality-critical outputs (emails, reports, code)
- Tasks where first-pass output needs polishing
- When you want self-improvement without manual assertions

**Replaces:**
- `dspy.Assert` + `backtrack_handler` (deprecated in 2.6)
- Manual retry loops with quality checks

### dspy.BestofN

**N-sample selection** - Generates N candidates and selects the best one using a reward model or metric.

```python
import dspy

class SolveTask(dspy.Signature):
    """Solve a complex reasoning task."""
    problem = dspy.InputField()
    solution = dspy.OutputField(desc="detailed solution")

# Generate 5 candidates, select best
bon = dspy.BestofN(SolveTask, N=5, reward_fn=my_quality_metric)

result = bon(problem="Design an algorithm for...")
print(result.solution)
# Best of 5 generated solutions
```

**Parameters:**
- `signature`: Task signature
- `N`: Number of candidates to generate
- `reward_fn`: Function to score candidates (optional)

**When to use:**
- High-stakes decisions requiring best output
- Tasks with measurable quality (metrics available)
- When single-attempt success rate is low

### dspy.asyncify

**Async wrapping** - Convert any synchronous DSPy module to async.

```python
import dspy
import asyncio

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

cot = dspy.ChainOfThought("question -> answer")

# Wrap for async usage
async_cot = dspy.asyncify(cot)

# Use in async context
async def main():
    result = await async_cot(question="What is DSPy?")
    print(result.answer)

asyncio.run(main())

# Parallel async calls
async def parallel_queries():
    questions = ["What is Python?", "What is Rust?", "What is Go?"]
    tasks = [async_cot(question=q) for q in questions]
    results = await asyncio.gather(*tasks)
    return results
```

**When to use:**
- Web frameworks (FastAPI, aiohttp)
- Parallel processing of multiple queries
- Non-blocking I/O requirements
- Event-driven architectures

### dspy.streamify

**Streaming outputs** - Stream module outputs token-by-token.

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Wrap module for streaming
cot = dspy.ChainOfThought("question -> answer")
stream_cot = dspy.streamify(cot)

# Stream tokens
for chunk in stream_cot(question="Explain quantum computing"):
    print(chunk, end="")
```

**When to use:**
- Chat interfaces (real-time token display)
- Long-form generation (show progress)
- Latency-sensitive applications

### dspy.TypedPredictor

**Structured output with Pydantic models.**

```python
from pydantic import BaseModel, Field

class PersonInfo(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years")
    occupation: str = Field(description="Current job")

class ExtractPerson(dspy.Signature):
    """Extract person information from text."""
    text = dspy.InputField()
    person: PersonInfo = dspy.OutputField()

extractor = dspy.TypedPredictor(ExtractPerson)
result = extractor(text="John Doe is a 35-year-old software engineer.")

print(result.person.name)       # "John Doe"
print(result.person.age)        # 35
print(result.person.occupation) # "software engineer"
```

**Benefits:**
- Type safety and automatic validation
- JSON schema generation
- IDE autocomplete
- Nested Pydantic models supported

### dspy.majority

**Majority voting over multiple predictions.**

```python
from dspy.primitives import majority

predictor = dspy.Predict("question -> answer")
predictions = [predictor(question="What is 2+2?") for _ in range(5)]

answer = majority([p.answer for p in predictions])
print(answer)  # "4"
```

## Module Composition

### Sequential Pipeline

```python
class Pipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.stage1 = dspy.Predict("input -> intermediate")
        self.stage2 = dspy.ChainOfThought("intermediate -> output")

    def forward(self, input):
        intermediate = self.stage1(input=input).intermediate
        output = self.stage2(intermediate=intermediate).output
        return dspy.Prediction(output=output)
```

### Conditional Logic

```python
class ConditionalModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.router = dspy.Predict("question -> category: str")
        self.simple_qa = dspy.Predict("question -> answer")
        self.complex_qa = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        category = self.router(question=question).category
        if category == "simple":
            return self.simple_qa(question=question)
        else:
            return self.complex_qa(question=question)
```

### Parallel with Consensus

```python
class ParallelModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.approach1 = dspy.ChainOfThought("question -> answer")
        self.approach2 = dspy.ProgramOfThought("question -> answer")

    def forward(self, question):
        answer1 = self.approach1(question=question).answer
        answer2 = self.approach2(question=question).answer

        if answer1 == answer2:
            return dspy.Prediction(answer=answer1, confidence="high")
        else:
            return dspy.Prediction(answer=answer1, confidence="low")
```

### Per-Module LM Selection

```python
class MultiModelPipeline(dspy.Module):
    """Use different LMs for different stages."""
    def __init__(self):
        super().__init__()
        self.cheap_lm = dspy.LM("openai/gpt-4o-mini")
        self.strong_lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
        self.classify = dspy.Predict("text -> category")
        self.analyze = dspy.ChainOfThought("text, category -> analysis")

    def forward(self, text):
        # Cheap model for classification
        with dspy.context(lm=self.cheap_lm):
            category = self.classify(text=text).category
        # Strong model for analysis
        with dspy.context(lm=self.strong_lm):
            return self.analyze(text=text, category=category)
```

## Saving and Loading

```python
# Save module (includes few-shot examples and instructions)
qa = dspy.ChainOfThought("question -> answer")
qa.save("models/qa_v1.json")

# Load module
loaded_qa = dspy.ChainOfThought("question -> answer")
loaded_qa.load("models/qa_v1.json")
```

**What gets saved:** Few-shot examples, prompt instructions, module configuration.
**What doesn't get saved:** Model weights, LM provider configuration.

## Module Selection Guide

| Task | Module | Reason |
|------|--------|--------|
| Simple classification | Predict | Fast, direct |
| Math word problems | ProgramOfThought | Reliable calculations |
| Logical reasoning | ChainOfThought | Better with steps |
| Multi-step research | ReAct | Tool usage |
| High-stakes decisions | BestofN | Best of N samples |
| Quality-critical output | Refine | Iterative improvement |
| Structured extraction | TypedPredictor | Type safety |
| Ambiguous questions | MultiChainComparison | Multiple perspectives |
| Web/API serving | asyncify(module) | Non-blocking I/O |
| Chat UI / streaming | streamify(module) | Token-by-token output |

## Performance Tips

1. **Start with Predict**, add reasoning only if needed
2. **Use `dspy.context(lm=...)`** to mix cheap/expensive LMs per stage
3. **Cache predictions** — enabled by default on `dspy.LM()` (disable with `cache=False`)
4. **Profile token usage** with `dspy.configure(track_usage=True)` + `result.get_lm_usage()`
5. **Inspect call history** with `lm.history` for debugging
6. **Use asyncify** for parallel execution in async contexts
7. **Optimize after prototyping** with teleprompters (MIPROv2 recommended)
