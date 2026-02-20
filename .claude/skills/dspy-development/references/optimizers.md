---
title: "Optimizers"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# DSPy Optimizers (DSPy 3.1+)

Complete guide to DSPy's optimization algorithms for improving prompts, evolving instructions, and training model weights.

## What Are Optimizers?

DSPy optimizers (historically called "teleprompters") automatically improve modules by:
- **Synthesizing few-shot examples** from training data
- **Proposing better instructions** through search
- **Evolving prompts reflectively** with feedback loops (3.0+)
- **Training model weights via RL** (3.0+)
- **Fine-tuning model weights** (optional)

**Key idea**: Instead of manually tuning prompts, define a metric and let DSPy optimize.

## Optimizer Selection Guide

| Optimizer | Best For | Speed | Quality | Data Needed |
|-----------|----------|-------|---------|-------------|
| `BootstrapFewShot` | Quick first try | Fast | Good | 10-50 examples |
| `BootstrapFewShotWithRandomSearch` | Better few-shot | Medium | Better | 10-50 examples |
| `dspy.MIPROv2` | **State-of-the-art (recommended)** | Medium | Excellent | 50-200 examples |
| `dspy.GEPA` | **Reflective prompt evolution (3.0+)** | Medium | Excellent | 20-100 examples |
| `dspy.SIMBA` | Self-reflection with feedback (3.0+) | Medium | Excellent | 20-100 examples |
| `ArborGRPO` | RL-based weight training (3.0+) | Slow | Excellent | 100+ examples |
| `BootstrapFinetune` | Model fine-tuning | Slow | Excellent | 100+ examples |
| `COPRO` | Prompt search | Medium | Good | 20-100 examples |
| `Ensemble` | Combine programs | Fast | Good | N/A |
| `KNNFewShot` | Quick baseline | Very fast | Fair | 10+ examples |

**Recommended starting point**: `dspy.MIPROv2(metric=metric, auto="light")`

## Core Optimizers

### BootstrapFewShot

**Most popular optimizer** - Generates few-shot demonstrations from training data.

**How it works:**
1. Takes training examples
2. Uses module to generate predictions
3. Selects high-quality predictions (based on metric)
4. Uses these as few-shot examples in future prompts

```python
import dspy
from dspy.teleprompt import BootstrapFewShot

# Configure LM
lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# Training data
trainset = [
    dspy.Example(question="What is 2+2?", answer="4").with_inputs("question"),
    dspy.Example(question="What is 3+5?", answer="8").with_inputs("question"),
    dspy.Example(question="What is 10-3?", answer="7").with_inputs("question"),
]

# Define metric
def validate_answer(example, pred, trace=None):
    return example.answer.lower() == pred.answer.lower()

# Create module
qa = dspy.ChainOfThought("question -> answer")

# Optimize
optimizer = BootstrapFewShot(
    metric=validate_answer,
    max_bootstrapped_demos=3,
    max_rounds=2
)
optimized_qa = optimizer.compile(qa, trainset=trainset)
```

**Parameters:**
- `metric`: Function that scores predictions (required)
- `max_bootstrapped_demos`: Max demonstrations to generate (default: 4)
- `max_labeled_demos`: Max labeled examples to use (default: 16)
- `max_rounds`: Optimization iterations (default: 1)
- `metric_threshold`: Minimum score to accept (optional)

**When to use:** First optimizer to try. You have 10+ labeled examples.

### BootstrapFewShotWithRandomSearch

**Enhanced BootstrapFewShot** - Runs multiple random configurations and picks the best.

```python
from dspy.teleprompt import BootstrapFewShotWithRandomSearch

optimizer = BootstrapFewShotWithRandomSearch(
    metric=validate_answer,
    max_bootstrapped_demos=3,
    max_labeled_demos=5,
    num_candidate_programs=16,  # Try 16 random configurations
    num_threads=8
)
optimized_qa = optimizer.compile(qa, trainset=trainset)
```

**When to use:** When BootstrapFewShot isn't enough but you don't have enough data for MIPROv2.

### dspy.MIPROv2 (Recommended)

**State-of-the-art optimizer** - Multi-prompt Instruction PRoposal Optimizer v2. Jointly optimizes instructions AND few-shot examples.

