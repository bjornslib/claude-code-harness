---
title: "Task Csv"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# Task CSV Management Guide

## CSV Task Management Protocol
**Tasks.csv is the single source of truth for all project tasks and progress tracking.**

## Core Task Management Rules

### One Task Rule
- **Only ONE task "In Progress" per assignee at a time**
- Complete current task before starting new one
- Mark tasks "Blocked" if unable to proceed

### Status Transitions
```
To Do → In Progress → Done
To Do → In Progress → Blocked → In Progress → Done
```

### CSV Structure
```csv
Task ID,Task Name,Description,Status,Assignee,Start Date,Due Date,Parent Task
```

## Daily Task Queries

### Check Your Work
```bash
# View my assigned tasks
"List tasks from Tasks.csv where Assignee='Claude' and Status='To Do'"

# Check current work in progress
"Show tasks from Tasks.csv where Assignee='Claude' and Status='In Progress'"

# Find blocking issues
"List tasks from Tasks.csv where Status='Blocked'"
```

### Priority Management
```bash
# Order by due date
"Show tasks from Tasks.csv where Status='To Do' ordered by Due Date"

# Check dependencies
"Show all tasks from Tasks.csv where Parent Task=42"

# Find subtasks
"List tasks from Tasks.csv where Parent Task IS NOT NULL"
```

### Progress Analysis
```bash
# Count tasks by status
"Count tasks by Status from Tasks.csv where Assignee='Claude'"

# Completed today  
"Show tasks from Tasks.csv where Status='Done' and Start Date='2025-06-18'"

# Upcoming deadlines
"Show tasks from Tasks.csv where Due Date<='2025-06-25' and Status!='Done'"
```

## Task Updates

### Starting Work
```bash
# Claim and start task
"Update task 42 in Tasks.csv: Status='In Progress', Start Date='2025-06-18'"

# With semantic insights
"Update task 42 in Tasks.csv: Status='In Progress', Start Date='2025-06-18', Description='Starting implementation of vector pipeline optimization with BM25+semantic fusion approach'"
```

### Progress Updates
```bash
# Add implementation details
"Update task 42 in Tasks.csv: Description='Implemented PostgreSQL connection pooling and VectorStoreManager with modern LlamaIndex patterns'"

# Mark blocking issue
"Update task 42 in Tasks.csv: Status='Blocked', Description='Waiting for Cohere API key configuration'"

# Resolve blocker
"Update task 42 in Tasks.csv: Status='In Progress', Description='Resolved: Added Cohere API key to environment configuration'"
```

### Task Completion
```bash
# Complete with summary
"Update task 42 in Tasks.csv: Status='Done', Description='Successfully implemented Enhanced Vector Pipeline with 100% test accuracy and 20ms latency performance'"

# Include test results
"Update task 42 in Tasks.csv: Status='Done', Description='Vector pipeline complete: 100% accuracy across 13 test categories, 59.8% speed improvement, production-ready'"
```

## Task Creation

### New Tasks
```bash
# Create new task
"Add to Tasks.csv: Task ID=50, Task Name='Setup monitoring', Status='To Do', Assignee='Claude', Due Date='2025-06-30'"

# With parent task relationship
"Add to Tasks.csv: Task Name='Configure Prometheus', Parent Task=50, Assignee='Claude', Status='To Do'"
```

### Subtask Management
```bash
# Create subtask for complex work
"Add to Tasks.csv: Task Name='Implement BM25Retriever integration', Parent Task=42, Assignee='Claude', Status='To Do', Due Date='2025-06-19'"

# Link related work
"Add to Tasks.csv: Task Name='Test Enhanced Vector Pipeline', Parent Task=42, Assignee='Claude', Status='To Do', Due Date='2025-06-20'"
```

### Task Dependencies
```bash
# Create dependent task
"Add to Tasks.csv: Task Name='Deploy to production', Parent Task=42, Assignee='DevOps', Status='To Do', Due Date='2025-06-25'"

# Check prerequisites
"Show all tasks from Tasks.csv where Task ID IN (SELECT DISTINCT Parent Task FROM Tasks.csv WHERE Task ID=45)"
```

## Semantic Metadata Integration

### Enhanced Descriptions
When updating task descriptions, include:
- **Technical approach** used
- **Key decisions** made  
- **Performance metrics** achieved
- **Blockers encountered** and resolutions
- **Test results** and validation
- **Integration points** with other tasks

