@journey @prd-S3-DOT-LIFECYCLE-002 @J2 @code-analysis @smoke
Scenario J2: Existing generate/validate/transition/checkpoint commands remain unchanged
  # Business objective: Phase 1 additions do NOT break existing workflows.
  # System 3's DOT Graph Navigation loop must continue to work.

  # Step 1: Existing generate (without --scaffold) still works
  Given beads task data exists
  When the LLM runs `attractor generate --output full.dot`
  Then a complete pipeline graph is produced (not a scaffold)
  And full.dot passes `attractor validate`

  # Step 2: Existing transition works on CRUD-modified graphs
  Given a graph modified by node/edge CRUD operations
  When the LLM runs `attractor transition modified.dot <node_id> active`
  Then the node status changes to active
  And the transition is logged to .transitions.jsonl

  # Step 3: Existing checkpoint works on CRUD-modified graphs
  And `attractor checkpoint save modified.dot` preserves all CRUD modifications
  And `attractor checkpoint restore <checkpoint.json>` restores the exact state

  # Business outcome:
  # Existing System 3 execution loops continue to function.
  # Phase 1 additions are purely additive.
