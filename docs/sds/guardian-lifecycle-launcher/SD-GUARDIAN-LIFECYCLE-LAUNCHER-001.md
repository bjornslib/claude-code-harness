---
title: "Guardian Lifecycle Launcher — Technical Spec"
description: "Implementation spec for launch_lifecycle() and system prompt child pipeline instructions"
version: "1.0.0"
last-updated: 2026-03-21
status: active
type: sd
---

# SD-GUARDIAN-LIFECYCLE-LAUNCHER-001

## Target File
`cobuilder/engine/guardian.py`

## Epic 1: launch_lifecycle() Function

### New Function

```python
def launch_lifecycle(
    prd_path: str,
    initiative_id: str | None = None,
    target_dir: str | None = None,
    max_cycles: int = 3,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    dry_run: bool = False,
) -> dict | None:
    """Launch a self-driving lifecycle pipeline from a PRD path.

    Steps:
    1. Derive initiative_id from PRD filename if not provided
    2. Create placeholder state files for sd_path validation
    3. Instantiate cobuilder-lifecycle template
    4. Validate rendered DOT
    5. Launch guardian on the pipeline (or return config if dry_run)
    """
    # 1. Derive initiative_id
    if initiative_id is None:
        # PRD-AUTH-001.md → AUTH-001
        stem = Path(prd_path).stem  # PRD-AUTH-001
        initiative_id = stem.replace("PRD-", "")

    # 2. Resolve paths
    project_root = os.getcwd()
    cobuilder_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if target_dir is None:
        target_dir = project_root

    # 3. Create placeholder state files
    state_dir = Path(target_dir) / "state"
    state_dir.mkdir(exist_ok=True)
    for suffix in ["-research.json", "-refined.md"]:
        placeholder = state_dir / f"{initiative_id}{suffix}"
        if not placeholder.exists():
            placeholder.write_text(f"# Placeholder — will be populated by {suffix.replace('-', ' ').strip()}\n")

    # 4. Instantiate template
    from cobuilder.templates.instantiator import instantiate_template
    dot_output = Path(".pipelines/pipelines") / f"lifecycle-{initiative_id}.dot"
    dot_output.parent.mkdir(parents=True, exist_ok=True)

    dot = instantiate_template(
        "cobuilder-lifecycle",
        {
            "initiative_id": initiative_id,
            "business_spec_path": str(Path(prd_path).resolve()),
            "target_dir": target_dir,
            "cobuilder_root": cobuilder_root,
            "max_cycles": max_cycles,
            "require_human_before_launch": True,
        },
        output_path=str(dot_output),
        validate=False,  # We validate via cli.py below
    )

    # 5. Validate
    import subprocess
    result = subprocess.run(
        ["python3", "cobuilder/engine/cli.py", "validate", str(dot_output)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise ValueError(f"Pipeline validation failed:\n{result.stderr or result.stdout}")

    # 6. Launch or dry-run
    dot_path = str(dot_output.resolve())
    pipeline_id = f"lifecycle-{initiative_id}"

    if dry_run:
        return {
            "dry_run": True,
            "initiative_id": initiative_id,
            "prd_path": prd_path,
            "dot_path": dot_path,
            "pipeline_id": pipeline_id,
            "model": model,
            "max_turns": max_turns,
            "max_cycles": max_cycles,
        }

    # Launch guardian (reuse existing launch_guardian logic)
    return launch_guardian(
        dot_path=dot_path,
        pipeline_id=pipeline_id,
        project_root=project_root,
        target_dir=target_dir,
        model=model,
        max_turns=max_turns,
    )
```

### CLI Integration

Add `--lifecycle` flag to `parse_args()`:

```python
parser.add_argument("--lifecycle", dest="lifecycle",
                    help="Path to PRD — auto-instantiates lifecycle pipeline and launches")
```

In `main()`, handle `--lifecycle` before `--dot`:
```python
if args.lifecycle:
    result = launch_lifecycle(
        prd_path=args.lifecycle,
        initiative_id=args.pipeline_id,  # optional override
        target_dir=args.target_dir,
        max_cycles=3,
        model=args.model,
        max_turns=args.max_turns,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(json.dumps(result, indent=2))
    return
```

## Epic 2: System Prompt — Child Pipeline Creation

Add to `build_system_prompt()` after the "Pipeline Graph Modification" section:

```
### Template Instantiation (For PLAN Nodes)
When a PLAN node needs to generate a child implementation pipeline:

1. Read the refined BS:
   cat state/{pipeline_id}-refined.md

2. Break into implementation tasks (each task = one codergen node)

3. Instantiate a template:
   python3 -c "
   from cobuilder.templates.instantiator import instantiate_template
   instantiate_template('sequential-validated', {
       'initiative_id': '{pipeline_id}-impl',
       'tasks': [...],  # from your analysis
       'target_dir': '{target_dir}',
       'cobuilder_root': '{cobuilder_root}',
   }, output_path='.pipelines/pipelines/{pipeline_id}-impl.dot')
   "

   OR create a DOT file manually using node/edge CRUD:
   python3 {scripts_dir}/cli.py node <dot_path> add impl_task_1 --handler codergen ...

4. Write the plan file:
   cat > state/{pipeline_id}-plan.json << 'EOF'
   {
       "dot_path": ".pipelines/pipelines/{pipeline_id}-impl.dot",
       "template": "sequential-validated",
       "task_count": N,
       "tasks": [{"id": "task_1", "description": "..."}]
   }
   EOF

5. The EXECUTE node will read this plan and implement each task.
```

## Acceptance Criteria Summary

| AC | Test |
|----|------|
| AC-1.1 | `guardian.py --lifecycle --help` shows the flag |
| AC-1.2 | `PRD-AUTH-001.md` → initiative_id `AUTH-001` |
| AC-1.3 | Template instantiation produces valid DOT |
| AC-1.4 | State placeholder files exist before validation |
| AC-1.5 | `cli.py validate` passes on rendered DOT |
| AC-1.6 | Guardian launches on the DOT (or dry-run returns config) |
| AC-2.1 | System prompt contains `template instantiate` |
| AC-2.2 | System prompt contains pattern for reading refined BS |
| AC-2.3 | System prompt contains `state/{id}-plan.json` format |
| AC-2.4 | Dry-run output includes template instructions |
