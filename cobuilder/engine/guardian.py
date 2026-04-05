#!/usr/bin/env python3
"""guardian.py — Pilot Agent + Terminal Bridge (Layers 0 & 1).

Merged from guardian_agent.py (Layer 1) and launch_guardian.py (Layer 0).

Provides the interactive terminal (ccsystem3 / Layer 0) with the ability to
launch one or more headless Pilot agents (Layer 1) via the claude_code_sdk,
monitor them for terminal-targeted signals, and handle escalations or
completion events.

Architecture:
    guardian.py (Layer 0/1 — launch bridge + Pilot agent process)
        │
        ├── parse_args()                → CLI argument parsing (--dot | --multi)
        ├── build_system_prompt()       → pipeline execution instructions for Claude
        ├── build_initial_prompt()      → first user message with pipeline context
        ├── build_options()             → ClaudeCodeOptions (Bash only, max_turns, model)
        ├── launch_guardian()           → Single Pilot launch via Agent SDK query()
        ├── launch_multiple_guardians() → Parallel launch via asyncio.gather
        ├── monitor_guardian()          → Health-check loop watching terminal signals
        ├── handle_escalation()         → Format + forward Pilot escalation to user
        └── handle_pipeline_complete()  → Finalize and summarise a completed pipeline

CLAUDECODE environment note:
    The Pilot may be launched from inside a Claude Code session. To avoid
    nested-session conflicts, the environment is cleaned by stripping
    CLAUDECODE, CLAUDE_SESSION_ID, and CLAUDE_OUTPUT_STYLE, and setting
    PIPELINE_SIGNAL_DIR and PROJECT_TARGET_DIR for worker context.

Usage:
    # Single guardian
    python guardian.py \\
        --dot <path_to_pipeline.dot> \\
        --pipeline-id <id> \\
        [--project-root <path>] \\
        [--model <model_id>] \\
        [--max-turns <n>] \\
        [--signal-timeout <seconds>] \\
        [--max-retries <n>] \\
        [--signals-dir <path>] \\
        [--dry-run]

    # Parallel launch from JSON config
    python guardian.py --multi <configs.json>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Ensure this file's directory is importable regardless of invocation CWD.

import cobuilder.engine.identity_registry as identity_registry
from cobuilder.engine.dispatch_worker import load_engine_env

# Import signal_protocol at module level so tests can patch
# ``guardian.wait_for_signal`` directly via unittest.mock.patch.
from cobuilder.engine.signal_protocol import wait_for_signal  # noqa: E402

# Import merge_queue so it is available in the Pilot process for signal handling
try:
    import cobuilder.engine.merge_queue as merge_queue  # noqa: F401  (imported for side-effects / availability)
except ImportError:
    pass  # merge_queue not available in test-only environments

# ---------------------------------------------------------------------------
# Logfire instrumentation (required)
# ---------------------------------------------------------------------------
import logfire

# ---------------------------------------------------------------------------
# Event bus — agent message events to JSONL
# ---------------------------------------------------------------------------
try:
    from cobuilder.engine.events.types import EventBuilder as _EvB
    from cobuilder.engine.events.jsonl_backend import write_event_jsonl as _write_event
    _EVENTS_AVAILABLE = True
except ImportError:
    _EvB = None  # type: ignore[assignment,misc]
    _write_event = None  # type: ignore[assignment]
    _EVENTS_AVAILABLE = False

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# Gracefully handle missing Logfire project credentials:

# ---------------------------------------------------------------------------
# Pilot allowed_tools (Epic 3: Expand Tools)
# ---------------------------------------------------------------------------
# Pilot is a coordinator AND quality gate with FULL file access.
# It needs all tools to act as an autonomous goal-pursuing agent:
# - Write/Edit: for Gherkin .feature files, reports, manifest generation, SD patches
# - Bash/Read/Glob/Grep: investigation, test execution, service management
# - ToolSearch/Skill/LSP: deferred MCP loading, skill invocation
# - Serena: code navigation for validation inspection
# - Hindsight: learning from prior pipeline runs
# - Chrome DevTools + Claude-in-Chrome: browser-based Gherkin scenario execution
# - Perplexity/Context7: research when investigating failures
# - WebFetch/WebSearch: external verification
# - TodoWrite: tracking validation progress across multiple gates
_GUARDIAN_TOOLS: list[str] = [
    # Base tools — full file access
    "Bash", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "ToolSearch", "Skill", "LSP", "TodoWrite", "WebFetch", "WebSearch",
    # Serena: code navigation for validation inspection
    "mcp__serena__activate_project",
    "mcp__serena__check_onboarding_performed",
    "mcp__serena__find_symbol",
    "mcp__serena__search_for_pattern",
    "mcp__serena__get_symbols_overview",
    "mcp__serena__find_referencing_symbols",
    "mcp__serena__find_file",
    # Hindsight: learning storage
    "mcp__hindsight__retain",
    "mcp__hindsight__recall",
    "mcp__hindsight__reflect",
    # Context7: framework documentation for validating implementation approaches
    "mcp__context7__resolve-library-id",
    "mcp__context7__query-docs",
    # Perplexity: research when investigating failures or unfamiliar patterns
    "mcp__perplexity__perplexity_ask",
    "mcp__perplexity__perplexity_reason",
    "mcp__perplexity__perplexity_research",
    "mcp__perplexity__perplexity_search",
    # Chrome DevTools MCP: browser-based validation (UI Gherkin scenarios)
    # Available via project-level MCP config — works in SDK sessions (unlike claude-in-chrome)
    "mcp__chrome-devtools__navigate_page",
    "mcp__chrome-devtools__take_screenshot",
    "mcp__chrome-devtools__take_snapshot",
    "mcp__chrome-devtools__evaluate_script",
    "mcp__chrome-devtools__click",
    "mcp__chrome-devtools__fill",
    "mcp__chrome-devtools__fill_form",
    "mcp__chrome-devtools__list_pages",
    "mcp__chrome-devtools__select_page",
    "mcp__chrome-devtools__new_page",
    "mcp__chrome-devtools__close_page",
    "mcp__chrome-devtools__hover",
    "mcp__chrome-devtools__press_key",
    "mcp__chrome-devtools__type_text",
    "mcp__chrome-devtools__wait_for",
    "mcp__chrome-devtools__list_console_messages",
    "mcp__chrome-devtools__list_network_requests",
]
# When running in an impl repo without .logfire/, logfire.configure()
# triggers an interactive prompt that crashes non-interactive contexts.
_send_to_logfire_env = os.environ.get("LOGFIRE_SEND_TO_LOGFIRE", "").lower()
if _send_to_logfire_env == "false":
    _logfire_enabled = False
elif _send_to_logfire_env == "true":
    _logfire_enabled = True
else:
    _logfire_enabled = (
        Path(".logfire").is_dir()
        or bool(os.environ.get("LOGFIRE_TOKEN"))
    )

logfire.configure(
    service_name="cobuilder-guardian",
    send_to_logfire=_logfire_enabled,
    inspect_arguments=False,
    scrubbing=False,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_TURNS = 200          # more turns than runner; Pilot runs longer
DEFAULT_SIGNAL_TIMEOUT = 600     # 10 minutes per wait cycle
DEFAULT_MAX_RETRIES = 3          # max retries per node before escalating
DEFAULT_MONITOR_TIMEOUT = 3600   # 1 hour total monitor timeout
DEFAULT_MODEL = "claude-sonnet-4-6"  # default Claude model for Pilot


# ---------------------------------------------------------------------------
# Public helper functions (importable for testing)
# ---------------------------------------------------------------------------


def build_system_prompt(
    dot_path: str,
    pipeline_id: str,
    scripts_dir: str,
    signal_timeout: float,
    max_retries: int,
    target_dir: str = "",
    max_cycles: int = 3,
    event_driven: bool = False,
) -> str:
    """Return the system prompt that instructs the Pilot agent how to run the pipeline.

    Args:
        dot_path: Absolute path to the pipeline DOT file.
        pipeline_id: Unique pipeline identifier string.
        scripts_dir: Absolute path to the attractor scripts directory.
        signal_timeout: Seconds to wait per signal wait cycle.
        max_retries: Maximum retries allowed per node before escalation.
        target_dir: Target implementation repo directory.
        max_cycles: Maximum full research→validate cycles before forced exit (default: 3).
        event_driven: If True, append event-driven mode instructions that override
            the polling behavior in Phase 2.

    Returns:
        Formatted system prompt string.
    """
    target_dir_line = f"- Target directory: {target_dir}"
    target_dir_flag = f" --target-dir {target_dir}"  # noqa: F841
    base_prompt = f"""\
You are the Pilot agent (Layer 1) in a 4-layer pipeline execution system.

Your role: Drive pipeline execution autonomously by reading the DOT graph, spawning
Runners for each codergen node, handling signals, and transitioning node statuses.

## Your Assignment
- Pipeline DOT: {dot_path}
- Pipeline ID: {pipeline_id}
- Scripts directory: {scripts_dir}
- Signal timeout: {signal_timeout}s per wait cycle
- Max retries per node: {max_retries}
{target_dir_line}

## Tools Available (via Bash — use python3 to invoke)
All scripts are in {scripts_dir}:

### Attractor CLI (pipeline management)
- python3 {scripts_dir}/cli.py status {dot_path} --filter=pending --deps-met --json    # Find ready nodes
- python3 {scripts_dir}/cli.py status {dot_path} --json                                  # Full status
- python3 {scripts_dir}/cli.py parse {dot_path} --output json                            # Full graph
- python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> <new_status>  # Advance status
- python3 {scripts_dir}/cli.py checkpoint save {dot_path}                                # Save checkpoint

### Signal Tools
- python3 {scripts_dir}/wait_for_signal.py --target guardian --timeout {signal_timeout}  # Wait for runner
- python3 {scripts_dir}/read_signal.py <signal_path>                                      # Read signal
- python3 {scripts_dir}/respond_to_runner.py VALIDATION_PASSED --node <id>               # Approve
- python3 {scripts_dir}/respond_to_runner.py VALIDATION_FAILED --node <id> --feedback <text>  # Reject
- python3 {scripts_dir}/respond_to_runner.py INPUT_RESPONSE --node <id> --response <text>     # Decide
- python3 {scripts_dir}/respond_to_runner.py GUIDANCE --node <id> --message <text>            # Guide
- python3 {scripts_dir}/respond_to_runner.py KILL_ORCHESTRATOR --node <id> --reason <text>    # Abort
- python3 {scripts_dir}/escalate_to_terminal.py --pipeline {pipeline_id} --issue <text>   # Escalate

