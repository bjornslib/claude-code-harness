# Failure Patterns and Anti-Patterns

What goes wrong and how to avoid it.

---

## Red Flags That Signal Retry

These aren't bugs to fix. They signal the reasoning chain went off track.

| Red Flag | Why It's Bad | Action |
|----------|--------------|--------|
| Modified files outside scope | Scope creep, breaks isolation | Reject, fresh retry |
| TODO/FIXME in output | Incomplete work | Reject, fresh retry |
| Validation steps fail | Feature doesn't work | Reject, fresh retry |
| Uncommitted changes | Incomplete delivery | Complete commit or reject |
| "I think" / "probably" | Uncertainty | Review carefully, likely retry |

**Key Insight**: A fresh retry often succeeds where patching a failed attempt fails.

---

## Orchestrator Anti-Patterns

### Multiple Features at Once

❌ **What happens**: Start feature A, get stuck, start feature B
✅ **What to do**: Complete or cleanly abandon A before starting B

### Skipping Regression Check

❌ **What happens**: Hidden regressions accumulate
✅ **What to do**: Always verify 1-2 passing features before new work

### Editing Feature Definitions

❌ **What happens**: Scope creep, confusion, lost progress
✅ **What to do**: Feature definitions are immutable; add new features instead

### Marking Pass Without Validation

❌ **What happens**: False progress, broken features discovered later
✅ **What to do**: Run every validation step, no exceptions

---

## Worker Anti-Patterns

### Exceeding Scope

❌ **What happens**: Worker "helpfully" fixes adjacent code
✅ **What to do**: Strict scope enforcement, report needs to orchestrator

### Skipping TDD

❌ **What happens**: Code works but tests don't exist
✅ **What to do**: RED-GREEN-REFACTOR, always

### Claiming Done Without Verification

❌ **What happens**: "It should work" but it doesn't
✅ **What to do**: Always use superpowers:verification-before-completion

### Partial Implementation

❌ **What happens**: "I'll finish the edge cases later"
✅ **What to do**: Complete implementation or don't start

---

## Recovery Patterns

### When Worker Fails

1. Note what went wrong in learnings
2. Create fresh worker (don't patch)
3. Provide clearer context if ambiguity caused failure
4. Reduce scope if task was too large

### When Voting Shows No Consensus

1. Task may be too ambiguous
2. Decompose into smaller decisions
3. Add more context/constraints
4. Re-run voting with refined problem

### When Regression Check Fails

1. STOP new work immediately
2. Mark failed feature as `passes: false`
3. Fix regression as next feature
4. Investigate what caused regression

---

## Learning Log

*Add failure patterns discovered during orchestration sessions here*
