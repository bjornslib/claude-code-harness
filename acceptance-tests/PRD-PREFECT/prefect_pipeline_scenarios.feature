# Prefect Pipeline Productionisation — Acceptance Scenarios
# =========================================================
#
# PURPOSE: Descriptive acceptance rubric for System 3 (guardian angel) to
# independently validate claims made by orchestrators and workers about
# Prefect productionisation work. These scenarios live OUTSIDE the
# implementation repo so implementers cannot see or game them.
#
# HOW TO USE: When an orchestrator claims work is "done", System 3 reads
# the actual codebase and evaluates each scenario against the evidence.
# Confidence is scored 0.0–1.0, not binary pass/fail. A claim of "done"
# with confidence < 0.6 across critical scenarios triggers rejection.
#
# SOURCES:
#   - prefect-bridge-implementation-report.md (2026-02-19, commit 2b2d0a52)
#   - prefect-workflow-orchestration-prd.md (v1.2.0)
#   - prefect-local-e2e-setup-prd.md (v1.1.0)
#
# SCORING GUIDE:
#   0.0 — No evidence found; claim appears false
#   0.2 — Minimal evidence; scaffolding exists but nothing functional
#   0.4 — Partial implementation; key pieces missing or stubbed
#   0.6 — Functional but incomplete; works in happy path, gaps in edges
#   0.8 — Solid implementation; works correctly with minor gaps
#   1.0 — Complete; all evidence confirms claim, edge cases handled
#
# RED FLAG GUIDE:
#   - Orchestrator claims "wired" but no import/call of bridge in verify chain
#   - Tests pass but are mocked at the wrong layer (mock the DB, not the bridge)
#   - "53 tests pass" repeated without new tests for new functionality
#   - File exists but function bodies are pass/TODO/NotImplementedError
#   - Docker compose file modified but services don't actually start
#   - Deployment registration code exists but worker CMD not updated
#
# DATE: 2026-02-19

# ==========================================================================
# Feature 1: Bridge Integration — The Critical Gap
# ==========================================================================
#
# CONTEXT: As of commit 2b2d0a52, the bridge module (prefect_bridge.py) is
# fully implemented and tested in isolation (53/53 tests). However, it is
# NOT called from anywhere in the application. The /verify endpoint creates
# cases and background_tasks but never invokes create_prefect_flow_run().
# This is the single most important integration point.

Feature: Prefect Bridge Integration into Verify Endpoint

  Background:
    Given the bridge module exists at prefect_flows/bridge/prefect_bridge.py
    And it exports create_prefect_flow_run(case_id, customer_id, task_id, check_type, db_url)
    And the feature flag USE_PREFECT_ORCHESTRATION gates all Prefect interaction
    And the current verify chain is: POST /api/v1/verify → submit_verification() → create_verification_task() → INSERT INTO background_tasks → return

  Scenario: Bridge is called after case creation
    Given the file services/work_history.py (or equivalent verify-chain file)
    When I search for "create_prefect_flow_run" in that file
    Then I should find an import of create_prefect_flow_run from prefect_flows.bridge
    And I should find an await call to create_prefect_flow_run() AFTER the background_tasks INSERT
    And the call should pass case_id, customer_id, task_id (from INSERT result), check_type, and DATABASE_URL
    And the call should be wrapped in try/except so bridge failure does NOT crash the verify endpoint

    # CONFIDENCE SCORING:
    #   1.0 — Import present, await call found after INSERT, try/except wrapping, correct params
    #   0.8 — Import and call present, but missing try/except safety wrapper
    #   0.6 — Import present but call is in wrong location (before INSERT or in different function)
    #   0.4 — Import present but call is commented out or behind a secondary flag
    #   0.2 — File mentions "prefect" in comments but no actual import/call
    #   0.0 — No trace of bridge integration in verify chain files

    # RED FLAGS:
    #   - Orchestrator says "wired" but only the bridge module tests were updated
    #   - Integration exists in a new file that's not in the actual request path
    #   - The call is inside an "if False:" or unreachable code block
    #   - Parameters are hardcoded (task_id=1) instead of from actual INSERT result

  Scenario: Bridge failure does not break case creation
    Given create_prefect_flow_run() raises a RuntimeError (Prefect server down)
    When a verification request is submitted via POST /api/v1/verify
    Then the case should still be created successfully in the database
    And the background_task row should exist (without prefect_flow_run_id)
    And the API should return a success response (not 500)
    And the error should be logged (not silently swallowed)

    # EVIDENCE TO CHECK:
    #   - Look for try/except around the create_prefect_flow_run() call
    #   - The except block should log (logger.error or logfire.span)
    #   - The except block should NOT re-raise (would crash the endpoint)
    #   - The return statement should be AFTER the try/except, not inside it

  Scenario: Feature flag provides instant rollback
    Given USE_PREFECT_ORCHESTRATION is set to "false" (or not set)
    When create_prefect_flow_run() is called
    Then the function returns None immediately on line ~375-380
    And no Prefect client is instantiated
    And no database queries are made by the bridge
    And no network calls to Prefect server occur

    # EVIDENCE TO CHECK:
    #   - First lines of create_prefect_flow_run() check the env var
    #   - Early return before any async operations
    #   - The check is case-insensitive (implementation report confirms this)


