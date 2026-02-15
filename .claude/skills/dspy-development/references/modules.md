# DSPy Modules (DSPy 3.1+)

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

### dspy.ProgramOfThought

**Code-based reasoning** - Generates and executes Python code in a sandboxed environment.

**Requires**: Deno runtime (`curl -fsSL https://deno.land/install.sh | sh`)

```python
pot = dspy.ProgramOfThought("question -> answer")

result = pot(question="What is 15% of 240?")
# Internally generates: answer = 240 * 0.15
print(result.answer)  # 36.0

# Can also use LocalSandbox for simpler execution
sandbox = dspy.LocalSandbox()
answer = sandbox.execute("value = 2*5 + 4\nvalue")
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

## DSPy 3.x Modules

### dspy.RLM (Recursive Language Model)

**NEW in 3.1** — Process documents far beyond the context window by treating them as external environments explored through sandboxed Python code.

Instead of feeding massive documents into the prompt, RLM loads the context as a Python variable. The LM writes code to peek, grep, partition, and transform the data, making recursive sub-calls via `llm_query()` to process chunks. Results are aggregated and returned via `SUBMIT()`.

**Requires**: Deno runtime for WASM sandbox.

**Parameters:**
- `max_iterations` (int, default=20): Max code generation cycles
- `max_llm_calls` (int, default=50): Max recursive LM sub-calls
- `max_output_chars` (int, default=10000): Max output length
- `sub_lm` (dspy.LM, optional): Cheaper model for sub-queries
- `tools` (list, optional): Additional tools available in sandbox
- `verbose` (bool, default=False): Print execution traces

```python
import dspy

lm = dspy.LM("openai/gpt-4o")
dspy.configure(lm=lm)

# Basic: Process a massive document
rlm = dspy.RLM("context, query -> answer", max_iterations=20)
result = rlm(
    context=massive_document,  # 100k+ tokens
    query="What was Q3 revenue and how did it compare to Q2?"
)

# Cost-efficient: Use cheaper model for recursive sub-queries
rlm = dspy.RLM(
    "context, query -> answer",
    sub_lm=dspy.LM("openai/gpt-4o-mini"),
    max_iterations=10,
    max_llm_calls=30
)

# Multi-document analysis
rlm = dspy.RLM(
    "documents, question -> analysis",
    max_iterations=15,
    verbose=True  # See code execution traces
)
```

**Built-in REPL tools (available in sandbox):**
- `llm_query(prompt)` — Make recursive LM call on a sub-problem
- `llm_query_batched(prompts)` — Batch multiple sub-queries
- `SUBMIT(output)` — Return final answer from the sandbox

**Performance:**
- RLM(GPT-4o-mini) outperforms base GPT-4o by 34 points on OOLONG benchmark (132k tokens)
- Handles inputs up to 2 orders of magnitude beyond model context windows
- Paper: "Recursive Language Models" (arXiv:2512.24601, Zhang/Kraska/Khattab, MIT CSAIL)

**When to use:**
- Documents exceeding context window (100k+ tokens)
- Codebase analysis and exploration
- Log file analysis
- Multi-document comparison
- Any task where "just read the whole thing" isn't feasible

**When NOT to use:**
- Short documents that fit in context window (use ChainOfThought instead)
- Real-time/low-latency requirements (recursive calls add latency)
- Tasks not requiring deep context exploration

### dspy.CodeAct

**NEW in 3.0** — Combines code generation with tool execution. Extends the ReAct pattern with the ability to generate and execute arbitrary code, enabling self-learning and dynamic tool composition.

```python
import dspy

lm = dspy.LM("openai/gpt-4o")
dspy.configure(lm=lm)

class DataAnalysis(dspy.Signature):
    """Analyze data by writing and executing code."""
    data_description = dspy.InputField()
    analysis = dspy.OutputField()

codeact = dspy.CodeAct(DataAnalysis, tools=[code_interpreter])
result = codeact(data_description="CSV with columns: date, revenue, region")
```

**When to use:**
- Dynamic data analysis requiring code execution
- Tasks where tools need to be composed programmatically
- Self-learning systems that improve through code feedback

### dspy.Refine

**Iterative self-refinement** - Generates an initial output, then iteratively improves it.

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
```

**Parameters:**
- `signature`: Task signature
- `N`: Maximum refinement iterations (default: 3)
- `reward_fn`: Optional function to score quality

**When to use:**
- Quality-critical outputs (emails, reports, code)
- Tasks where first-pass output needs polishing
- When you want self-improvement without manual assertions

### dspy.BestofN

**N-sample selection** - Generates N candidates and selects the best one.

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
```

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
async_cot = dspy.asyncify(cot)

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

### dspy.streamify

**Streaming outputs** - Stream module outputs token-by-token.

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

cot = dspy.ChainOfThought("question -> answer")
stream_cot = dspy.streamify(cot)

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

### dspy.majority

**Majority voting over multiple predictions.**

```python
from dspy.primitives import majority

predictor = dspy.Predict("question -> answer")
predictions = [predictor(question="What is 2+2?") for _ in range(5)]

answer = majority([p.answer for p in predictions])
print(answer)  # "4"
```

## Types System (3.0+)

DSPy 3.0 introduced a rich type system for multi-modal and structured I/O:

### Multi-Modal Types

```python
import dspy

# Image input
class ImageQA(dspy.Signature):
    """Answer questions about images."""
    image: dspy.Image = dspy.InputField()
    question = dspy.InputField()
    answer = dspy.OutputField()

