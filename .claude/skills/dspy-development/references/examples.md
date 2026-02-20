---
title: "Examples"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# DSPy Real-World Examples (DSPy 3.1+)

Practical examples of building production systems with DSPy.

## Table of Contents
- RAG Systems
- Agent Systems
- RLM — Long Context Processing
- Multi-Modal Pipelines
- Classification
- Async, Streaming, and Batch Patterns
- Teacher-Student Distillation
- Data Processing
- Multi-Stage Pipelines
- Production Patterns

## RAG Systems

### Basic RAG

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class BasicRAG(dspy.Module):
    def __init__(self, num_passages=3):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=num_passages)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        passages = self.retrieve(question).passages
        context = "\n\n".join(passages)
        return self.generate(context=context, question=question)

# Configure retriever (example with Chroma)
from dspy.retrieve.chromadb_rm import ChromadbRM

retriever = ChromadbRM(
    collection_name="my_docs",
    persist_directory="./chroma_db",
    k=3
)
dspy.configure(lm=lm, rm=retriever)

rag = BasicRAG()
result = rag(question="What is DSPy?")
```

### Optimized RAG with GEPA (3.0+)

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

trainset = [
    dspy.Example(
        question="What is retrieval augmented generation?",
        answer="RAG combines retrieval of relevant documents with generation..."
    ).with_inputs("question"),
    # ... more examples
]

def answer_correctness(example, pred, trace=None):
    return example.answer.lower() in pred.answer.lower()

# Optimize with GEPA for reflective prompt evolution
optimizer = dspy.GEPA(
    metric=answer_correctness,
    auto="light",
    num_threads=8,
    reflection_lm=dspy.LM("openai/gpt-4o", temperature=1.0, max_tokens=32000)
)
optimized_rag = optimizer.compile(BasicRAG(), trainset=trainset)
```

### Multi-Hop RAG

```python
class MultiHopRAG(dspy.Module):
    """RAG that follows chains of reasoning across documents."""
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=3)
        self.generate_query = dspy.ChainOfThought("question -> search_query")
        self.generate_answer = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        # First retrieval
        query1 = self.generate_query(question=question).search_query
        passages1 = self.retrieve(query1).passages

        # Generate follow-up query based on first results
        context1 = "\n".join(passages1)
        query2 = self.generate_query(
            question=f"Based on: {context1}\nFollow-up: {question}"
        ).search_query

        # Second retrieval + combine all context
        passages2 = self.retrieve(query2).passages
        all_context = "\n\n".join(passages1 + passages2)

        return self.generate_answer(context=all_context, question=question)
```

### RAG with Reranking

```python
class RerankedRAG(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=10)
        self.rerank = dspy.Predict("question, passage -> relevance_score: float")
        self.answer = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        passages = self.retrieve(question).passages

        scored = []
        for passage in passages:
            score = float(self.rerank(question=question, passage=passage).relevance_score)
            scored.append((score, passage))

        top_passages = [p for _, p in sorted(scored, reverse=True)[:3]]
        context = "\n\n".join(top_passages)
        return self.answer(context=context, question=question)
```

## Agent Systems

### ReAct Agent

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

def search_wikipedia(query: str) -> str:
    """Search Wikipedia for information."""
    import wikipedia
    try:
        return wikipedia.summary(query, sentences=3)
    except:
        return "No results found"

def calculate(expression: str) -> str:
    """Evaluate mathematical expression safely."""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except:
        return "Invalid expression"

class ResearchAgent(dspy.Signature):
    """Answer questions using available tools."""
    question = dspy.InputField()
    answer = dspy.OutputField()

agent = dspy.ReAct(ResearchAgent, tools=[search_wikipedia, calculate])
result = agent(question="What is the population of France divided by 10?")
```

### CodeAct Agent (3.0+)

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

def fetch_data(url: str) -> str:
    """Fetch data from a URL."""
    import requests
    return requests.get(url).text[:1000]

def save_file(path: str, content: str) -> str:
    """Save content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Saved to {path}"

class DataProcessor(dspy.Signature):
    """Process and analyze data from web sources."""
    task = dspy.InputField()
    result = dspy.OutputField()

# CodeAct generates and executes code with tool access
processor = dspy.CodeAct(DataProcessor, tools=[fetch_data, save_file])
result = processor(task="Fetch the latest Python release info and summarize it")
```

### Multi-Agent System

