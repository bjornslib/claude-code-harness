# Task Decomposition Patterns

Patterns that work well for breaking down tasks.

---

## Core Principle

From the MAKER paper: "Reliability comes from better orchestration and task decomposition, not better models."

---

## Effective Decomposition

### Feature Size Guidelines

| Good Size | Too Large | Too Small |
|-----------|-----------|-----------|
| Completable in one session | Requires multiple sessions | Trivial, adds overhead |
| Clear validation criteria | Vague "it works" | No real validation needed |
| Focused scope (1-3 files) | Touches many files | Single line change |

### Decomposition Checklist

Before adding a feature to feature_list.json:

- [ ] Can a worker complete this in ~30 min to 2 hours?
- [ ] Are validation steps specific and executable?
- [ ] Is the scope clearly bounded?
- [ ] Are dependencies explicit?
- [ ] Is one validation type (browser/api/unit) sufficient?

---

## Patterns That Work

### UI Features

Break into:
1. Component structure (no styling)
2. Styling and layout
3. Interactive behavior
4. Integration with backend

### API Endpoints

Break into:
1. Route definition and basic handler
2. Input validation
3. Business logic
4. Response formatting
5. Error handling

### Data Flow

Break into:
1. Data model/schema
2. Data access layer
3. Business logic
4. API/UI integration

---

## Anti-Patterns

### "Implement the whole thing"
❌ Bad: "Implement user authentication"
✅ Good: Break into login form, auth endpoint, token storage, session management

### "Make it work and look good"
❌ Bad: "Build the dashboard"
✅ Good: Separate functionality from styling

### Implicit Dependencies
❌ Bad: Assuming features can be done in any order
✅ Good: Explicit dependency chain in feature_list.json

---

## Learning Log

*Add patterns discovered during orchestration sessions here*