### Pipeline Runner Launch
- python3 {scripts_dir}/pipeline_runner.py --dot-file {dot_path} &   # Launch runner in BACKGROUND
- python3 {scripts_dir}/cli.py status {dot_path} --json              # Check runner progress

CRITICAL: Always run pipeline_runner.py with & (background). If you run it in the foreground,
you will DEADLOCK when the runner hits a gate node — it will wait for your GATE_RESPONSE signal,
but you'll be blocked waiting for it to exit.

### Gate Handling
When a node with handler=wait.cobuilder or wait.human becomes active, the runner is blocked
waiting for you to validate or approve.

For wait.cobuilder gates:
1. Read the codergen node's acceptance criteria from the DOT
2. Verify the work was done (check files exist, run tests via Bash)
3. If PASS: transition the gate to validated
   python3 {scripts_dir}/cli.py transition {dot_path} <gate_node> validated
4. If FAIL: transition the codergen node back to pending for retry
   python3 {scripts_dir}/cli.py transition {dot_path} <codergen_node> pending

For wait.human gates:
1. Check if you can validate autonomously (technical criteria)
2. If autonomous: transition to validated
3. If human needed: escalate to Terminal

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

### Signal Handler Types
When reading signals via wait_for_signal.py, you may encounter these signal types from runners:
- NEEDS_REVIEW: Worker completed but requires Pilot review before validation
- NEEDS_INPUT: Worker is blocked and requires human input to proceed
- VIOLATION: Policy or constraint violation detected during execution
- ORCHESTRATOR_STUCK: The orchestrator has stalled and cannot make progress
- ORCHESTRATOR_CRASHED: The orchestrator process terminated unexpectedly
- NODE_COMPLETE: A node has finished execution and is ready for transition

### Response Types (via respond_to_runner.py)
- VALIDATION_PASSED: Approve the work and transition node to validated
- VALIDATION_FAILED: Reject the work with feedback, retry or escalate
- INPUT_RESPONSE: Provide the requested input to unblock the worker
- GUIDANCE: Send guidance to help the worker without approval/rejection
- KILL_ORCHESTRATOR: Terminate the runner process for the specified node

## Signal-Based Communication System
Nodes communicate via signal files. The signal directory is your primary observability layer.

### How It Works
1. **Workers** write completion signals: `{{status, files_changed, message}}`
2. **Validators** write scoring signals: `{{result, scores, overall_score, criteria_results}}`
3. **Runner** reads signals, moves them to `processed/`, and transitions node statuses
4. **Next node** in the DAG reads predecessor signals from `processed/` for context

### What You Can Read
- **Active signals** (pending pickup): check the signals directory for in-flight results
- **Processed signals** (historical): read validator scores, worker outputs, retry feedback
- **Score history**: check if validation scores are improving across retries

### Validator Scoring (MANDATORY)
Every validation signal MUST include `scores`, `overall_score`, and `criteria_results`.
The runner rejects pass signals without scores (requeues the validation).
- Pass threshold: overall_score >= 7.0
- Dimensions: correctness (35%), completeness (25%), code_quality (15%), sd_adherence (10%), process_discipline (15%)
- Each `criteria_results` entry is a per-AC verdict that the worker sees on retry

### How to Use This for Decisions
When a node fails and you need to decide whether to retry, inject a fix-it node, or escalate:
1. Read the validator's signal in `processed/` — check `criteria_results` for specific failures
2. Read `overall_score` history — is the score improving? If plateau detected, restructure
3. Read the worker's signal — check `files_changed` and `message` for what was attempted

This is a file-based messaging system. Each node leaves breadcrumbs for the next.

## Pipeline Execution Flow

### Phase 0: Load CoBuilder Context
BEFORE anything else, invoke the CoBuilder skill to load project conventions,
architecture patterns, and pipeline awareness:
```
Skill(skill="cobuilder")
```
Do this FIRST. It provides critical context for all subsequent decisions.

### Phase 1: Initialize
1. Parse the DOT file:
   python3 {scripts_dir}/cli.py parse {dot_path} --output json
2. Validate the pipeline:
   python3 {scripts_dir}/cli.py validate {dot_path} --output json
3. Get current status:
   python3 {scripts_dir}/cli.py status {dot_path} --json

### Phase 2a: Dispatch Research Nodes (BEFORE codergen)
4a. Find ready research nodes:
    python3 {scripts_dir}/cli.py status {dot_path} --filter=pending --deps-met --json
    Filter output for nodes with handler="research".
4b. For each ready research node:
   a. Transition to active:
      python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> active
   b. Save checkpoint:
      python3 {scripts_dir}/cli.py checkpoint save {dot_path}
   c. Run research agent (synchronous — completes in seconds):
      python3 {scripts_dir}/run_research.py --node <node_id> --prd <prd_ref> \
          --solution-design <solution_design_attr> --target-dir {target_dir} \
          --frameworks <research_queries_attr> \
          --prd-path <prd_path_attr if present>
   d. Parse the JSON output from stdout
   e. If status=ok and sd_updated=true:
      - The SD has been updated with validated patterns
      - Transition research node to validated:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> validated
      - Save checkpoint
      - Log: "Research validated N frameworks, updated SD at <sd_path>"
   f. If status=ok and sd_updated=false:
      - SD was already current — no changes needed
      - Transition research node to validated:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> validated
      - Save checkpoint
   g. If status=error:
      - Transition to failed:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> failed
      - Escalate: python3 {scripts_dir}/escalate_to_terminal.py --pipeline {pipeline_id} --issue "Research failed for <node_id>: <error>"

Research nodes are dispatched BEFORE codergen nodes. The downstream codergen node's dependency
on the research node is enforced by DOT edges — it won't appear in --deps-met until research
is validated.

### Phase 2a.5: Dispatch Refine Nodes (AFTER research, BEFORE codergen)
4c. Find ready refine nodes:
    python3 {scripts_dir}/cli.py status {dot_path} --filter=pending --deps-met --json
    Filter output for nodes with handler="refine".
4d. For each ready refine node:
   a. Transition to active:
      python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> active
   b. Save checkpoint:
      python3 {scripts_dir}/cli.py checkpoint save {dot_path}
   c. Run refine agent (synchronous — uses Sonnet, takes ~30-60s):
      python3 {scripts_dir}/run_refine.py --node <node_id> --prd <prd_ref> \
          --solution-design <solution_design_attr> --target-dir {target_dir} \
          --evidence-path <evidence_path_attr> \
          --prd-path <prd_path_attr if present>
   d. Parse the JSON output from stdout
   e. If status=ok and sd_updated=true:
      - The SD has been rewritten with research findings as first-class content
      - All inline research annotations have been removed
      - Transition refine node to validated:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> validated
      - Save checkpoint
      - Log: "Refine completed: rewrote N sections, patched M sections, removed K annotations"
   f. If status=ok and sd_updated=false:
      - SD needed no refinement beyond what research already did
      - Transition refine node to validated:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> validated
      - Save checkpoint
   g. If status=error:
      - Transition to failed:
        python3 {scripts_dir}/cli.py transition {dot_path} transition <node_id> failed
      - Escalate: python3 {scripts_dir}/escalate_to_terminal.py --pipeline {pipeline_id} --issue "Refine failed for <node_id>: <error>"

Refine nodes run AFTER research and BEFORE codergen. They transform inline research
annotations into production-quality SD content. The downstream codergen node's dependency
on the refine node is enforced by DOT edges — it won't appear in --deps-met until refine
is validated.

### Phase 2: Launch Pipeline Runner (Background)
4. Launch the pipeline runner in the BACKGROUND:
   python3 {scripts_dir}/pipeline_runner.py --dot-file {dot_path} &
   RUNNER_PID=$!
   echo "Pipeline runner launched with PID: $RUNNER_PID"

   CRITICAL: Always use & (background). Foreground execution will DEADLOCK at gate nodes.

5. Poll the runner process and handle gates:
   ```bash
   while ps -p $RUNNER_PID > /dev/null 2>&1; do
       # Check for gate signals (runner is blocked waiting for you)
       ls {scripts_dir}/../signals/*GATE*.signal 2>/dev/null

       # Check node statuses for progress
       python3 {scripts_dir}/cli.py status {dot_path} --json

       sleep 30
   done
   ```

