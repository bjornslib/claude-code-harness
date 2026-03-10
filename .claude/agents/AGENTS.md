# Agent Directory - Worker Menu

## Overview
This directory lists all available AI agents in the system with their specializations and appropriate use cases. Use this as a reference to select the right agent for your specific task.

## Specialized Workers

### [Frontend Dev Expert](../.claude/agents/frontend-dev-expert.md)
- **Specialization**: Modern web technologies, UI/UX implementation, React/Vue/Angular, component architecture
- **Best for**: Frontend development, UI implementation, responsive design, client-side logic
- **Triggers**: "I need to create a login form", "mobile layout is broken", "CSS performance optimization needed"
- **Capabilities**: React, TypeScript, Tailwind, CSS, responsive design, UI architecture

### [Backend Solutions Engineer](../.claude/agents/backend-solutions-engineer.md)
- **Specialization**: Python backend, APIs, databases, PydanticAI agents, pydantic-graph workflows
- **Best for**: API development, database operations, server-side logic, backend infrastructure
- **Triggers**: "Create an API endpoint", "PydanticAI agent debugging", "Database integration needed"
- **Capabilities**: FastAPI, Pydantic, PydanticAI, SQLAlchemy, database design, server-side architecture

### [TDD Test Engineer](../.claude/agents/tdd-test-engineer.md)
- **Specialization**: Automated testing, test-driven development, CI/CD, unit/integration/e2e testing
- **Best for**: Writing comprehensive tests, test architecture, test execution and analysis
- **Triggers**: "Write tests for feature X", "Test coverage improvement", "Bug reproduction via testing"
- **Capabilities**: Pytest, Jest, Playwright, testing frameworks, TDD methodology, CI/CD integration

### [Solution Architect](../.claude/agents/solution-architect.md)
- **Specialization**: High-level design, architecture decisions, technical planning, system design
- **Best for**: System architecture, technical planning, technology choices, solution design
- **Triggers**: "Design solution for X", "Architectural review needed", "Technology stack decisions"
- **Capabilities**: System design, architectural patterns, PRD analysis, technology evaluation

### [UX Designer](../.claude/agents/ux-designer.md)
- **Specialization**: UX audits, design concepts, UI mockups, user experience optimization
- **Best for**: UX analysis, design briefs, UI concept creation, user journey mapping
- **Triggers**: "Audit our dashboard UX", "Create design concepts", "User experience review"
- **Capabilities**: UX auditing, design concepts, UI mockups, user research, design-to-code translation

## Validation and Quality

### [Validation Test Agent](../.claude/agents/validation-test-agent.md)
- **Specialization**: PRD acceptance validation, technical verification, requirement compliance
- **Best for**: Verifying implementations meet requirements, acceptance testing, validation
- **Triggers**: "Validate implementation", "Run acceptance tests", "Does it work?", "PRD compliance check"
- **Capabilities**: PRD validation, acceptance testing, technical verification, compliance checking

### [Code Review Agent](../.claude/agents/code-reviewer.md)
- **Specialization**: Code quality assessment, best practices enforcement, security review
- **Best for**: Code review, quality assurance, security scanning, best practice validation
- **Triggers**: "Review authentication implementation", "Security review needed", "Code quality assessment"
- **Capabilities**: Code analysis, security review, best practices, quality metrics

## Coordination and Management

### [Orchestrator](../.claude/output-styles/orchestrator.md)
- **Specialization**: Multi-agent coordination, task delegation, workflow management
- **Best for**: Coordinating complex multi-agent tasks, project management, delegation
- **Triggers**: "Coordinate complex feature development", "Multi-agent workflow needed", "Project orchestration"
- **Capabilities**: Agent coordination, task delegation, workflow management, progress tracking

### [System 3 Meta-Orchestrator](../.claude/output-styles/system3-meta-orchestrator.md)
- **Specialization**: Strategic planning, OKR tracking, business validation, high-level coordination
- **Best for**: Strategic initiatives, business validation, high-level goal tracking
- **Triggers**: "Strategic planning needed", "Business validation required", "OKR alignment check"
- **Capabilities**: Strategic planning, business validation, OKR tracking, high-level coordination

## Agent Selection Guidelines

