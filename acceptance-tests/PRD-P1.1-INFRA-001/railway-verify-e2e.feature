@railway-e2e @live @prd-P1.1-INFRA-001
Feature: Railway Dev E2E - Worker Pool Fix + /verify-call Task Creation

  These scenarios validate that:
  1. The Prefect worker registers properly with voice-pool (not serve() push mode)
  2. POST /api/v1/verify creates a background_tasks row on Railway dev
  3. The full pipeline (API → DB → Prefect) is connected

  Background:
    Given the Railway project "agencheck" environment is "development"
    And zenagent dev is healthy at https://zenagent-development.up.railway.app/health
    And Prefect server is healthy at https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/health

  # AC-1: Worker mode changed from serve() to worker start
  @AC-1 @infra
  Scenario: Prefect worker uses 'prefect worker start' not serve()
    When I inspect the Dockerfile.prefect-worker.railway CMD
    Then the CMD uses "prefect worker start" with "--pool voice-pool"
    And the CMD does NOT use "python -m prefect_flows.flows.deployments"

    # Confidence scoring:
    # 1.0 — CMD is 'prefect worker start --pool voice-pool --type process'
    # 0.5 — CMD changed but missing --pool or --type flags
    # 0.0 — Still using serve() (python -m prefect_flows.flows.deployments)

    # Evidence to check:
    # - agencheck-support-agent/Dockerfile.prefect-worker.railway: CMD line
    # - Git diff showing CMD change
    # - Railway deployment logs showing "Starting worker..." not "Starting Prefect serve"

    # Red flags:
    # - serve() still in CMD
    # - Missing --type process flag
    # - Missing PREFECT_WORK_POOL_NAME env var

  # AC-2: Worker registered with voice-pool
  @AC-2 @api @weight-0.25
  Scenario: Worker appears ONLINE in voice-pool work pool
    Given the prefect-worker deployment status is "SUCCESS" on Railway
    When I query the voice-pool work pool workers via Prefect API
    Then at least 1 worker is listed
    And the worker status is "ONLINE"
    And the work pool status is "READY" (not "NOT_READY")
    And last_polled is within the last 120 seconds

    # Confidence scoring:
    # 1.0 — Worker ONLINE, pool READY, heartbeat within 60s
    # 0.5 — Worker listed but pool still NOT_READY
    # 0.0 — 0 workers registered (serve() mode still active)

    # Validation commands:
    # TOOL: curl
    # curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/work_pools/voice-pool
    # curl -s -X POST https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/work_pools/voice-pool/workers/filter -H "Content-Type: application/json" -d '{}'

    # Red flags:
    # - 0 workers (serve() mode — no registration)
    # - last_polled: null/never
    # - Pool type != "process"

  # AC-3: All 4 deployments linked to voice-pool
  @AC-3 @api @weight-0.20
  Scenario: All flow deployments are associated with voice-pool
    When I query the Prefect server for deployments
    Then the following 4 deployments exist:
      | deployment_name           | work_pool_name |
      | voice-verification        | voice-pool     |
      | verification-orchestrator | voice-pool     |
      | catch-up-poller           | voice-pool     |
      | email-outreach            | voice-pool     |
    And NONE have work_pool_name: null

    # Confidence scoring:
    # 1.0 — All 4 deployments show work_pool_name: "voice-pool"
    # 0.5 — Some deployments linked, some still null
    # 0.0 — All deployments show work_pool_name: null (serve() mode)

    # Validation commands:
    # TOOL: curl
    # curl -s -X POST https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/deployments/filter \
    #   -H "Content-Type: application/json" -d '{}'
    # Check: each deployment has work_pool_name == "voice-pool"

    # Red flags:
    # - work_pool_name: null on any deployment
    # - Fewer than 4 deployments
    # - Deployments use different pool names

  # AC-4: /verify-call creates a background_task row
  @AC-4 @api @db @weight-0.30
  Scenario: POST /api/v1/verify creates a task in background_tasks table
    Given I have valid API credentials for the test account
    When I POST to https://zenagent-development.up.railway.app/api/v1/verify with a valid work history payload:
      """json
      {
        "check_type": "work_history",
        "employer_name": "Test Corp Pty Ltd",
        "employer_phone": "+61200000000",
        "candidate_name": "Jane Test",
        "verify_fields": {
          "job_title": "Senior Engineer",
          "dates_employed": "2023-01-01 to 2024-12-31"
        }
      }
      """
    Then the API returns HTTP 200 or 202
    And the response body contains a task_id
    And querying Railway dev PostgreSQL for that task_id:
      """sql
      SELECT id, task_id, task_type, status, context_data
      FROM background_tasks
      WHERE task_id = '<returned_task_id>'
      """
    Then exactly 1 row is returned
    And status is one of ('started', 'pending', 'queued')
    And task_type is 'work_history' or contains 'verification'

    # Confidence scoring:
    # 1.0 — POST returns task_id, DB row exists with correct status
    # 0.5 — POST returns 200 but no DB row (API not connected to DB)
    # 0.0 — POST returns 4xx/5xx (endpoint broken or auth required)

    # Validation commands:
    # TOOL: curl + direct psql query
    # 1. POST /api/v1/verify
    # 2. Extract task_id from response
    # 3. psql $DATABASE_URL -c "SELECT * FROM background_tasks WHERE task_id='...'"

    # Red flags:
    # - HTTP 401/403 (auth required but not configured for dev)
    # - HTTP 500 (DB connection error, missing table)
    # - Row created but no Prefect flow triggered (USE_PREFECT_ORCHESTRATION=false)
    # - task_type mismatch between API and DB

  # AC-5: Acceptance tests passing
  @AC-5 @meta @weight-0.10
  Scenario: Adapted acceptance tests validate Railway dev environment
    Given the acceptance test scenarios exist in acceptance-tests/PRD-P1.1-INFRA-001/
    When all @railway-e2e scenarios are executed against Railway dev
    Then AC-1 through AC-4 all score >= 0.8
    And no scenario scores 0.0

    # This is a meta-scenario — scored by the guardian after running AC-1 through AC-4

  # E2E Journey: Full pipeline verification
  @e2e @journey @weight-0.15
  Scenario: E2E - Verify request creates task and Prefect picks it up
    Given the worker is ONLINE in voice-pool (AC-2 passed)
    And deployments are linked to voice-pool (AC-3 passed)
    When I POST /api/v1/verify with a test payload
    Then a background_tasks row is created (task_id returned)
    And eventually a Prefect flow run appears for that verification
    And the flow run transitions to RUNNING within 60 seconds

    # This proves: API → DB → Prefect Server → Work Pool → Worker → Execution
    # Even if the flow fails (mock mode, missing LiveKit), RUNNING proves connectivity.

    # Validation commands:
    # TOOL: curl + psql + polling
    # 1. POST /api/v1/verify → get task_id
    # 2. psql → confirm background_tasks row
    # 3. Poll: curl -s .../api/flow_runs/filter -d '{"flow_runs": {"name": {"like_": "%<task_id>%"}}}'
    # 4. Wait up to 60s for state_name == "Running" or "Completed"

    # Red flags:
    # - Flow run never appears (USE_PREFECT_ORCHESTRATION=false)
    # - Flow run stays in PENDING (worker not picking up from pool)
    # - Flow run appears but in wrong pool (deployment not linked)