6. When the runner hits a gate node (wait.cobuilder or wait.human):
   a. Read the gate signal file to identify which node is blocked
   b. For wait.cobuilder gates — run the **Pilot Gherkin Validation Protocol**:

      ### Pilot Gherkin Validation Protocol
      You MUST independently validate the upstream worker's implementation. Do NOT rubber-stamp
      — you are the quality gate. Code analysis alone is NOT sufficient for UI features.

      CRITICAL RULE: If a feature has validation_method=browser-required, you MUST call
      mcp__chrome-devtools__* tools (navigate_page, evaluate_script, take_screenshot, click, wait_for).
      If you validate a browser-required feature using ONLY code reading or npm run build,
      the validation is INVALID and you MUST NOT pass the gate. Score it 0.0 instead.
      Browser validation is NON-NEGOTIABLE for UI features — there are no fallbacks.

      **Step 0: Check for pre-existing acceptance tests (ALWAYS DO THIS FIRST)**
      - Read the gate node's `prompt` attribute for the PRD/SD reference
      - Check if `acceptance-tests/<prd_ref>/` exists in the harness repo (cobuilder_root)
      - If it exists, read `acceptance-tests/<prd_ref>/manifest.yaml` for:
        - Feature list with `validation_method` per feature
        - Scoring thresholds (accept/investigate/reject)
      - If `acceptance-tests/<prd_ref>/executable-tests/` exists:
        - These are EXECUTABLE browser test specs — YAML files that map Gherkin scenarios
          to mcp__chrome-devtools__* tool calls with assertions
        - You MUST execute these using mcp__chrome-devtools__* tools — NOT just read them
        - Read `executable-tests/config.yaml` for base_url and test data
        - For EACH test in each YAML file:
          1. Call mcp__chrome-devtools__navigate_page to load the page
          2. Call mcp__chrome-devtools__evaluate_script to run each JS assertion
          3. Call mcp__chrome-devtools__take_screenshot for evidence
          4. Record PASS/FAIL per assertion
        - If Chrome is not reachable, score ALL browser-required features as BLOCKED (0.0)
          and report the blocker — do NOT fall back to code analysis

      **Step 1: Gather context**
      - Read the upstream codergen node's `acceptance` attribute from the DOT file
      - Read the worker's completion signal from processed/ to see `files_changed`
      - Read the validator's scoring signal (if exists) to see `criteria_results`

      **Step 2: Determine validation method per feature**
      Check `validation_method` in the manifest (or infer from file types):
      - `browser-required` → You MUST use mcp__chrome-devtools__* tools to load the page
        and verify DOM structure, CSS classes, layout, and visual elements
      - `api-required` → You MUST make real HTTP requests (curl/httpx)
      - `code-analysis` → Read source files and verify logic
      - `hybrid` → Mix of methods as appropriate

      If executable-tests/ exist, use them. Otherwise write your own Gherkin:
      Create a `.feature` file: `acceptance-tests/{{pipeline_id}}/<gate_node>-pilot.feature`

      Each AC gets a scenario tagged with its validation method:
      - `AC-1 [browser-check]: ...` → tag scenario with `@browser-check`
      - `AC-2 [api-call]: ...` → tag scenario with `@api-call`
      - `AC-3 [unit-test]: ...` → tag scenario with `@unit-test`
      - No method specified → infer from file types (`.tsx` → browser, `routes.py` → API, else unit)

      ```gherkin
      Feature: Pilot validation of <node_label>

        @api-call
        Scenario: AC-1 API endpoint returns correct response
          Given the API server is running on the target project
          When I POST /api/endpoint with valid payload
          Then the response status is 200
          And the response body matches the AC specification
      ```

      **Step 3: Execute each scenario**
      Run each scenario using its tagged method:
      - `@browser-check`: Use mcp__chrome-devtools__navigate_page, evaluate_script,
        take_screenshot, click, wait_for to load pages and verify UI
      - `@api-call`: Use `Bash(command="curl ...")` or httpx to make real HTTP requests
      - `@unit-test`: Run `Bash(command="pytest <test_file>")` or `Bash(command="jest <test>")`
      - `@code-review`: Use Read/Grep to inspect implementation (LOWEST confidence — avoid for UI)

      **Step 4: Decide based on results**
      - ALL scenarios pass → transition gate to validated:
        python3 {scripts_dir}/cli.py transition {dot_path} <gate_node> validated
      - ANY scenario fails → transition codergen node back to pending with feedback:
        python3 {scripts_dir}/cli.py transition {dot_path} <codergen_node> pending
        Write failure details to the signal directory so the worker gets them on retry.

   c. For wait.human gates:
      - If you can validate autonomously: transition to validated
      - If human input needed: escalate to Terminal

### Phase 2.5: SD Fidelity Monitoring (during implementation)
While the runner is executing worker nodes, actively monitor SD fidelity:

