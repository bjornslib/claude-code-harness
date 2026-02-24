@prd-S3-DOT-LIFECYCLE-002
Feature: LLM-Collaborative Attractor Pipeline — Phase 1

  # ============================================================
  # EPIC A: Node CRUD Operations (Weight: 0.30)
  # ============================================================

  @feature-epic-a @weight-0.30
  Scenario: node_add — Add a new node to a DOT pipeline
    Given a valid DOT pipeline file exists
    When the LLM runs `attractor node add <file.dot> --id new_task --shape box --handler codergen --label "Implement auth"`
    Then the DOT file contains a node with id "new_task"
    And the node has shape "box" and handler "codergen"
    And the node has label "Implement auth"
    And the DOT file passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — `node add` command exists in cli.py, creates valid DOT node with all attributes,
    #        file is written in place, validates successfully afterward
    # 0.5 — Command exists but some attributes are missing or DOT syntax has minor issues
    # 0.0 — Command does not exist, or produces invalid DOT that fails validation

    # Evidence to check:
    # - cli.py dispatches "node" subcommand (or "node add" subcommand)
    # - A node_ops.py or similar module handles node CRUD
    # - The --id, --shape, --handler, --label flags are accepted
    # - Generated DOT syntax is valid Graphviz

    # Red flags:
    # - Node added but DOT file not written back
    # - Attributes not properly quoted in DOT output
    # - No validation of duplicate node IDs
    # - Shape values not validated against the 7 allowed shapes


  @feature-epic-a @weight-0.30
  Scenario: node_add_at_pairing — Auto-create AT hexagon when adding codergen node
    Given a valid DOT pipeline file exists
    When the LLM runs `attractor node add <file.dot> --id impl_task --shape box --handler codergen`
    Then the DOT file contains both "impl_task" (box) and "impl_task_AT" (hexagon) nodes
    And an edge exists from "impl_task" to "impl_task_AT"
    And the AT hexagon has handler "acceptance_test"
    And using `--no-at-pair` flag skips the AT hexagon creation

    # Confidence scoring guide:
    # 1.0 — AT pairing is automatic for box/codergen nodes, creates hexagon with correct
    #        handler, adds edge, --no-at-pair flag suppresses this behavior
    # 0.5 — AT pairing exists but edge is missing, or --no-at-pair not implemented
    # 0.0 — No AT pairing logic at all

    # Evidence to check:
    # - Logic that detects shape=box and auto-creates hexagon
    # - Edge creation between codergen and AT node
    # - --no-at-pair flag handling
    # - AT node has handler="acceptance_test" (or similar)

    # Red flags:
    # - AT node created but handler not set
    # - AT pairing not suppressed by --no-at-pair
    # - AT node ID naming convention inconsistent


  @feature-epic-a @weight-0.30
  Scenario: node_remove — Remove a node from a DOT pipeline
    Given a DOT pipeline file with node "old_task" that has connected edges
    When the LLM runs `attractor node remove <file.dot> old_task` without --cascade
    Then the command fails with an error about existing edges
    And the DOT file is unchanged

    # Confidence scoring guide:
    # 1.0 — Remove without --cascade correctly refuses when edges exist, shows clear error
    # 0.5 — Remove works but error message is unclear or exits silently
    # 0.0 — Remove silently deletes node leaving orphan edges, or command doesn't exist

    # Evidence to check:
    # - Edge existence check before removal
    # - Clear error message naming the connected edges
    # - File not modified on failure

    # Red flags:
    # - Orphan edges left in the file
    # - No edge check at all (just removes the node)
    # - File written even on "failure"


  @feature-epic-a @weight-0.30
  Scenario: node_remove_cascade — Remove node with cascade deletes edges
    Given a DOT pipeline file with node "old_task" connected to "start" and "exit"
    When the LLM runs `attractor node remove <file.dot> old_task --cascade`
    Then the node "old_task" is removed from the DOT file
    And all edges to/from "old_task" are removed
    And the DOT file passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — --cascade removes node AND all connected edges, file validates afterward
    # 0.5 — --cascade removes node but misses some edges, or validation fails
    # 0.0 — --cascade flag not implemented

    # Evidence to check:
    # - Both incoming and outgoing edges removed
    # - If removing codergen node, paired AT hexagon also removed (with --force)
    # - File validates after removal

    # Red flags:
    # - Only outgoing edges removed (incoming left as orphans)
    # - AT paired node not handled during cascade


  @feature-epic-a @weight-0.30
  Scenario: node_modify — Modify attributes of an existing node
    Given a DOT pipeline file with node "task_1" having label "Original"
    When the LLM runs `attractor node modify <file.dot> task_1 --label "Updated" --worker-type backend-solutions-engineer`
    Then node "task_1" has label "Updated"
    And node "task_1" has worker_type "backend-solutions-engineer"
    And the node ID and shape are unchanged
    And the DOT file passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — Modify updates specified attributes, preserves unspecified ones,
    #        refuses to change ID or shape, validates
    # 0.5 — Modify works but allows changing ID or shape (which shouldn't be allowed)
    # 0.0 — Modify command doesn't exist or corrupts the node

    # Evidence to check:
    # - Attribute update logic preserves existing attributes not being modified
    # - --id and --shape modifications are rejected with clear error
    # - Modified attributes validated against schema

    # Red flags:
    # - All attributes overwritten (not just the specified ones)
    # - No validation of modified values
    # - Shape change silently allowed


  @feature-epic-a @weight-0.30
  Scenario: node_validation — All node operations produce valid DOT
    Given any sequence of node add/remove/modify operations
    When the resulting DOT file is checked with `attractor validate`
    Then validation passes (structural rules OK)
    And no duplicate node IDs exist
    And all node shapes are from the 7 valid shapes

    # Confidence scoring guide:
    # 1.0 — Every node operation writes valid DOT, duplicate ID check exists,
    #        shape validation against schema
    # 0.5 — Most operations valid but edge cases produce invalid DOT
    # 0.0 — Node operations produce DOT that fails validation

    # Evidence to check:
    # - DOT serialization logic (quoting, escaping)
    # - Duplicate ID detection
    # - Shape validation against allowed set

    # Red flags:
    # - Unquoted labels containing spaces
    # - Missing semicolons or brackets
    # - HTML entities not properly escaped


  # ============================================================
  # EPIC B: Edge CRUD Operations (Weight: 0.30)
  # ============================================================

  @feature-epic-b @weight-0.30
  Scenario: edge_add — Add an edge between two nodes
    Given a DOT pipeline file with nodes "task_a" and "task_b"
    When the LLM runs `attractor edge add <file.dot> task_a task_b --label "depends on"`
    Then an edge from "task_a" to "task_b" exists in the DOT file
    And the edge has label "depends on"
    And the DOT file passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — Edge add creates valid DOT edge syntax, both nodes verified to exist,
    #        no duplicate edge check, optional label supported
    # 0.5 — Edge created but node existence not verified, or label not supported
    # 0.0 — Command doesn't exist or produces invalid DOT

    # Evidence to check:
    # - cli.py dispatches "edge add" subcommand
    # - Both source and target nodes verified to exist
    # - Duplicate edge detection (warn or reject)
    # - Self-loop detection (from == to)

    # Red flags:
    # - Edge created without verifying node existence
    # - No duplicate edge check
    # - Self-loops allowed silently


  @feature-epic-b @weight-0.30
  Scenario: edge_add_cycle_detection — Warn about cycles when adding edge
    Given a DOT pipeline file with edge path A -> B -> C
    When the LLM runs `attractor edge add <file.dot> C A`
    Then the command warns that this creates a cycle
    And the edge is NOT added by default
    And using `--allow-cycle` flag adds the edge despite the cycle

    # Confidence scoring guide:
    # 1.0 — Cycle detection implemented, warns clearly, blocks by default,
    #        --allow-cycle overrides the block
    # 0.5 — Cycle detection exists but --allow-cycle not implemented, or
    #        detection misses some cycle paths
    # 0.0 — No cycle detection at all

    # Evidence to check:
    # - Graph traversal algorithm for cycle detection (DFS/BFS)
    # - Warning message identifies the cycle path
    # - --allow-cycle flag handling
    # - Detection works for indirect cycles (not just direct back-edges)

    # Red flags:
    # - Only detects direct back-edges (A->B->A) but not longer cycles
    # - Cycle added silently without warning
    # - Detection algorithm is O(n^3) or worse


  @feature-epic-b @weight-0.30
  Scenario: edge_remove — Remove an edge between two nodes
    Given a DOT pipeline file with an edge from "task_a" to "task_b"
    When the LLM runs `attractor edge remove <file.dot> task_a task_b`
    Then the edge from "task_a" to "task_b" is removed
    And the DOT file passes `attractor validate`
    And removing a non-existent edge fails with a clear error

    # Confidence scoring guide:
    # 1.0 — Edge remove correctly identifies and removes the specific edge,
    #        fails cleanly when edge doesn't exist
    # 0.5 — Edge removed but error handling for missing edge is poor
    # 0.0 — Command doesn't exist or removes wrong edges

    # Evidence to check:
    # - Correct edge identified (not just any edge involving those nodes)
    # - Error when edge not found
    # - File unchanged on error

    # Red flags:
    # - Removes ALL edges between two nodes (when there might be multiple with different labels)
    # - No error when edge doesn't exist


  @feature-epic-b @weight-0.30
  Scenario: edge_list — List all edges with optional filtering
    Given a DOT pipeline file with multiple edges
    When the LLM runs `attractor edge list <file.dot>`
    Then all edges are listed with source, target, and label
    And `--from task_a` filters to edges originating from task_a
    And `--to task_b` filters to edges terminating at task_b
    And `--json` produces machine-readable output

    # Confidence scoring guide:
    # 1.0 — Edge list shows all edges, supports --from, --to, and --json filters
    # 0.5 — List works but filtering is missing or --json not supported
    # 0.0 — Command doesn't exist

    # Evidence to check:
    # - Human-readable table output by default
    # - --from and --to filter correctly
    # - --json produces valid JSON array

    # Red flags:
    # - Filters are AND instead of OR (or vice versa, depending on PRD intent)
    # - --json output not valid JSON


  @feature-epic-b @weight-0.30
  Scenario: edge_validation — All edge operations produce valid DOT
    Given any sequence of edge add/remove operations
    When the resulting DOT file is checked with `attractor validate`
    Then validation passes
    And no duplicate edges exist (same source and target)
    And no self-loops exist (unless --allow-cycle was used)

    # Confidence scoring guide:
    # 1.0 — All edge operations preserve DOT validity, self-loop and duplicate detection
    # 0.5 — Most operations valid but edge cases fail
    # 0.0 — Edge operations frequently produce invalid DOT

    # Evidence to check:
    # - DOT edge syntax correct (->  not --)
    # - Label quoting
    # - Consistent with digraph format

    # Red flags:
    # - Using undirected edge syntax (--)
    # - Missing node references in edges


  # ============================================================
  # EPIC C: Scaffold Generation Mode (Weight: 0.20)
  # ============================================================

  @feature-epic-c @weight-0.20
  Scenario: scaffold_basic — Generate minimal scaffold from beads
    Given beads exist with task data (epics/features)
    When the LLM runs `attractor generate --scaffold --output scaffold.dot`
    Then the output DOT file has exactly one start node and one exit node
    And each epic/feature maps to one placeholder codergen node
    And nodes are connected sequentially (start -> placeholder1 -> ... -> exit)
    And placeholder nodes have handler=codergen and status=pending
    And the DOT file passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — --scaffold flag produces minimal graph with start, exit, sequential
    #        placeholders, all nodes have correct attributes, validates
    # 0.5 — Scaffold generates but structure is not minimal (includes AT pairing,
    #        validation gates, or conditional routing)
    # 0.0 — --scaffold flag not implemented, or generates same as full generate

    # Evidence to check:
    # - --scaffold flag recognized by generate.py
    # - Start and exit nodes present
    # - Sequential (not parallel) edge layout
    # - No validation gates or conditional routing in scaffold
    # - Each placeholder labeled with epic/feature title

    # Red flags:
    # - Scaffold includes AT hexagons (should be added by LLM later)
    # - Scaffold includes diamond decision nodes (LLM designs these)
    # - More edges than (n-1) where n = number of nodes


  @feature-epic-c @weight-0.20
  Scenario: scaffold_prd_aware — Generate scaffold from PRD file
    Given a PRD markdown file exists with epic/feature headings
    When the LLM runs `attractor generate --scaffold --prd PRD-file.md --output scaffold.dot`
    Then each PRD epic maps to one placeholder codergen node
    And the node label matches the epic title from the PRD
    And acceptance criteria from the PRD are set as the node's acceptance attribute
    And if beads exist for the same epic, bead_id is cross-referenced

    # Confidence scoring guide:
    # 1.0 — --prd flag reads PRD markdown, extracts epics, maps to nodes with
    #        labels and acceptance criteria, cross-references beads
    # 0.5 — PRD parsing works but acceptance criteria not extracted, or bead
    #        cross-referencing missing
    # 0.0 — --prd flag not implemented

    # Evidence to check:
    # - PRD markdown parsing logic (regex or structured parser)
    # - Epic title extraction
    # - Acceptance criteria extraction
    # - Bead ID cross-referencing logic

    # Red flags:
    # - Only reads beads, ignores --prd file
    # - PRD parsing brittle (only works with specific heading format)
    # - No acceptance criteria in generated nodes


  @feature-epic-c @weight-0.20
  Scenario: scaffold_validation — Scaffold is a valid starting point for refinement
    Given a scaffold generated by `attractor generate --scaffold`
    When the LLM uses node/edge CRUD to add nodes, edges, validation gates
    Then each modification is individually validated
    And the final refined graph passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — Scaffold works as a base for iterative refinement, CRUD operations
    #        compose correctly with scaffold structure
    # 0.5 — Some CRUD operations fail on scaffold-generated DOT (parsing issues)
    # 0.0 — Scaffold output format incompatible with CRUD operations

    # Evidence to check:
    # - Scaffold DOT uses same format/conventions as CRUD output
    # - Node IDs in scaffold are valid DOT identifiers
    # - CRUD operations can parse scaffold-generated DOT

    # Red flags:
    # - Scaffold uses different DOT conventions than CRUD expects
    # - Node IDs contain characters that break CRUD parsing


  # ============================================================
  # EPIC D: Documentation Updates (Weight: 0.10)
  # ============================================================

  @feature-epic-d @weight-0.10
  Scenario: s3_output_style_docs — S3 output style has iterative refinement loop
    Given the System 3 output style file (system3-meta-orchestrator.md)
    When checked for DOT Graph Navigation documentation
    Then an "Iterative Refinement Loop" subsection exists
    And it documents: scaffold -> parse -> node add/remove -> edge add/remove -> validate -> checkpoint
    And it uses real CLI command examples (not pseudocode)
    And backward compatibility with existing workflows is noted

    # Confidence scoring guide:
    # 1.0 — Subsection exists with complete workflow, real CLI examples,
    #        backward compatibility note
    # 0.5 — Subsection exists but incomplete (missing some steps or using pseudocode)
    # 0.0 — No documentation update

    # Evidence to check:
    # - system3-meta-orchestrator.md contains "Iterative Refinement" section
    # - CLI command examples match actual implemented commands
    # - Existing DOT Graph Navigation section preserved

    # Red flags:
    # - Documentation references commands that don't exist
    # - Existing DOT Graph Navigation content removed or broken
    # - Only pseudocode, no real CLI examples


  @feature-epic-d @weight-0.10
  Scenario: orchestrator_skill_docs — Orchestrator skill has graph editing workflow
    Given the orchestrator-multiagent SKILL.md
    When checked for graph editing documentation
    Then a section on LLM graph editing workflow exists
    And it documents when orchestrators should use graph editing
    And it shows an example workflow of refining a scaffold
    And backward compatibility with existing workflows is noted

    # Confidence scoring guide:
    # 1.0 — Section exists with complete workflow, timing guidance (before execution),
    #        example refinement workflow, backward compatibility
    # 0.5 — Section exists but incomplete or lacks timing guidance
    # 0.0 — No documentation update

    # Evidence to check:
    # - orchestrator-multiagent/SKILL.md contains graph editing section
    # - Timing guidance: "use graph editing during planning, before execution"
    # - Example shows scaffold -> refine -> validate -> execute flow

    # Red flags:
    # - Documentation placed in wrong file
    # - Example workflow is generic (not specific to attractor CLI)


  # ============================================================
  # EPIC E: E2E Verification (Weight: 0.10)
  # ============================================================

  @feature-epic-e @weight-0.10
  Scenario: story_writer_scaffold — Generate scaffold for story-writer project
    Given the story-writer project at ~/Documents/Windsurf/story-writer
    When the LLM runs scaffold generation against story-writer
    Then a valid scaffold DOT file is produced
    And the scaffold passes `attractor validate`
    And placeholder nodes represent story-writer's structure

    # Confidence scoring guide:
    # 1.0 — Scaffold generated for story-writer, validates, nodes match project
    # 0.5 — Scaffold generates but doesn't reflect story-writer structure
    # 0.0 — Scaffold generation fails for story-writer

    # Evidence to check:
    # - Scaffold generated from story-writer beads or test PRD
    # - DOT file is valid Graphviz
    # - Validation passes

    # Red flags:
    # - Scaffold is generic (doesn't use story-writer data)
    # - Validation fails


  @feature-epic-e @weight-0.10
  Scenario: story_writer_refine — Refine story-writer scaffold with CRUD
    Given a scaffold generated for story-writer
    When the LLM uses node add, node remove, edge add, edge remove, node modify
    Then each operation succeeds without errors
    And the refined graph passes `attractor validate`

    # Confidence scoring guide:
    # 1.0 — All 5 CRUD operations work on the scaffold, result validates
    # 0.5 — Most operations work but some fail or produce invalid DOT
    # 0.0 — CRUD operations fail on story-writer scaffold

    # Evidence to check:
    # - Each of the 5 CRUD operations tested
    # - Result DOT file passes validation
    # - No orphan nodes or edges after operations

    # Red flags:
    # - Operations work on test files but not on real scaffold
    # - Validation fails after certain operation sequences


  @feature-epic-e @weight-0.10
  Scenario: story_writer_lifecycle — Full lifecycle test on story-writer
    Given a refined graph for story-writer
    When the LLM runs checkpoint save, status, and verifies dispatchable nodes
    Then checkpoint save produces a valid checkpoint JSON
    And status shows correct node states
    And dispatchable nodes are identified correctly

    # Confidence scoring guide:
    # 1.0 — Checkpoint, status, and dispatch identification all work on refined graph
    # 0.5 — Some commands work but not all
    # 0.0 — Post-refinement commands fail

    # Evidence to check:
    # - Checkpoint JSON file created
    # - Status table shows all nodes with correct status
    # - --filter=pending --deps-met identifies correct nodes

    # Red flags:
    # - Checkpoint doesn't preserve CRUD modifications
    # - Status doesn't show nodes added by CRUD
