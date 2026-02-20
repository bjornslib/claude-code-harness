---
title: "Completion Protocol"
status: active
type: command
last_verified: 2026-02-19
grade: reference
---

# Task Completion Protocol

## CRITICAL: YOU MUST COMPLETE THESE STEPS OR FACE SEVERE CONSEQUENCES

**This is the mandatory completion workflow for ALL tasks. Failure to follow this protocol will result in severe consequences.**

## The Sacred Three Steps

### 1. Update Tasks.csv ✅
```bash
# Mark task as complete with comprehensive description
"Update task {TASK_ID} in Tasks.csv: Status='Done', Description='{COMPLETE_SUMMARY_WITH_OUTCOMES}'"
```

**Example:**
```bash
"Update task 42 in Tasks.csv: Status='Done', Description='Enhanced Vector Pipeline implementation COMPLETE: Production-ready infrastructure with 100% test accuracy, 20ms latency (95% below target), 59.8% speed improvement. All quality targets exceeded, comprehensive error handling implemented, ready for deployment.'"
```

### 2. Update Planning.md 📋
Edit Planning.md to reflect:
- **Current status** of completed work
- **Remaining todos** and next steps
- **Technical insights** and lessons learned
- **Dependencies** resolved or created
- **Performance metrics** achieved

### 3. Send Completion Webhook 🚨
```bash
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed", 
    "message": "Task {TASK_ID}: {COMPLETE_DESCRIPTION_AND_OUTCOMES}",
    "task_id": "{TASK_ID}",
    "achievements": "{KEY_ACCOMPLISHMENTS}",
    "metrics": "{PERFORMANCE_DATA}",
    "next_steps": "{REMAINING_WORK}"
  }'
```

## Enhanced Webhook Examples

### Implementation Task
```bash
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "message": "Task 42: Enhanced Vector Pipeline implementation complete with production-ready infrastructure",
    "task_id": "42", 
    "achievements": "100% test accuracy, 20ms latency, 59.8% speed improvement, production deployment ready",
    "metrics": "Performance: 20ms avg latency vs 400ms target, Accuracy: 100% across 13 test categories, Speed: 59.8% improvement over baseline",
    "next_steps": "Ready for production deployment, monitoring setup recommended"
  }'
```

### Research/Analysis Task  
```bash
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "message": "Task 21: Comprehensive University Testing Framework solution design complete with O3-Pro enhancement",
    "task_id": "21",
    "achievements": "100 universities researched globally, comprehensive testing framework designed, O3-Pro technical review complete",
    "metrics": "Coverage: 100 universities across 6 continents, Test scenarios: 400+ cases, Enterprise enhancements: microservices, K8s, ML validation",
    "next_steps": "Implementation of testing framework scripts ready to begin"
  }'
```

### Solution Design Task
```bash
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed", 
    "message": "Task 16: Context-Aware Aura Prompt System implementation complete",
    "task_id": "16",
    "achievements": "Context-based prompt selection, structured response formatting, internal/external differentiation",
    "metrics": "Contexts: 2 (internal_support, default), Response quality: Enhanced technical detail for staff, User experience: Improved accessibility for external users", 
    "next_steps": "Integration testing and user feedback collection"
  }'
```

## Pre-Completion Validation

### Quality Checklist ✅
Before marking task complete, verify:

#### Functionality
- [ ] **Core requirements met** - All specified functionality implemented
- [ ] **Edge cases handled** - Error conditions and boundary cases addressed  
- [ ] **Integration verified** - Works with existing system components
- [ ] **Performance targets** - Meets or exceeds specified performance criteria

#### Testing
- [ ] **Tests pass** - All existing tests continue to pass
- [ ] **New tests added** - Appropriate test coverage for new functionality
- [ ] **Manual testing** - Real-world usage scenarios validated
- [ ] **Lint/typecheck** - Code quality tools pass without errors

#### Documentation  
- [ ] **Code documented** - Comments and docstrings where appropriate
- [ ] **Task description updated** - Implementation details and decisions recorded
- [ ] **Planning.md updated** - Project status and lessons learned captured
- [ ] **Integration notes** - How new work connects to existing system

