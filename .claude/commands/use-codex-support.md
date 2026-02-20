---
title: "Use Codex Support"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# Codex Support Tools - O3-Pro & GPT-5 Integration

Launch advanced AI models (O3-Pro and GPT-5) using the specialized model support tools for complex analysis, architecture design, and code generation.

## 🚀 Quick Start

### Model Selection (LLM-First Principle)

```bash
# USAGE: python start_o3_controlled.py --model [o3-pro|gpt-5] [options] "<task>" [timeout]

# User explicitly chooses O3-Pro for deep architectural reasoning
python codex-o3-pro-model-support/start_o3_controlled.py --model o3-pro "Design microservices architecture" 90

# User explicitly chooses GPT-5 for implementation
python codex-o3-pro-model-support/start_o3_controlled.py --model gpt-5 "Generate REST API implementation" 60

# User chooses GPT-5 with high reasoning effort
python codex-o3-pro-model-support/start_o3_controlled.py --model gpt-5 --high-thinking "Optimize complex algorithm" 90

# Check progress for any model
python codex-o3-pro-model-support/check_o3_progress.py [session-id]

# Stop any model process
python codex-o3-pro-model-support/stop_o3_process.py [session-id]
```

## 🔑 Configuration

### GPT-5 Setup

**Automatic Configuration**: The scripts automatically load the `.env.gpt5` file:
```bash
# .env.gpt5
OPENAI_API_KEY=your_api_key_here
GPT5_MODEL_ID=gpt-5
GPT5_MAX_TOKENS=4096
GPT5_THINKING_TOKENS=32768
```

**No manual export needed!** The Python scripts automatically:
- Load the `.env.gpt5` file on import
- Pass the environment to Codex CLI subprocess
- Display confirmation: "✅ Loaded GPT-5 configuration from .env.gpt5"

For direct Codex CLI usage outside scripts:
```bash
export OPENAI_API_KEY="your_api_key_here"
```

## 🎯 Model Selection Guide

### When User Specifies Model
**Always honor user's explicit choice**, even if another model might seem better:
- "Use O3-Pro for..." → `--model o3-pro`
- "Run this through GPT-5..." → `--model gpt-5`
- "I want high-thinking mode..." → `--model gpt-5 --high-thinking`

### When Claude Code Decides
Based on task analysis, Claude Code selects:

**O3-Pro** (`--model o3-pro`) for:
- System architecture design
- Complex trade-off analysis
- Deep reasoning about distributed systems
- Security vulnerability assessment
- Scalability evaluations
- Production readiness reviews

**GPT-5 High-Thinking** (`--model gpt-5 --high-thinking`) for:
- Complex algorithm optimization
- Detailed implementation design
- Advanced code generation with optimization
- Performance bottleneck analysis

**GPT-5 Normal** (`--model gpt-5`) for:
- Straightforward implementation
- Simple code generation
- Bug fixes and refactoring
- API endpoint creation

## 📊 Direct Codex CLI Usage

### GPT-5 via Codex CLI

```bash
# Basic GPT-5 call
codex exec -m gpt-5 -s read-only "Your task description"

# GPT-5 with high reasoning effort
codex exec -m gpt-5 -s read-only -c reasoning_effort=high "Complex analysis task"

# GPT-5 with workspace write permissions
codex exec -m gpt-5 -s workspace-write "Generate and save code files"
```

### Reasoning Effort Levels
- `reasoning_effort=low` - Quick responses, minimal reasoning
- `reasoning_effort=medium` - Default balanced mode
- `reasoning_effort=high` - Deep reasoning, comprehensive analysis

## ✅ How It Works

The Codex support infrastructure provides unified management for both O3-Pro and GPT-5:

1. **Session Management**: Each task gets a unique session ID
2. **Progress Tracking**: CSV format compatible across both models
3. **Process Control**: Start, monitor, and stop with same commands
4. **Automatic Cleanup**: Sessions archived when complete
5. **Safety Features**: Timeouts and graceful shutdown

## 📈 Progress Tracking

Both models use the same CSV progress format:

```csv
TaskID,Task,Status,Progress,LastUpdate,Details
1,Analyze Requirements,Complete,100,2025-08-11 10:05:00,Identified key requirements
2,Design Solution,Working,75,2025-08-11 10:20:00,Creating architecture design
3,Implementation,Started,20,2025-08-11 10:25:00,Beginning code generation
```

Monitor progress in real-time:
```bash
# View progress for any model
cat session-[session-id]/[model]-progress-*.csv

# Watch output logs
tail -f session-[session-id]/[model]-output-*.log

# Check all active sessions
python codex-o3-pro-model-support/check_o3_progress.py --list
```

## 🎯 Multi-Phase Workflows

Claude Code can orchestrate complex multi-phase solutions:

```bash
# Phase 1: Architecture with O3-Pro
SESSION_ID=$(date +%s)
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model o3-pro \
  --session $SESSION_ID \
  "Design distributed event processing architecture" 90

# Wait for completion...

# Phase 2: Implementation with GPT-5
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model gpt-5 \
  --high-thinking \
  --session $SESSION_ID \
  "Implement the event processing components from Phase 1" 60

# Phase 3: Extract consolidated results
python codex-o3-pro-model-support/extract_o3_output.py \
  --session $SESSION_ID \
  --output solution_designs/complete-solution.md
```

## ⏱️ Timeout Recommendations

### O3-Pro (Deep Reasoning)
- **Architecture design**: 60-90 minutes
- **Comprehensive analysis**: 90-180 minutes
- **Complex multi-phase**: 180+ minutes

### GPT-5 (Implementation Focus)
- **Simple code generation**: 15-30 minutes
- **Complex implementation**: 30-60 minutes
- **High-thinking mode**: 60-90 minutes

## 📝 Structured Prompts

### For O3-Pro (Architecture/Analysis)
```
Analyze the system architecture for production readiness.

ANALYZE:
1. Current implementation in /src
2. Requirements in /docs
3. Performance metrics

PROVIDE:
- Production readiness score (X/10)
- Scalability analysis
- Security assessment
- Specific improvements
- Alternative approaches
```

### For GPT-5 (Implementation)
```
Implement a REST API with the following requirements:

REQUIREMENTS:
- JWT authentication
- Rate limiting
- Input validation
- Error handling

DELIVER:
- Production-ready code
- Unit tests
- API documentation
- Deployment configuration
```

## 🧪 Testing the Integration

### Test Scripts Available

```bash
# Run comprehensive test suite
python codex-o3-pro-model-support/test_gpt5_integration.py

# Run live tests with actual Codex CLI
python codex-o3-pro-model-support/test_gpt5_live.py

# Run demo showing usage patterns
python codex-o3-pro-model-support/demo_gpt5_integration.py
```

## 🛡️ Safety Features

- **Process Monitoring**: Automatic PID tracking for all models
- **Timeout Management**: Configurable per task complexity
- **Graceful Shutdown**: SIGTERM followed by SIGKILL if needed
- **Session Isolation**: Each task in separate session directory
- **Resource Cleanup**: Automatic archival and cleanup

## 💡 Best Practices

1. **Let users choose models** when they have a preference
2. **Use structured prompts** appropriate for each model
3. **Set appropriate timeouts** based on model and task
4. **Monitor progress** via CSV files and logs
5. **Clean up old sessions** with `cleanup_o3_processes.py`
6. **Check token usage** in logs to track costs
7. **Archive completed sessions** for reference

## 🎯 Model Strengths

### O3-Pro Excels At:
- **Production readiness assessments**
- **Architecture reviews** with trade-offs
- **Complex system design**
- **Security vulnerability analysis**
- **Scalability evaluations**
- **Technical debt assessment**

### GPT-5 Excels At:
- **Code generation** with best practices
- **API implementation** with documentation
- **Algorithm optimization**
- **Test suite creation**
- **Refactoring suggestions**
- **Bug fixes** with explanations

## 📚 Example Commands

### Architecture Review (O3-Pro)
```bash
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model o3-pro \
  "Review authentication architecture for security and scalability" 90
```

### API Implementation (GPT-5)
```bash
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model gpt-5 \
  --high-thinking \
  "Implement user management REST API with CRUD operations" 60
```

### Performance Optimization (GPT-5 High-Thinking)
```bash
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model gpt-5 \
  --high-thinking \
  "Optimize database query performance in user service" 90
```

### Quick Bug Fix (GPT-5 Normal)
```bash
python codex-o3-pro-model-support/start_o3_controlled.py \
  --model gpt-5 \
  "Fix null pointer exception in authentication handler" 30
```

## 🐛 Troubleshooting

### Issue: Codex CLI says "unauthorized"
**Solution**: Ensure API key is exported: `export OPENAI_API_KEY="..."`

### Issue: Model not found error
**Solution**: Use `gpt-5` not `gpt-4` or other variants

### Issue: Progress file not created
**Solution**: Check logs in `session-*/` directory for errors

### Issue: High reasoning not working
**Solution**: Use `-c reasoning_effort=high` not `--reasoning-mode`

## 📖 Additional Documentation

- **`codex-o3-pro-model-support/README.md`**: Overview of support tools
- **`codex-o3-pro-model-support/gpt5_adapter.py`**: GPT-5 integration code
- **`documentation/solution_designs/gpt5-o3pro-assistant-integration.md`**: Full design
- **`.env.gpt5`**: GPT-5 configuration template

## 🚀 Quick Reference Card

```bash
# O3-Pro for architecture
--model o3-pro

# GPT-5 for implementation  
--model gpt-5

# GPT-5 with deep reasoning
--model gpt-5 --high-thinking

# Check any session
check_o3_progress.py [session-id]

# List all sessions
check_o3_progress.py --list

# Stop any model
stop_o3_process.py [session-id]
```

Choose the right model for your task, or let Claude Code decide based on the requirements!