7. After each node reaches `impl_complete`, BEFORE the validator runs:
   a. Read the worker's completion signal from the processed/ directory
   b. Read the Solution Design for that node (from the node's `sd_path` attribute)
   c. Compare `files_changed` against the SD's expected file structure
   d. Check: did the worker create the files the SD specifies?
   e. Check: did the worker touch files NOT in the SD scope? (drift detection)
   f. If major SD drift is detected (>50% of files are off-plan):
      - Write a warning to `acceptance-tests/{pipeline_id}/<node_id>-sd-fidelity.md`
      - The validator will read this as additional context for scoring `sd_adherence`
   g. If the worker's approach is clearly superior to the SD, note it — SD can be evolved

### Phase 3: Validate Stage — Gherkin + Integration + PRD

This is where you act as the quality gate. Don't rubber-stamp — you are the user's agent.

**Per-Node Validation (at each gate):**

8. When a gate node fires (wait.cobuilder):
   a. Run the **Pilot Gherkin Validation Protocol** (see Gate Handling above)
   b. Additionally perform **Cross-Node Integration Check**:
      - Read all predecessor nodes' signals from processed/
      - Check API contracts: do frontend nodes call endpoints backend nodes created?
      - Check shared types: do interfaces match across nodes?
      - Check file overlap: did multiple nodes modify the same files?
      - Write integration findings to `acceptance-tests/{pipeline_id}/integration-report.md`

**Gherkin Persistence (across retries):**
   c. On first attempt: write `acceptance-tests/{pipeline_id}/<node_id>.feature` with scenarios
   d. On retry: READ the existing `.feature` file, DON'T rewrite from scratch:
      - Add regression scenarios for previously-failing ACs
      - Evolve Given/When/Then based on what changed
      - Add comments tracking which attempt each scenario was added
   e. The `.feature` file is a living document — it grows across retries

### Phase 4: Pipeline Completion Validation

When all nodes reach `accepted`, DO NOT immediately signal PIPELINE_COMPLETE.
First, run a pipeline-level E2E validation:

9. **Auto-generate manifest** from DOT node ACs:
   - Read all node `acceptance` attributes (with per-AC `[method]` tags)
   - Write `acceptance-tests/<prd_ref>/manifest.yaml` with features, weights, methods
   - This replaces any hand-written manifest

10. **Aggregate Gherkin into E2E suite**:
   - Read all per-node `.feature` files from `acceptance-tests/{pipeline_id}/`
   - Write `acceptance-tests/{pipeline_id}/e2e-suite.feature` with:
     a. Cross-cutting scenarios that test the full feature end-to-end
     b. Integration scenarios that verify nodes work together
     c. PRD-level scenarios that map back to original requirements

11. **Execute the E2E suite**:
   - Run each scenario using its tagged method (@browser-check, @api-call, @unit-test)
   - Record pass/fail per scenario

12. **Write pipeline validation report**:
   - Save to `acceptance-tests/{pipeline_id}/pipeline-validation-report.md`
   - Include: per-node scores, cross-node integration results, PRD coverage
   - Include: score trends across retries (improving? stalled?)
   - Include: SD fidelity summary across all nodes
   - Include: final E2E suite results

13. **Decide**:
   - ALL E2E scenarios pass AND PRD requirements covered:
     - Save final checkpoint: python3 {scripts_dir}/cli.py checkpoint save {dot_path}
     - Signal completion: python3 {scripts_dir}/escalate_to_terminal.py --pipeline {pipeline_id} --issue "PIPELINE_COMPLETE"
   - ANY E2E scenario fails:
     - Identify which node(s) need rework
     - Transition those nodes back to pending with specific feedback
     - Re-launch runner: python3 {scripts_dir}/pipeline_runner.py --dot-file {dot_path} &
     - Do NOT signal PIPELINE_COMPLETE until E2E passes

### Phase 5: Handle Failures

14. Handle based on node state:

   ANY NODE failed permanently (retries exhausted or plateau detected):
   - Check if the failure blocks downstream nodes
   - If the failure is isolated: can remaining nodes still complete?
   - If the failure cascades: escalate
     python3 {scripts_dir}/escalate_to_terminal.py --pipeline {pipeline_id} --issue "Node <node_id> failed after {max_retries} retries"

   RUNNER CRASHED (no status update):
   - Check stderr logs for diagnostics
   - Retry or escalate as appropriate

15. Pipeline is complete ONLY when:
   - All non-start/exit nodes are validated/accepted
   - Pipeline E2E suite passes
   - PRD requirements are covered

## Retry Tracking
Track retries per node in memory (dict). When a node exceeds {max_retries} retries, do not
spawn again — escalate to Terminal with full context.

## Hook Phase Tracking
Update pipeline phase at lifecycle transitions:

When beginning validation of a pipeline node:
```bash
python3 {scripts_dir}/hook_manager.py update-phase guardian {pipeline_id} validating
```

After successful merge of a node:
```bash
python3 {scripts_dir}/hook_manager.py update-phase guardian {pipeline_id} merged
```

## Merge Queue Integration
The merge queue handles sequential merging of completed nodes. Use these commands:

Check for pending merges:
```bash
python3 {scripts_dir}/merge_queue.py process_next --pipeline {pipeline_id}
```

Signal merge completion:
```bash
python3 {scripts_dir}/merge_queue.py write_signal MERGE_COMPLETE --node <node_id>
```

Signal merge failure:
```bash
python3 {scripts_dir}/merge_queue.py write_signal MERGE_FAILED --node <node_id> --reason <reason>
```

## Identity Scanning
Before dispatching workers, scan for identity conflicts in the DOT graph.
Ensure all nodes have unique identifiers and no duplicate handler assignments.

## Failure Context for Retry Loops
When a validation fails and you need to loop back to research:
1. Write a failure summary BEFORE transitioning back:
   ```bash
   cat >> state/${{INITIATIVE_ID}}-failures.md << 'EOF'
   ## Cycle N Failure Summary
   - Node: <node_id>
   - Reason: <why it failed>
   - Attempted: <what was tried>
   - Root cause: <analysis>
   EOF
   ```
2. Use APPEND (`>>`) not overwrite (`>`) — each cycle adds context
3. The RESEARCH node will read this file on its next run to focus investigation

## Cycle Tracking and Bounds Enforcement
Track the number of full research→validate cycles in a state file:

Before each loop-back to RESEARCH:
1. Read current cycle count:
   ```bash
   CYCLES=$(cat state/{pipeline_id}-cycle-count.txt 2>/dev/null || echo 0)
   ```
2. Increment:
   ```bash
   echo $((CYCLES + 1)) > state/{pipeline_id}-cycle-count.txt
   ```
3. Check against max_cycles ({max_cycles}):
   ```bash
   if [ $((CYCLES + 1)) -ge {max_cycles} ]; then
       # Max cycles reached — transition to CLOSE with exhaustion reason
       python3 {scripts_dir}/cli.py transition {dot_path} close active
       python3 {scripts_dir}/cli.py transition {dot_path} close validated
       echo "Max cycles ({max_cycles}) exhausted. Closing pipeline."
       exit 0
   fi
   ```
4. Only loop back if cycles remain

The max_cycles value is {max_cycles} (from pipeline manifest or default).

### Template Instantiation (For PLAN Nodes)
When a PLAN node needs to generate a child implementation pipeline:

1. Read the refined BS:
   cat state/{pipeline_id}-refined.md

2. Break into implementation tasks (each task = one codergen node)

3. Instantiate a template:
   python3 -c "
   from cobuilder.templates.instantiator import instantiate_template
   instantiate_template('sequential-validated', {{
       'initiative_id': '{pipeline_id}-impl',
       'tasks': [...],
       'target_dir': '{target_dir}',
       'cobuilder_root': '{{cobuilder_root}}',
   }}, output_path='.pipelines/pipelines/{pipeline_id}-impl.dot')
   "

   OR create a DOT file manually using node/edge CRUD:
   python3 {scripts_dir}/cli.py node <dot_path> add impl_task_1 --handler codergen ...

4. Write the plan file:
   cat > state/{pipeline_id}-plan.json << 'EOF'
   {{
       "dot_path": ".pipelines/pipelines/{pipeline_id}-impl.dot",
       "template": "sequential-validated",
       "task_count": N,
       "tasks": [{{"id": "task_1", "description": "..."}}]
   }}
   EOF

5. The EXECUTE node will read this plan and implement each task.

## Important Rules
- You have FULL file access (Write/Edit) for: Gherkin .feature files, reports, manifests, SD patches
- Do NOT use Write/Edit to modify implementation source code — that's workers' job
- NEVER guess at node status — always read from the DOT file via CLI
- ALWAYS checkpoint after every status transition
- When in doubt about a validation decision, err on the side of VALIDATION_FAILED with specific feedback
- Escalate to Terminal (Layer 0) only when you cannot resolve without human input
- You are an AUTONOMOUS AGENT acting on behalf of the user to achieve the PRD goal
- Your job is not just to check boxes — it's to ensure the software actually works end-to-end
- If the SD is wrong but the implementation is better, note it and update the SD
- If the PRD requirements aren't achievable as written, escalate with a specific proposal
"""

    if not event_driven:
        return base_prompt

    # In event-driven mode, append override instructions that replace the polling loop.
    event_driven_section = f"""

## EVENT-DRIVEN MODE (ACTIVE)

**IMPORTANT: You are running in event-driven mode. This OVERRIDES the polling instructions
in Phase 2 Step 5 above.**

### How Event-Driven Mode Works
- You will receive GATE EVENTS, FAILURE EVENTS, and COMPLETION EVENTS as separate
  user messages (queries) in this same conversation
- Between queries, you are SLEEPING at zero cost — the Python layer watches the signal
  directory using filesystem events (watchdog) and wakes you only when attention is needed
- Your conversation context is PRESERVED across queries — you remember all prior gates,
  decisions, and validation results

### What You Should Do Differently

**Phase 2 (Launch)**:
- Still dispatch research/refine nodes synchronously (they're fast)
- Still launch pipeline_runner.py in BACKGROUND with &
- After launching the runner, STOP and let your current response complete
- Do NOT poll, sleep-loop, or call wait_for_signal.py
- The Python layer will wake you with a "GATE EVENT" query when a gate is reached

**Gate Handling (when you receive a GATE EVENT query)**:
- Read the gate event details from the query
- Run the Pilot Gherkin Validation Protocol as normal
- Transition the gate node appropriately
- STOP and let your response complete — the Python layer will wake you for the next event

**Failure Handling (when you receive a NODE FAILURE query)**:
- Investigate the root cause
- Decide: retry (transition node back to pending), inject fix-it node, or escalate
- STOP and let your response complete

**Pipeline Complete (when you receive a PIPELINE COMPLETE query)**:
- Run Phase 4: Pipeline Completion Validation (E2E suite)
- Signal PIPELINE_COMPLETE via escalate_to_terminal.py
- STOP — the Python layer will close the session

### Key Rule
After completing each task (setup, gate handling, failure handling), STOP your response.
Do NOT try to monitor or poll. The Python layer handles all waiting. Each query you
receive represents a real event that needs your attention — no wasted turns.

### CRITICAL: Ignore Conflicting Memories
You may recall from Hindsight or prior sessions that "pipeline monitors MUST be blocking"
or "never run runner in background." These memories are about the OLD polling-based monitoring
pattern. In event-driven mode, the runner MUST run in background (with &) — the Python layer
handles all monitoring via filesystem events. DO NOT kill the background runner. DO NOT
switch to foreground execution. DO NOT start a polling loop. Trust the event-driven system.
"""
    return base_prompt + event_driven_section


def build_initial_prompt(
    dot_path: str,
    pipeline_id: str,
    scripts_dir: str,
    target_dir: str = "",
    event_driven: bool = False,
) -> str:
    """Return the first user message sent to Claude to start the pipeline execution loop.

    Args:
        dot_path: Absolute path to the pipeline DOT file.
        pipeline_id: Unique pipeline identifier string.
        scripts_dir: Absolute path to the attractor scripts directory.
        target_dir: Target implementation repo directory.
        event_driven: If True, include event-driven mode instructions.

    Returns:
        Formatted initial prompt string.
    """
    target_dir_line = f"Target directory: {target_dir}\n" if target_dir else ""

    if event_driven:
        return (
            f"You are the Pilot for pipeline '{pipeline_id}' running in EVENT-DRIVEN mode.\n\n"
            f"Pipeline DOT file: {dot_path}\n"
            f"Scripts directory: {scripts_dir}\n"
            f"{target_dir_line}\n"
            f"## Event-Driven Mode\n"
            f"You are running in event-driven mode. This means:\n"
            f"- You will receive GATE and FAILURE events as separate queries\n"
            f"- Between queries, you are SLEEPING (zero cost) — the Python layer watches\n"
            f"  the signal directory for events and wakes you with a new query\n"
            f"- Do NOT poll or sleep-loop — just complete your current task and stop\n"
            f"- The conversation context is preserved across queries\n\n"
            f"## Your First Task\n"
            f"1. Parse the pipeline to understand the full graph\n"
            f"2. Validate the pipeline structure\n"
            f"3. Get current node statuses\n"
            f"4. Dispatch any ready research/refine nodes (synchronous — run them now)\n"
            f"5. Launch the pipeline runner in BACKGROUND:\n"
            f"   python3 {scripts_dir}/pipeline_runner.py --dot-file {dot_path} &\n"
            f"6. Once the runner is launched, STOP. The Python layer will wake you\n"
            f"   when a gate event occurs.\n\n"
            f"If the pipeline is already partially complete (some nodes are already validated),\n"
            f"skip those nodes and continue from the current state.\n"
        )

    return (
        f"You are the Pilot for pipeline '{pipeline_id}'.\n\n"
        f"Pipeline DOT file: {dot_path}\n"
        f"Scripts directory: {scripts_dir}\n"
        f"{target_dir_line}\n"
        f"Begin by:\n"
        f"1. Parsing the pipeline to understand the full graph\n"
        f"2. Validating the pipeline structure\n"
        f"3. Getting current node statuses\n\n"
        f"Then proceed with Phase 2 (dispatch ready nodes) of the execution flow.\n\n"
        f"If the pipeline is already partially complete (some nodes are already validated),\n"
        f"skip those nodes and continue from the current state.\n"
    )


# ---------------------------------------------------------------------------
# Pilot Stop Hook Factory
# ---------------------------------------------------------------------------


def _create_guardian_stop_hook(dot_path: str, pipeline_id: str) -> dict:
    """Create a Stop hook that checks pipeline completion instead of promises/hindsight.

    The Pilot should continue driving the pipeline until all nodes reach terminal
    states (validated, accepted, or failed). This hook blocks exit if non-terminal
    nodes (pending, active, impl_complete) remain, with a safety valve after 3 blocks.

    Args:
        dot_path: Absolute path to the pipeline DOT file.
        pipeline_id: Unique pipeline identifier string.

    Returns:
        Dict suitable for ClaudeCodeOptions.hooks parameter:
        {"Stop": [HookMatcher(hooks=[callback])]}
    """
    _block_count = 0
    _MAX_BLOCKS = 3  # Safety valve — allow exit after this many blocks

    async def _check_pipeline(hook_input: dict, event_name: str | None, context: Any) -> Any:
        """Stop hook: block exit if pipeline has non-terminal nodes."""
        nonlocal _block_count
        import subprocess

        try:
            result = subprocess.run(
                ["python3", "cobuilder/engine/cli.py", "status", dot_path, "--json", "--summary"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json
                status = json.loads(result.stdout)
                summary = status.get("summary", {})
                # Non-terminal states that require continued work
                non_terminal = (
                    summary.get("pending", 0)
                    + summary.get("active", 0)
                    + summary.get("impl_complete", 0)
                )
                if non_terminal == 0:
                    return {}  # All nodes terminal — allow exit

                _block_count += 1
                if _block_count > _MAX_BLOCKS:
                    return {}  # Safety valve — allow exit

                return {
                    "decision": "block",
                    "systemMessage": (
                        f"PIPELINE STOP GATE ({_block_count}/{_MAX_BLOCKS}): "
                        f"Pipeline '{pipeline_id}' has {non_terminal} non-terminal nodes.\n\n"
                        f"Continue driving the pipeline to completion. Check node statuses with:\n"
                        f"  python3 cobuilder/engine/cli.py status {dot_path}\n\n"
                        f"Dispatch any ready nodes, handle gates, and monitor for completion."
                    ),
                }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logfire.warning("[guardian-stop-hook] Status check failed: %s", e)
            # On error, allow exit — don't block indefinitely

        return {}  # Default: allow exit

    try:
        from claude_code_sdk.types import HookMatcher
        return {"Stop": [HookMatcher(hooks=[_check_pipeline])]}
    except ImportError:
        logfire.warning("[hooks] claude_code_sdk.types not available — guardian stop hook disabled")
        return {}


def build_options(
    system_prompt: str,
    cwd: str,
    model: str,
    max_turns: int,
    hooks: dict | None = None,
    signals_dir: str | None = None,
    target_dir: str | None = None,
) -> Any:
    """Construct a ClaudeCodeOptions instance for the Pilot agent.

    The Pilot is a coordinator (not implementer) — it gets read/investigation
    tools (Bash, Read, Glob, Grep, ToolSearch, Skill, LSP) plus Serena and Hindsight
    for code navigation and learning storage. It does NOT get Write/Edit/MultiEdit.

    Args:
        system_prompt: Pipeline execution instructions for Claude.
        cwd: Working directory for the agent (project root).
        model: Claude model identifier.
        max_turns: Maximum turns before the SDK stops the conversation.
        hooks: Optional hooks dict for Stop hook configuration.
        signals_dir: Path to signals directory (set as PIPELINE_SIGNAL_DIR).
        target_dir: Target implementation repo directory (set as PROJECT_TARGET_DIR).

    Returns:
        Configured ClaudeCodeOptions instance.
    """
    with logfire.span("guardian.build_options", model=model):
        from claude_code_sdk import ClaudeCodeOptions

        # Build clean environment: strip session identifiers and set pipeline context.
        # This matches the pattern in pipeline_runner.py:1513-1516.
        clean_env = {
            k: v for k, v in os.environ.items()
            if k not in ("CLAUDECODE", "CLAUDE_SESSION_ID", "CLAUDE_OUTPUT_STYLE")
        }
        if signals_dir:
            clean_env["PIPELINE_SIGNAL_DIR"] = str(signals_dir)
        if target_dir:
            clean_env["PROJECT_TARGET_DIR"] = str(target_dir)

        options_kwargs = {
            "allowed_tools": _GUARDIAN_TOOLS,
            "permission_mode": "bypassPermissions",
            "system_prompt": system_prompt,
            "cwd": cwd,
            "model": model,
            "max_turns": max_turns,
            "env": clean_env,
        }
        if hooks:
            options_kwargs["hooks"] = hooks

        return ClaudeCodeOptions(**options_kwargs)


def resolve_scripts_dir() -> str:
    """Return the absolute path to the attractor scripts directory.

    Resolution order:
    1. The directory containing this file (guardian.py is inside attractor/).
    2. Falls back to current working directory if for some reason _THIS_DIR is unavailable.

    Returns:
        Absolute path string.
    """
    return _THIS_DIR


def build_env_config(
    signals_dir: str | None = None,
    target_dir: str | None = None,
) -> dict[str, str]:
    """Return environment overrides for the Pilot agent.

    Strips session identifiers (CLAUDECODE, CLAUDE_SESSION_ID, CLAUDE_OUTPUT_STYLE)
    and sets pipeline context variables (PIPELINE_SIGNAL_DIR, PROJECT_TARGET_DIR).

    Note: ClaudeCodeOptions.env only adds/overrides keys, it cannot delete.
    This function provides the clean environment dict that should be passed
    directly to the options.

    Args:
        signals_dir: Path to signals directory (set as PIPELINE_SIGNAL_DIR).
        target_dir: Target implementation repo directory (set as PROJECT_TARGET_DIR).

    Returns:
        Dict of cleaned env vars with pipeline context set.
    """
    clean_env = {
        k: v for k, v in os.environ.items()
        if k not in ("CLAUDECODE", "CLAUDE_SESSION_ID", "CLAUDE_OUTPUT_STYLE")
    }
    if signals_dir:
        clean_env["PIPELINE_SIGNAL_DIR"] = str(signals_dir)
    if target_dir:
        clean_env["PROJECT_TARGET_DIR"] = str(target_dir)
    return clean_env


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for guardian.py.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        prog="guardian.py",
        description=(
            "Pilot Agent launcher (Layers 0/1): launch Pilot agents and "
            "monitor pipeline execution via claude_code_sdk."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python guardian.py --dot /path/to/pipeline.dot --pipeline-id my-pipeline

  python guardian.py --dot /path/to/pipeline.dot --pipeline-id my-pipeline \\
      --project-root /my/project --max-turns 300 --signal-timeout 300 --dry-run

  python guardian.py --multi /path/to/configs.json
        """,
    )

    # Mutually exclusive groups: single-launch vs multi-launch vs lifecycle
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dot", dest="dot",
                       help="Path to pipeline .dot file (single Pilot mode)")
    group.add_argument("--multi", dest="multi",
                       help="Path to JSON file containing a list of pipeline configs")
    group.add_argument("--lifecycle", dest="lifecycle",
                       help="Path to PRD — auto-instantiates lifecycle pipeline and launches")

    parser.add_argument("--pipeline-id", dest="pipeline_id", default=None,
                        help="Unique pipeline identifier (required with --dot)")
    parser.add_argument("--project-root", default=None, dest="project_root",
                        help="Working directory for the agent (default: cwd)")
    parser.add_argument("--target-dir", default=None, dest="target_dir",
                        help="Target implementation repo directory (overrides DOT graph attr)")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                        dest="max_turns",
                        help=f"Max SDK turns (default: {DEFAULT_MAX_TURNS})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--signals-dir", default=None, dest="signals_dir",
                        help="Override signals directory path")
    parser.add_argument("--signal-timeout", type=float, default=DEFAULT_SIGNAL_TIMEOUT,
                        dest="signal_timeout",
                        help=f"Seconds to wait per signal wait cycle (default: {DEFAULT_SIGNAL_TIMEOUT})")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        dest="max_retries",
                        help=f"Max retries per node before escalating (default: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Log configuration without invoking the SDK (for testing)")
    parser.add_argument("--event-driven", action="store_true", dest="event_driven",
                        help="Use event-driven multi-query mode: Pilot sleeps between "
                             "gates (zero LLM cost) and wakes on filesystem events. "
                             "Default: continuous single-conversation mode.")

    ns = parser.parse_args(argv)

    # Validate --dot requires --pipeline-id
    if ns.dot is not None and ns.pipeline_id is None:
        parser.error("--pipeline-id is required when using --dot")

    return ns