```python
class MultiAgentSystem(dspy.Module):
    def __init__(self):
        super().__init__()
        self.router = dspy.Predict("question -> agent_type: str")
        self.research_agent = dspy.ReAct(ResearchAgent, tools=[search_wikipedia])
        self.math_agent = dspy.ProgramOfThought("problem -> answer")
        self.reasoning_agent = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        agent_type = self.router(question=question).agent_type

        if agent_type == "research":
            return self.research_agent(question=question)
        elif agent_type == "math":
            return self.math_agent(problem=question)
        else:
            return self.reasoning_agent(question=question)
```

## RLM — Long Context Processing (3.1+)

### Financial Document Analysis

Process documents far beyond context limits via sandboxed Python REPL:

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

# RLM handles 100k+ token documents by writing code to explore them
rlm = dspy.RLM(
    "context, query -> answer",
    max_iterations=20,       # Max REPL cycles
    max_llm_calls=10,        # Max recursive sub-queries via llm_query()
    max_output_chars=50000   # Max context passed to sub-calls
)

# Load a massive financial report
with open("10k_annual_report.txt") as f:
    report = f.read()  # 200k+ tokens

result = rlm(
    context=report,
    query="What was the company's Q3 revenue and how did it compare to Q2?"
)
# Internally, the LM writes Python code:
#   lines = context.split('\n')
#   q3_section = [l for l in lines if 'Q3' in l and 'revenue' in l]
#   ... then uses llm_query() for semantic understanding
print(result.answer)
```

### Codebase Exploration with RLM

```python
import os

def load_codebase(root_dir):
    """Load entire codebase as a single context string."""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(('.py', '.ts', '.js')):
                path = os.path.join(dirpath, f)
                with open(path) as fh:
                    files.append(f"=== {path} ===\n{fh.read()}")
    return "\n\n".join(files)

codebase = load_codebase("./src")  # Potentially millions of tokens

rlm = dspy.RLM(
    "context, query -> answer",
    max_iterations=30,
    max_llm_calls=15
)

result = rlm(
    context=codebase,
    query="Find all API endpoints and list their HTTP methods and paths"
)
```

### RLM with Cheaper Sub-LM

```python
# Use expensive model for main reasoning, cheap model for sub-queries
cheap = dspy.LM("openai/gpt-4o-mini")

rlm = dspy.RLM(
    "context, query -> answer",
    max_iterations=20,
    sub_lm=cheap  # Recursive llm_query() calls use cheaper model
)

result = rlm(
    context=massive_document,
    query="Summarize the key findings across all sections"
)
```

### RLM Built-in REPL Tools

The LM has access to these functions inside the sandbox:

```python
# Available inside RLM's sandboxed Python REPL:

# peek(start, end) — View specific character range of context
text = peek(0, 5000)  # First 5000 chars

# grep(pattern) — Search context with regex
matches = grep(r"revenue.*Q[1-4]")  # Returns matching lines

# llm_query(sub_context, question) — Recursive sub-call
answer = llm_query(section_text, "What is the main argument here?")

# llm_query_batched(contexts, question) — Parallel sub-calls
answers = llm_query_batched(
    [section1, section2, section3],
    "Summarize this section"
)

# SUBMIT(answer) — Return final answer
SUBMIT("The Q3 revenue was $4.2B, up 12% from Q2's $3.75B")
```

## Multi-Modal Pipelines (3.0+)

### Image Description

```python
import dspy

lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
dspy.configure(lm=lm)

class DescribeImage(dspy.Signature):
    """Describe an image in detail."""
    image: dspy.Image = dspy.InputField()
    description = dspy.OutputField(desc="detailed visual description")

describer = dspy.Predict(DescribeImage)
result = describer(image=dspy.Image.from_url("https://example.com/photo.jpg"))
print(result.description)
```

### Image + Text Analysis

```python
class AnalyzeChart(dspy.Signature):
    """Analyze a chart image and answer questions about it."""
    chart: dspy.Image = dspy.InputField(desc="chart or graph image")
    question = dspy.InputField(desc="question about the chart")
    analysis = dspy.OutputField(desc="detailed analysis with data points")

analyzer = dspy.ChainOfThought(AnalyzeChart)
result = analyzer(
    chart=dspy.Image.from_file("quarterly_revenue.png"),
    question="What quarter showed the highest growth?"
)
```

### Audio Processing

```python
class TranscribeAndSummarize(dspy.Signature):
    """Transcribe audio and provide a summary."""
    audio: dspy.Audio = dspy.InputField()
    transcript = dspy.OutputField(desc="full transcript")
    summary = dspy.OutputField(desc="brief summary of key points")

