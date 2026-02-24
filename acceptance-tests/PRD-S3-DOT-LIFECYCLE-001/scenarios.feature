# PRD-S3-DOT-LIFECYCLE-001: ZeroRepo-Powered Pipeline Lifecycle
# Blind acceptance tests — meta-orchestrators MUST NOT see this file

# ============================================================================
# EPIC 1: ZeroRepo .dot Export (weight: 0.30)
# ============================================================================

@feature-E1 @weight-0.30
Feature: ZeroRepo Attractor Pipeline Export

  @scenario-attractor_pipeline_export
  Scenario: Export produces valid Attractor-compatible DOT
    Given a ZeroRepo delta report exists with MODIFIED and NEW components
    When zerorepo-run-pipeline.py is invoked with --format=attractor-pipeline
    Then a .dot file is produced alongside the delta report
    And the .dot file passes `attractor validate` with zero errors
    And the .dot contains Mdiamond (start) and Msquare (finalize) bookend nodes

    # Confidence scoring guide:
    # 1.0 — .dot produced, passes validate, has correct bookends, correct shapes
    # 0.8 — .dot produced and passes validate but missing start/finalize bookends
    # 0.5 — .dot file produced but fails attractor validate (structural errors)
    # 0.2 — Export code exists but crashes or produces empty output
    # 0.0 — No --format=attractor-pipeline option exists; no attractor_exporter module

    # Evidence to check:
    # - src/zerorepo/graph_construction/attractor_exporter.py exists and has AttractorExporter class
    # - .claude/skills/orchestrator-multiagent/scripts/zerorepo-run-pipeline.py accepts --format=attractor-pipeline
    # - Run: python zerorepo-run-pipeline.py --format=attractor-pipeline on a test PRD
    # - Run: python .claude/scripts/attractor/cli.py validate <output.dot>

    # Red flags:
    # - attractor_exporter.py is empty or only has import statements
    # - .dot output is hardcoded rather than generated from delta data
    # - No unit tests for the exporter

  @scenario-delta_to_node_mapping
  Scenario: Delta classifications map to correct DOT node types
    Given a delta report with 2 MODIFIED and 3 NEW components and 1 EXISTING
    When the attractor pipeline export runs
    Then EXISTING components are NOT included in the .dot graph
    And MODIFIED components become box-shaped codergen nodes
    And NEW components become box-shaped codergen nodes
    And each codergen node has attributes: worker_type, acceptance, prd_ref

    # Confidence scoring guide:
    # 1.0 — All 3 classifications handled correctly, node attributes complete
    # 0.7 — Nodes created but EXISTING not filtered out, or attributes incomplete
    # 0.5 — Some nodes created but classification mapping is wrong
    # 0.2 — Code attempts mapping but crashes or produces invalid nodes
    # 0.0 — No delta-to-node mapping logic exists

    # Evidence to check:
    # - attractor_exporter.py: method that reads delta_status from components
    # - Grep for DeltaClassification.EXISTING, MODIFIED, NEW in exporter
    # - Node attributes in generated .dot: worker_type=, acceptance=, prd_ref=
    # - tests/unit/test_attractor_exporter.py tests for each classification

    # Red flags:
    # - All components become nodes regardless of delta_status
    # - worker_type is always "general-purpose" (no inference logic)
    # - No filtering of EXISTING components

  @scenario-at_pairing_generation
  Scenario: Every codergen node gets AT (Acceptance Test) pairing
    Given the attractor export produces codergen nodes
    When the .dot is generated
    Then every codergen node has a paired hexagon (validation gate) node
    And every hexagon has a paired diamond (decision) node
    And the triplet is connected: codergen → hexagon → diamond
    And the diamond has pass and fail outgoing edges

    # Confidence scoring guide:
    # 1.0 — All triplets present, edges correct, diamond has pass/fail routing
    # 0.7 — Triplets exist but diamond missing pass/fail edges
    # 0.5 — Hexagon nodes exist but not paired correctly to codergen
    # 0.2 — Only codergen nodes, no hexagon or diamond nodes
    # 0.0 — No AT pairing logic in the exporter

    # Evidence to check:
    # - attractor_exporter.py: loop or method that creates hexagon+diamond per codergen
    # - Generated .dot: count codergen nodes == count hexagon nodes == count diamond nodes
    # - Edge validation: each diamond has exactly 2 outgoing edges (pass, fail)
    # - attractor validate output: "AT pairing: OK"

    # Red flags:
    # - Hexagon nodes exist but are disconnected from codergen
    # - Diamond nodes have only 1 outgoing edge (no fail path)
    # - AT pairing is manually added rather than auto-generated

  @scenario-worker_type_inference
  Scenario: Worker type is inferred from file paths
    Given components have file paths like **/components/*.tsx and **/api/*.py
    When the attractor export generates codergen nodes
    Then .tsx components get worker_type="frontend-dev-expert"
    And .py API files get worker_type="backend-solutions-engineer"
    And test files get worker_type="tdd-test-engineer"
    And ambiguous files get worker_type="general-purpose"

    # Confidence scoring guide:
    # 1.0 — All 4 path patterns correctly inferred with tests
    # 0.7 — 3 of 4 patterns work, one falls through to general-purpose
    # 0.5 — Inference exists but only handles 1-2 patterns
    # 0.2 — worker_type field exists but is always hardcoded
    # 0.0 — No worker_type inference logic

    # Evidence to check:
    # - attractor_exporter.py: function matching file paths to worker types
    # - Pattern table: components/ → frontend, api/ → backend, tests/ → tdd
    # - tests/unit/test_attractor_exporter.py: test_worker_type_inference tests
    # - Generated .dot node attributes for mixed-path delta reports

    # Red flags:
    # - All nodes have worker_type="general-purpose"
    # - No regex or pattern matching in the inference code
    # - Tests mock the inference rather than testing real path patterns


# ============================================================================
# EPIC 2: Definition Pipeline Workflow (weight: 0.20)
# ============================================================================

@feature-E2 @weight-0.20
Feature: Definition Pipeline — PRD to .dot in One Command

  @scenario-end_to_end_definition
  Scenario: Single command produces validated .dot from PRD
    Given a PRD file exists at .taskmaster/docs/PRD-XXX.md
    When zerorepo-pipeline.sh --prd <PRD-FILE> --format=attractor is executed
    Then ZeroRepo init runs (if no baseline exists)
    And ZeroRepo generate runs with the PRD as spec
    And the delta is exported to Attractor-compatible .dot
    And attractor validate passes on the generated .dot
    And the .dot is stored at .claude/attractor/pipelines/<PRD-ID>.dot

    # Confidence scoring guide:
    # 1.0 — Full pipeline runs end-to-end, .dot at correct path, validate passes
    # 0.7 — Pipeline runs but .dot stored at wrong path or validate has warnings
    # 0.5 — Pipeline script exists but fails at one stage (e.g., export crashes)
    # 0.3 — Script exists but only does init+generate, no attractor export
    # 0.0 — No zerorepo-pipeline.sh script exists

    # Evidence to check:
    # - .claude/skills/orchestrator-multiagent/scripts/zerorepo-pipeline.sh exists
    # - Script has stages: init, generate, export, validate, annotate, init-promise
    # - Run the script on a test PRD and check output path
    # - .claude/attractor/pipelines/ directory structure

    # Red flags:
    # - Script only wraps zerorepo-run-pipeline.py without attractor steps
    # - No error handling between stages (one failure corrupts the whole pipeline)
    # - Summary report is hardcoded rather than computed from actual output

  @scenario-checkpoint_and_promise
  Scenario: Definition stage creates checkpoint and completion promise
    Given the definition pipeline has produced a valid .dot
    When the pipeline completes
    Then a checkpoint is saved at .claude/attractor/checkpoints/<PRD-ID>-definition.json
    And a completion promise is created with one AC per hexagon validation gate
    And a summary report is printed showing node counts by type and worker_type

    # Confidence scoring guide:
    # 1.0 — Checkpoint saved, promise created with correct AC count, summary accurate
    # 0.7 — Checkpoint saved but promise has wrong AC count or summary is incomplete
    # 0.5 — One of checkpoint/promise/summary is missing
    # 0.2 — Script completes but no checkpoint, promise, or summary
    # 0.0 — No checkpoint/promise/summary logic in the pipeline script

    # Evidence to check:
    # - zerorepo-pipeline.sh: calls to `attractor checkpoint save`
    # - zerorepo-pipeline.sh: calls to `cs-promise --create` with --ac flags
    # - Checkpoint file structure matches attractor CLI checkpoint schema
    # - Summary output: node_count, edge_count, worker_type distribution

    # Red flags:
    # - Checkpoint is a copy of the .dot file rather than the attractor JSON format
    # - Promise has a single generic AC instead of per-hexagon ACs
    # - Summary shows static numbers rather than actual graph statistics


# ============================================================================
# EPIC 3: Implementation Navigation (weight: 0.15)
# ============================================================================

@feature-E3 @weight-0.15
Feature: System 3 DOT Navigation for Orchestrator Dispatch

  @scenario-deps_met_filter
  Scenario: Status filter identifies dispatchable nodes
    Given a pipeline .dot with 5 codergen nodes and dependency edges
    And 2 upstream nodes are already validated
    When `attractor status --filter=pending --deps-met` is run
    Then only nodes whose ALL upstream dependencies are validated are returned
    And nodes with pending upstream dependencies are excluded

    # Confidence scoring guide:
    # 1.0 — Filter correctly identifies only dependency-met nodes with tests
    # 0.7 — Filter works but edge case with diamond nodes is wrong
    # 0.5 — --deps-met flag exists but doesn't check upstream status correctly
    # 0.2 — --filter=pending works but --deps-met is not implemented
    # 0.0 — No --deps-met flag in attractor CLI

    # Evidence to check:
    # - .claude/scripts/attractor/status.py: --deps-met argument handling
    # - Logic: for each pending node, check all upstream edges, all sources must be validated
    # - Unit test with a graph fixture testing dependency filtering
    # - cli.py status subcommand accepts --deps-met

    # Red flags:
    # - --deps-met only checks immediate parents, not transitive dependencies
    # - Filter returns ALL pending nodes regardless of upstream status
    # - No test for the dependency-met logic

  @scenario-orchestrator_spawn_metadata
  Scenario: Orchestrator spawn includes node metadata
    Given System 3 reads a pending .dot node with acceptance, worker_type, file_path, prd_ref
    When System 3 spawns an orchestrator for that node
    Then the orchestrator's wisdom injection includes the node's acceptance criteria
    And the recommended worker type matches the node's worker_type attribute
    And the scope boundaries include the node's file paths
    And the prd_ref is included for context

    # Confidence scoring guide:
    # 1.0 — Output style and skill docs updated, spawn template references node attributes
    # 0.7 — Spawn template exists but missing one of: acceptance/worker_type/file_paths/prd_ref
    # 0.5 — Documentation mentions node metadata but spawn template is unchanged
    # 0.2 — Only the output style mentions it, no actual template changes
    # 0.0 — No changes to spawn workflow or output style for node metadata injection

    # Evidence to check:
    # - .claude/output-styles/system3-meta-orchestrator.md DOT Navigation section
    # - .claude/skills/system3-orchestrator/SKILL.md spawn workflow
    # - Wisdom injection template: references to node.acceptance, node.worker_type
    # - ORCHESTRATOR_INITIALIZATION_TEMPLATE.md changes

    # Red flags:
    # - Changes are only comments/docs with no actual template modification
    # - Node attributes are mentioned but not parsed from the .dot graph
    # - Spawn workflow still uses hardcoded values instead of node attributes


# ============================================================================
# EPIC 4: Validation Gate Integration (weight: 0.20)
# ============================================================================

@feature-E4 @weight-0.20
Feature: Validation Gates Trigger Real Validation

  @scenario-hexagon_activation
  Scenario: impl_complete codergen activates paired hexagon
    Given a codergen node has reached impl_complete status
    When the attractor transition logic runs
    Then the paired hexagon (validation gate) node becomes activatable
    And s3-validator receives the hexagon's acceptance criteria as scope

    # Confidence scoring guide:
    # 1.0 — Activation logic implemented, hexagon receives correct acceptance criteria
    # 0.7 — Hexagon activates but acceptance criteria not passed to validator
    # 0.5 — Activation code exists but doesn't find the paired hexagon correctly
    # 0.2 — No activation logic, hexagon status must be changed manually
    # 0.0 — No changes to transition.py for hexagon activation

    # Evidence to check:
    # - .claude/scripts/attractor/transition.py: impl_complete handler
    # - Logic to find paired hexagon (traverse edges from codergen to hexagon)
    # - s3-validator prompt construction includes hexagon.acceptance attribute
    # - Test: transition codergen to impl_complete → hexagon becomes activatable

    # Red flags:
    # - Hexagon must be manually transitioned (no automatic activation)
    # - Acceptance criteria is hardcoded rather than read from hexagon attributes
    # - No edge traversal logic to find the paired hexagon

  @scenario-dual_pass_validation
  Scenario: Validation runs technical then business pass
    Given a hexagon node is activated with acceptance criteria
    When s3-validator runs validation
    Then technical validation (--mode=technical) runs first
    And if technical passes, business validation (--mode=business --prd=<prd_ref>) runs
    And if technical fails, business validation is skipped
    And evidence is stored at .claude/evidence/<node-id>/

    # Confidence scoring guide:
    # 1.0 — Both passes implemented, sequential logic correct, evidence stored
    # 0.7 — Both passes run but always sequentially (no short-circuit on tech fail)
    # 0.5 — Only one pass implemented (technical OR business, not both)
    # 0.2 — Validation logic exists but doesn't use node-specific criteria
    # 0.0 — No changes to validation workflow for node-based scoping

    # Evidence to check:
    # - .claude/skills/s3-guardian/SKILL.md Phase 4 integration
    # - .claude/agents/validation-test-agent.md node-based scope
    # - Evidence directory structure: .claude/evidence/{node-id}/
    # - Sequential logic: tech fail → skip business

    # Red flags:
    # - Both passes always run regardless of technical result
    # - Evidence stored at task-id level instead of node-id level
    # - validation_method not auto-inferred from file paths

  @scenario-fail_retry_routing
  Scenario: Failed validation routes codergen back to active
    Given a hexagon validation has failed
    When the decision diamond processes the failure
    Then the codergen node transitions back to active (retry)
    And a rejection message is sent to the orchestrator with failure details
    And the hexagon resets to pending

    # Confidence scoring guide:
    # 1.0 — Full fail path: diamond routes fail → codergen=active, hexagon=pending, message sent
    # 0.7 — Codergen goes back to active but hexagon doesn't reset
    # 0.5 — Fail path exists but no message sent to orchestrator
    # 0.2 — Diamond node exists but only pass edge implemented
    # 0.0 — No fail routing logic in the transition code

    # Evidence to check:
    # - transition.py: diamond node handler with pass/fail branching
    # - Fail branch: codergen → active, hexagon → pending
    # - Message bus or SendMessage call with failure details
    # - Finalize node blocks until ALL hexagons are validated

    # Red flags:
    # - Diamond only has a pass edge (no fail handling)
    # - Failed validation leaves codergen in impl_complete (stuck)
    # - No feedback mechanism to the orchestrator


# ============================================================================
# EPIC 5: Lifecycle Dashboard (weight: 0.08)
# ============================================================================

@feature-E5 @weight-0.08
Feature: Pipeline Lifecycle Dashboard

  @scenario-dashboard_output
  Scenario: Dashboard produces unified progress view
    Given a pipeline .dot with nodes in various states
    When `attractor dashboard <pipeline.dot>` is run
    Then output includes pipeline stage (Definition/Implementation/Validation/Finalized)
    And output includes node status distribution (pending/active/impl_complete/validated/failed)
    And output includes per-node detail with worker assignment and time in state
    And --output json produces machine-readable equivalent

    # Confidence scoring guide:
    # 1.0 — All 4 output sections present in both human and JSON formats
    # 0.7 — Dashboard shows status distribution but missing per-node detail or stage
    # 0.5 — Dashboard subcommand exists but only shows basic status (same as `status`)
    # 0.2 — Dashboard script file exists but doesn't produce useful output
    # 0.0 — No dashboard subcommand in attractor CLI

    # Evidence to check:
    # - .claude/scripts/attractor/dashboard.py exists
    # - .claude/scripts/attractor/cli.py: dashboard subcommand registered
    # - Output sections: stage, distribution, per-node table, promise progress
    # - JSON output: valid JSON matching human-readable content

    # Red flags:
    # - Dashboard is just an alias for `status` with no additional information
    # - Time-in-state calculation is hardcoded or always shows "0s"
    # - No JSON output mode


# ============================================================================
# EPIC 6: Regression Detection (weight: 0.07)
# ============================================================================

@feature-E6 @weight-0.07
Feature: Post-Finalize Regression Detection

  @scenario-regression_delta
  Scenario: Baseline comparison catches unintended changes
    Given a pre-implementation ZeroRepo baseline exists
    And implementation has modified in-scope files AND an out-of-scope file
    When zerorepo diff --baseline-before --baseline-after runs
    Then the out-of-scope file is flagged as unexpected change
    And a regression-check.dot graph is generated with the flagged files
    And in-scope modifications are NOT flagged (they are expected)

    # Confidence scoring guide:
    # 1.0 — Diff runs, flags only unexpected changes, produces regression .dot
    # 0.7 — Diff identifies changes but doesn't distinguish expected vs unexpected
    # 0.5 — Diff command exists but doesn't produce a .dot graph
    # 0.2 — Only the diff command exists, no regression classification logic
    # 0.0 — No zerorepo diff command or regression check script

    # Evidence to check:
    # - src/zerorepo/commands/diff.py exists
    # - .claude/scripts/zerorepo-regression-check.sh exists
    # - Logic: compare before/after, filter out in-scope components, flag EXISTING→MODIFIED
    # - Output: regression-check.dot with affected file paths

    # Red flags:
    # - All changes flagged as regressions (no in-scope filtering)
    # - Diff command only computes statistics, doesn't classify
    # - regression-check.dot is not Attractor-compatible