# ==========================================================================
# Feature 2: Prefect Flow Scheduling Pipeline
# ==========================================================================
#
# CONTEXT: When the bridge IS called, it executes a 6-step pipeline:
# ensure_employer_contact → resolve_timezone → calculate_business_hour →
# resolve_sla_config → create_flow_run → update_background_tasks.
# Each step has dependencies and can fail independently.

Feature: Prefect Flow Run Creation Pipeline

  Background:
    Given USE_PREFECT_ORCHESTRATION is "true"
    And a case exists with id=1, linked employer contact, and verification_metadata
    And Prefect server is running with registered deployments

  Scenario: Employer contact resolution from database
    Given a case with employer_contact_id linked to a university_contacts row
    And the university_contacts row has entity_type='employer', phone_number, and timezone
    When mock_ensure_employer_contact(case_id, db_url) is called
    Then it should query cases JOIN university_contacts via asyncpg
    And return a dict with keys: id, employer_name, phone_number, country, timezone, city
    And raise ValueError with message containing "not found" if case doesn't exist
    And raise ValueError with message containing "phone" if phone_number is NULL

    # CONFIDENCE SCORING:
    #   1.0 — Real SQL query, proper JOIN, all validations, descriptive errors
    #   0.8 — Query works but missing one validation (e.g., phone check)
    #   0.6 — Query exists but uses SELECT * instead of specific columns
    #   0.4 — Function exists but returns hardcoded data (mock not replaced)
    #   0.0 — Function body is pass/TODO/NotImplementedError

  Scenario: Timezone resolution priority chain
    Given an employer contact dict with possible timezone and country fields
    When mock_resolve_timezone(contact) is called
    Then the resolution priority should be:
      | Priority | Condition                              | Result                        |
      | 1st      | contact["timezone"] is truthy           | Return it directly            |
      | 2nd      | contact["country"] in fallback map      | Return mapped IANA timezone   |
      | 3rd      | Neither matches                         | Return "UTC"                  |
    And the fallback map should cover at minimum: Australia, United States, United Kingdom
    And the returned value should be a valid IANA timezone string (e.g., "Australia/Sydney")

    # EVIDENCE TO CHECK:
    #   - COUNTRY_TIMEZONE_FALLBACK dict with >= 9 country entries
    #   - Conditional chain: if timezone → elif country → else UTC
    #   - No ZoneInfo validation in this mock (that's downstream)

  Scenario: Business hour scheduling correctness
    Given an employer timezone (e.g., "Australia/Sydney")
    And the current time in that timezone
    When calculate_next_business_hour(employer_timezone) is called
    Then the result should be a UTC datetime
    And if current time is within 9am-5pm weekday: result should be near-immediate
    And if current time is after 5pm weekday: result should be next day 9am
    And if current time is Saturday or Sunday: result should be Monday 9am
    And if current time is Friday after 5pm: result should be Monday 9am
    And the conversion from local to UTC should use ZoneInfo (not manual offset)

    # CONFIDENCE SCORING:
    #   1.0 — All time scenarios handled, ZoneInfo used, UTC output verified
    #   0.8 — Works for most cases but DST edge case not handled
    #   0.6 — Basic logic works but weekend handling has off-by-one
    #   0.4 — Function exists but always returns "now" regardless of time
    #   0.0 — Function is stub/TODO

    # RED FLAGS:
    #   - Using timedelta(hours=N) instead of ZoneInfo for timezone conversion
    #   - Hardcoded UTC offset (e.g., +10 for Sydney) — breaks during DST
    #   - No weekday check (weekday() or isoweekday() absent)

  Scenario: SLA configuration resolution
    Given a customer_id and check_type
    When mock_resolve_sla_config(customer_id, check_type) is called
    Then it should return a list of check_steps matching background_check_sequence.check_steps shape
    And each step should have: subflow_name, max_attempts, retry_intervals, human_in_the_loop
    And the default should be: voice-verification with max_attempts=5 and retry_intervals=[2, 4, 24, 48]

    # NOTE: This is currently a mock that ignores inputs. That's acceptable
    # for Phase 1. Check whether it's been replaced with real DB query
    # (querying background_check_sequence table). If still mock, score 0.6
    # (functional but known limitation). If replaced, score higher.

  Scenario: Prefect flow run is created with correct parameters
    Given all preceding steps succeeded (contact, timezone, business hour, SLA config)
    When the Prefect client creates a flow run from deployment
    Then the deployment target should be "verification-orchestrator/verification-orchestrator"
    And the flow run state should be Scheduled with scheduled_time from calculate_next_business_hour
    And the parameters should include: case_id, customer_id, task_id, check_type, check_steps, scheduled_time
    And after creation, background_tasks should be updated with:
      | Column                    | Value                                |
      | prefect_flow_run_id       | UUID from Prefect response           |
      | prefect_deployment_name   | "verification-orchestrator/..."      |
      | prefect_scheduled_start   | UTC datetime from scheduling step    |

    # EVIDENCE TO CHECK:
    #   - Prefect get_client() usage (not httpx direct call)
    #   - create_flow_run_from_deployment() call with deployment name
    #   - Scheduled state import and usage
    #   - UPDATE background_tasks SQL after flow run creation
    #   - The UPDATE uses the actual flow_run.id, not a placeholder