**How it works:**
1. Generates candidate instructions using a prompt model
2. Proposes few-shot demonstrations
3. Evaluates combinations on training set
4. Uses Bayesian optimization to find best combination

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# MIPROv2 with auto mode (EASIEST way to start)
tp = dspy.MIPROv2(metric=validate_answer, auto="light")
optimized = tp.compile(qa, trainset=trainset)

# Auto modes:
# - "light"  : Quick optimization, few trials (~30s-2min)
# - "medium" : Moderate optimization (~5-15min)
# - "heavy"  : Thorough optimization (~30min-2hrs)
```

**Full control mode:**

```python
tp = dspy.MIPROv2(
    metric=validate_answer,
    num_candidates=10,       # Instruction candidates per predictor
    num_threads=8,           # Parallel evaluation threads
    max_errors=5,            # Stop after 5 errors
    verbose=True
)

optimized = tp.compile(
    qa,
    trainset=trainset,
    max_bootstrapped_demos=2,  # Few-shot examples per predictor
    max_labeled_demos=2,       # Labeled examples per predictor
    num_trials=50              # Bayesian optimization trials
)
```

**Teacher-student distillation:**

```python
teacher = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
student = dspy.LM("openai/gpt-4o-mini")

dspy.configure(lm=student)

tp = dspy.MIPROv2(
    metric=validate_answer,
    auto="medium",
    teacher_settings=dict(lm=teacher),  # Use teacher to generate demos
    prompt_model=teacher                 # Use teacher to propose instructions
)
optimized = tp.compile(qa, trainset=trainset)
# Student now performs near teacher level via optimized prompts
```

**When to use:**
- Default choice for most optimization tasks
- Start with `auto="light"`, upgrade to `"medium"` if needed
- Have 20+ training examples (50+ for best results)
- Want joint instruction + few-shot optimization

## New Optimizers (3.0+)

### dspy.GEPA — Reflective Prompt Evolution

**Genetic-Evolutionary Prompt Architect** — Uses evolutionary algorithms with reflective feedback to optimize prompts. Maintains a Pareto frontier of strategies and evolves them.

**How it works:**
1. Generates initial prompt candidates
2. Evaluates each on training data with full trace access
3. Uses a reflection LM to analyze successes and failures
4. Mutates and evolves prompts based on reflective feedback
5. Maintains Pareto frontier of best strategies

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

# GEPA with auto mode (recommended starting point)
optimizer = dspy.GEPA(
    metric=validate_answer,
    auto="light",
    num_threads=32
)
optimized = optimizer.compile(my_module, trainset=trainset, valset=valset)
```

**Full control with reflection LM:**

```python
# Use a strong model for reflection (analyzing why prompts succeed/fail)
reflection_lm = dspy.LM("openai/gpt-4o", temperature=1.0, max_tokens=32000)

optimizer = dspy.GEPA(
    metric=metric_with_feedback,
    auto="medium",
    num_threads=32,
    reflection_lm=reflection_lm,              # LM that reasons about prompt quality
    reflection_minibatch_size=25,              # Examples per reflection batch
)
optimized = optimizer.compile(
    program,
    trainset=trainset,
    valset=valset  # GEPA benefits from explicit validation set
)
```

**GEPA with custom feedback metric:**

```python
def metric_with_feedback(example, pred, trace=None):
    """Return score AND feedback for GEPA reflection."""
    score = 0.0
    feedback = []

    if example.answer.lower() in pred.answer.lower():
        score += 0.5
        feedback.append("Correct answer found")
    else:
        feedback.append(f"Expected '{example.answer}', got '{pred.answer}'")

    if len(pred.answer.split()) <= 20:
        score += 0.25
        feedback.append("Concise response")
    else:
        feedback.append("Response too verbose")

    # Return (score, feedback_string) for GEPA reflection
    return score, "; ".join(feedback)

optimizer = dspy.GEPA(
    metric=metric_with_feedback,
    auto="light",
    num_threads=32
)
```

**Parameters:**
- `metric`: Evaluation metric — can return (score, feedback) tuple for reflection
- `auto`: `"light"`, `"medium"`, `"heavy"` — controls evolution generations
- `num_threads`: Parallel evaluation threads
- `reflection_lm`: LM for analyzing prompt performance (default: uses configured LM)
- `reflection_minibatch_size`: Examples per reflection batch

