
---

# Hindsight Fallback — Session 2026-04-03 (write_ts node, SD-GASCITY-INT-001)

## Patterns learned this session

### gc Binary PATH Clash (HIGH PRIORITY)
- `/usr/local/bin/gc` is GraphViz gc, NOT GasCity controller binary
- gascity_bridge._find_gc_binary() MUST use GOPATH-first resolution and skip /usr/local/bin
- Verify via: binary version output must contain "gas" not "graphviz"

### bd Metadata API — --set-metadata is Internal
- `bd update --set-metadata` is NOT user-facing (bd v0.49.1)
- Use `--notes '<json>'` for prototype metadata storage
- Retrieve: `bd show <id> --json | jq -r '.notes'`

### dispatch_worker.py — No Changes Needed
- No build_worker_prompt() function exists; prompt is inlined
- PRD mentioned extraction but it's not needed; pool_dispatch handles prompts

### Integration Opt-in Pattern
- COBUILDER_GASCITY_ENABLED=1 env var for pipeline-wide pool dispatch
- dispatch_mode="pool" DOT attribute for per-node control
- Default = zero behavior change

### Epic Order
- Epic 2 (pool dispatch) before Epic 1 (controller) — lower risk integration path
- Epic 3 (event bridge) fully deferrable
