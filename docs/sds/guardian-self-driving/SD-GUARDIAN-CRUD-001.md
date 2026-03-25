---
title: "Add CRUD Operations to Guardian System Prompt"
description: "Teach the guardian agent how to modify its own pipeline graph via node/edge CLI"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD: Add CRUD Operations to Guardian System Prompt

## File to Modify
`cobuilder/engine/guardian.py` — the `build_system_prompt()` function (starts ~line 117)

## What
The system prompt currently teaches the guardian about:
- `cli.py status` / `cli.py transition` / `cli.py checkpoint` / `cli.py parse` / `cli.py validate`

But NOT about:
- `cli.py node add/remove/modify`
- `cli.py edge add/remove`

## Implementation

Add a new section to the f-string returned by `build_system_prompt()`, after the existing "### Signal Tools" section (around line 172) and before "### Signal Handler Types" (line 177).

### Content to Add

```
### Pipeline Graph Modification (Node/Edge CRUD)
When you need to modify the pipeline structure (e.g., inject a refinement node after failure,
add a parallel research branch, or restructure after validation failure):

Node operations:
- python3 {scripts_dir}/cli.py node {dot_path} add <node_id> --handler codergen --label "Fix: <description>" --set sd_path=<path> --set worker_type=backend-solutions-engineer --set llm_profile=alibaba-glm5 --set prompt="<task>" --set acceptance="<criteria>" --set prd_ref=<prd> --set bead_id=<id>
- python3 {scripts_dir}/cli.py node {dot_path} add <node_id> --handler research --label "Research: <topic>" --set llm_profile=anthropic-fast
- python3 {scripts_dir}/cli.py node {dot_path} add <node_id> --handler refine --label "Refine: <topic>" --set sd_path=<path>
- python3 {scripts_dir}/cli.py node {dot_path} modify <node_id> --set prompt="<updated_prompt>" --set acceptance="<updated_criteria>"
- python3 {scripts_dir}/cli.py node {dot_path} remove <node_id>
- python3 {scripts_dir}/cli.py node {dot_path} list

Edge operations:
- python3 {scripts_dir}/cli.py edge {dot_path} add <from_node> <to_node> --label "<description>"
- python3 {scripts_dir}/cli.py edge {dot_path} remove <from_node> <to_node>
- python3 {scripts_dir}/cli.py edge {dot_path} list

Common patterns:
1. Inject fix-it node after validation failure:
   python3 {scripts_dir}/cli.py node {dot_path} add fix_<id> --handler codergen --label "Fix: <gap>" --set sd_path=<path> --set worker_type=backend-solutions-engineer
   python3 {scripts_dir}/cli.py edge {dot_path} add <failed_node> fix_<id> --label "fix required"
   python3 {scripts_dir}/cli.py edge {dot_path} add fix_<id> <next_gate> --label "re-validate"

2. Add research branch for unknown domain:
   python3 {scripts_dir}/cli.py node {dot_path} add research_<topic> --handler research --label "Research: <topic>"
   python3 {scripts_dir}/cli.py edge {dot_path} add <predecessor> research_<topic> --label "investigate"
   python3 {scripts_dir}/cli.py edge {dot_path} add research_<topic> <successor> --label "findings ready"

3. Restructure after repeated failure (replace node):
   python3 {scripts_dir}/cli.py node {dot_path} remove <old_node>
   python3 {scripts_dir}/cli.py node {dot_path} add <new_node> --handler codergen --label "<new approach>" --set sd_path=<path>
   (re-wire edges from predecessor/successor)

IMPORTANT: After ANY graph modification, always:
   python3 {scripts_dir}/cli.py validate {dot_path}
   python3 {scripts_dir}/cli.py checkpoint save {dot_path}
```

## Acceptance Criteria
1. `build_system_prompt()` f-string contains `node add`, `edge add`, `node modify`, `node remove`, `edge remove`
2. Uses `{scripts_dir}` and `{dot_path}` template variables correctly
3. Common patterns for failure injection, research branching included
4. Validate + checkpoint reminder after modifications
5. `guardian.py --dry-run` still works

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