processor = dspy.Predict(TranscribeAndSummarize)
result = processor(audio=dspy.Audio.from_file("meeting.mp3"))
```

## Classification

### Optimized Classifier

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class SentimentClassifier(dspy.Module):
    def __init__(self):
        super().__init__()
        self.classify = dspy.Predict("text -> sentiment: str")

    def forward(self, text):
        return self.classify(text=text)

trainset = [
    dspy.Example(text="I love this!", sentiment="positive").with_inputs("text"),
    dspy.Example(text="Terrible experience", sentiment="negative").with_inputs("text"),
]

def accuracy(example, pred, trace=None):
    return example.sentiment == pred.sentiment

# Optimize with MIPROv2
tp = dspy.MIPROv2(metric=accuracy, auto="light")
optimized = tp.compile(SentimentClassifier(), trainset=trainset)
result = optimized(text="This product is amazing!")
print(result.sentiment)  # "positive"
```

### Multi-Class with Confidence

```python
class TopicSignature(dspy.Signature):
    """Classify text into one of: technology, sports, politics, entertainment."""
    text = dspy.InputField()
    category = dspy.OutputField(desc="one of: technology, sports, politics, entertainment")
    confidence = dspy.OutputField(desc="0.0 to 1.0")

classifier = dspy.ChainOfThought(TopicSignature)
result = classifier(text="The Lakers won the championship")
print(result.category)    # "sports"
print(result.confidence)  # 0.95
```

### Hierarchical Classifier

```python
class HierarchicalClassifier(dspy.Module):
    def __init__(self):
        super().__init__()
        self.coarse = dspy.Predict("text -> broad_category: str")
        self.fine_tech = dspy.Predict("text -> tech_subcategory: str")
        self.fine_sports = dspy.Predict("text -> sports_subcategory: str")

    def forward(self, text):
        broad = self.coarse(text=text).broad_category
        if broad == "technology":
            fine = self.fine_tech(text=text).tech_subcategory
        elif broad == "sports":
            fine = self.fine_sports(text=text).sports_subcategory
        else:
            fine = "other"
        return dspy.Prediction(broad_category=broad, fine_category=fine)
```

## Async, Streaming, and Batch Patterns

### Async Module for Web APIs

```python
import dspy
import asyncio

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Wrap any module for async
cot = dspy.ChainOfThought("question -> answer")
async_cot = dspy.asyncify(cot)

# FastAPI integration
from fastapi import FastAPI
app = FastAPI()

@app.get("/ask")
async def ask(question: str):
    result = await async_cot(question=question)
    return {"answer": result.answer}
```

### Parallel Async Queries

```python
async def parallel_queries(questions: list[str]):
    """Process multiple questions concurrently."""
    cot = dspy.ChainOfThought("question -> answer")
    async_cot = dspy.asyncify(cot)

    tasks = [async_cot(question=q) for q in questions]
    results = await asyncio.gather(*tasks)
    return [r.answer for r in results]

# 10 questions processed concurrently
answers = asyncio.run(parallel_queries([
    "What is Python?",
    "What is Rust?",
    "What is Go?",
    # ... more questions
]))
```

### Streaming Chat Interface

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class ChatBot(dspy.Module):
    def __init__(self):
        super().__init__()
        self.respond = dspy.ChainOfThought("history, message -> response")

    def forward(self, history, message):
        return self.respond(history=history, message=message)

# Wrap for streaming
stream_chat = dspy.streamify(ChatBot())

# Stream tokens to client
for chunk in stream_chat(history="", message="Tell me about quantum computing"):
    print(chunk, end="", flush=True)
```

### Thread-Safe Batch Processing (3.0+)

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

qa = dspy.ChainOfThought("question -> answer")

# Process many inputs concurrently with Module.batch
questions = [
    {"question": "What is Python?"},
    {"question": "What is Rust?"},
    {"question": "What is Go?"},
    {"question": "What is TypeScript?"},
    # ... hundreds more
]

results = qa.batch(
    questions,
    num_threads=8,              # Parallel threads
    return_failed_examples=True, # Don't crash on errors
    max_errors=5                 # Stop after 5 failures
)

for r in results:
    print(r.answer)
```

### Async RAG Pipeline

```python
import dspy
import asyncio

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class AsyncRAG(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        passages = self.retrieve(question).passages
        context = "\n".join(passages)
        return self.generate(context=context, question=question)

async_rag = dspy.asyncify(AsyncRAG())

# Process batch of questions concurrently
async def batch_rag(questions):
    tasks = [async_rag(question=q) for q in questions]
    return await asyncio.gather(*tasks)
```

## Teacher-Student Distillation

### Basic Distillation