# ==========================================================================
# Feature 3: Docker Stack for Local E2E
# ==========================================================================
#
# CONTEXT: The prefect-local-e2e-setup-prd requires a one-command Docker
# stack that includes both Prefect infrastructure AND the application
# database. Currently docker-compose.prefect.yaml has Prefect server but
# no app database and no worker service.

Feature: Local Docker Stack Completeness

  Background:
    Given docker-compose.prefect.yaml exists in the agencheck-support-agent directory

  Scenario: Docker compose includes all required services
    Given I read docker-compose.prefect.yaml
    Then I should find these service definitions:
      | Service          | Purpose                        | Key Port |
      | prefect-postgres | Prefect metadata database      | 5433     |
      | prefect-redis    | Prefect messaging              | 6380     |
      | prefect-server   | Prefect API + UI               | 4200     |
      | prefect-worker   | Flow execution (polls pool)    | N/A      |
      | app-postgres     | Application database           | 5434     |
    And prefect-worker should depend on prefect-server
    And app-postgres should use a PostgreSQL 17 image (matching Railway)
    And each service should have a health check defined

    # CONFIDENCE SCORING:
    #   1.0 — All 5 services defined with health checks and correct ports
    #   0.8 — All services present but missing health check on one
    #   0.6 — 4 of 5 services present (usually missing app-postgres or worker)
    #   0.4 — Only Prefect infrastructure services (no app-postgres, no worker)
    #   0.2 — File exists but services are commented out or broken
    #   0.0 — File unchanged from pre-productionisation state

    # RED FLAGS:
    #   - app-postgres defined but no volumes (data lost on restart)
    #   - Worker service defined but CMD still points to "prefect worker start"
    #     (should use deployments.py entrypoint)
    #   - Port conflicts (both postgres on 5432)

  Scenario: Worker service uses deployment registration
    Given the prefect-worker service in docker-compose.prefect.yaml
    When I examine its CMD or entrypoint
    Then it should run the deployment registration module (e.g., python -m prefect.flows.deployments)
    And NOT just "prefect worker start --pool voice-pool" (which starts polling but registers nothing)
    And the Dockerfile.prefect-worker should copy application code (not just Prefect)

    # CONTEXT: This is GAP 3 + GAP 5 from the local E2E PRD. Without
    # deployment registration, create_flow_run_from_deployment() fails
    # because no deployment exists on the server.

  Scenario: Seed script creates test fixtures
    Given a seed script (scripts/seed_local_db.py or similar)
    When executed against app-postgres
    Then it should run ALL migrations (001-041) creating the full schema
    And insert at minimum:
      | Table                  | Fixture                                          |
      | verification_subjects  | At least 1 row (first_name, last_name)           |
      | university_contacts    | At least 1 employer row (phone, timezone, entity_type='employer') |
      | cases                  | At least 1 case linking subject + contact + verification_metadata |
    And verification_metadata should contain employer, employment, verify_fields, customer_agreement keys

    # CONFIDENCE SCORING:
    #   1.0 — Script runs all migrations, inserts all fixtures, idempotent
    #   0.8 — Migrations run, fixtures present but missing one field
    #   0.6 — Script exists but only runs some migrations (skips 040-041)
    #   0.4 — Script exists but is a placeholder (TODO/empty functions)
    #   0.0 — No seed script found


