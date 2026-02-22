@railway-deployment @live @prd-P1.1-INFRA-001
Feature: Railway Prefect Worker Live Deployment Validation

  These scenarios validate the LIVE deployment of the Prefect worker service
  to Railway's development environment. They map directly to the 7 acceptance
  criteria in completion promise-0cf7cadb.

  Background:
    Given the Railway project "agencheck" is linked
    And the environment is "development"
    And the prefect-worker service exists in Railway

  # AC-1: Service created with correct Dockerfile
  @AC-1 @smoke
  Scenario: Prefect worker service uses correct Dockerfile
    When I query the prefect-worker service instance via Railway API
    Then the rootDirectory is "agencheck"
    And the dockerfilePath is "agencheck-support-agent/Dockerfile.prefect-worker.railway"
    And the builder is "DOCKERFILE"
    And the source repo is "bjornslib/zenagent"

    # Confidence scoring:
    # 1.0 — All 4 build settings correct, deployment succeeded
    # 0.5 — Service exists but wrong Dockerfile or root directory
    # 0.0 — Service does not exist

    # Validation command:
    # TOOL: Railway GraphQL API
    # curl -s "https://backboard.railway.app/graphql/v2" \
    #   -H "Authorization: Bearer $RAILWAY_TOKEN" \
    #   -d '{"query": "{ service(id: \"SERVICE_ID\") { serviceInstances { edges { node { rootDirectory dockerfilePath } } } } }"}'

  # AC-2: Worker connects to Prefect server
  @AC-2 @api
  Scenario: Worker registers with Prefect server and appears in work pool
    Given the prefect-worker deployment status is "SUCCESS"
    When I check the Prefect server API at the public URL
    Then GET /api/health returns HTTP 200
    And the worker appears in the "voice-pool" work pool
    And the worker status is "ONLINE"

    # Confidence scoring:
    # 1.0 — Worker online in voice-pool, processing flow runs
    # 0.5 — Worker deployed but not yet registered with server
    # 0.0 — Worker crashed or cannot reach Prefect server

    # Validation commands:
    # TOOL: curl
    # curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/health
    # curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/work_pools/voice-pool/workers

    # Red flags:
    # - Worker restart loop (check deployment logs for crash-restart pattern)
    # - PREFECT_API_URL using public URL instead of internal (latency)
    # - Work pool "voice-pool" doesn't exist (needs creation)

  # AC-3: Worker connects to app-postgres
  @AC-3 @api
  Scenario: Worker can reach application database
    Given the prefect-worker deployment status is "SUCCESS"
    When the worker runs database-dependent flows
    Then the DATABASE_URL uses internal networking (postgres.railway.internal:5432)
    And the worker can query the background_tasks table

    # Confidence scoring:
    # 1.0 — Worker successfully queries app database tables
    # 0.5 — DATABASE_URL set but connectivity unverified
    # 0.0 — DATABASE_URL missing or uses wrong host

    # Validation commands:
    # TOOL: Railway variables check
    # railway variables -s "prefect-worker" | grep DATABASE_URL
    # Expected: postgresql://supabase_admin:...@postgres.railway.internal:5432/postgres

  # AC-4: Worker connects to Redis DB 1
  @AC-4 @api
  Scenario: Worker uses Redis DB 1 for Prefect broker
    Given the prefect-worker deployment status is "SUCCESS"
    When I check the REDIS_URL environment variable
    Then the REDIS_URL ends with "/1" (database 1)
    And the host is redis.railway.internal

    # Confidence scoring:
    # 1.0 — REDIS_URL points to DB 1 on internal domain
    # 0.5 — Redis URL set but using DB 0 (conflicts with app streams)
    # 0.0 — No Redis URL configured

    # Validation commands:
    # TOOL: Railway variables check
    # railway variables -s "prefect-worker" | grep REDIS_URL
    # Expected: redis://default:...@redis.railway.internal:6379/1

  # AC-5: All 4 flow deployments registered
  @AC-5 @api
  Scenario: All four Prefect flow deployments are registered
    Given the prefect-worker deployment status is "SUCCESS"
    And the worker has started successfully
    When I query the Prefect server for deployments
    Then the following 4 deployments exist:
      | deployment_name          | flow_name                |
      | voice-verification       | voice_verification_flow  |
      | verification-orchestrator| verification_orchestrator_flow |
      | catch-up-poller          | catch_up_poller_flow     |
      | email-outreach           | email_outreach_flow      |
    And each deployment is associated with the "voice-pool" work pool

    # Confidence scoring:
    # 1.0 — All 4 deployments registered and associated with voice-pool
    # 0.5 — Some deployments registered but not all 4
    # 0.0 — No deployments registered (worker failed to start)

    # Validation commands:
    # TOOL: curl
    # curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/deployments/filter \
    #   -H "Content-Type: application/json" \
    #   -d '{"work_pool_filter": {"name": {"any_": ["voice-pool"]}}}'

    # Red flags:
    # - Fewer than 4 deployments (missing email_outreach_flow?)
    # - Deployments not linked to voice-pool
    # - Import errors in deployment logs

  # AC-6: Prefect server health check
  @AC-6 @smoke @api
  Scenario: Prefect server health check passes
    When I GET the Prefect server health endpoint
    Then HTTP status is 200
    And the response indicates the server is healthy

    # Validation commands:
    # TOOL: curl
    # curl -s -o /dev/null -w "%{http_code}" \
    #   https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/health

  # AC-7: Worker in ONLINE state in work pool
  @AC-7 @api
  Scenario: Worker appears ONLINE in Prefect UI work pool
    Given the prefect-worker deployment status is "SUCCESS"
    When I query the voice-pool work pool workers
    Then at least one worker is listed
    And the worker status is "ONLINE"
    And the worker last_heartbeat_time is within the last 60 seconds

    # Confidence scoring:
    # 1.0 — Worker ONLINE with recent heartbeat
    # 0.5 — Worker listed but status is not ONLINE
    # 0.0 — No workers in voice-pool

    # Validation commands:
    # TOOL: curl
    # curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/work_pools/voice-pool/workers
    # Check: response contains at least 1 worker with status ONLINE

    # Red flags:
    # - Worker heartbeat older than 60s (worker may have crashed)
    # - Multiple workers listed (duplicate deployments?)
    # - Work pool "voice-pool" returns 404 (needs creation first)

  # Bonus: End-to-end smoke test
  @e2e @smoke
  Scenario: Submit a test flow run and verify execution
    Given the prefect-worker is ONLINE in voice-pool
    When I create a flow run for the "catch-up-poller" deployment via the API
    Then the flow run transitions to "RUNNING" within 30 seconds
    And the flow run completes (COMPLETED or FAILED) within 120 seconds

    # This proves the full pipeline: API -> Server -> Work Pool -> Worker -> Execution
    # Even if the flow fails (e.g., missing data), the fact that it RUNS proves connectivity.

    # Validation commands:
    # TOOL: curl
    # 1. Create flow run:
    #    curl -s -X POST \
    #      https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/deployments/{deployment-id}/create_flow_run \
    #      -H "Content-Type: application/json" \
    #      -d '{}'
    # 2. Poll flow run status:
    #    curl -s https://prefecthqprefect3-latest-development-c95e.up.railway.app/api/flow_runs/{flow-run-id}