# Audio input
class TranscribeAudio(dspy.Signature):
    """Transcribe audio to text."""
    audio: dspy.Audio = dspy.InputField()
    transcript = dspy.OutputField()
```

### Special Types

| Type | Purpose | Added |
|------|---------|-------|
| `dspy.Image` | Image input for vision models | 3.0 |
| `dspy.Audio` | Audio input for speech models | 3.0 |
| `dspy.History` | Conversation history management | 3.0 |
| `dspy.ToolCalls` | Structured tool invocation format | 3.0 |
| `dspy.Reasoning` | Structured reasoning output | 3.1 |
| `dspy.Code` | Code type with language spec | 3.1.1 |
| `dspy.File` | File handling | 3.1 |

### dspy.Reasoning (3.1+)

For models with native reasoning capabilities (e.g., o1, o3):

```python
class ReasonedQA(dspy.Signature):
    """Answer with structured reasoning."""
    question = dspy.InputField()
    reasoning: dspy.Reasoning = dspy.OutputField()
    answer = dspy.OutputField()

module = dspy.ChainOfThought(ReasonedQA)
result = module(question="Complex multi-step problem...")
print(result.reasoning)  # Structured reasoning trace
print(result.answer)
```

## Adapters (3.0+)

Adapters control how DSPy formats prompts for the LM:

| Adapter | Description | Use Case |
|---------|-------------|----------|
| `dspy.ChatAdapter` | Field-based with `[[ ## markers ]]` (default) | General purpose |
| `dspy.JSONAdapter` | Native JSON generation | Structured output, APIs |
| `dspy.XMLAdapter` | XML-based formatting | XML-focused workflows |
| `dspy.BAMLAdapter` | BAML integration | BAML users |

```python
import dspy

# Explicit adapter configuration
dspy.configure(
    lm=dspy.LM("openai/gpt-4o-mini"),
    adapter=dspy.ChatAdapter()  # This is the default
)

# JSONAdapter for structured output
dspy.configure(
    lm=dspy.LM("openai/gpt-4o-mini"),
    adapter=dspy.JSONAdapter()
)

# ChatAdapter with native function calling
adapter = dspy.ChatAdapter(use_native_function_calling=True)
dspy.configure(lm=dspy.LM("openai/gpt-4o"), adapter=adapter)

# Inspect formatted messages
adapter = dspy.ChatAdapter()
messages = adapter.format(
    signature=dspy.Signature("question -> answer"),
    demos=[{"question": "What is 1+1?", "answer": "2"}],
    inputs={"question": "What is 2+2?"}
)
print(messages)
```

All adapters support:
- Token and status streaming
- Async paths
- Intelligent fallback to native LLM structured outputs

## Batch Processing (3.0+)

Thread-safe batch processing for high-throughput scenarios:

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

module = dspy.ChainOfThought("question -> answer")

# Process many inputs concurrently
inputs = [{"question": f"What is {i}+{i}?"} for i in range(100)]
results = module.batch(
    inputs,
    num_threads=8,
    return_failed_examples=True,
    max_errors=5
)
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
        with dspy.context(lm=self.cheap_lm):
            category = self.classify(text=text).category
        with dspy.context(lm=self.strong_lm):
            return self.analyze(text=text, category=category)
```

## Saving and Loading

```python
# Save module state (JSON format)
qa = dspy.ChainOfThought("question -> answer")
qa.save("models/qa_v1.json")

# Save entire program with metadata (3.0+ — guaranteed 3.x compatibility)
qa.save("models/qa_v1", save_program=True)

# Load module
loaded_qa = dspy.ChainOfThought("question -> answer")
loaded_qa.load("models/qa_v1.json")
```

**What gets saved:** Few-shot examples, prompt instructions, module configuration.
**What doesn't get saved:** Model weights, LM provider configuration.
**Compatibility:** Programs saved in dspy>=3.0.0 have guaranteed compatibility across 3.x versions.

## Module Selection Guide

| Task | Module | Reason |
|------|--------|--------|
| Simple classification | Predict | Fast, direct |
| Math word problems | ProgramOfThought | Reliable calculations |
| Logical reasoning | ChainOfThought | Better with steps |
| Multi-step research | ReAct | Tool usage |
| Long document analysis | RLM | Recursive exploration beyond context window |
| Dynamic code execution | CodeAct | Code + tool composition |
| High-stakes decisions | BestofN | Best of N samples |
| Quality-critical output | Refine | Iterative improvement |
| Structured extraction | TypedPredictor | Type safety |
| Ambiguous questions | MultiChainComparison | Multiple perspectives |
| Web/API serving | asyncify(module) | Non-blocking I/O |
| Chat UI / streaming | streamify(module) | Token-by-token output |
| High throughput | module.batch() | Thread-safe concurrency |

## Performance Tips

1. **Start with Predict**, add reasoning only if needed
2. **Use `dspy.context(lm=...)`** to mix cheap/expensive LMs per stage
3. **Cache predictions** — enabled by default on `dspy.LM()` (disable with `cache=False`)
4. **Profile token usage** with `dspy.configure(track_usage=True)` + `result.get_lm_usage()`
5. **Inspect call history** with `lm.history` or `dspy.inspect_history()` for debugging
6. **Use asyncify** for parallel execution in async contexts
7. **Use Module.batch** for high-throughput batch processing (3.0+)
8. **Use RLM with sub_lm** for cost-efficient long-context processing
9. **Optimize after prototyping** with optimizers (MIPROv2 or GEPA recommended)
