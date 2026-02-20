---
title: "Explore Prompts"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Explore Agent Prompt Templates

Comprehensive collection of prompt templates for common codebase navigation tasks.

---

## 1. File Discovery Prompts

### Find Definition
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find definition of [SYMBOL_NAME]

SEARCH FOR:
- Class definition: class [SYMBOL_NAME]
- Function definition: def [SYMBOL_NAME] or function [SYMBOL_NAME]
- Variable/constant definition
- Type definition

RETURN:
{
  "definition": {
    "file": "path/to/file.py",
    "line": 42,
    "type": "class|function|variable",
    "signature": "full signature or declaration"
  },
  "related": [
    {"file": "...", "line": N, "relationship": "imports|extends|uses"}
  ]
}"""
)
```

### Find All Implementations
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find all implementations of interface/protocol [NAME]

SEARCH FOR:
- Classes that implement [NAME]
- Classes that inherit from [NAME]
- Functions that satisfy [NAME] protocol

RETURN:
{
  "interface": "[NAME]",
  "implementations": [
    {
      "file": "path/to/impl.py",
      "line": N,
      "class_name": "ConcreteImpl",
      "methods_implemented": ["method1", "method2"]
    }
  ],
  "total": N
}"""
)
```

### Find Entry Points
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find application entry points

SEARCH FOR:
- main() functions
- if __name__ == "__main__" blocks
- FastAPI/Flask app definitions
- Next.js page components
- CLI entry points (argparse, click)

RETURN:
{
  "entry_points": [
    {
      "file": "path/to/main.py",
      "type": "cli|web|api|worker",
      "description": "Main API server entry point"
    }
  ]
}"""
)
```

---

## 2. Pattern Search Prompts

### Find API Endpoints
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find all API endpoints

SEARCH FOR:
- @app.get, @app.post, @app.put, @app.delete decorators
- @router.* decorators
- FastAPI route definitions
- Express.js routes (app.get, router.get)

RETURN:
{
  "endpoints": [
    {
      "method": "GET|POST|PUT|DELETE",
      "path": "/api/users",
      "handler": "get_users",
      "file": "api/routes/users.py",
      "line": 42
    }
  ],
  "total": N,
  "by_method": {"GET": N, "POST": N, ...}
}"""
)
```

### Find Database Operations
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find all database operations

SEARCH FOR:
- SQL queries (SELECT, INSERT, UPDATE, DELETE)
- ORM operations (.query, .filter, .add, .commit)
- Database connections and pools
- Migration files

RETURN:
{
  "operations": [
    {
      "type": "read|write|schema",
      "file": "path/to/file.py",
      "line": N,
      "table": "users",
      "operation": "SELECT with filter"
    }
  ],
  "tables_accessed": ["users", "orders", ...],
  "migration_files": ["001_init.py", ...]
}"""
)
```

### Find Test Coverage
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Analyze test coverage for [MODULE/FEATURE]

SEARCH FOR:
- Test files matching [MODULE] pattern
- Test functions/classes
- Fixtures and mocks
- Test utilities

RETURN:
{
  "test_files": [
    {
      "file": "tests/test_users.py",
      "test_count": 15,
      "fixtures": ["db_session", "mock_user"],
      "covers": ["api/routes/users.py"]
    }
  ],
  "total_tests": N,
  "patterns": ["pytest", "unittest", "jest"]
}"""
)
```

---

## 3. Architecture Analysis Prompts

### Map Layer Architecture
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Map the codebase layer architecture

ANALYZE:
1. Presentation layer (UI, API routes, CLI)
2. Business logic layer (services, use cases)
3. Data access layer (repositories, ORM, queries)
4. Infrastructure layer (config, external services)

RETURN:
{
  "layers": {
    "presentation": {
      "directories": ["app/", "api/routes/"],
      "patterns": ["FastAPI", "React"],
      "key_files": ["main.py", "App.tsx"]
    },
    "business": {
      "directories": ["services/", "use_cases/"],
      "patterns": ["Service classes", "Use case handlers"],
      "key_files": ["user_service.py"]
    },
    "data": {
      "directories": ["repositories/", "models/"],
      "patterns": ["Repository pattern", "SQLAlchemy"],
      "key_files": ["user_repository.py"]
    },
    "infrastructure": {
      "directories": ["config/", "external/"],
      "patterns": ["Settings", "API clients"],
      "key_files": ["settings.py"]
    }
  },
  "data_flow": "API → Service → Repository → Database"
}"""
)
```

### Analyze Dependencies
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Analyze dependencies of [MODULE/CLASS]

TRACE:
1. What does [MODULE] import? (direct dependencies)
2. What imports [MODULE]? (dependents)
3. External packages used
4. Circular dependency risks

RETURN:
{
  "target": "[MODULE]",
  "imports": [
    {"module": "database.connection", "type": "internal"},
    {"module": "sqlalchemy", "type": "external"}
  ],
  "imported_by": [
    {"module": "api.routes.users", "usage": "UserService instance"}
  ],
  "external_packages": ["sqlalchemy", "pydantic"],
  "circular_risks": []
}"""
)
```

### Find Design Patterns
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Identify design patterns in codebase

LOOK FOR:
1. Creational: Factory, Builder, Singleton
2. Structural: Adapter, Decorator, Facade
3. Behavioral: Observer, Strategy, Command
4. Architectural: MVC, Repository, CQRS

RETURN:
{
  "patterns": [
    {
      "pattern": "Repository",
      "location": "repositories/",
      "examples": ["UserRepository", "OrderRepository"],
      "description": "Data access abstraction"
    },
    {
      "pattern": "Factory",
      "location": "factories/",
      "examples": ["ServiceFactory"],
      "description": "Service instantiation"
    }
  ]
}"""
)
```