### Example Enhanced Updates
```bash
# Technical implementation details
"Update task 42 in Tasks.csv: Description='Enhanced Vector Pipeline: Implemented production DatabasePoolManager with asyncpg (5-50 connections), VectorStoreManager using SupabaseVectorStore with modern LlamaIndex .as_retriever() patterns, EnhancedRerankerSystem with Cohere API + local fallback, PydanticAI ValidationAgent following Context7 best practices'"

# Performance and testing results  
"Update task 42 in Tasks.csv: Description='Testing complete: 100% accuracy across all 13 test categories (misspellings, abbreviations, international names), 20ms average latency (95% below 400ms target), 59.8% speed improvement over baseline. Production-ready with comprehensive error handling.'"

# Architectural insights
"Update task 42 in Tasks.csv: Description='Architecture insight: BM25+Semantic fusion with Cohere reranking provides optimal accuracy/performance balance. Key pattern: Load complete datasets into agent context rather than pre-filtering for LLM-first architecture.'"
```

## Integration with TodoWrite

### Complex Task Breakdown
For tasks requiring 3+ steps, use TodoWrite for immediate tracking:

```python
# Use TodoWrite for subtask tracking within larger CSV task
TodoWrite([
  {"content": "Setup database connection pooling", "status": "pending", "priority": "high"},
  {"content": "Implement VectorStoreManager", "status": "pending", "priority": "high"},  
  {"content": "Create EnhancedRerankerSystem", "status": "pending", "priority": "medium"}
])
```

### Sync Completion Status
```bash
# Mark TodoWrite items complete, then update CSV task
"Update task 42 in Tasks.csv: Status='Done', Description='All subtasks completed: DatabasePoolManager, VectorStoreManager, EnhancedRerankerSystem implemented and tested'"
```

## Quality Assurance

### Before Marking Done
Verify task completion criteria:
1. **Functionality works** as specified
2. **Tests pass** (run lint/typecheck if available)
3. **No breaking changes** to existing code
4. **Documentation updated** if required
5. **Performance metrics** meet targets
6. **Integration verified** with dependent tasks

### Completion Validation
```bash
# Document completion verification
"Update task 42 in Tasks.csv: Status='Done', Description='Enhanced Vector Pipeline COMPLETE: All functionality implemented ✓, 100% test pass rate ✓, Performance targets exceeded ✓, Production deployment ready ✓, Documentation updated ✓'"
```

## Advanced Queries

### Complex Analysis
```bash
# Find overdue tasks
"Show tasks from Tasks.csv where Due Date < '2025-06-18' and Status != 'Done'"

# Workload analysis by assignee
"Count tasks by Assignee and Status from Tasks.csv"

# Find orphaned subtasks
"Show tasks from Tasks.csv where Parent Task IS NOT NULL and Parent Task NOT IN (SELECT Task ID FROM Tasks.csv)"

# Dependency chain analysis  
"Show tasks from Tasks.csv where Task ID IN (SELECT Parent Task FROM Tasks.csv WHERE Assignee='Claude')"
```

### Historical Analysis
```bash
# Completed work this week
"Show tasks from Tasks.csv where Status='Done' and Start Date >= '2025-06-15'"

# Average task completion time
"Show Task ID, Task Name, Start Date, (current_date - Start Date) as Duration from Tasks.csv where Status='Done'"

# Success rate analysis
"Show Status, COUNT(*) as Count from Tasks.csv GROUP BY Status"
```

## Error Handling

### Common Issues
1. **Task ID conflicts**: Check existing IDs before creating new tasks
2. **Parent task references**: Verify parent task exists before creating subtasks  
3. **Date formatting**: Use YYYY-MM-DD format consistently
4. **Status values**: Use exact values: "To Do", "In Progress", "Done", "Blocked"

### Recovery Patterns
```bash
# Fix incorrect status
"Update task 42 in Tasks.csv: Status='In Progress'"

# Correct assignee
"Update task 42 in Tasks.csv: Assignee='Claude'"

# Update due date
"Update task 42 in Tasks.csv: Due Date='2025-06-25'"
```

## Command Line Integration

### Use with argument support
```bash
# Task management with specific focus
/project:management/task-csv query        # Focus on querying tasks
/project:management/task-csv update       # Focus on updating tasks  
/project:management/task-csv create       # Focus on creating tasks
/project:management/task-csv examples     # Show example commands
```

**📋 Master CSV task management for systematic project tracking with semantic metadata and quality assurance integration.**