**When to use:**
- Agentic tasks where feedback is rich
- Complex pipelines where you can provide qualitative feedback
- When MIPROv2 plateaus — GEPA's reflective evolution finds different optima
- 20-100 training examples

**Performance**: GEPA achieves 35x fewer rollouts than GRPO while matching quality on many benchmarks.

### dspy.SIMBA — Self-Reflection with Feedback

**Self-Improving Model-Based Architect** — Focuses on intelligent instruction exploration with self-reflection.

```python
import dspy

lm = dspy.LM("openai/gpt-4o-mini")
dspy.configure(lm=lm)

optimizer = dspy.SIMBA(
    metric=validate_answer,
    auto="light",
    num_threads=16
)
optimized = optimizer.compile(my_module, trainset=trainset)
```

**How it differs from GEPA:**
- GEPA: Evolutionary + Pareto frontier + reflective feedback
- SIMBA: Focuses on self-reflection cycles with instruction mutation
- SIMBA is often faster for simpler tasks
- GEPA tends to find better optima for complex multi-step programs

**When to use:**
- Simpler optimization needs where GEPA is overkill
- When you want self-reflection benefits without full evolutionary search
- 20-100 training examples

### ArborGRPO — RL-Based Weight Training

**Arbor Group Relative Policy Optimization** — Uses reinforcement learning to train model weights, not just prompts. First multi-module GRPO implementation.

**Requires**: The `arbor` library and an Arbor server.

```python
import dspy
from arbor import ArborProvider

# Initialize Arbor RL training server
provider = ArborProvider()
arbor_lm = provider.get_lm()  # RL-trainable LM

dspy.configure(lm=arbor_lm)

# ArborGRPO trains actual model weights
optimizer = ArborGRPO(
    metric=validate_answer,
    num_threads=8
)
optimized = optimizer.compile(my_module, trainset=trainset)
```

**How it differs from other optimizers:**
- MIPROv2/GEPA/SIMBA: Optimize **prompts** (instructions, few-shot examples)
- ArborGRPO: Optimizes **model weights** via reinforcement learning
- ArborGRPO: First optimizer to support multi-module GRPO (trains weights across a full pipeline)

**When to use:**
- 100+ training examples
- You have infrastructure for RL training (Arbor server)
- Want to train model weights, not just optimize prompts
- Building production systems where inference cost matters

### BootstrapFinetune

**Fine-tune model weights** - Creates training dataset for fine-tuning.

```python
from dspy.teleprompt import BootstrapFinetune

# Generate fine-tuning data
optimizer = BootstrapFinetune(metric=validate_answer)
optimized_qa = optimizer.compile(qa, trainset=trainset)

# After fine-tuning, load your model:
finetuned_lm = dspy.LM("openai/ft:gpt-3.5-turbo:your-model-id")
dspy.configure(lm=finetuned_lm)
```

**When to use:**
- 100+ examples, latency critical, task is narrow

### COPRO (Coordinate Prompt Optimization)

**Optimize prompts via gradient-free search.**

```python
from dspy.teleprompt import COPRO

optimizer = COPRO(
    metric=validate_answer,
    breadth=10,   # Candidates per iteration
    depth=3       # Optimization rounds
)
optimized_qa = optimizer.compile(qa, trainset=trainset)
```

**When to use:** Want prompt optimization, have 20-100 examples, MIPROv2 too slow.

### Ensemble

**Combine multiple optimized programs.**

```python
from dspy.teleprompt import Ensemble

# First optimize with different strategies
programs = []
for seed in range(5):
    opt = BootstrapFewShot(metric=validate_answer)
    prog = opt.compile(qa, trainset=trainset)
    programs.append(prog)

# Ensemble combines them
ensemble = Ensemble(reduce_fn=dspy.majority)
ensemble_program = ensemble.compile(programs)
```

**When to use:** Combine multiple optimized programs for higher reliability.

### KNNFewShot

**Simple k-nearest neighbors** - Selects similar examples for each query.

```python
from dspy.teleprompt import KNNFewShot

optimizer = KNNFewShot(k=3)
optimized_qa = optimizer.compile(qa, trainset=trainset)
# For each query, uses 3 most similar examples from trainset
```

**When to use:** Quick baseline, diverse training examples.