```python
import dspy

# Teacher: expensive, high-quality model
teacher = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
# Student: cheap, fast model
student = dspy.LM("openai/gpt-4o-mini")

# Configure student as the runtime model
dspy.configure(lm=student)

# Training data
trainset = [
    dspy.Example(question="Explain photosynthesis", answer="...").with_inputs("question"),
    # ... 50+ examples
]

def answer_quality(example, pred, trace=None):
    judge = dspy.Predict("question, gold, predicted -> score: float")
    with dspy.context(lm=teacher):  # Use teacher to judge
        result = judge(question=example.question, gold=example.answer, predicted=pred.answer)
    return float(result.score)

# Optimize student using teacher's knowledge
tp = dspy.MIPROv2(
    metric=answer_quality,
    auto="medium",
    teacher_settings=dict(lm=teacher),  # Teacher generates demos
    prompt_model=teacher                 # Teacher proposes instructions
)

qa = dspy.ChainOfThought("question -> answer")
optimized_student = tp.compile(qa, trainset=trainset)

# Student now performs near teacher level
optimized_student.save("models/distilled_qa", save_program=True)
```

### Multi-Stage Distillation Pipeline

```python
import dspy

teacher = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
student = dspy.LM("openai/gpt-4o-mini")

class AnalysisPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.Predict("text -> key_points")
        self.analyze = dspy.ChainOfThought("key_points -> analysis")
        self.conclude = dspy.Predict("analysis -> conclusion")

    def forward(self, text):
        kp = self.extract(text=text).key_points
        analysis = self.analyze(key_points=kp).analysis
        conclusion = self.conclude(analysis=analysis).conclusion
        return dspy.Prediction(key_points=kp, analysis=analysis, conclusion=conclusion)

# Distill entire pipeline
dspy.configure(lm=student)
tp = dspy.MIPROv2(
    metric=quality_metric,
    auto="medium",
    teacher_settings=dict(lm=teacher),
    prompt_model=teacher
)
optimized_pipeline = tp.compile(AnalysisPipeline(), trainset=trainset)
```

## Data Processing

### Information Extraction

```python
import dspy
from pydantic import BaseModel, Field

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class PersonInfo(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years")
    occupation: str = Field(description="Job title")
    location: str = Field(description="City and country")

class ExtractPerson(dspy.Signature):
    """Extract person information from text."""
    text = dspy.InputField()
    person: PersonInfo = dspy.OutputField()

extractor = dspy.TypedPredictor(ExtractPerson)

text = "Dr. Jane Smith, 42, is a neuroscientist at Stanford in Palo Alto, California."
result = extractor(text=text)
print(result.person.name)       # "Dr. Jane Smith"
print(result.person.age)        # 42
print(result.person.occupation) # "neuroscientist"
```

### Text Summarization with Refinement

```python
class RefinedSummarizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Refine(
            dspy.Signature("text, target_length -> summary"),
            N=2  # Up to 2 refinement rounds
        )

    def forward(self, text, target_length="3 sentences"):
        return self.summarize(text=text, target_length=target_length)
```

## Multi-Stage Pipelines

### Document Processing Pipeline

```python
class DocumentPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.Predict("document -> key_points")
        self.classify = dspy.Predict("key_points -> category")
        self.summarize = dspy.ChainOfThought("key_points, category -> summary")
        self.tag = dspy.Predict("summary -> tags")

    def forward(self, document):
        key_points = self.extract(document=document).key_points
        category = self.classify(key_points=key_points).category
        summary = self.summarize(key_points=key_points, category=category).summary
        tags = self.tag(summary=summary).tags
        return dspy.Prediction(
            key_points=key_points, category=category,
            summary=summary, tags=tags
        )
```

### Quality Control Pipeline with Refine

```python
class QualityPipeline(dspy.Module):
    """Generate output and iteratively refine for quality."""
    def __init__(self):
        super().__init__()
        self.generate = dspy.Refine(
            dspy.Signature("prompt -> output"),
            N=3  # Up to 3 refinement iterations
        )

    def forward(self, prompt):
        return self.generate(prompt=prompt)
```

### RLM + RAG Hybrid Pipeline

```python
class LongDocQA(dspy.Module):
    """Use RLM for long documents, RAG for knowledge base queries."""
    def __init__(self):
        super().__init__()
        self.router = dspy.Predict("question, has_document -> approach: str")
        self.rlm = dspy.RLM("context, query -> answer", max_iterations=20)
        self.rag_retrieve = dspy.Retrieve(k=5)
        self.rag_answer = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question, document=None):
        has_doc = "yes" if document else "no"
        approach = self.router(question=question, has_document=has_doc).approach

        if approach == "rlm" and document:
            return self.rlm(context=document, query=question)
        else:
            passages = self.rag_retrieve(question).passages
            context = "\n\n".join(passages)
            return self.rag_answer(context=context, question=question)
```