# ==========================================================================
# Feature 4: Stub Wiring — Flow Tasks Execute Real Logic
# ==========================================================================
#
# CONTEXT: Four stub files currently return hardcoded/None values. The
# local E2E PRD requires them to be wired to real database queries.

Feature: Prefect Flow Task Stub Wiring

  Background:
    Given the flow tasks are at prefect/flows/tasks/ (or prefect_flows/tasks/)
    And a shared database pool helper exists (prefect/flows/helpers/db.py or equivalent)

  Scenario: prepare_call queries real database
    Given prefect/flows/tasks/prepare_call.py
    When I read the function body of prepare_call()
    Then it should:
      | Step | What                                                    | Evidence                          |
      | 1    | Query cases table for case_id + customer_id             | SELECT ... FROM cases WHERE id=$1 |
      | 2    | Query verification_subjects for subject name            | SELECT first_name, last_name ...  |
      | 3    | Query university_contacts for employer phone + timezone | SELECT phone_number, timezone ... |
      | 4    | Build job_metadata dict from query results              | Dict with phone_number, candidate_info, verify_fields |
    And it should NOT return a dict with all None values (that's the stub behavior)
    And it should use asyncpg (connection pool or direct connect)

    # CONFIDENCE SCORING:
    #   1.0 — All 4 steps with real SQL, proper error handling
    #   0.8 — Queries work but error handling is minimal (no ValueError on missing case)
    #   0.6 — Some queries real, some still returning hardcoded values
    #   0.4 — Function restructured but queries commented out or using ORM instead of asyncpg
    #   0.2 — Only the function signature changed, body still returns Nones
    #   0.0 — File unchanged from stub state

    # RED FLAGS:
    #   - return {"phone_number": None, "candidate_info": {...}} — stub behavior unchanged
    #   - Queries present but using wrong table/column names
    #   - No import of asyncpg or db pool helper

  Scenario: dispatch_call supports dual mode
    Given prefect/flows/tasks/dispatch_call.py
    When I read the dispatch function
    Then it should check PREFECT_DISPATCH_MODE environment variable
    And in "local_mock" mode: simulate dispatch, return synthetic result after configurable delay
    And in "live" mode: call dispatch_work_history_call() from communication-agent
    And the mock mode should log what it would do ("Mock dispatch: would call +61...")
    And the live mode should poll background_tasks for completion with timeout

    # CONFIDENCE SCORING:
    #   1.0 — Dual mode implemented, mock logs clearly, live mode has timeout + polling
    #   0.8 — Both modes work but live mode missing timeout handling
    #   0.6 — Mock mode works, live mode is TODO/stub
    #   0.4 — Original stub with sleep() still present, just renamed
    #   0.0 — wait_for_call_completion() still just sleeps and returns mock

  Scenario: process_result persists to database
    Given prefect/flows/tasks/process_result.py
    When I read the process function
    Then it should:
      | Step | What                                                     |
      | 1    | Build verification_outcome from call_result               |
      | 2    | UPDATE cases SET verification_results=$1, status=$2       |
      | 3    | INSERT INTO workflow_events with event_type='result_processed' |
      | 4    | Determine should_retry based on outcome status            |
    And it should NOT just build the outcome dict without persisting (that's the stub)
    And the workflow_events INSERT should include flow_run_id, case_id, channel

    # CONFIDENCE SCORING:
    #   1.0 — All 4 steps, cases updated, workflow_events created, retry logic correct
    #   0.8 — Cases updated but workflow_events INSERT missing
    #   0.6 — Outcome dict built and returned, UPDATE exists but untested
    #   0.4 — Function exists but persistence is commented out
    #   0.0 — Original stub: builds dict but doesn't persist

  Scenario: verification_router routes to Prefect or legacy
    Given api/services/verification_router.py
    When I read _create_prefect_task and _create_legacy_task
    Then _create_prefect_task should:
      | Step | What                                                     |
      | 1    | Use Prefect get_client() to connect to server             |
      | 2    | Call create_flow_run_from_deployment() with deployment ID  |
      | 3    | Return dict with flow_run_id, orchestrator="prefect"      |
    And _create_legacy_task should:
      | Step | What                                                     |
      | 1    | Use BackgroundTaskService to create a task row            |
      | 2    | Return dict with task_id, orchestrator="legacy"           |
    And neither function should return mock UUIDs (that's the stub behavior)

    # RED FLAGS:
    #   - return {"task_id": 1, "flow_run_id": "mock-uuid-..."} — stub unchanged
    #   - Prefect client imported but never used (dead code)
    #   - _create_legacy_task still returns hardcoded dict


# ==========================================================================
# Feature 5: End-to-End Pipeline Execution
# ==========================================================================
#
# CONTEXT: This is the ultimate validation — does the complete chain work?
# A verification request submitted via API should result in a Prefect flow
# being scheduled, picked up by a worker, and producing results in the DB.

Feature: Complete Pipeline Execution (API to Results)

  Scenario: Happy path — verify request to stored results
    Given the Docker stack is running (all 5 services healthy)
    And the database is seeded with a test case (case_id=1)
    And USE_PREFECT_ORCHESTRATION=true
    And PREFECT_DISPATCH_MODE=local_mock (no real LiveKit needed)
    When POST /api/v1/verify is called with case_id=1, customer_id=1, check_type=work_history
    Then within 10 seconds: background_tasks.prefect_flow_run_id should be non-NULL
    And within 30 seconds: the Prefect flow run state should transition from Scheduled → Running
    And within 120 seconds: cases.verification_results should be populated (non-NULL JSONB)
    And cases.status should no longer be "pending"
    And workflow_events should have at least one row with case_id=1

    # CONFIDENCE SCORING:
    #   1.0 — Full chain works: API → bridge → Prefect → worker → prepare → dispatch → process → DB
    #   0.8 — Chain works but one step skipped (e.g., no workflow_events row)
    #   0.6 — Prefect flow created and picked up, but results not stored in cases
    #   0.4 — Flow created in Prefect but worker never picks it up (deployment not registered)
    #   0.2 — background_task created but prefect_flow_run_id is NULL (bridge not wired)
    #   0.0 — API returns 500 or nothing happens in the database

    # THIS IS THE SINGLE MOST IMPORTANT SCENARIO. If this scores < 0.6,
    # the productionisation work is not complete regardless of what
    # individual components look like in isolation.

  Scenario: Live dispatch — real case through LiveKit
    Given the Docker stack is running (all 6 services healthy, including app-server)
    And PREFECT_DISPATCH_MODE=live (real LiveKit credentials configured)
    And LiveKit is configured with URL, API key, API secret, and SIP trunk ID
    And case 18 exists in the database:
      | Field                | Value                        |
      | case_id              | 18                           |
      | customer_id          | 1                            |
      | case_type            | work_history                 |
      | status               | pending                      |
      | employer_contact_id  | 7522                         |
      | subject              | Marcus Rivera                |
      | employer             | DataStream Analytics Pty Ltd |
      | phone                | +61404236990                 |
      | country              | Australia                    |
    When POST /api/v1/verify is called with valid payload:
      | Field         | Value                        |
      | candidate     | {first_name: Marcus, last_name: Rivera} |
      | employer      | {company_name: DataStream Analytics Pty Ltd} |
      | phone_numbers | ["+61404236990"]             |
      | check_type    | work_history                 |
    Then within 10 seconds: a Prefect flow run should be created (background_tasks.prefect_flow_run_id non-NULL)
    And the flow run should transition to Running state
    And the prepare_call task should complete with real data from the database (not None values)
    And the dispatch task should create a LiveKit SIP participant (real outbound call)
    And the Prefect flow logs should show "dispatch_work_history_call" execution (not mock)
    And the LiveKit room should be created with a SIP participant targeting +61404236990
    And eventually: call results should be stored in cases.verification_results (even if call fails/goes to voicemail)

    # CONFIDENCE SCORING:
    #   1.0 — Full chain: API → bridge → Prefect → worker → prepare (real DB) → dispatch (real LiveKit) → results stored
    #   0.8 — LiveKit call dispatched but results not stored (post-call processing gap)
    #   0.6 — Flow runs and prepare_call works with real data, but dispatch falls back to mock
    #   0.4 — Flow created but prepare_call fails (DB query issues with real case data)
    #   0.2 — POST /verify returns success but no Prefect flow is created
    #   0.0 — App-server returns 500 or LiveKit credentials are misconfigured

    # THIS SCENARIO PROVES THE FULL BUSINESS VALUE: A real phone call is made
    # to verify employment. Without this, the "pipeline" is just task scheduling
    # without the actual verification happening.

    # EVIDENCE TO CHECK:
    #   - LiveKit room list API: GET /rooms on LiveKit cloud should show a new room
    #   - SIP participant: The room should have a SIP participant with phone +61404236990
    #   - Prefect flow logs: Should show dispatch_work_history_call() execution, not mock
    #   - background_tasks: prefect_flow_run_id populated, status transitions visible
    #   - cases: verification_results JSONB should contain call outcome (even voicemail)

    # RED FLAGS:
    #   - PREFECT_DISPATCH_MODE silently defaults to local_mock in Docker
    #   - LiveKit env vars are set in docker-compose but not passed to the worker container
    #   - dispatch function checks mode but always falls through to mock branch
    #   - prepare_call queries correct tables but returns None for case 18 (query bug)
    #   - "ModuleNotFoundError" in worker logs (incomplete COPY in Dockerfile)

  Scenario: Retry scheduling after voice failure
    Given a completed flow run where the call result is "voicemail_left"
    And the SLA config has retry_intervals=[2, 4, 24, 48] hours
    When process_result determines should_retry=true
    Then a new Prefect flow run should be scheduled at current_time + 2 hours
    And background_tasks should track the retry (attempt_count incremented)
    And after 5 failed attempts: status should become "max_retries_exceeded"
    And manual review escalation should be triggered (or flagged for it)

    # NOTE: This may not be fully implemented in Phase 1. If the retry
    # logic exists in the bridge/flow code but hasn't been E2E tested,
    # score 0.6. If retry intervals are only in mock_resolve_sla_config
    # but not acted upon, score 0.4.

  Scenario: Legacy fallback when Prefect is disabled
    Given USE_PREFECT_ORCHESTRATION=false (or not set)
    When POST /api/v1/verify is called
    Then the bridge should return None (no Prefect interaction)
    And a background_task row should be created via the legacy path
    And background_tasks.prefect_flow_run_id should be NULL
    And the legacy scheduler_service should be able to pick up this task
    And the API response should still be successful (200)

    # This validates the feature flag safety net. If this doesn't work,
    # there's no safe rollback from Prefect to legacy scheduling.


# ==========================================================================
# Feature 6: Observability — Can We See What's Happening?
# ==========================================================================

Feature: Pipeline Observability and Traceability

  Scenario: Prefect UI shows flow runs
    Given Prefect server is running at localhost:4200
    When a flow run is created by the bridge
    Then it should be visible in the Prefect UI flow runs list
    And it should show the deployment name
    And it should show the scheduled time
    And state transitions (Scheduled → Running → Completed/Failed) should be visible

    # EVIDENCE: Check /api/flow_runs endpoint, or screenshot of Prefect UI

  Scenario: Database has complete audit trail
    Given a verification request has been processed through the pipeline
    When I query the database
    Then I should find:
      | Table              | Evidence                                         |
      | cases              | verification_results JSONB populated              |
      | background_tasks   | prefect_flow_run_id, prefect_deployment_name set  |
      | workflow_events    | At least 1 row with event_type, state, case_id    |
    And the workflow_events should have timestamps for tracking latency
    And the background_tasks row should show when Prefect scheduled the run

  Scenario: Logfire spans replace Prometheus metrics
    Given the Prefect hooks and metrics modules
    When I read metrics_hooks.py, prefect_metrics.py, and state_hooks.py
    Then I should find logfire.span() calls replacing Prometheus Counter/Histogram/Gauge
    And the spans should include business attributes (case_id, deployment, state, duration)
    And the /metrics endpoint should still work for infrastructure monitoring (Prometheus format)

    # CONFIDENCE SCORING:
    #   1.0 — Full Logfire migration, dual-emit working, business spans present
    #   0.8 — Logfire spans added but Prometheus not yet removed (dual stack)
    #   0.6 — Some Logfire usage but Prometheus still primary
    #   0.4 — Logfire imported but not used in flow hooks
    #   0.0 — No Logfire integration (still pure Prometheus)

    # NOTE: Logfire migration is Phase 3 of the local E2E PRD. If the
    # orchestrator focused on Phase 1-2 (stack + wiring), scoring 0.4
    # here is acceptable. But if they claim Logfire is done, verify.


# ==========================================================================
# Feature 7: Test Quality — Are Tests Real or Hollow?
# ==========================================================================
#
# CONTEXT: The implementation report states 53/53 tests pass. But these
# test the bridge in isolation with full mocking. The productionisation
# work should ADD tests, not just rely on the existing 53.

Feature: Test Suite Quality and Coverage

  Scenario: New tests exist beyond the original 53
    Given the test directory tests/prefect/
    When I count test files and test functions
    Then the total test count should be > 53 (original bridge tests)
    And new test files should exist for:
      | Test File                          | Tests What                        |
      | test_e2e_voice_flow.py             | Happy path E2E                    |
      | test_e2e_legacy_fallback.py        | Legacy path when Prefect disabled |
      | test_e2e_retry_escalation.py       | Retry logic and escalation        |
      | test_task_wiring.py                | Stub wiring with real DB queries  |
    And existing xfailed tests for voice path should be promoted to regular passing

    # CONFIDENCE SCORING:
    #   1.0 — All 4 new test files with substantive tests, xfail promoted, total > 70
    #   0.8 — 3 of 4 files exist with real tests
    #   0.6 — Files exist but tests are mostly pytest.skip() or shallow
    #   0.4 — Only 1-2 new test files, or files exist but are empty
    #   0.2 — Original 53 tests only, no new test files
    #   0.0 — Test count decreased or tests removed

    # RED FLAGS:
    #   - "53 tests pass" repeated without mention of new tests
    #   - New test files exist but contain only def test_placeholder(): pass
    #   - Tests import from bridge but don't assert DB state (hollow mocks)
    #   - All new tests are @pytest.mark.skip("TODO")

  Scenario: Integration tests use real database
    Given test files marked as integration or e2e
    When I read the test code
    Then at least some tests should use asyncpg to connect to a real database
    And they should insert test data, run the function, and assert DB state changed
    And they should NOT only mock asyncpg.connect (that's unit testing, not integration)
    And conftest.py should have fixtures for database setup/teardown

    # EVIDENCE: Look for DATABASE_URL usage in tests, actual SQL in conftest,
    # @pytest.fixture decorators that create/destroy test data


# ==========================================================================
# Feature 8: Migration and Schema Readiness
# ==========================================================================

Feature: Database Schema Supports Prefect Pipeline

  Scenario: Migration 041 adds Prefect columns to background_tasks
    Given database/migrations/ directory
    When I find migration 041
    Then it should add these columns to background_tasks:
      | Column                    | Type         |
      | prefect_flow_run_id       | UUID         |
      | prefect_deployment_name   | VARCHAR/TEXT |
      | prefect_scheduled_start   | TIMESTAMPTZ  |
    And the columns should be NULLABLE (backward compatible with legacy tasks)

  Scenario: Migration 040 creates workflow_events table
    Given database/migrations/ directory
    When I find migration 040
    Then it should CREATE TABLE workflow_events with at minimum:
      | Column         | Required |
      | id             | Yes      |
      | event_type     | Yes      |
      | flow_run_id    | Yes      |
      | case_id        | Yes      |
      | state          | Yes      |
      | payload        | Yes      |
      | created_at     | Yes      |
    And it should have indexes on flow_run_id, case_id, and event_type

  Scenario: All migrations run cleanly from scratch
    Given a fresh PostgreSQL database
    When migrations 001 through 041 are applied in sequence
    Then all migrations should succeed without errors
    And the resulting schema should have: cases, background_tasks, verification_subjects,
        university_contacts, workflow_events tables
    And background_tasks should have the Prefect columns from migration 041

    # NOTE: This is validated by the seed script. If the seed script
    # runs all migrations successfully, this scenario passes.


# ==========================================================================
# Validation Rubric Summary
# ==========================================================================
#
# When evaluating an orchestrator's claim of "Prefect productionisation done":
#
# CRITICAL (must be >= 0.6 to accept):
#   Feature 1: Bridge Integration — Is create_prefect_flow_run() actually called?
#   Feature 5, Scenario 1: Happy Path — Does the full chain work end-to-end?
#
# IMPORTANT (should be >= 0.4):
#   Feature 2: Flow Scheduling — Are the pipeline steps functional?
#   Feature 3: Docker Stack — Can you run it locally?
#   Feature 4: Stub Wiring — Are stubs replaced with real logic?
#
# NICE TO HAVE (acceptable at any level for Phase 1):
#   Feature 6: Observability — Logfire migration is Phase 3, may be deferred
#   Feature 7: Test Quality — New tests should exist but count matters less than substance
#   Feature 8: Migrations — Should already be done (commit 2b2d0a52)
#
# OVERALL CONFIDENCE = weighted average:
#   Feature 1 weight: 0.30 (most critical — the integration gap)
#   Feature 5 weight: 0.25 (ultimate proof — does it work?)
#   Feature 4 weight: 0.20 (stub wiring is the bulk of the work)
#   Feature 3 weight: 0.10 (Docker stack enables everything)
#   Feature 2 weight: 0.05 (pipeline logic was already working)
#   Feature 6 weight: 0.05 (Phase 3, deferrable)
#   Feature 7 weight: 0.03 (tests are evidence, not deliverable)
#   Feature 8 weight: 0.02 (migrations likely pre-existing)
#
# ACCEPT threshold: overall >= 0.6 AND no critical feature below 0.4
# REJECT threshold: any critical feature below 0.4 OR overall < 0.5
