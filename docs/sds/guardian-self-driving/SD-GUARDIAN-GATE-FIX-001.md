---
title: "Fix Gate Deadlock in Guardian System Prompt"
description: "Teach the guardian to launch pipeline_runner.py asynchronously and handle gates"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD: Fix Gate Deadlock in Guardian System Prompt

## Root Cause
The guardian system prompt teaches `runner.py --spawn` (which doesn't exist as expected). When the guardian falls back to `pipeline_runner.py --resume`, it runs it as a BLOCKING subprocess. This creates a deadlock when the runner hits any gate node:
- Runner blocks waiting for GATE_RESPONSE signal from guardian
- Guardian blocks waiting for runner subprocess to exit
- Deadlock

## File to Modify
`cobuilder/engine/guardian.py` — the `build_system_prompt()` function

## Implementation

### 1. Replace the runner spawn command
Replace the broken `runner.py --spawn` reference with the correct `pipeline_runner.py` command, and teach the guardian to run it in the BACKGROUND:

```
### Launching Pipeline Runner
Run the pipeline runner in the BACKGROUND so you can handle gates:
   python3 {scripts_dir}/pipeline_runner.py --dot-file {dot_path} &
   RUNNER_PID=$!
   echo "Runner PID: $RUNNER_PID"

CRITICAL: Always run with & (background). If you run it in the foreground,
you will DEADLOCK when the runner hits a gate node — it will wait for your
signal, but you'll be blocked waiting for it to exit.

After launching, poll for status and handle gates:
   while ps -p $RUNNER_PID > /dev/null 2>&1; do
       # Check for gate signals
       ls {dot_dir}/signals/*gate*.signal 2>/dev/null
       # Check node statuses
       python3 {scripts_dir}/cli.py status {dot_path} --json
       sleep 30
   done
```

### 2. Add Gate Handling Instructions
After the runner launch section, add instructions for handling gates:

```
### Handling Gate Nodes
When a node with handler=wait.cobuilder or wait.human becomes active,
the runner is blocked waiting for you to validate or approve.

For wait.cobuilder gates:
1. Read the codergen node's acceptance criteria
2. Verify the work was done (check files, run tests)
3. If PASS: transition the gate to validated
   python3 {scripts_dir}/cli.py transition {dot_path} <gate_node> validated
4. If FAIL: transition the codergen node back to pending for retry
   python3 {scripts_dir}/cli.py transition {dot_path} <codergen_node> pending

For wait.human gates:
1. Check if you can validate autonomously (technical criteria)
2. If autonomous: transition to validated
3. If human needed: escalate to Terminal
```

### 3. Remove broken runner.py --spawn references
Remove or update all references to `runner.py --spawn` in the system prompt.

## Acceptance Criteria
1. System prompt no longer references `runner.py --spawn`
2. System prompt teaches `pipeline_runner.py --dot-file` with `&` (background)
3. Gate handling instructions present
4. Guardian can handle the hello-world pipeline without deadlock
5. `guardian.py --dry-run` still works
