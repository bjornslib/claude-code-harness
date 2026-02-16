# Voting Details for Workers

**Purpose**: Detailed voting procedures when orchestrator triggers consensus-building
**Parent Skill**: worker-focused-execution

---

## Table of Contents

1. [When Voting Happens](#when-voting-happens)
2. [Your Role in Voting](#your-role-in-voting)
3. [Producing Your Solution](#producing-your-solution)
4. [Solution Format](#solution-format)
5. [What Happens After](#what-happens-after)

---

## When Voting Happens

The orchestrator triggers voting for:

| Scenario | Why Voting |
|----------|------------|
| Architecture decision with multiple valid approaches | Need confidence in direction |
| Critical path feature (errors are costly) | Reduce risk of single-point failure |
| After 2+ failed attempts | Fresh perspectives needed |
| Controversial design choices | Build consensus |

**You will know voting is triggered** when your assignment includes:

```markdown
**Mode**: VOTING
**Other Workers**: 3-5 (working independently)
**Output Required**: Complete solution with reasoning
```

---

## Your Role in Voting

### The Independence Rule

**CRITICAL**: You work completely independently.

- ❌ Do NOT look at other workers' solutions
- ❌ Do NOT communicate with other workers
- ❌ Do NOT ask orchestrator what others are doing
- ✅ Do YOUR best analysis
- ✅ Do YOUR best solution
- ✅ Document YOUR reasoning

### Why Independence Matters

If workers influence each other:
- Groupthink emerges
- Diverse solutions disappear
- Voting becomes pointless

The value is in DIFFERENT perspectives converging (or not).

---

## Producing Your Solution

### Step 1: Understand the Problem

Read the assignment thoroughly:
- What is being decided?
- What are the constraints?
- What are the success criteria?

### Step 2: Analyze Options

Consider multiple approaches:
- What are the obvious solutions?
- What are less obvious alternatives?
- What are the tradeoffs?

### Step 3: Choose Your Approach

Pick the approach you believe is best:
- Document WHY you chose it
- Acknowledge tradeoffs
- Be specific about implementation

### Step 4: Implement Completely

Produce a complete solution:
- Not a sketch or outline
- Fully working code (if code)
- Complete reasoning (if decision)

### Step 5: Self-Review

Before submitting:
- Does it solve the problem?
- Is it complete?
- Is reasoning clear?

---

## Solution Format

### For Code Solutions

```markdown
## Voting Solution: [Worker ID]

### My Approach
[1-2 sentence summary of approach]

### Reasoning
1. [Why I chose this approach]
2. [Tradeoffs I considered]
3. [Alternatives I rejected and why]

### Implementation

\`\`\`[language]
[Complete, working code]
\`\`\`

### How to Validate
1. [Step to verify it works]
2. [Step to verify it works]

### Concerns/Risks
- [Any risks with this approach]
- [Edge cases to watch]
```

### For Architecture Decisions

```markdown
## Voting Solution: [Worker ID]

### My Recommendation
[Clear statement of recommendation]

### Analysis

**Option A: [Name]**
- Pros: [list]
- Cons: [list]
- When to use: [conditions]

**Option B: [Name]**
- Pros: [list]
- Cons: [list]
- When to use: [conditions]

[Repeat for other options]

### My Choice: [Option X]

**Primary Reasons**:
1. [Most important reason]
2. [Second reason]
3. [Third reason]

**Acknowledged Downsides**:
- [Downside 1 and mitigation]
- [Downside 2 and mitigation]

### Implementation Sketch
[High-level implementation approach]
```

### For Bug Fix Approaches

```markdown
## Voting Solution: [Worker ID]

### Root Cause Analysis
[What I believe is causing the issue]

### Evidence
1. [Evidence supporting this analysis]
2. [Evidence supporting this analysis]

### Proposed Fix

\`\`\`[language]
[The fix]
\`\`\`

### Why This Fixes It
[Explanation of how fix addresses root cause]

### Testing Plan
1. [How to verify fix works]
2. [How to verify no regressions]

### Alternative Approaches Considered
- [Alternative 1]: Rejected because [reason]
- [Alternative 2]: Rejected because [reason]
```

---

## What Happens After

### Orchestrator Analysis

The orchestrator will:

1. **Collect all solutions** (3-5 workers)
2. **Analyze for consensus**:

| Consensus Level | Meaning | Action |
|-----------------|---------|--------|
| High (4-5 same) | Strong agreement | Implement consensus |
| Moderate (3 similar) | Partial agreement | Examine differences, implement majority |
| No consensus | Disagreement | Decompose further or add context |

3. **Make decision** based on analysis
4. **Implement** chosen approach

### You May Be Asked To

- **Implement**: If your solution is chosen
- **Review**: Another worker's implementation
- **Retry**: If no consensus and task decomposed

### Learning From Results

After voting completes:
- Review what was chosen
- Understand why (if different from yours)
- Update your mental models

---

## Voting Anti-Patterns

### Don't Do These

| Anti-Pattern | Why Bad |
|--------------|---------|
| Rushing to submit first | Quality matters, not speed |
| Copying common patterns without thinking | Need YOUR analysis |
| Over-engineering | Simple solutions often win |
| Under-specifying | Must be implementable |
| Ignoring constraints | Solution must be valid |
| Not documenting reasoning | Others can't evaluate |

### Good Voting Behavior

| Good Practice | Why Good |
|---------------|----------|
| Thorough analysis | Better solutions |
| Clear reasoning | Others can evaluate |
| Complete implementation | Actually usable |
| Honest about tradeoffs | Builds trust |
| Acknowledging uncertainty | Calibrated confidence |

---

## Example Voting Scenario

### Assignment

```markdown
**Problem**: Chat messages sometimes appear out of order
**Mode**: VOTING
**Workers**: 5
**Constraint**: Minimal frontend changes
**Constraint**: Must not break existing functionality
```

### Good Solution

```markdown
## Voting Solution: Worker-3

### My Approach
Add timestamp-based sorting with optimistic rendering

### Reasoning
1. Root cause is async responses arriving out of order
2. Timestamps provide definitive ordering
3. Optimistic rendering maintains UX

### Implementation

\`\`\`typescript
// In messageSlice.ts
const sortedMessages = useMemo(() =>
  [...messages].sort((a, b) =>
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  ),
  [messages]
);
\`\`\`

### How to Validate
1. Send 3 rapid messages
2. Verify they appear in sent order
3. Verify existing conversations still load correctly

### Concerns/Risks
- Requires backend to provide consistent timestamps
- Additional computation on each render (mitigated by useMemo)
```

---

## Quick Checklist

Before submitting your voting solution:

- [ ] Read assignment completely
- [ ] Analyzed multiple approaches
- [ ] Chose ONE clear approach
- [ ] Documented reasoning thoroughly
- [ ] Provided complete implementation
- [ ] Included validation steps
- [ ] Acknowledged risks/tradeoffs
- [ ] Worked completely independently

---

**Reference**: See orchestrator skill for when voting is triggered and how consensus is evaluated.