## Writing Metrics

Metrics are functions that score predictions. They're critical for optimization.

### Binary Metrics

```python
def exact_match(example, pred, trace=None):
    return example.answer.lower() == pred.answer.lower()

def contains_answer(example, pred, trace=None):
    return example.answer.lower() in pred.answer.lower()
```

### Continuous Metrics

```python
def f1_score(example, pred, trace=None):
    pred_tokens = set(pred.answer.lower().split())
    gold_tokens = set(example.answer.lower().split())
    if not pred_tokens or not gold_tokens:
        return 0.0
    precision = len(pred_tokens & gold_tokens) / len(pred_tokens)
    recall = len(pred_tokens & gold_tokens) / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)
```

### Multi-Factor Metrics

```python
def comprehensive_metric(example, pred, trace=None):
    score = 0.0
    # Correctness (50%)
    if example.answer.lower() in pred.answer.lower():
        score += 0.5
    # Conciseness (25%)
    if len(pred.answer.split()) <= 20:
        score += 0.25
    # Citation (25%)
    if "source:" in pred.answer.lower():
        score += 0.25
    return score
```

### Metrics with Feedback (for GEPA/SIMBA)

```python
def feedback_metric(example, pred, trace=None):
    """Return (score, feedback) for reflective optimizers."""
    score = 0.0
    feedback_parts = []

    # Check correctness
    if example.answer.lower() in pred.answer.lower():
        score += 0.6
        feedback_parts.append("Answer correct")
    else:
        feedback_parts.append(f"Wrong: expected '{example.answer}', got '{pred.answer}'")

    # Check reasoning quality (if available)
    if hasattr(pred, 'rationale') and len(pred.rationale) > 50:
        score += 0.2
        feedback_parts.append("Good reasoning depth")
    else:
        feedback_parts.append("Reasoning too shallow")

    # Check conciseness
    if len(pred.answer.split()) <= 15:
        score += 0.2
        feedback_parts.append("Concise")

    return score, "; ".join(feedback_parts)
```

### LM-as-Judge Metric

```python
def llm_judge_metric(example, pred, trace=None):
    """Use an LM to judge output quality."""
    judge = dspy.Predict("question, gold_answer, predicted_answer -> score: float")
    result = judge(
        question=example.question,
        gold_answer=example.answer,
        predicted_answer=pred.answer
    )
    return float(result.score)
```

## Evaluation

### Basic Evaluation

```python
from dspy.evaluate import Evaluate

evaluator = Evaluate(
    devset=testset,
    metric=validate_answer,
    num_threads=4,
    display_progress=True
)

# Evaluate baseline
baseline_score = evaluator(qa)

# Evaluate optimized
optimized_score = evaluator(optimized_qa)

print(f"Baseline: {baseline_score:.2%}")
print(f"Optimized: {optimized_score:.2%}")
print(f"Improvement: {optimized_score - baseline_score:.2%}")
```

### Comparing Optimizers

```python
results = {}
for opt_name, optimizer in [
    ("baseline", None),
    ("fewshot", BootstrapFewShot(metric=validate_answer)),
    ("mipro_light", dspy.MIPROv2(metric=validate_answer, auto="light")),
    ("gepa_light", dspy.GEPA(metric=validate_answer, auto="light")),
]:
    if optimizer is None:
        module_opt = qa
    else:
        module_opt = optimizer.compile(qa, trainset=trainset)
    score = evaluator(module_opt)
    results[opt_name] = score

print(results)
# {'baseline': 0.65, 'fewshot': 0.78, 'mipro_light': 0.82, 'gepa_light': 0.85}
```

### Token Usage Tracking

```python
dspy.configure(lm=lm, track_usage=True)

result = optimized_qa(question="What is gravity?")
usage = result.get_lm_usage()
print(usage)  # Token counts per provider/model
```

## Advanced Patterns

### Multi-Stage Optimization

```python
# Stage 1: Bootstrap few-shot
stage1 = BootstrapFewShot(metric=validate_answer, max_bootstrapped_demos=3)
optimized1 = stage1.compile(qa, trainset=trainset)

# Stage 2: MIPROv2 instruction tuning on top
stage2 = dspy.MIPROv2(metric=validate_answer, auto="medium")
optimized2 = stage2.compile(optimized1, trainset=trainset)
```

