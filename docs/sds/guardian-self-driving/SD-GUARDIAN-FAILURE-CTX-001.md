---
title: "Implement Failure Context Passing Between Cycles"
description: "Guardian writes failure summaries that flow back to research nodes on retry"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD: Implement Failure Context Passing

## Problem
The cobuilder-lifecycle template has `$previous_failures` variable in the RESEARCH node prompt, but nothing populates it. When a cycle fails and loops back, the research node has no context about what went wrong.

## Files to Modify

### 1. `cobuilder/engine/guardian.py` — System Prompt
Add instructions for the guardian to write failure context:

```
### Failure Context for Retry Loops
When a validation fails and you need to loop back to research:
1. Write a failure summary BEFORE transitioning back:
   echo "## Cycle N Failure Summary\n- Node: <node_id>\n- Reason: <why it failed>\n- Attempted: <what was tried>\n- Root cause: <analysis>" > state/{initiative_id}-failures.md
2. The RESEARCH node will read this file on its next run
3. Append (don't overwrite) — each cycle adds context
```

### 2. `.cobuilder/templates/cobuilder-lifecycle/template.dot.j2` — Research Node Prompt
Update the research node's prompt to include the failure context file:

Current prompt includes: `If $previous_failures is set, focus on investigating root causes...`

Change to explicitly reference the state file:
```
prompt="Research the problem domain for {{ initiative_id }}. Read {{ business_spec_path }}. Identify unknowns, framework constraints, and prior art. Check if state/{{ initiative_id }}-failures.md exists — if so, read it and focus on investigating root causes of prior failures rather than general domain research. Write findings to state/{{ initiative_id }}-research.json."
```

## Acceptance Criteria
1. Guardian system prompt teaches writing failure summaries to `state/{initiative_id}-failures.md`
2. Template research node prompt references the failures file path explicitly
3. Failure context is appended (not overwritten) per cycle
4. `cli.py validate` still passes on rendered templates

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