---

## 4. Code Quality Prompts

### Find Code Smells
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find code quality issues

SEARCH FOR:
- TODO, FIXME, HACK, XXX comments
- Functions > 50 lines
- Files > 500 lines
- Deeply nested code (> 4 levels)
- Duplicate code patterns

RETURN:
{
  "issues": [
    {
      "type": "TODO",
      "file": "path/to/file.py",
      "line": 42,
      "content": "TODO: Refactor this"
    }
  ],
  "large_functions": [
    {"file": "...", "function": "...", "lines": N}
  ],
  "large_files": [
    {"file": "...", "lines": N}
  ],
  "summary": {"todos": N, "fixmes": N, "large_files": N}
}"""
)
```

### Find Security Concerns
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find potential security concerns

SEARCH FOR:
- Hardcoded secrets (API keys, passwords)
- SQL string concatenation
- eval() or exec() usage
- Unsafe deserialization
- Missing input validation

RETURN:
{
  "concerns": [
    {
      "type": "hardcoded_secret",
      "severity": "high|medium|low",
      "file": "path/to/file.py",
      "line": 42,
      "description": "API key in source code"
    }
  ],
  "recommendations": ["Move secrets to environment variables", ...]
}"""
)
```

---

## 5. Feature-Specific Prompts

### Trace Feature Implementation
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Trace implementation of [FEATURE_NAME]

TRACE END-TO-END:
1. UI components handling [FEATURE]
2. API endpoints for [FEATURE]
3. Service layer logic
4. Database operations
5. Tests covering [FEATURE]

RETURN:
{
  "feature": "[FEATURE_NAME]",
  "flow": [
    {"layer": "ui", "files": ["UserForm.tsx"], "description": "Form submission"},
    {"layer": "api", "files": ["users.py"], "description": "POST /api/users"},
    {"layer": "service", "files": ["user_service.py"], "description": "create_user()"},
    {"layer": "data", "files": ["user_repo.py"], "description": "insert into users"}
  ],
  "tests": ["test_create_user.py"],
  "config": ["user_settings.py"]
}"""
)
```

### Find Related Files
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find all files related to [TOPIC]

SEARCH:
- Files with [TOPIC] in name
- Files importing [TOPIC] modules
- Tests for [TOPIC]
- Configuration for [TOPIC]
- Documentation for [TOPIC]

RETURN:
{
  "topic": "[TOPIC]",
  "core_files": ["main implementation files"],
  "support_files": ["utilities, helpers"],
  "test_files": ["test files"],
  "config_files": ["configuration"],
  "doc_files": ["documentation"]
}"""
)
```

---

## 6. Migration & Refactoring Prompts

### Find Refactoring Candidates
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find refactoring opportunities

ANALYZE:
1. Duplicate code blocks
2. Long parameter lists (> 5 params)
3. Feature envy (class using another class's data extensively)
4. Dead code (unused functions/classes)

RETURN:
{
  "opportunities": [
    {
      "type": "extract_method",
      "file": "path/to/file.py",
      "lines": "42-67",
      "description": "Repeated validation logic",
      "effort": "low|medium|high"
    }
  ],
  "priority": ["high impact items first"]
}"""
)
```

### Assess Migration Impact
```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Assess impact of migrating [OLD] to [NEW]

FIND:
1. All usages of [OLD]
2. Files that would need changes
3. Tests that would need updates
4. Configuration changes required

RETURN:
{
  "migration": "[OLD] → [NEW]",
  "usages": N,
  "files_affected": [
    {"file": "path/to/file.py", "usages": N, "complexity": "simple|moderate|complex"}
  ],
  "tests_affected": ["test files"],
  "config_changes": ["config files"],
  "estimated_effort": "low|medium|high",
  "risks": ["potential issues"]
}"""
)
```

---

## Usage Guidelines

### Combine Templates
Mix and match sections for complex explorations:

```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Comprehensive analysis of authentication system

PART 1 - Find Components:
[Use "Find Related Files" template]

PART 2 - Trace Flow:
[Use "Trace Feature Implementation" template]

PART 3 - Check Quality:
[Use "Find Security Concerns" template]

RETURN combined results in JSON format."""
)
```

### Adjust Thoroughness
Add to any prompt:
- `Thoroughness: quick` - Surface level, first matches only
- `Thoroughness: medium` - Moderate depth, common patterns
- `Thoroughness: very thorough` - Deep analysis, edge cases

### Set Token Limits
Always include output constraints:
- `MAX OUTPUT: 300 tokens` - Summary results
- `MAX OUTPUT: 500 tokens` - Standard results
- `MAX OUTPUT: 1000 tokens` - Detailed results