### Teacher-Student Pipeline

```python
# 1. Build with expensive model
teacher_lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929")
student_lm = dspy.LM("openai/gpt-4o-mini")

# 2. Optimize student to match teacher
dspy.configure(lm=student_lm)
tp = dspy.MIPROv2(
    metric=validate_answer,
    auto="medium",
    teacher_settings=dict(lm=teacher_lm),
    prompt_model=teacher_lm
)
optimized_student = tp.compile(qa, trainset=trainset)

# 3. Deploy cheap student with teacher-quality results
optimized_student.save("models/distilled_qa", save_program=True)
```

### Save and Load Optimized Programs

```python
# Save best model (stable format, guaranteed 3.x compatibility)
optimized_qa.save("models/best_model", save_program=True)

# Load later
loaded_qa = dspy.ChainOfThought("question -> answer")
loaded_qa.load("models/best_model.json")

# Verify loaded model works
result = loaded_qa(question="Test question")
```

## Optimization Workflow (Recommended)

### 1. Establish Baseline

```python
baseline = dspy.ChainOfThought("question -> answer")
baseline_score = evaluator(baseline)
print(f"Baseline: {baseline_score:.2%}")
```

### 2. Try MIPROv2 Light (Quick Win)

```python
tp = dspy.MIPROv2(metric=validate_answer, auto="light")
optimized = tp.compile(baseline, trainset=trainset)
light_score = evaluator(optimized)
print(f"MIPROv2 light: {light_score:.2%} (+{light_score - baseline_score:.2%})")
```

### 3. Try GEPA if MIPROv2 Plateaus (3.0+)

```python
gepa = dspy.GEPA(metric=feedback_metric, auto="light", num_threads=32)
optimized_gepa = gepa.compile(baseline, trainset=trainset, valset=valset)
gepa_score = evaluator(optimized_gepa)
print(f"GEPA light: {gepa_score:.2%}")
```

### 4. If Needed, Upgrade to Medium

```python
tp = dspy.MIPROv2(metric=validate_answer, auto="medium")
optimized = tp.compile(baseline, trainset=trainset)
medium_score = evaluator(optimized)
print(f"MIPROv2 medium: {medium_score:.2%}")
```

### 5. Save Best Model

```python
optimized.save("models/best_model", save_program=True)
```

## Common Pitfalls

### 1. Overfitting to Training Data

```python
# Bad: Too many demos
optimizer = BootstrapFewShot(max_bootstrapped_demos=20)  # Overfits!

# Good: Moderate demos
optimizer = BootstrapFewShot(max_bootstrapped_demos=3)
```

### 2. Metric Doesn't Match Task

```python
# Bad: Binary metric for nuanced task
def bad_metric(example, pred, trace=None):
    return example.answer == pred.answer  # Too strict!

# Good: Graded metric
def good_metric(example, pred, trace=None):
    return f1_score(example.answer, pred.answer)  # Allows partial credit
```

### 3. Using Old API

```python
# Bad: Deprecated DSPy 1.x API
from dspy.teleprompt import MIPRO  # Old version
dspy.settings.configure(lm=lm)    # Old config

# Good: DSPy 3.x API
tp = dspy.MIPROv2(metric=metric, auto="light")  # New version
dspy.configure(lm=lm)                            # New config
```

### 4. No Validation Set

```python
# Bad: Optimizing on test set
optimizer.compile(module, trainset=testset)  # Cheating!

# Good: Proper splits
optimizer.compile(module, trainset=trainset)
evaluator(optimized, devset=testset)
```

### 5. Not Using Feedback Metrics with GEPA

```python
# Bad: Binary metric wastes GEPA's reflection capability
def binary(example, pred, trace=None):
    return example.answer == pred.answer

# Good: Return feedback for GEPA reflection
def with_feedback(example, pred, trace=None):
    correct = example.answer.lower() in pred.answer.lower()
    feedback = "Correct" if correct else f"Expected {example.answer}"
    return float(correct), feedback
```

## Resources

- **Paper**: "DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines"
- **GEPA Paper**: Described in DSPy 3.0 release notes
- **GitHub**: https://github.com/stanfordnlp/dspy
- **Discord**: https://discord.gg/XCGy2WDCQB