### When to Use Each Agent Category

#### Investigation Phase
- **General Purpose Agent**: Initial exploration, codebase understanding, research
- **Explore Agent**: Codebase navigation, pattern searching, architectural analysis

#### Planning Phase
- **Solution Architect**: System design, technical planning, PRD analysis
- **UX Designer**: UX audits, design concepts, UI planning

#### Implementation Phase
- **Frontend Dev Expert**: Frontend development, UI implementation
- **Backend Solutions Engineer**: Backend development, API implementation
- **General Purpose**: Simple implementation tasks that don't require specialization

#### Validation Phase
- **TDD Test Engineer**: Test implementation and execution
- **Validation Test Agent**: PRD compliance and acceptance testing
- **Code Review Agent**: Quality and security review

#### Coordination Phase
- **Orchestrator**: Multi-agent task coordination
- **System 3**: Strategic oversight and business validation

## Agent Communication Protocols

### Handoff Procedures
1. **Agent A to Agent B**: When transferring work between agents, clearly document:
   - Current state of the task
   - Completed components
   - Remaining work to be done
   - Known issues or constraints
   - Expected deliverables

2. **Escalation Procedures**: If an agent encounters a problem outside its scope:
   - Document the issue with specific context
   - Identify the appropriate specialized agent
   - Transfer the context cleanly to the next agent

### Collaboration Patterns
- **Sequential**: One agent completes work, then hands off to next agent
- **Parallel**: Multiple agents work on independent components simultaneously
- **Validation Loop**: Implementation agent works, validation agent verifies, repeat as needed

## Agent Boundaries and Responsibilities

### Frontend vs Backend
- **Frontend**: UI, client-side logic, user interaction, styling
- **Backend**: APIs, databases, server-side logic, data processing

### Architecture vs Implementation
- **Solution Architect**: Design decisions, system architecture, technology choices
- **Implementation Agents**: Execute the designed solution

### Validation vs Execution
- **Validation Agents**: Verify correctness, compliance, quality
- **Execution Agents**: Perform the actual implementation work

## Capability Matrix

| Agent | Tech Stack | Validation | Coordination | Specialization Focus |
|-------|------------|------------|--------------|---------------------|
| Frontend Dev Expert | React, TS, CSS | Self-validation | None | UI/UX Implementation |
| Backend Solutions Engineer | Python, FastAPI, DBs | Self-validation | None | Backend Implementation |
| TDD Test Engineer | Testing frameworks | Strong | None | Test Architecture |
| Solution Architect | Architecture tools | Design validation | Light | System Design |
| Validation Test Agent | N/A (reads existing) | Strong | None | Compliance Validation |
| Orchestrator | Multi-agent tools | Light | Heavy | Task Coordination |

## Decision Tree for Agent Selection

When faced with a task, follow this decision tree:

1. **Is it strategic/business-level?**
   - Yes → System 3 Meta-Orchestrator
   - No → Continue to 2

2. **Is it coordination/management of multiple agents?**
   - Yes → Orchestrator
   - No → Continue to 3

3. **Is it design/planning/architecture?**
   - Yes → Solution Architect
   - No → Continue to 4

4. **Is it validation/compliance/checking?**
   - Yes → Validation Test Agent or Code Review Agent
   - No → Continue to 5

5. **Is it frontend/UI focused?**
   - Yes → Frontend Dev Expert
   - No → Continue to 6

6. **Is it backend/server-side focused?**
   - Yes → Backend Solutions Engineer
   - No → General Purpose Agent

7. **Is it testing focused?**
   - Yes → TDD Test Engineer
   - No → General Purpose Agent

## Troubleshooting Common Issues

### Agent Not Appropriate for Task
If the selected agent seems inappropriate, use the decision tree above to reassess, or consult with an Orchestrator or System 3 agent.

### Agent Unable to Complete Task
If an agent encounters a limitation:
1. Document the specific constraint
2. Identify the required capability
3. Escalate to the appropriate specialized agent
4. Provide full context to the next agent

### Agent Communication Failures
If agents aren't communicating effectively:
1. Ensure proper handoff documentation
2. Verify the receiving agent has necessary context
3. Consider using an Orchestrator to coordinate