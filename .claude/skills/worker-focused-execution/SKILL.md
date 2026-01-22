---
name: worker-focused-execution
description: Focused single-task execution for multi-agent orchestration workers. Use when implementing a feature from feature_list.json, following scope constraints, using TDD red-green-refactor, validating with browser/API/unit tests, or participating in voting consensus. Triggers on worker execution, feature implementation, scope enforcement, TDD, red-green-refactor, validation, superpowers skills, verification before completion.
---

# Worker Focused Execution Skill

## Purpose

Execute a single feature with complete focus, strict scope adherence, and mandatory verification. Workers are part of a larger orchestration but focus only on their assigned task.

**Core Principle**: Complete one feature fully. Never exceed scope. Always verify before claiming done.

---

## 🧠 Serena Integration (MANDATORY)

### Mode Activation
Set Serena mode at the start of every feature execution:
```python
# For implementation work (DEFAULT)
mcp__serena__switch_modes(["editing", "interactive"])
```

### Checkpoint Protocol

| Checkpoint | When | Tool | Purpose |
|------------|------|------|---------|
| Context Validation | After step 2 (read assignment) | `think_about_collected_information` | Ensure scope, validation criteria, and dependencies are understood |
| Task Adherence | Every 5 tool calls | `think_about_task_adherence` | Prevent scope creep, stay within boundaries |
| Completion Gate | Before step 8 (verification-before-completion) | `think_about_whether_you_are_done` | Prevent premature completion claims |

### Integrated Execution Flow
```
1. Receive assignment from orchestrator
   ↓
2. Read feature scope and validation criteria
   ↓
   🧠 CHECKPOINT: mcp__serena__think_about_collected_information()
   └─ Validate: Do I understand scope? Validation criteria clear? Dependencies met?
   ↓
3. Use superpowers:brainstorming if approach unclear
   ↓
4-6. RED-GREEN-REFACTOR (TDD cycle)
   ↓
   🧠 CHECKPOINT (every 5 tool calls): mcp__serena__think_about_task_adherence()
   └─ Validate: Still within scope? Following TDD correctly?
   ↓
7. Run validation steps (browser/API/unit)
   ↓
   🧠 MANDATORY CHECKPOINT: mcp__serena__think_about_whether_you_are_done()
   └─ Verify: All validation steps ACTUALLY pass (not assumed)
   └─ Verify: Only scoped files modified
   └─ Verify: No TODO/FIXME in code
   ↓
8. Use superpowers:verification-before-completion
   ↓
9. Commit and report
```

---

## Quick Reference

### Required Superpowers Skills
```
Skill("superpowers:verification-before-completion")  # MANDATORY before done
Skill("superpowers:test-driven-development")         # RED-GREEN-REFACTOR
Skill("superpowers:brainstorming")                   # Before unclear decisions
Skill("superpowers:systematic-debugging")            # For troubleshooting
Skill("superpowers:root-cause-tracing")              # For complex bugs
```

### Model Hierarchy
- **You (Worker)**: Opus 4.5
- **Your Subagents**: Haiku 4.5 (for code implementation)

### Completion Checklist
- [ ] All validation steps pass
- [ ] ONLY scoped files modified
- [ ] No TODO/FIXME in code
- [ ] Tests pass
- [ ] Changes committed
- [ ] Git status clean
- [ ] Used verification-before-completion

---

## Execution Flow

```
1. Receive assignment from orchestrator
   ↓
2. Read feature scope and validation criteria
   ↓
3. Use superpowers:brainstorming if approach unclear
   ↓
4. RED PHASE: Write failing tests (superpowers:test-driven-development)
   ↓
5. GREEN PHASE: Implement code (delegate to Haiku 4.5 subagent)
   ↓
6. REFACTOR PHASE: Clean up while tests pass
   ↓
7. Run validation steps (browser/API/unit)
   ↓
8. Use superpowers:verification-before-completion
   ↓
9. Commit with message: "feat(F00X): [description]"
   ↓
10. Report completion to orchestrator
```

---

## Scope Enforcement

### The Scope Rule

**You can ONLY modify files listed in the `scope` field of your assignment.**

```json
{
  "scope": ["agencheck-support-frontend/components/ChatInterface.tsx"]
}
```

