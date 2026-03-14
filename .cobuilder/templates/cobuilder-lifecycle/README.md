# cobuilder-lifecycle Template

**Version**: 1.0
**Topology**: Cyclic
**Min Nodes**: 9
**Max Nodes**: 12

## Overview

Self-driving CoBuilder Guardian lifecycle pipeline that orchestrates the full research-to-close cycle with bounded loop-back for iterative refinement.

```
START → RESEARCH → REFINE → PLAN → [WAIT.HUMAN] → EXECUTE → VALIDATE → EVALUATE → CLOSE
                                                        ↓
                                          (loop back if goals not met)
```

## Nodes

| Node | Shape | Handler | Description |
|------|-------|---------|-------------|
| `start` | Mdiamond | start | Entry point, state initialization |
| `research` | tab | research | Problem domain investigation |
| `refine` | box | codergen | Update Business Spec with findings |
| `plan` | box | codergen | Generate child pipeline DOT |
| `wait_approval` | octagon | wait.human | Human approval gate (conditional) |
| `execute` | house | manager_loop | Spawn child pipeline |
| `validate` | hexagon | wait.cobuilder | Acceptance test gate |
| `evaluate` | diamond | conditional | Goal check, loop decision |
| `close` | Msquare | close | Session finalization |

## Parameters

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `initiative_id` | string | Initiative identifier (e.g., INIT-AUTH-001) |
| `business_spec_path` | string | Path to the Business Spec markdown file |
| `target_dir` | string | Path to the target repository/directory |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_cycles` | integer | 3 | Maximum research-to-evaluate cycles |
| `execution_template` | string | "hub-spoke" | Child pipeline template |
| `require_human_before_launch` | boolean | true | Require human approval before EXECUTE |
| `model_research` | string | "haiku" | LLM for research node |
| `model_refine` | string | "opus" | LLM for refinement node |
| `model_plan` | string | "opus" | LLM for planning node |

## Usage

### Basic Instantiation

```bash
cobuilder template instantiate cobuilder-lifecycle \
  --param initiative_id="INIT-AUTH-001" \
  --param business_spec_path="docs/bs/BS-AUTH-001.md" \
  --param target_dir="/path/to/repo" \
  --output pipelines/INIT-AUTH-001-lifecycle.dot
```

### Automated Pipeline (No Human Gate)

```bash
cobuilder template instantiate cobuilder-lifecycle \
  --param initiative_id="INIT-AUTH-001" \
  --param business_spec_path="docs/bs/BS-AUTH-001.md" \
  --param target_dir="/path/to/repo" \
  --param require_human_before_launch=false \
  --output pipelines/INIT-AUTH-001-lifecycle.dot
```

### With Custom Model Profile

```bash
cobuilder template instantiate cobuilder-lifecycle \
  --param initiative_id="INIT-AUTH-001" \
  --param business_spec_path="docs/bs/BS-AUTH-001.md" \
  --param target_dir="/path/to/repo" \
  --param model_research="sonnet" \
  --param model_refine="opus" \
  --param model_plan="opus" \
  --output pipelines/INIT-AUTH-001-lifecycle.dot
```

## Lifecycle Flow

1. **START**: Initialize state for `{{ initiative_id }}`
2. **RESEARCH**: Investigate problem domain, read Business Spec, identify unknowns
3. **REFINE**: Update Business Spec with research findings and constraints
4. **PLAN**: Select execution template, generate child pipeline DOT
5. **WAIT.HUMAN** (conditional): Human approval gate before launch
6. **EXECUTE**: Spawn child pipeline via ManagerLoopHandler
7. **VALIDATE**: Run acceptance tests against Business Spec
8. **EVALUATE**: Check if goals met; loop back if not (bounded by `max_cycles`)
9. **CLOSE**: Finalize session, cleanup resources

## Constraints

### Bounded Loop

The `bounded_lifecycle` constraint prevents runaway loops:

```yaml
bounded_lifecycle:
  type: loop_constraint
  rule:
    max_per_node_visits: 4
    max_pipeline_visits: 35
```

### Path Constraint

Execute must pass through validate before reaching close:

```yaml
must_validate_before_close:
  type: path_constraint
  rule:
    from_shape: house
    must_pass_through:
      - hexagon
    before_reaching:
      - Msquare
```

## Signal Protocol

Each node writes completion to `signals/{{ initiative_id }}/{node_id}.json`:

```json
{
  "node_id": "research",
  "status": "success",
  "timestamp": "2026-03-14T12:00:00Z",
  "result": {
    "findings_path": "state/INIT-AUTH-001-research.json"
  }
}
```

## Migration from s3-lifecycle

If migrating from `s3-lifecycle`, note these breaking changes:

| s3-lifecycle | cobuilder-lifecycle |
|--------------|---------------------|
| `prd_ref` | `initiative_id` |
| `prd_path` | `business_spec_path` |
| `deploy` node | Removed (handle externally) |
| Linear topology | Cyclic with loop-back |

## See Also

- [PRD-COBUILDER-UPGRADE-001](../../docs/prds/cobuilder-upgrade/PRD-COBUILDER-UPGRADE-001.md) - Epic 7 requirements
- [hub-spoke template](../hub-spoke/) - Default execution template
- [s3-lifecycle template](../s3-lifecycle/) - Predecessor (deprecated)