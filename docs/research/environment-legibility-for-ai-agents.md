# Environment Legibility for AI Agents: Making Codebases Discoverable

## Overview
This document outlines best practices for making codebases discoverable and navigable for AI agents and workers. Based on research from Martin Fowler, OpenAI, Anthropic, and other industry leaders, it provides practical guidance for creating legible environments that enable effective AI agent operation.

## 1. Repository-Level Documentation for Workers

AI agents and workers require specific documentation to understand and navigate codebases effectively. The following documentation should be present at the repository level:

### Essential Documentation Files:
- **`CLAUDE.md`**: Contains project-specific guidelines, coding standards, architectural decisions, and development workflows that override general best practices
- **`README.md`**: High-level overview of the project, setup instructions, and key entry points
- **`ARCHITECTURE.md`**: System architecture diagrams, component relationships, and technical design overview
- **`TOC.md` or `INDEX.md`**: Table of contents linking to major documentation sections and code areas

### Architecture Documentation Components:
The repository should contain architectural diagrams showing:
- Component relationships and data flows
- Dependency maps (both internal and external dependencies)
- Service boundaries and integration points
- Technology stack and framework relationships

## 2. Structuring AGENTS.md as a 'Menu' for Worker Discovery

The agents documentation should serve as a clear menu system for discovering the right worker for specific tasks. Here's the recommended structure:

```markdown
# Agent Directory - Worker Menu

## Specialized Workers

### [Frontend Dev Expert](./agents/frontend-dev-expert.md)
- **Specialization**: Modern web technologies, UI/UX implementation, React/Vue/Angular
- **Best for**: Frontend development, component architecture, responsive design
- **Triggers**: "I need to create a login form", "mobile layout is broken"

### [Backend Solutions Engineer](./agents/backend-solutions-engineer.md)
- **Specialization**: Python backend, APIs, databases, PydanticAI agents
- **Best for**: API development, database operations, server-side logic
- **Triggers**: "Create an API endpoint", "PydanticAI agent debugging"

### [TDD Test Engineer](./agents/tdd-test-engineer.md)
- **Specialization**: Automated testing, test-driven development, CI/CD
- **Best for**: Writing comprehensive tests, test architecture
- **Triggers**: "Write tests for feature X", "Test coverage improvement"

### [Solution Architect](./agents/solution-architect.md)
- **Specialization**: High-level design, architecture decisions, technical planning
- **Best for**: System design, architectural patterns, technology choices
- **Triggers**: "Design solution for X", "Architectural review needed"

## Validation and Quality

### [Validation Test Agent](./agents/validation-test-agent.md)
- **Specialization**: PRD acceptance validation, technical verification
- **Best for**: Verifying implementations meet requirements
- **Triggers**: "Validate implementation", "Run acceptance tests", "Does it work?"

## Usage Guidelines

### When to Use Each Agent
- **Investigation**: Use general agents or orchestrators for analysis
- **Implementation**: Delegate to specialized workers based on technology domain
- **Validation**: Always use validation-test-agent before task completion
- **Architecture**: Engage solution architect for significant design decisions

### Interaction Patterns
- Agents are invoked with specific skills and contexts
- Workers focus on implementation while orchestrators coordinate
- Validation happens in layers: unit, integration, end-to-end
```

## 3. Boundary Invariants and Linting Rules

To prevent drift and maintain consistency for AI agents, boundary invariants should be implemented:

### Linter Rules:
- **Code formatting**: Enforce consistent style for readability by AI agents
- **Import validation**: Prevent circular dependencies and improper layering
- **Naming conventions**: Maintain consistent terminology across the codebase
- **Documentation requirements**: Ensure critical functions/classes have proper documentation

### Schema Validation:
- **Configuration schemas**: Ensure configuration files follow predefined schemas
- **API contracts**: Validate that interfaces maintain backward compatibility
- **Data schemas**: Ensure data structures remain consistent across services

### Structured Logging:
- **Consistent log formats**: Enable AI agents to parse and analyze logs effectively
- **Context preservation**: Include relevant contextual information in logs
- **Severity classification**: Clear categorization for automated log analysis