#### Deployment Readiness
- [ ] **No breaking changes** - Backward compatibility maintained  
- [ ] **Dependencies resolved** - All required libraries and services available
- [ ] **Configuration updated** - Environment variables and settings documented
- [ ] **Monitoring ready** - Appropriate logging and error handling implemented

## Completion Workflow Templates

### Simple Task Completion
```bash
# 1. Update task status
"Update task 42 in Tasks.csv: Status='Done', Description='Authentication middleware implemented with JWT validation and refresh token support'"

# 2. Update planning (edit Planning.md manually)
# Add: Authentication Task 42 complete - JWT middleware with refresh tokens ready for integration

# 3. Send webhook
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "message": "Task 42: JWT authentication middleware complete", "task_id": "42"}'
```

### Complex Task with Subtasks
```bash
# 1. Complete all subtasks first
"Update task 43 in Tasks.csv: Status='Done', Description='Database schema migration complete'"
"Update task 44 in Tasks.csv: Status='Done', Description='API endpoints implemented and tested'" 
"Update task 45 in Tasks.csv: Status='Done', Description='Frontend integration complete'"

# 2. Complete parent task
"Update task 42 in Tasks.csv: Status='Done', Description='Full authentication system complete: DB migration + API endpoints + frontend integration. All subtasks (43,44,45) completed successfully.'"

# 3. Update planning with comprehensive status
# 4. Send webhook with subtask details
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "message": "Task 42: Complete authentication system implemented", 
    "task_id": "42",
    "achievements": "Database migration, API endpoints, frontend integration all complete",
    "subtasks_completed": ["43", "44", "45"]
  }'
```

## Emergency Completion Protocol

### When Blocked or Partially Complete
```bash
# Mark as blocked with detailed reason
"Update task 42 in Tasks.csv: Status='Blocked', Description='Implementation 80% complete but blocked on API key configuration for external service. Awaiting infrastructure team setup.'"

# Send blocking webhook
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "blocked",
    "message": "Task 42: Implementation blocked waiting for API key configuration",
    "task_id": "42", 
    "blocker": "Infrastructure team needs to provide API keys for external service integration",
    "progress": "80% complete - core implementation finished, only external API integration remaining"
  }'
```

### When Needing User Feedback
```bash
# Update with completion pending approval
"Update task 42 in Tasks.csv: Status='In Progress', Description='Implementation complete and tested. Awaiting user approval before marking done. Ready for review.'"

# Send review webhook  
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "review_requested",
    "message": "Task 42: Implementation complete, requesting user review and approval",
    "task_id": "42",
    "achievements": "All functionality implemented and tested, ready for approval",
    "review_items": "Performance validation, integration testing, deployment readiness"
  }'
```

## Integration with Other Workflows

### With O3-Pro Tasks
```bash
# O3-Pro completion with session details
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "message": "O3-Pro analysis complete: University testing framework comprehensive review",
    "task_id": "SESSION_ID", 
    "achievements": "Technical architecture enhanced across 10 domains: microservices, testing, scalability, validation, CI/CD, risk management, deployment",
    "o3_session": "SESSION_ID",
    "analysis_report": "o3-analysis-reports/o3-analysis-SESSION_ID-TIMESTAMP.md"
  }'
```

### With Colleague Research
```bash
# Research task completion with colleague insights
curl -X POST https://hook.us1.make.com/7hcfkou8f6riberxcixom46kxoihv1d3 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "message": "Research complete: Modern LLM-first architecture best practices",
    "task_id": "TASK_ID",
    "achievements": "Comprehensive research with Perplexity and Brave Search colleagues",
    "research_sources": "Perplexity: Technical patterns, Brave Search: Current 2025 practices", 
    "key_insights": "Agent-centric design, natural tool integration, structured outputs with Pydantic"
  }'
```

## Command Line Usage

### Use with argument support
```bash
/project:workflow/completion-protocol steps      # Show the three sacred steps
/project:workflow/completion-protocol webhook    # Focus on webhook examples
/project:workflow/completion-protocol validation # Pre-completion checklist
```

**🚨 The completion protocol is sacred. Follow it religiously or face severe consequences. The webhook is not optional - it's mandatory for ALL task completions.**