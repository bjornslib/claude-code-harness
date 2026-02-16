# Parallel Exploration Patterns

Advanced patterns for launching multiple Explore agents simultaneously.

---

## Why Parallel Exploration?

**Benefits**:
1. **Speed**: Multiple searches run concurrently
2. **Coverage**: Different perspectives on same codebase
3. **Context isolation**: Each agent has its own context window
4. **Aggregation**: Combine results for comprehensive view

**When to use**:
- Exploring multiple layers (frontend/backend/tests)
- Searching different concern areas simultaneously
- Building architecture maps
- Comprehensive feature analysis

---

## Pattern 1: Layer-Based Parallel Search

Explore different architectural layers simultaneously:

```python
# Launch all three in parallel (single message, multiple Task calls)
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Explore frontend layer
    FOCUS: app/, components/, pages/
    FIND: React components, state management, routing
    RETURN: {layer: "frontend", key_files: [...], patterns: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Explore backend layer
    FOCUS: api/, services/, repositories/
    FIND: API routes, services, database access
    RETURN: {layer: "backend", key_files: [...], patterns: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Explore infrastructure layer
    FOCUS: config/, deploy/, .github/
    FIND: Configuration, CI/CD, deployment
    RETURN: {layer: "infrastructure", key_files: [...], patterns: [...]}"""
)
```

**Result**: Three JSON responses that can be combined into complete architecture map.

---

## Pattern 2: Feature Decomposition Search

Explore all aspects of a feature simultaneously:

```python
# For feature "user authentication"
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find auth UI components
    SEARCH: Login forms, auth modals, protected routes
    RETURN: {aspect: "ui", files: [...], components: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find auth API endpoints
    SEARCH: Login, logout, token refresh, session endpoints
    RETURN: {aspect: "api", endpoints: [...], middleware: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find auth services/logic
    SEARCH: Auth service, token generation, password hashing
    RETURN: {aspect: "service", services: [...], utils: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find auth tests
    SEARCH: Auth test files, fixtures, mocks
    RETURN: {aspect: "tests", test_files: [...], coverage: [...]}"""
)
```

---

## Pattern 3: Cross-Cutting Concern Search

Find how a concern is handled across the codebase:

```python
# For concern "error handling"
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find error handling in frontend
    SEARCH: try/catch, error boundaries, error states
    RETURN: {layer: "frontend", patterns: [...], files: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find error handling in backend
    SEARCH: exception handlers, error middleware, logging
    RETURN: {layer: "backend", patterns: [...], files: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find error handling in tests
    SEARCH: error test cases, exception assertions
    RETURN: {layer: "tests", patterns: [...], files: [...]}"""
)
```

---

## Pattern 4: Dependency Graph Building

Map dependencies from multiple entry points:

```python
# Trace dependencies of key modules
modules = ["UserService", "OrderService", "PaymentService"]

# Launch parallel for each
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Trace UserService dependencies
    FIND: imports, dependents, external packages
    RETURN: {module: "UserService", imports: [...], imported_by: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Trace OrderService dependencies
    FIND: imports, dependents, external packages
    RETURN: {module: "OrderService", imports: [...], imported_by: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Trace PaymentService dependencies
    FIND: imports, dependents, external packages
    RETURN: {module: "PaymentService", imports: [...], imported_by: [...]}"""
)
```

**Post-processing**: Combine results to build complete dependency graph.

---

## Pattern 5: Multi-Pattern Search

Search for multiple patterns simultaneously:

```python
# Instead of sequential pattern searches
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find TODO comments
    RETURN: {pattern: "TODO", matches: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find FIXME comments
    RETURN: {pattern: "FIXME", matches: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Find deprecated code
    RETURN: {pattern: "deprecated", matches: [...]}"""
)
```

---

## Pattern 6: Comparative Analysis

Compare implementations across modules:

```python
Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Analyze user management implementation
    FOCUS: How users are created, updated, deleted
    RETURN: {module: "users", operations: [...], patterns: [...]}"""
)

Task(
    subagent_type="Explore",
    model="haiku",
    prompt="""MISSION: Analyze order management implementation
    FOCUS: How orders are created, updated, deleted
    RETURN: {module: "orders", operations: [...], patterns: [...]}"""
)

# Compare results to identify inconsistencies or patterns
```

---

## Aggregation Strategies

### Simple Merge
```python
results = [agent1_result, agent2_result, agent3_result]
combined = {
    "layers": {r["layer"]: r for r in results},
    "total_files": sum(len(r["files"]) for r in results)
}
```

### Weighted Merge
Prioritize results by relevance scores if provided.

### Deduplication
Remove duplicate file references across results.

### Conflict Resolution
When same file appears in multiple results, merge contexts.

---

## Performance Considerations

### Optimal Parallelism
- **2-3 agents**: Low overhead, good for focused searches
- **4-6 agents**: Medium overhead, good for layer exploration
- **7+ agents**: Higher overhead, use for comprehensive analysis

### Result Size Management
- Request `MAX OUTPUT: 300-500 tokens` per agent
- Aggregate results shouldn't exceed ~2000 tokens total
- Compress results in post-processing if needed

### Error Handling
```python
# Check for failed agents
for result in results:
    if result.get("error"):
        # Log and handle gracefully
        continue
    # Process successful result
```

---

## When NOT to Use Parallel

Avoid parallel exploration when:
1. **Single file known**: Direct read is faster
2. **Simple pattern**: One Grep is sufficient
3. **Sequential dependency**: Results depend on each other
4. **Resource constrained**: Too many parallel agents
