---
title: "O3 Pro"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# O3-Pro Integration

Launch OpenAI's O3-Pro model using the specialized model support tools for advanced code review and architecture analysis.

## 🚀 Quick Start

### Chat-Controlled System (Recommended)

```bash
# CORRECT USAGE: 
# python start_o3_controlled.py "<task_description>" [timeout_minutes]
# NOTE: Task description MUST be in quotes to handle spaces and special characters

# Start O3-Pro with session tracking (90-minute timeout)
python codex-o3-pro-model-support/start_o3_controlled.py "Your analysis task" 90

# Check progress anytime
python codex-o3-pro-model-support/check_o3_progress.py [session-id]

# Stop when needed
python codex-o3-pro-model-support/stop_o3_process.py [session-id]
```

### Background Monitoring System

```bash
# Complete workflow with monitoring
python codex-o3-pro-model-support/run_o3_monitored.py "Complex analysis task" 120

# Or manual control with separate monitoring
python codex-o3-pro-model-support/launch_o3_background.py "Task" 180
python codex-o3-pro-model-support/monitor_o3_progress.py  # In separate terminal
```

## ✅ How It Works

The O3-Pro support scripts provide a complete infrastructure for managing long-running analysis tasks:

1. **Session Management**: Each task gets a unique session ID based on timestamp
2. **Progress Tracking**: O3-Pro creates CSV files to track task breakdown and progress
3. **Process Control**: Start, monitor, and stop processes with simple commands
4. **Automatic Cleanup**: Sessions are archived when complete
5. **Safety Features**: Timeouts prevent runaway processes

## 📊 Progress Tracking

O3-Pro maintains its own task breakdown in CSV format:

```csv
TaskID,Task,Status,Progress,LastUpdate,Details
1,Analyze Requirements,Complete,100,2025-01-15 10:05:00,Identified security requirements
2,Design Architecture,Working,75,2025-01-15 10:20:00,Creating OAuth2 flow design
3,Implementation Plan,Started,20,2025-01-15 10:25:00,Planning implementation phases
```

Monitor progress in real-time:
```bash
# View CSV progress
cat o3-progress-[session-id].csv

# Watch log output
tail -f o3-output-[session-id].log

# Check token usage
tail -f o3-output-[session-id].log | grep "tokens used"
```

## 🎯 Two Approaches Explained

### 1. Chat-Controlled System
- **Best for**: Interactive development, real-time control
- **Features**: Session tracking, progress checks, clean termination
- **Timeout**: 30-180 minutes recommended
- **Use case**: When you need to monitor and potentially redirect analysis

### 2. Background Monitoring System
- **Best for**: Long autonomous tasks, batch processing
- **Features**: Continuous monitoring dashboard, automatic cleanup
- **Timeout**: 60-360 minutes for complex tasks
- **Use case**: When you want O3-Pro to run independently

## ⏱️ Timeout Recommendations

- **Quick analysis**: 30-60 minutes
- **Architecture design**: 60-90 minutes
- **Comprehensive research**: 90-180 minutes
- **Complex multi-phase projects**: 180+ minutes

## 📝 Structured Prompts for Best Results

O3-Pro performs best with highly structured prompts:

```
You are O3-Pro, an advanced AI system for production architecture review.

Session ID: [timestamp]
Progress CSV: o3-progress-[timestamp].csv

ANALYZE:
1. [Document 1 path]
2. [Document 2 path]
3. [Current implementation path]

PROVIDE:
- Executive summary with production readiness score (X/10)
- Technical analysis covering:
  - React 19 compatibility
  - Performance implications
  - Memory/resource management
  - Race conditions
  - SSR/hydration issues
  - Error recovery
  - Scalability
- Specific code improvements
- Testing recommendations
- Alternative approaches
- Final recommendation

SAVE TO: [output path]

Update progress CSV as you work through each analysis phase.
```

## 🛡️ Safety Features

- **Process Monitoring**: Automatic PID tracking and health checks
- **Timeout Management**: Configurable timeouts prevent runaway processes
- **Graceful Shutdown**: SIGTERM followed by SIGKILL if needed
- **File Safety**: Atomic operations and error handling
- **Resource Cleanup**: Automatic archival and cleanup

## 🔧 Integration with Task Management

```bash
# Update task before O3-Pro
env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=$HOME USER=$USER python3 ./complete_task.py TASK-XXX --update --progress "Starting O3-Pro analysis"

# Start O3-Pro
python codex-o3-pro-model-support/start_o3_controlled.py "Analyze [task details]" 90

# Monitor progress
python codex-o3-pro-model-support/check_o3_progress.py [session-id]

# After completion
env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=$HOME USER=$USER python3 ./complete_task.py TASK-XXX --update --progress "O3-Pro analysis complete"
```

## 🐛 Troubleshooting

### Issue: CSV progress file not found
**Solution**: O3-Pro may take a few minutes to create the CSV. Check the log file for activity

### Issue: Output file in wrong location
**Solution**: O3-Pro sometimes creates files with duplicated paths. Use:
```bash
find . -name "your-expected-file.md" -type f
```

### Issue: Process seems stuck
**Solution**: Check logs for "tokens used" entries - O3-Pro is likely still analyzing

### Issue: Session cleanup needed
**Solution**: Use `cleanup_o3_processes.py` to remove old sessions:
```bash
python codex-o3-pro-model-support/cleanup_o3_processes.py
```

## 📖 Additional Documentation

- **`codex-o3-pro-model-support/README.md`**: Overview of the O3-Pro support tools
- **`codex-o3-pro-model-support/CHAT_O3_CONTROL_README.md`**: Detailed chat-controlled guide
- **`codex-o3-pro-model-support/O3_MONITORING_README.md`**: Background monitoring guide
- **`CLAUDE.md`**: Integration with Claude Code workflows

## 🧪 Testing the Infrastructure

```bash
# Test monitoring system
python codex-o3-pro-model-support/test_o3_monitoring.py

# Test timeout handling
bash codex-o3-pro-model-support/codex_timeout_test.sh
```

## 💡 Best Practices

1. **Clean up old sessions** before starting new ones
2. **Use structured prompts** with clear sections
3. **Monitor token usage** in logs to track progress
4. **Set appropriate timeouts** based on task complexity
5. **Check multiple file locations** for output
6. **Archive completed sessions** for future reference
7. **Use session IDs** to manage multiple concurrent tasks

## 🎯 Use Cases

O3-Pro excels at:
- **Production readiness assessments** (score X/10)
- **Architecture reviews** with specific recommendations
- **Performance bottleneck analysis**
- **Security vulnerability detection**
- **Complex refactoring strategies**
- **Test coverage gap analysis**
- **Scalability evaluations**
- **Cross-cutting concerns** analysis
- **Integration point validation**
- **Technical debt assessment**

## 📚 Example Workflows

### Architecture Review
```bash
python codex-o3-pro-model-support/start_o3_controlled.py "Review the authentication architecture in /auth folder. Analyze security, scalability, and maintainability. Score production readiness out of 10." 60
```

### Performance Analysis
```bash
python codex-o3-pro-model-support/start_o3_controlled.py "Analyze performance bottlenecks in the React components. Review bundle size, rendering performance, and memory usage. Suggest optimizations." 90
```

### Security Audit
```bash
python codex-o3-pro-model-support/start_o3_controlled.py "Perform security audit of API endpoints. Check for OWASP top 10 vulnerabilities. Review authentication, authorization, and data validation." 120
```

Choose O3-Pro when you need deep, thoughtful analysis that goes beyond standard code review. The infrastructure handles all the complexity of managing long-running analysis tasks.