# ---------------------------------------------------------------------------
# Async agent runner
# ---------------------------------------------------------------------------


async def _run_agent(
    initial_prompt: str,
    options: Any,
    *,
    pipeline_id: str = "",
    signals_dir: str = "",
) -> None:
    """Stream messages from the claude_code_sdk ClaudeSDKClient and log them.

    Each SDK message type is logged to Logfire as a structured event AND
    written to the pipeline JSONL event stream so that ``cli.py watch``
    can display agent activity in real-time.

    Uses ClaudeSDKClient pattern (connect() then query()) to enable Stop hooks.

    Args:
        initial_prompt: The first user message to send to Claude.
        options: Configured ClaudeCodeOptions instance.
        pipeline_id: Pipeline identifier for event correlation.
        signals_dir: Signal/run directory containing pipeline-events.jsonl.
    """
    import time as _time

    from claude_code_sdk import (
        ClaudeSDKClient,
        AssistantMessage,
        UserMessage,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    )

    turn_count = 0
    tool_call_count = 0
    start_time = _time.time()

    # Resolve JSONL path for event writing
    _jsonl_path = ""
    if _EVENTS_AVAILABLE and _write_event and signals_dir:
        _jsonl_path = os.path.join(signals_dir, "pipeline-events.jsonl")

    def _emit(event: Any) -> None:
        """Write event to JSONL (fire-and-forget)."""
        if _jsonl_path and _write_event:
            try:
                _write_event(_jsonl_path, event)
            except Exception:
                pass  # never block the agent loop

    with logfire.span("guardian.run_agent") as agent_span:
        async with ClaudeSDKClient(options=options) as client:
            await client.connect()
            await client.query(initial_prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    turn_count += 1
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_preview = block.text[:300] if block.text else ""
                            logfire.info(
                                "guardian.assistant_text",
                                turn=turn_count,
                                text_length=len(block.text) if block.text else 0,
                                text_preview=text_preview,
                            )
                            if _EvB and pipeline_id:
                                _emit(_EvB.agent_message(
                                    pipeline_id=pipeline_id,
                                    node_id=None,
                                    agent_role="guardian",
                                    turn=turn_count,
                                    text=block.text or "",
                                ))
                            print(f"[Pilot] {block.text}", flush=True)

                        elif isinstance(block, ToolUseBlock):
                            tool_call_count += 1
                            input_preview = json.dumps(block.input)[:500]
                            logfire.info(
                                "guardian.tool_use",
                                tool_name=block.name,
                                tool_use_id=block.id,
                                tool_input_preview=input_preview,
                                turn=turn_count,
                                tool_call_number=tool_call_count,
                            )
                            if _EvB and pipeline_id:
                                _emit(_EvB.agent_tool_call(
                                    pipeline_id=pipeline_id,
                                    node_id=None,
                                    agent_role="guardian",
                                    turn=turn_count,
                                    tool_name=block.name,
                                    tool_use_id=block.id,
                                    input_preview=input_preview,
                                ))
                            print(f"[Pilot tool] {block.name}: {input_preview[:200]}", flush=True)

                        elif isinstance(block, ThinkingBlock):
                            logfire.info(
                                "guardian.thinking",
                                turn=turn_count,
                                thinking_length=len(block.thinking) if block.thinking else 0,
                                thinking_preview=(block.thinking or "")[:200],
                            )
                            if _EvB and pipeline_id:
                                _emit(_EvB.agent_thinking(
                                    pipeline_id=pipeline_id,
                                    node_id=None,
                                    agent_role="guardian",
                                    turn=turn_count,
                                    thinking=block.thinking or "",
                                ))

                elif isinstance(message, UserMessage):
                    # UserMessage carries tool results back from tool execution
                    if isinstance(message.content, list):
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                content_preview = ""
                                content_length = 0
                                if isinstance(block.content, str):
                                    content_preview = block.content[:500]
                                    content_length = len(block.content)
                                elif isinstance(block.content, list):
                                    content_preview = json.dumps(block.content)[:500]
                                    content_length = len(json.dumps(block.content))
                                logfire.info(
                                    "guardian.tool_result",
                                    tool_use_id=block.tool_use_id,
                                    is_error=block.is_error or False,
                                    content_length=content_length,
                                    content_preview=content_preview,
                                    turn=turn_count,
                                )
                                if _EvB and pipeline_id:
                                    _emit(_EvB.agent_tool_result(
                                        pipeline_id=pipeline_id,
                                        node_id=None,
                                        agent_role="guardian",
                                        turn=turn_count,
                                        tool_use_id=block.tool_use_id,
                                        is_error=block.is_error or False,
                                        content_length=content_length,
                                    ))

                elif isinstance(message, ResultMessage):
                    elapsed = _time.time() - start_time
                    logfire.info(
                        "guardian.result",
                        session_id=message.session_id,
                        is_error=message.is_error,
                        num_turns=message.num_turns,
                        duration_ms=message.duration_ms,
                        duration_api_ms=message.duration_api_ms,
                        total_cost_usd=message.total_cost_usd,
                        usage=message.usage,
                        result_preview=(message.result or "")[:300],
                        wall_time_seconds=round(elapsed, 2),
                        total_tool_calls=tool_call_count,
                    )
                    print(f"[Pilot done] turns={message.num_turns} cost=${message.total_cost_usd} tools={tool_call_count}", flush=True)


# ---------------------------------------------------------------------------
# Event-driven agent runner (multi-query pattern)
# ---------------------------------------------------------------------------


async def _run_agent_event_driven(
    initial_prompt: str,
    options: Any,
    *,
    pipeline_id: str = "",
    signals_dir: str = "",
    dot_path: str = "",
    gate_timeout: float = DEFAULT_SIGNAL_TIMEOUT,
) -> None:
    """Run the Pilot in event-driven mode using multi-query on one SDK session.

    Instead of the Pilot polling in a bash sleep loop (burning LLM turns on
    "nothing happened yet"), this function:

    1. Sends the initial prompt — Pilot parses DOT, dispatches research/refine,
       launches pipeline_runner.py in background
    2. Blocks on filesystem events via gate_watch.async_watch() — ZERO LLM cost
    3. When an event occurs (gate, failure, completion), sends a new query to the
       SAME conversation — Pilot handles the event with full prior context
    4. Repeats until pipeline completes, fails terminally, or max retries exhausted

    The conversation context is preserved across queries — the Pilot remembers
    all prior gates, decisions, and validation results.

    Args:
        initial_prompt: First user message to start pipeline execution.
        options: Configured ClaudeCodeOptions instance.
        pipeline_id: Pipeline identifier for event correlation.
        signals_dir: Signal directory to watch for gate/failure events.
        dot_path: DOT file path for pipeline completion detection.
        gate_timeout: Max seconds to wait per gate watch cycle.
    """
    import time as _time

    from claude_code_sdk import (
        ClaudeSDKClient,
        AssistantMessage,
        UserMessage,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
    )
    from cobuilder.engine.gate_watch import async_watch

    turn_count = 0
    tool_call_count = 0
    query_count = 0
    start_time = _time.time()
    max_queries = 50  # safety limit — each query handles one event

    # Resolve JSONL path for event writing
    _jsonl_path = ""
    if _EVENTS_AVAILABLE and _write_event and signals_dir:
        _jsonl_path = os.path.join(signals_dir, "pipeline-events.jsonl")

    def _emit(event: Any) -> None:
        if _jsonl_path and _write_event:
            try:
                _write_event(_jsonl_path, event)
            except Exception:
                pass

    async def _consume_response(client: ClaudeSDKClient) -> ResultMessage | None:
        """Consume all messages from receive_response(), logging them."""
        nonlocal turn_count, tool_call_count
        result_msg = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                turn_count += 1
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_preview = block.text[:300] if block.text else ""
                        logfire.info("guardian.assistant_text", turn=turn_count,
                                     text_length=len(block.text) if block.text else 0,
                                     text_preview=text_preview)
                        if _EvB and pipeline_id:
                            _emit(_EvB.agent_message(
                                pipeline_id=pipeline_id, node_id=None,
                                agent_role="guardian", turn=turn_count,
                                text=block.text or ""))
                        print(f"[Pilot] {block.text}", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        tool_call_count += 1
                        input_preview = json.dumps(block.input)[:500]
                        logfire.info("guardian.tool_use", tool_name=block.name,
                                     tool_use_id=block.id,
                                     tool_input_preview=input_preview,
                                     turn=turn_count, tool_call_number=tool_call_count)
                        if _EvB and pipeline_id:
                            _emit(_EvB.agent_tool_call(
                                pipeline_id=pipeline_id, node_id=None,
                                agent_role="guardian", turn=turn_count,
                                tool_name=block.name, tool_use_id=block.id,
                                input_preview=input_preview))
                        print(f"[Pilot tool] {block.name}: {input_preview[:200]}", flush=True)
                    elif isinstance(block, ThinkingBlock):
                        logfire.info("guardian.thinking", turn=turn_count,
                                     thinking_length=len(block.thinking) if block.thinking else 0,
                                     thinking_preview=(block.thinking or "")[:200])
                        if _EvB and pipeline_id:
                            _emit(_EvB.agent_thinking(
                                pipeline_id=pipeline_id, node_id=None,
                                agent_role="guardian", turn=turn_count,
                                thinking=block.thinking or ""))
            elif isinstance(message, UserMessage):
                if isinstance(message.content, list):
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            content_preview = ""
                            content_length = 0
                            if isinstance(block.content, str):
                                content_preview = block.content[:500]
                                content_length = len(block.content)
                            elif isinstance(block.content, list):
                                content_preview = json.dumps(block.content)[:500]
                                content_length = len(json.dumps(block.content))
                            logfire.info("guardian.tool_result",
                                         tool_use_id=block.tool_use_id,
                                         is_error=block.is_error or False,
                                         content_length=content_length,
                                         content_preview=content_preview,
                                         turn=turn_count)
                            if _EvB and pipeline_id:
                                _emit(_EvB.agent_tool_result(
                                    pipeline_id=pipeline_id, node_id=None,
                                    agent_role="guardian", turn=turn_count,
                                    tool_use_id=block.tool_use_id,
                                    is_error=block.is_error or False,
                                    content_length=content_length))
            elif isinstance(message, ResultMessage):
                elapsed = _time.time() - start_time
                logfire.info("guardian.result",
                             session_id=message.session_id,
                             is_error=message.is_error,
                             num_turns=message.num_turns,
                             duration_ms=message.duration_ms,
                             duration_api_ms=message.duration_api_ms,
                             total_cost_usd=message.total_cost_usd,
                             usage=message.usage,
                             result_preview=(message.result or "")[:300],
                             wall_time_seconds=round(elapsed, 2),
                             total_tool_calls=tool_call_count)
                print(f"[Pilot query #{query_count}] turns={message.num_turns} cost=${message.total_cost_usd} tools={tool_call_count}", flush=True)
                result_msg = message
        return result_msg

    with logfire.span("guardian.run_agent_event_driven", pipeline_id=pipeline_id):
        async with ClaudeSDKClient(options=options) as client:
            await client.connect()

            # --- Query 1: Initial setup (parse, validate, dispatch, launch runner) ---
            query_count += 1
            logfire.info("guardian.query_initial", query=query_count)
            print(f"\n[Gate Watch] Query #{query_count}: Initial pipeline setup", flush=True)
            await client.query(initial_prompt)
            await _consume_response(client)

            # --- Event loop: block on filesystem events, wake Pilot per event ---
            while query_count < max_queries:
                logfire.info("guardian.gate_watch_start", query=query_count,
                             signal_dir=signals_dir, dot_path=dot_path)
                print(f"\n[Gate Watch] Sleeping on filesystem events (timeout={gate_timeout}s)...", flush=True)

                event = await async_watch(
                    signal_dir=signals_dir,
                    dot_path=dot_path,
                    timeout=gate_timeout,
                )

                event_type = event.get("event", "unknown")
                logfire.info("guardian.gate_watch_wake", event_type=event_type,
                             event=event, query=query_count)
                print(f"[Gate Watch] Woke up: {event_type} — {json.dumps(event, indent=2)[:500]}", flush=True)

                # Handle based on event type
                if event_type == "pipeline_complete":
                    query_count += 1
                    logfire.info("guardian.query_completion", query=query_count)
                    print(f"\n[Gate Watch] Query #{query_count}: Pipeline complete — running E2E validation", flush=True)
                    await client.query(
                        f"PIPELINE COMPLETE. All nodes have reached terminal states.\n\n"
                        f"Event details:\n{json.dumps(event, indent=2)}\n\n"
                        f"Run Phase 4: Pipeline Completion Validation (E2E suite, cross-node integration, "
                        f"PRD coverage). Then signal PIPELINE_COMPLETE via escalate_to_terminal.py."
                    )
                    await _consume_response(client)
                    break  # Pipeline done — exit event loop

                elif event_type == "gate":
                    query_count += 1
                    gate_type = event.get("gate_type", "unknown")
                    node_id = event.get("node_id", "unknown")
                    logfire.info("guardian.query_gate", query=query_count,
                                 gate_type=gate_type, node_id=node_id)
                    print(f"\n[Gate Watch] Query #{query_count}: Gate {gate_type} on {node_id}", flush=True)
                    await client.query(
                        f"GATE EVENT: A pipeline gate requires your attention.\n\n"
                        f"Gate type: {gate_type}\n"
                        f"Node ID: {node_id}\n"
                        f"Epic ID: {event.get('epic_id', 'N/A')}\n"
                        f"Timestamp: {event.get('timestamp', 'N/A')}\n\n"
                        f"Handle this gate according to the protocol:\n"
                        f"- For wait.cobuilder: Run the Pilot Gherkin Validation Protocol\n"
                        f"- For wait.human: Evaluate if you can validate autonomously, "
                        f"otherwise escalate to Terminal\n\n"
                        f"After handling, transition the gate node appropriately and "
                        f"the runner will continue automatically."
                    )
                    await _consume_response(client)

                elif event_type == "failure":
                    query_count += 1
                    node_id = event.get("node_id", "unknown")
                    logfire.info("guardian.query_failure", query=query_count, node_id=node_id)
                    print(f"\n[Gate Watch] Query #{query_count}: Failure on {node_id}", flush=True)
                    await client.query(
                        f"NODE FAILURE: A pipeline node has failed.\n\n"
                        f"Node ID: {node_id}\n"
                        f"Signal type: {event.get('signal_type', 'UNKNOWN')}\n"
                        f"Message: {event.get('message', 'No details')}\n\n"
                        f"Investigate the root cause. Options:\n"
                        f"1. Fix the issue and transition the node back to pending for retry\n"
                        f"2. Inject a fix-it node into the pipeline\n"
                        f"3. Escalate to Terminal if the failure cannot be resolved\n\n"
                        f"Check the signal file and runner logs for details."
                    )
                    await _consume_response(client)

                elif event_type == "timeout":
                    query_count += 1
                    logfire.info("guardian.query_timeout", query=query_count)
                    print(f"\n[Gate Watch] Query #{query_count}: Watch timeout — checking status", flush=True)
                    await client.query(
                        f"WATCH TIMEOUT: No gate events detected for {event.get('elapsed_seconds', gate_timeout)}s.\n\n"
                        f"Check the pipeline status to determine if:\n"
                        f"1. The runner is still alive and making progress\n"
                        f"2. A node is stuck without signaling\n"
                        f"3. The pipeline needs intervention\n\n"
                        f"Use: python3 {{scripts_dir}}/cli.py status {{dot_path}} --json"
                    )
                    await _consume_response(client)

                else:
                    # Unknown event — log and continue watching
                    logfire.warning("guardian.unknown_event", event=event)
                    print(f"[Gate Watch] Unknown event type: {event_type}. Continuing watch.", flush=True)

            total_elapsed = _time.time() - start_time
            logfire.info("guardian.event_driven_complete",
                         total_queries=query_count,
                         total_turns=turn_count,
                         total_tool_calls=tool_call_count,
                         total_elapsed_seconds=round(total_elapsed, 2))
            print(f"\n[Pilot event-driven] Complete: queries={query_count} turns={turn_count} tools={tool_call_count} elapsed={round(total_elapsed)}s", flush=True)


# ---------------------------------------------------------------------------
# Core public API (launch/monitor functions)
# ---------------------------------------------------------------------------


async def _launch_guardian_async(
    dot_path: str,
    project_root: str,
    pipeline_id: str,
    *,
    model: str = "claude-sonnet-4-6",
    max_turns: int = DEFAULT_MAX_TURNS,
    signal_timeout: float = DEFAULT_SIGNAL_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    signals_dir: Optional[str] = None,
    dry_run: bool = False,
    target_dir: str = "",
    event_driven: bool = False,
) -> dict[str, Any]:
    """Async implementation of launch_guardian().

    Args:
        dot_path: Absolute path to the pipeline DOT file.
        project_root: Working directory for the agent.
        pipeline_id: Unique pipeline identifier string.
        model: Claude model identifier.
        max_turns: Maximum SDK turns.
        signal_timeout: Seconds to wait per signal wait cycle.
        max_retries: Maximum retries per node before escalation.
        signals_dir: Override signals directory path.
        dry_run: If True, return config dict without invoking SDK.
        target_dir: Target implementation repo directory.
        event_driven: If True, use multi-query event-driven mode instead of
            single continuous conversation. The Pilot sleeps between gates
            (zero LLM cost) and wakes on filesystem events.

    Returns:
        Dict with status and pipeline metadata.
    """
    scripts_dir = resolve_scripts_dir()

    with logfire.span("guardian.launch_guardian_async", pipeline_id=pipeline_id):
        system_prompt = build_system_prompt(
            dot_path=dot_path,
            pipeline_id=pipeline_id,
            scripts_dir=scripts_dir,
            signal_timeout=signal_timeout,
            max_retries=max_retries,
            target_dir=target_dir,
            event_driven=event_driven,
        )

        initial_prompt = build_initial_prompt(
            dot_path=dot_path,
            pipeline_id=pipeline_id,
            scripts_dir=scripts_dir,
            target_dir=target_dir,
            event_driven=event_driven,
        )

        config: dict[str, Any] = {
            "dry_run": dry_run,
            "dot_path": dot_path,
            "pipeline_id": pipeline_id,
            "model": model,
            "max_turns": max_turns,
            "signal_timeout": signal_timeout,
            "max_retries": max_retries,
            "project_root": project_root,
            "signals_dir": signals_dir,
            "scripts_dir": scripts_dir,
            "target_dir": target_dir,
            "system_prompt_length": len(system_prompt),
            "initial_prompt_length": len(initial_prompt),
        }

        if dry_run:
            return config

        # In event-driven mode, don't use the stop hook — the Python event loop
        # controls when the Pilot stops between queries. The stop hook would prevent
        # the Pilot from finishing its turn (so gate_watch can take over), because
        # it blocks exit when non-terminal nodes remain.
        if event_driven:
            hooks = {}
        else:
            hooks = _create_guardian_stop_hook(dot_path, pipeline_id)

        options = build_options(
            system_prompt=system_prompt,
            cwd=project_root,
            model=model,
            max_turns=max_turns,
            hooks=hooks,
            signals_dir=signals_dir,
            target_dir=target_dir,
        )

    try:
        if event_driven:
            await _run_agent_event_driven(
                initial_prompt,
                options,
                pipeline_id=pipeline_id,
                signals_dir=signals_dir or "",
                dot_path=dot_path,
                gate_timeout=signal_timeout,
            )
        else:
            await _run_agent(
                initial_prompt,
                options,
                pipeline_id=pipeline_id,
                signals_dir=signals_dir or "",
            )
        return {
            "status": "ok",
            "pipeline_id": pipeline_id,
            "dot_path": dot_path,
            "mode": "event_driven" if event_driven else "continuous",
        }
    except Exception as exc:
        return {
            "status": "error",
            "pipeline_id": pipeline_id,
            "dot_path": dot_path,
            "error": str(exc),
        }


def launch_guardian(
    dot_path: str,
    project_root: str,
    pipeline_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Launch a single Pilot agent via the Agent SDK.

    Constructs ClaudeCodeOptions with allowed_tools=["Bash"] and
    env={"CLAUDECODE": ""}, then streams the SDK conversation until
    the Pilot completes or errors.

    Args:
        dot_path: Path to the pipeline .dot file.
        project_root: Working directory for the agent.
        pipeline_id: Unique pipeline identifier string.
        **kwargs: Optional overrides — model, max_turns, signal_timeout,
                  max_retries, signals_dir, dry_run.

    Returns:
        Dict with ``status`` ("ok" | "error"), ``pipeline_id``, ``dot_path``,
        and optionally ``error`` on failure.  In dry_run mode returns the
        full config dict with ``dry_run: True``.
    """
    dot_path = os.path.abspath(dot_path)
    return asyncio.run(
        _launch_guardian_async(
            dot_path=dot_path,
            project_root=project_root,
            pipeline_id=pipeline_id,
            **kwargs,
        )
    )


async def _launch_multiple_async(
    pipeline_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Async implementation of launch_multiple_guardians().

    Args:
        pipeline_configs: List of config dicts, each with at minimum
            dot_path, project_root, pipeline_id.

    Returns:
        List of result dicts, one per config.
    """
    tasks = [
        _launch_guardian_async(
            dot_path=os.path.abspath(cfg["dot_path"]),
            project_root=cfg.get("project_root", os.getcwd()),
            pipeline_id=cfg["pipeline_id"],
            model=cfg.get("model", "claude-sonnet-4-6"),
            max_turns=cfg.get("max_turns", DEFAULT_MAX_TURNS),
            signal_timeout=cfg.get("signal_timeout", DEFAULT_SIGNAL_TIMEOUT),
            max_retries=cfg.get("max_retries", DEFAULT_MAX_RETRIES),
            signals_dir=cfg.get("signals_dir"),
            dry_run=cfg.get("dry_run", False),
            target_dir=cfg.get("target_dir", ""),
        )
        for cfg in pipeline_configs
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Normalise exceptions to error dicts so callers receive a uniform type.
    output: list[dict[str, Any]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            cfg = pipeline_configs[i]
            output.append({
                "status": "error",
                "pipeline_id": cfg.get("pipeline_id", "unknown"),
                "dot_path": cfg.get("dot_path", "unknown"),
                "error": str(result),
            })
        else:
            output.append(result)  # type: ignore[arg-type]

    return output


def launch_multiple_guardians(
    pipeline_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Launch multiple Pilot agents concurrently.

    Uses asyncio.gather with return_exceptions=True so an individual
    failure does not abort the remaining launches.

    Args:
        pipeline_configs: List of config dicts, each with:
            - dot_path (str, required)
            - project_root (str, required)
            - pipeline_id (str, required)
            - model, max_turns, signal_timeout, max_retries,
              signals_dir, dry_run (all optional)

    Returns:
        List of result dicts (one per config).  Any individual failure
        is represented as ``{"status": "error", ...}`` rather than
        raising an exception.
    """
    return asyncio.run(_launch_multiple_async(pipeline_configs))


def monitor_guardian(
    guardian_process: Any,
    dot_path: str,
    signals_dir: Optional[str] = None,
    *,
    timeout: float = DEFAULT_MONITOR_TIMEOUT,
    poll_interval: float = 5.0,
) -> dict[str, Any]:
    """Watch for terminal-targeted signals from a running Pilot.

    Polls the signals directory for signals with target="terminal" until
    either a PIPELINE_COMPLETE or terminal-escalation signal arrives, or
    the timeout is reached.

    Args:
        guardian_process: The guardian process handle (may be None for
            signal-only monitoring).  Currently unused but reserved for
            future process health checks.
        dot_path: Absolute path to the pipeline DOT file (used for
            metadata in returned dicts).
        signals_dir: Override the default signals directory.
        timeout: Maximum seconds to wait for a terminal signal.
        poll_interval: Seconds between directory polls.

    Returns:
        Dict with ``status`` ("complete" | "escalation" | "timeout") and
        the received ``signal_data`` (if any).
    """
    try:
        signal_data = wait_for_signal(
            target_layer="terminal",
            timeout=timeout,
            signals_dir=signals_dir,
            poll_interval=poll_interval,
        )
    except TimeoutError:
        return {
            "status": "timeout",
            "dot_path": dot_path,
            "signal_data": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "dot_path": dot_path,
            "error": str(exc),
            "signal_data": None,
        }

    signal_type = signal_data.get("signal_type", "")

    if "PIPELINE_COMPLETE" in signal_type or (
        signal_data.get("payload", {}).get("issue", "").startswith("PIPELINE_COMPLETE")
    ):
        return handle_pipeline_complete(signal_data, dot_path)

    if "VALIDATION_COMPLETE" in signal_type:
        return handle_validation_complete(signal_data, dot_path)

    # Any other terminal-targeted signal is treated as an escalation.
    return handle_escalation(signal_data)


def handle_validation_complete(
    signal_data: dict[str, Any],
    dot_path: str,
) -> dict[str, Any]:
    """Handle VALIDATION_COMPLETE signal from a Runner via terminal.

    Args:
        signal_data: Parsed signal dict from the Runner.
        dot_path: Absolute path to the pipeline DOT file.

    Returns:
        Dict with validation complete details.
    """
    payload = signal_data.get("payload", {})
    return {
        "status": "validation_complete",
        "node_id": payload.get("node_id", "unknown"),
        "pipeline_id": payload.get("pipeline_id", ""),
        "dot_path": dot_path,
        "summary": payload.get("summary", ""),
        "timestamp": signal_data.get("timestamp"),
        "source": signal_data.get("source"),
        "raw": signal_data,
    }


def handle_escalation(signal_data: dict[str, Any]) -> dict[str, Any]:
    """Forward a Pilot escalation signal to the terminal user.

    Reads the escalation signal payload and formats it for terminal
    display as a JSON dict.

    Args:
        signal_data: Parsed signal dict with fields source, target,
            signal_type, timestamp, payload.

    Returns:
        Dict with escalation details formatted for terminal display:
        ``{"status": "escalation", "signal_type": ..., "pipeline_id": ...,
           "issue": ..., "options": ..., "timestamp": ..., "raw": ...}``
    """
    payload = signal_data.get("payload", {})

    result: dict[str, Any] = {
        "status": "escalation",
        "signal_type": signal_data.get("signal_type", "ESCALATE"),
        "pipeline_id": payload.get("pipeline_id", "unknown"),
        "issue": payload.get("issue", "No issue description provided"),
        "options": payload.get("options"),
        "timestamp": signal_data.get("timestamp"),
        "source": signal_data.get("source"),
        "raw": signal_data,
    }

    return result


def handle_pipeline_complete(
    signal_data: dict[str, Any],
    dot_path: str,
) -> dict[str, Any]:
    """Finalise a pipeline after receiving PIPELINE_COMPLETE signal.

    Reads the PIPELINE_COMPLETE signal payload and produces a completion
    summary with node statuses.

    Args:
        signal_data: Parsed signal dict from the Pilot.
        dot_path: Absolute path to the pipeline DOT file.

    Returns:
        Dict with completion summary:
        ``{"status": "complete", "pipeline_id": ..., "dot_path": ...,
           "node_statuses": ..., "timestamp": ..., "raw": ...}``
    """
    payload = signal_data.get("payload", {})

    # Extract node statuses from payload if available (Pilot may include them).
    node_statuses = payload.get("node_statuses", {})

    # Parse issue string to extract structured data if node_statuses not present.
    issue = payload.get("issue", "")
    if not node_statuses and issue:
        node_statuses = {"summary": issue}

    result: dict[str, Any] = {
        "status": "complete",
        "pipeline_id": payload.get("pipeline_id", "unknown"),
        "dot_path": dot_path,
        "node_statuses": node_statuses,
        "issue": issue,
        "timestamp": signal_data.get("timestamp"),
        "source": signal_data.get("source"),
        "raw": signal_data,
    }

    return result


# ---------------------------------------------------------------------------
# Lifecycle launcher
# ---------------------------------------------------------------------------


def launch_lifecycle(
    prd_path: str,
    initiative_id: str | None = None,
    target_dir: str | None = None,
    max_cycles: int = 3,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    dry_run: bool = False,
    event_driven: bool = False,
) -> dict | None:
    """Launch a self-driving lifecycle pipeline from a PRD path.

    Steps:
    1. Derive initiative_id from PRD filename if not provided
    2. Create placeholder state files for sd_path validation
    3. Instantiate cobuilder-lifecycle template
    4. Validate rendered DOT
    5. Launch Pilot on the pipeline (or return config if dry_run)

    Args:
        prd_path: Path to the PRD markdown file (e.g. PRD-AUTH-001.md).
        initiative_id: Optional override for the initiative identifier.
            Defaults to the PRD stem with 'PRD-' prefix stripped.
        target_dir: Target implementation repo directory. Defaults to cwd.
        max_cycles: Maximum full research→validate cycles before forced exit.
        model: Claude model to use for the Pilot.
        max_turns: Maximum SDK turns.
        dry_run: If True, return config dict without launching the Pilot.

    Returns:
        Result dict from launch_guardian(), or a dry-run config dict.
    """
    import subprocess

    # 1. Derive initiative_id
    if initiative_id is None:
        stem = Path(prd_path).stem  # e.g. PRD-AUTH-001
        initiative_id = stem.replace("PRD-", "", 1)

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
            placeholder.write_text(
                f"# Placeholder — will be populated by pipeline\n"
            )

    # 4. Instantiate template
    from cobuilder.templates.instantiator import instantiate_template
    dot_output = Path(".pipelines/pipelines") / f"lifecycle-{initiative_id}.dot"
    dot_output.parent.mkdir(parents=True, exist_ok=True)

    instantiate_template(
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
        validate=False,  # Validate via cli.py below
    )

    # 5. Validate
    result = subprocess.run(
        ["python3", "cobuilder/engine/cli.py", "validate", str(dot_output)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"Pipeline validation failed:\n{result.stderr or result.stdout}"
        )

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

    # Launch Pilot (reuse existing launch_guardian logic)
    return launch_guardian(
        dot_path=dot_path,
        project_root=project_root,
        pipeline_id=pipeline_id,
        model=model,
        max_turns=max_turns,
        target_dir=target_dir,
        event_driven=event_driven,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and launch one or multiple Pilot agents."""
    # Load attractor-specific API credentials before any SDK call.
    # claude_code_sdk.query() reads ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL from
    # os.environ, so this must happen before argparse or SDK initialisation.
    os.environ.update(load_engine_env())

    args = parse_args(argv)

    # -----------------------------------------------------------------------
    # Multi-launch mode: --multi <configs.json>
    # -----------------------------------------------------------------------
    if args.multi is not None:
        multi_path = os.path.abspath(args.multi)
        try:
            with open(multi_path, encoding="utf-8") as fh:
                configs = json.load(fh)
        except FileNotFoundError:
            print(json.dumps({
                "status": "error",
                "message": f"Config file not found: {multi_path}",
            }))
            sys.exit(1)
        except json.JSONDecodeError as exc:
            print(json.dumps({
                "status": "error",
                "message": f"Invalid JSON in {multi_path}: {exc}",
            }))
            sys.exit(1)

        if not isinstance(configs, list):
            print(json.dumps({
                "status": "error",
                "message": "--multi JSON file must contain a list of config dicts",
            }))
            sys.exit(1)

        # Propagate top-level dry_run flag to all configs that don't set it.
        if args.dry_run:
            for cfg in configs:
                cfg.setdefault("dry_run", True)

        results = launch_multiple_guardians(configs)
        print(json.dumps(results, indent=2))
        return

    # -----------------------------------------------------------------------
    # Lifecycle mode: --lifecycle <prd_path>
    # -----------------------------------------------------------------------
    if args.lifecycle is not None:
        result = launch_lifecycle(
            prd_path=args.lifecycle,
            initiative_id=args.pipeline_id,  # optional override
            target_dir=args.target_dir,
            max_cycles=3,
            model=args.model,
            max_turns=args.max_turns,
            dry_run=args.dry_run,
            event_driven=args.event_driven,
        )
        if args.dry_run:
            print(json.dumps(result, indent=2))
        return

    # -----------------------------------------------------------------------
    # Single Pilot mode: --dot + --pipeline-id
    # -----------------------------------------------------------------------
    dot_path = os.path.abspath(args.dot)
    cwd = args.project_root or os.getcwd()
    scripts_dir = resolve_scripts_dir()

    # Read target_dir from DOT graph_attrs (CLI arg overrides DOT value).
    graph_target_dir = ""
    if os.path.exists(dot_path):
        from cobuilder.engine.dispatch_parser import parse_dot  # noqa: PLC0415 (lazy import — intentional)
        with open(dot_path, encoding="utf-8") as _fh:
            dot_data = parse_dot(_fh.read())
        graph_target_dir = dot_data.get("graph_attrs", {}).get("target_dir", "")
    target_dir = args.target_dir or graph_target_dir
    if not target_dir:
        print(json.dumps({
            "status": "error",
            "message": "target_dir is required: set in DOT graph attrs or pass --target-dir",
        }))
        sys.exit(1)

    with logfire.span("guardian.main", pipeline_id=args.pipeline_id):
        system_prompt = build_system_prompt(
            dot_path=dot_path,
            pipeline_id=args.pipeline_id,
            scripts_dir=scripts_dir,
            signal_timeout=args.signal_timeout,
            max_retries=args.max_retries,
            target_dir=target_dir,
            event_driven=args.event_driven,
        )

        initial_prompt = build_initial_prompt(
            dot_path=dot_path,
            pipeline_id=args.pipeline_id,
            scripts_dir=scripts_dir,
            target_dir=target_dir,
        )

    # Dry-run: log config and exit without calling the SDK.
    if args.dry_run:
        config: dict[str, Any] = {
            "dry_run": True,
            "dot_path": dot_path,
            "pipeline_id": args.pipeline_id,
            "model": args.model,
            "max_turns": args.max_turns,
            "signal_timeout": args.signal_timeout,
            "max_retries": args.max_retries,
            "project_root": cwd,
            "signals_dir": args.signals_dir,
            "target_dir": target_dir,
            "scripts_dir": scripts_dir,
            "event_driven": args.event_driven,
            "system_prompt_length": len(system_prompt),
            "initial_prompt_length": len(initial_prompt),
        }
        print(json.dumps(config, indent=2))
        sys.exit(0)

    # Register Layer 0/1 (Pilot) identity before starting the agent loop.
    identity_registry.create_identity(
        role="launch",
        name="guardian",
        session_id="launch-guardian",
        worktree=os.getcwd(),
    )

    # Live run: launch the Pilot agent with retry loop.
    # If the Pilot SDK session crashes or times out, retry up to max_retries times.
    guardian_retries = args.max_retries
    attempt = 0
    while True:
        attempt += 1
        print(f"[Layer 0] Launching Pilot (attempt {attempt}/{guardian_retries + 1})", flush=True)
        result = launch_guardian(
            dot_path=dot_path,
            project_root=cwd,
            pipeline_id=args.pipeline_id,
            model=args.model,
            max_turns=args.max_turns,
            signal_timeout=args.signal_timeout,
            max_retries=args.max_retries,
            signals_dir=args.signals_dir,
            target_dir=target_dir,
            event_driven=args.event_driven,
        )
        print(json.dumps(result, indent=2))

        status = result.get("status", "error")
        if status == "ok":
            break  # Pilot completed successfully

        # Check if we should retry
        if attempt > guardian_retries:
            print(f"[Layer 0] Pilot failed after {attempt} attempts. Giving up.", file=sys.stderr, flush=True)
            sys.exit(1)

        # Retry on timeout or error (Pilot SDK crash)
        print(f"[Layer 0] Pilot returned status={status}. Retrying in 5s...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
