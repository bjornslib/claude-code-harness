---
title: "Add Runtime Constraint Enforcement"
description: "Guardian enforces max_cycles from manifest before looping back to research"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD: Add Runtime Constraint Enforcement

## Problem
The cobuilder-lifecycle manifest defines `max_cycles` (default 3) and `bounded_lifecycle` constraints, but nothing enforces them at runtime. The guardian could loop indefinitely.

## File to Modify
`cobuilder/engine/guardian.py` — the `build_system_prompt()` function

## Implementation

Add a section to the system prompt about cycle tracking and enforcement:

```
### Cycle Tracking and Bounds Enforcement
Track the number of full research→validate cycles in a state file:

Before each loop-back to RESEARCH:
1. Read current cycle count:
   CYCLES=$(cat state/{pipeline_id}-cycle-count.txt 2>/dev/null || echo 0)
2. Increment:
   echo $((CYCLES + 1)) > state/{pipeline_id}-cycle-count.txt
3. Check against max_cycles (from pipeline graph attributes or default 3):
   if [ $((CYCLES + 1)) -ge {max_cycles} ]; then
       # Max cycles reached — transition to CLOSE with exhaustion reason
       python3 {scripts_dir}/cli.py transition {dot_path} close active
       python3 {scripts_dir}/cli.py transition {dot_path} close validated
       echo "Max cycles ({max_cycles}) exhausted. Closing pipeline."
       exit 0
   fi
4. Only loop back if cycles remain

The max_cycles value comes from the pipeline's graph-level attributes.
Parse it from the DOT file or default to 3 if not set.
```

Also add max_cycles as a parameter to `build_system_prompt()` so it can be injected from the manifest.

## Acceptance Criteria
1. Guardian system prompt teaches cycle counting via state file
2. max_cycles check happens before each loop-back
3. Pipeline transitions to CLOSE when max_cycles exhausted
4. Default max_cycles is 3 if not specified
5. `guardian.py --dry-run` still works