## 4. Plans, Progress Logs, and Decision History as Git-Committed Artifacts

### Git-Committed Artifacts for Worker State Persistence:

#### Planning Artifacts:
- **PRD files** (`docs/prds/`): Product requirement documents in version control
- **Solution designs** (`docs/sds/`): Technical solution architectures
- **Task breakdowns**: Individual task specifications and acceptance criteria

#### Progress Tracking:
- **Decision logs** (`decisions/`): Architectural decision records (ADRs)
- **Progress logs** (`progress/`): Chronological progress tracking
- **Evidence files** (`evidence/`): Validation evidence and test results

#### Version Control Strategy:
- Commit decisions and plans as artifacts in the repository
- Use descriptive commit messages explaining the reasoning behind decisions
- Maintain change logs to track evolution of architecture and decisions
- Tag important milestones and releases for easy reference

## 5. Best Practices for AI Agent Discoverability

### Naming Conventions
- Use clear, consistent naming across all files, directories, and variables
- Employ kebab-case for directories and file names
- Use descriptive names that convey purpose and function
- Follow consistent abbreviations and acronyms

### Documentation Standards
- Maintain frontmatter in all documentation files with:
  - title: Human-readable title
  - status: active | draft | archived | deprecated
  - type: skill | agent | output-style | guide | etc.
  - last_verified: YYYY-MM-DD format
  - grade: authoritative | reference | archive | draft

### Cross-Link Integrity
- All relative markdown links must resolve to real files
- Use relative paths consistently
- Maintain link validity during refactoring
- Include alternative pathways for critical navigation

### Context Provision
- Provide sufficient context for AI agents to understand their operating environment
- Include architectural context in all technical decisions
- Maintain living documentation that evolves with the codebase
- Use consistent terminology across all documentation

## 6. Comparison Against Current Implementation

### Current State Analysis:
The current implementation demonstrates many best practices:

✅ **Positive aspects:**
- Clear specialization and role definitions for each agent
- Well-defined trigger conditions and use cases
- Model-specific configurations (Sonnet for complex tasks, Haiku for simple tasks)
- Skill requirement declarations to guide proper tool usage
- YAML frontmatter with metadata (title, status, type, last_verified, grade)

⚠️ **Areas for improvement:**
- Centralized AGENTS.md menu could be implemented
- More explicit cross-linking between related agents
- Additional guidance on agent handoff protocols
- Clearer documentation of boundary conditions between agents

### Recommended Actions:
1. Create AGENTS.md as a central directory linking all agent documentation
2. Add dependency graphs showing how agents interact with each other
3. Document escalation procedures for when one agent needs assistance from another
4. Include failure scenarios and recovery patterns for each agent type
5. Add competency matrices showing what each agent can/cannot do
6. Implement the doc-gardener linter to enforce documentation standards
7. Establish staleness thresholds for documentation review

## 7. Implementation Checklist

Use this checklist to ensure your codebase is legible for AI agents:

### Documentation
- [ ] All essential documentation files are present and up-to-date
- [ ] Architecture diagrams clearly show component relationships
- [ ] AGENTS.md exists as a centralized menu for worker discovery
- [ ] All documentation follows consistent naming and structure

### Codebase Structure
- [ ] Clear directory structure with consistent naming conventions
- [ ] Configuration files follow predictable patterns
- [ ] Logging is structured and consistent across services

### Validation and Quality
- [ ] Linters enforce code quality and naming conventions
- [ ] Schema validation is applied to configuration files
- [ ] Documentation linting ensures cross-links are valid
- [ ] Frontmatter requirements are enforced for documentation

### Git Practices
- [ ] Plans and decisions are committed as artifacts
- [ ] Progress tracking is maintained in version control
- [ ] Evidence and validation results are persisted
- [ ] Change logs document evolution of the codebase

## Conclusion

Creating legible environments for AI agents requires a combination of thoughtful documentation, consistent naming conventions, proper tooling, and disciplined git practices. By following these guidelines, teams can ensure their codebases are discoverable, navigable, and maintainable by AI agents, leading to more effective and reliable automated development processes.