This means:
- ✅ Edit `ChatInterface.tsx`
- ❌ Edit any other file
- ❌ Create new files outside scope
- ❌ "Quick fix" in related files

### What If You Need More?

If you genuinely need to modify files outside scope:

1. **STOP** - Do not modify
2. **Report to orchestrator** - Explain what's needed
3. **Wait for scope expansion** - Orchestrator decides
4. **Never self-expand** - This breaks the system

### Why Scope Matters

- Prevents scope creep
- Enables parallel workers
- Makes changes auditable
- Keeps features atomic

---

## TDD: Red-Green-Refactor

### Invoke the Skill First

```
Skill("superpowers:test-driven-development")
```

### The Cycle

**RED Phase**:
1. Write test for expected behavior
2. Run test - it MUST fail
3. If test passes → feature already works or test is wrong

**GREEN Phase**:
1. Write minimal code to make test pass
2. Use Haiku 4.5 subagent for implementation
3. Run test - it MUST pass
4. Don't add features beyond what test requires

**REFACTOR Phase**:
1. Clean up code while tests stay green
2. Remove duplication
3. Improve naming
4. Run tests after each change

### Haiku Sub-Agent Pattern (MAKER-Inspired)

**Core Principle**: Each sub-agent does ONE atomic step. Code OR Test, never both.

#### Pattern A: Code Implementation Sub-Agent
```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    prompt="""Implement ONLY this single function/component:

## Task
[Specific function name and signature]

## Context
- File: [exact file path]
- Purpose: [what it does]

## Constraints
- Do NOT modify any other files
- Do NOT add tests (separate sub-agent)
- Do NOT add features beyond specification

## Acceptance Criteria
- [ ] Function exists with correct signature
- [ ] Returns expected output for given inputs

When done, report: CODE_COMPLETE or CODE_BLOCKED
"""
)
```

#### Pattern B: Test Verification Sub-Agent (Dedicated)
```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    prompt="""Run and verify tests ONLY:

## Task
Run: [specific test command]

## Expected
- Tests should PASS/FAIL (depending on TDD phase)

## Constraints
- Do NOT modify any code files
- Do NOT modify test files
- ONLY run tests and report results

## Report Format
TEST_RESULTS:
- Total: X
- Passed: Y
- Failed: Z
- Errors: [list any]

When done, report: TESTS_PASSED or TESTS_FAILED with details
"""
)
```

#### Why Separate Sub-Agents for Code and Test?
| Approach | Risk | Outcome |
|----------|------|---------|
| Same agent codes + tests | May adjust tests to pass code | False positives |
| Separate agents | Independent verification | Higher reliability |
| MAKER pattern | One step per agent | Maximum decomposition |

#### Worker Coordination of Sub-Agents

```
WORKER (Opus) coordinates:

1. RED Phase:
   └─ Sub-agent A (Haiku): Write failing test
   └─ Sub-agent B (Haiku): Run test, verify it fails

2. GREEN Phase:
   └─ Sub-agent C (Haiku): Implement code
   └─ Sub-agent D (Haiku): Run test, verify it passes

3. REFACTOR Phase:
   └─ Sub-agent E (Haiku): Refactor code
   └─ Sub-agent F (Haiku): Run test, verify still passes
```

---

## Validation Types

### Browser Validation (`validation: "browser"`)

**For detailed procedures, see**: [TESTING_DETAILS.md](TESTING_DETAILS.md)

**Quick Pattern**:
```javascript
// 1. Navigate
await browser_navigate("http://localhost:5001");

// 2. Interact
await browser_type({ element: "input", ref: "[ref]", text: "test" });
await browser_click({ element: "button", ref: "[ref]" });

// 3. Wait for response
await browser_wait({ time: 5 });

// 4. Verify
const snapshot = await browser_snapshot();
// Check snapshot for expected content
```

### API Validation (`validation: "api"`)

**Quick Pattern**:
```bash
# Health check
curl http://localhost:8000/health

# Test endpoint
curl -X POST http://localhost:8000/agencheck \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "thread_id": "test-001"}'
```

### Unit Validation (`validation: "unit"`)

**Quick Pattern**:
```bash
# Frontend
npm run test -- --testPathPattern="ComponentName"

# Backend
pytest tests/test_specific.py -v
```

---

## Verification Before Completion

### MANDATORY: Use the Skill

Before claiming ANY work is done:

```
Skill("superpowers:verification-before-completion")
```

### What Gets Verified

1. **All validation steps actually pass** (not assumed)
2. **Only scoped files modified** (git diff check)
3. **No TODO/FIXME markers** in code
4. **Git status is clean** (everything committed)
5. **Tests pass** (re-run, don't assume)

### Common Failures

| Claim | Reality | Fix |
|-------|---------|-----|
| "Tests pass" | Didn't run them | Run tests |
| "Feature works" | Only tested happy path | Test edge cases |
| "Code is clean" | Has TODO markers | Remove or complete |
| "Committed" | Uncommitted changes | Complete commit |

---

## Red Flags (Self-Check)

### Immediate Stop Signals

If you notice ANY of these, STOP and reassess:

| Red Flag | What It Means | Action |
|----------|---------------|--------|
| Modifying files outside scope | Scope creep | Report to orchestrator |
| Writing TODO/FIXME | Incomplete work | Complete it now |
| "I think this works" | No verification | Actually verify |
| "Probably fine" | Uncertainty | Get certain |
| Skipping tests | Rushing | Write the tests |
| "Quick fix" elsewhere | Scope violation | Stay in scope |

### These Signal Retry, Not Fix

Red flags aren't bugs to patch. They indicate the reasoning chain went off track. Often better to:

1. Stop current approach
2. Clear context
3. Start fresh with lessons learned

---

## Voting Participation

### When Orchestrator Triggers Voting

You may be one of 3-5 workers asked to solve the same problem independently.

**For detailed voting procedures, see**: [VOTING_DETAILS.md](VOTING_DETAILS.md)

**Quick Summary**:
1. Work independently (no peeking at other workers)
2. Document your reasoning
3. Produce complete solution
4. Let orchestrator analyze consensus

---

## Communication with Orchestrator

### Completion Report

When done, report:

```markdown
## Feature F00X Complete

**Status**: PASSED / FAILED

**Validation Results**:
- Step 1: ✅/❌ [result]
- Step 2: ✅/❌ [result]

**Files Modified**:
- [file1.ts] - [what changed]

**Commit**: [hash] "feat(F00X): [message]"

**Notes**: [anything orchestrator should know]
```

### Blocker Report

If blocked, report:

```markdown
## Feature F00X Blocked

**Blocker**: [what's blocking]

**Attempted**:
1. [what you tried]
2. [what you tried]

**Need**: [what would unblock]

**Recommendation**: [your suggestion]
```

---

## Subagent Usage

### When to Delegate to Haiku 4.5

- Actual code implementation
- Repetitive changes
- Well-defined transformations
- Test writing (after you define what to test)

### How to Delegate

```markdown
## Subagent Task

**Goal**: [Single specific goal]

**Context**:
- File: [path]
- Function: [name]
- Current behavior: [what it does now]
- Desired behavior: [what it should do]

**Constraints**:
- Do NOT modify [specific things]
- Do NOT add [features beyond scope]
- Do NOT create new files

**Acceptance Criteria**:
- [ ] [Specific check 1]
- [ ] [Specific check 2]
```

### When NOT to Delegate

- Architectural decisions (you decide)
- Scope questions (ask orchestrator)
- Validation (you verify)
- Debugging complex issues (use systematic-debugging skill)

---

## Quick Commands

```bash
# Check what files you modified
git diff --name-only

# Verify only scoped files changed
git diff --name-only | grep -v "allowed/path"  # Should be empty

# Check for TODO/FIXME
grep -r "TODO\|FIXME" [scoped-files]

# Run specific test
npm run test -- --testPathPattern="Feature"
pytest tests/test_feature.py -v

# Commit feature
git add -A && git commit -m "feat(F00X): [description]"
```

---

## References

- **Testing Details**: [TESTING_DETAILS.md](TESTING_DETAILS.md)
- **Voting Details**: [VOTING_DETAILS.md](VOTING_DETAILS.md)
- **Superpowers Skills**: https://github.com/obra/superpowers
- **Orchestrator Skill**: `.claude/skills/orchestrator-multiagent/SKILL.md`

---

**Skill Version**: 1.0
**Line Count**: <500 (following 500-line rule)
**Progressive Disclosure**: Testing in TESTING_DETAILS.md, Voting in VOTING_DETAILS.md