## Production Patterns

### Error Handling with Fallback

```python
class RobustModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.primary = dspy.ChainOfThought("input -> output")
        self.fallback = dspy.Predict("input -> output")

    def forward(self, input):
        try:
            return self.primary(input=input)
        except Exception:
            return self.fallback(input=input)
```

### Multi-Model Fallback

```python
class MultiModelFallback(dspy.Module):
    """Try expensive model first, fall back to cheaper one."""
    def __init__(self):
        super().__init__()
        self.strong = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
        self.cheap = dspy.LM("openai/gpt-4o-mini")
        self.predict = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        try:
            with dspy.context(lm=self.strong):
                return self.predict(question=question)
        except Exception:
            with dspy.context(lm=self.cheap):
                return self.predict(question=question)
```

### Token Usage Monitoring

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm, track_usage=True)

class MonitoredPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.step1 = dspy.Predict("input -> intermediate")
        self.step2 = dspy.ChainOfThought("intermediate -> output")

    def forward(self, input):
        r1 = self.step1(input=input)
        r2 = self.step2(intermediate=r1.intermediate)

        # Check cumulative usage
        usage = r2.get_lm_usage()
        print(f"Total tokens: {usage}")

        return r2
```

### A/B Testing with MIPROv2

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Optimize two variants with different strategies
qa = dspy.ChainOfThought("question -> answer")

# Variant A: Light optimization
tp_light = dspy.MIPROv2(metric=validate_answer, auto="light")
variant_a = tp_light.compile(qa, trainset=trainset)

# Variant B: Medium optimization
tp_medium = dspy.MIPROv2(metric=validate_answer, auto="medium")
variant_b = tp_medium.compile(qa, trainset=trainset)

# Evaluate both
from dspy.evaluate import Evaluate
evaluator = Evaluate(devset=testset, metric=validate_answer)

score_a = evaluator(variant_a)
score_b = evaluator(variant_b)

# Deploy the winner
winner = variant_b if score_b > score_a else variant_a
winner.save("models/production_qa", save_program=True)
print(f"Deployed: {'B' if score_b > score_a else 'A'} (score: {max(score_a, score_b):.2%})")
```

### Reasoning Model Integration (3.1+)

```python
import dspy

# Use with OpenAI reasoning models (o1, o3)
lm = dspy.LM("openai/o3-mini")
dspy.configure(lm=lm)

class MathSolver(dspy.Signature):
    """Solve complex math problems."""
    problem = dspy.InputField()
    reasoning: dspy.Reasoning = dspy.InputField()  # Captures native CoT
    answer = dspy.OutputField()

solver = dspy.Predict(MathSolver)
result = solver(problem="Find all primes p where p^2 + 2 is also prime")
# dspy.Reasoning captures the model's native chain-of-thought
```

### Complete: Customer Support Bot

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

class CustomerSupportBot(dspy.Module):
    def __init__(self):
        super().__init__()
        self.classify_intent = dspy.Predict("message -> intent: str")
        self.technical_handler = dspy.ChainOfThought("message, history -> response")
        self.billing_handler = dspy.ChainOfThought("message, history -> response")
        self.general_handler = dspy.Predict("message, history -> response")
        self.retrieve = dspy.Retrieve(k=3)
        self.history = []

    def forward(self, message):
        intent = self.classify_intent(message=message).intent
        docs = self.retrieve(message).passages
        context = "\n".join(docs)
        history_str = "\n".join(self.history)
        full_message = f"Context: {context}\n\nMessage: {message}"

        if intent == "technical":
            response = self.technical_handler(message=full_message, history=history_str).response
        elif intent == "billing":
            response = self.billing_handler(message=full_message, history=history_str).response
        else:
            response = self.general_handler(message=full_message, history=history_str).response

        self.history.append(f"User: {message}")
        self.history.append(f"Bot: {response}")
        return dspy.Prediction(response=response, intent=intent)

# Optimize with MIPROv2
tp = dspy.MIPROv2(metric=response_quality, auto="medium")
optimized_bot = tp.compile(CustomerSupportBot(), trainset=trainset)
optimized_bot.save("models/support_bot_v1", save_program=True)
```

## Resources

- **Documentation**: https://dspy.ai
- **Learn Path**: https://dspy.ai/learn/
- **Examples Repo**: https://github.com/stanfordnlp/dspy/tree/main/examples
- **Discord**: https://discord.gg/XCGy2WDCQB
