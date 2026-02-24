@journey @prd-S3-DOT-LIFECYCLE-002 @J1 @code-analysis @smoke
Scenario J1: LLM can iteratively design a pipeline graph via CLI tools
  # This is THE core business objective: an LLM can go from zero to
  # a validated, execution-ready pipeline using only CLI commands.

  # Step 1: Generate scaffold
  Given a PRD markdown file exists for an initiative
  When the LLM runs `attractor generate --scaffold --prd <prd.md> --output scaffold.dot`
  Then scaffold.dot contains start, exit, and placeholder nodes

  # Step 2: Inspect structure
  And `attractor parse scaffold.dot --output json` returns structured data
  And `attractor status scaffold.dot` shows all nodes as pending

  # Step 3: Refine with node CRUD
  And `attractor node add scaffold.dot --id validation_gate --shape diamond --handler conditional` succeeds
  And `attractor node modify scaffold.dot placeholder_1 --worker-type backend-solutions-engineer` succeeds

  # Step 4: Refine with edge CRUD
  And `attractor edge remove scaffold.dot placeholder_1 placeholder_2` succeeds
  And `attractor edge add scaffold.dot placeholder_1 validation_gate` succeeds
  And `attractor edge add scaffold.dot validation_gate placeholder_2 --label "pass"` succeeds

  # Step 5: Validate
  And `attractor validate scaffold.dot` passes with no errors

  # Step 6: Checkpoint
  And `attractor checkpoint save scaffold.dot` produces a valid checkpoint file

  # Step 7: Status shows dispatchable nodes
  And `attractor status scaffold.dot --filter=pending --deps-met` identifies correct nodes

  # Business outcome:
  # The LLM has gone from PRD -> scaffold -> refined graph -> validated -> checkpointed
  # entirely through CLI commands, with incremental validation at each step.
