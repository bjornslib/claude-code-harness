# Journey J5: E2E — Submit Work History Verification via /verify and Observe Full Pipeline
#
# CROSS-LAYER: Claude in Chrome (Frontend) → /verify API → Case Creation → Prefect Flow
#              → DB-backed Config Resolution → Channel Dispatch → background_tasks Audit
# BUSINESS OUTCOME: A customer submits a work history verification request through the
#   frontend UI, which hits POST /api/v1/verify. The system creates a case, resolves
#   SLA config from the database, dispatches the Prefect verification_orchestrator_flow,
#   and records the attempt in background_tasks with full audit metadata.
#
# THIS IS THE MONEY TEST. If this passes, the UE-A pipeline works end-to-end.
#
# EXECUTION ENVIRONMENT:
#   Frontend: npm run dev (feature branch) on http://localhost:5002
#   Backend:  Docker app-server (feature branch) on http://localhost:8000
#   Database: Docker app-postgres on port 5434 (migration 035 applied)
#   Prefect:  Docker prefect-server on port 4200 (PREFECT_DISPATCH_MODE=local_mock)
#   Browser:  Claude in Chrome (chrome-devtools MCP) for frontend interactions
#   API:      curl for direct /verify submission and verification
#   DB:       docker exec psql for audit trail verification
#
# BLIND: This test is invisible to the S3 operator and its workers.

@journey @prd-uea-001 @J5 @e2e @verify @claude-in-chrome
Feature: J5 — E2E work history verification submission through full pipeline

  Background:
    Given the frontend dev server is running at http://localhost:5002 (npm run dev, feature branch)
    And the backend API Docker container is running at http://localhost:8000 (feature branch)
    And PostgreSQL Docker container has migration 035 applied
    And Prefect server is running at http://localhost:4200
    And PREFECT_DISPATCH_MODE=local_mock is set
    And an active work_history sequence exists for customer_id=1 with:
      | step               | max_attempts | retry_intervals   |
      | voice-verification | 5            | [2, 4, 24, 48]    |
      | email-outreach     | 3            | [24, 72, 120]     |
      | human-review       | 1            | []                |
    And browser automation uses Claude in Chrome (chrome-devtools MCP tools)

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 1: Submit /verify via curl and observe pipeline
  # ─────────────────────────────────────────────────────────────────

  @api @smoke
  Scenario: POST /verify creates case, resolves DB config, triggers Prefect flow
    # STEP 1: Submit verification request via curl
    When POST /api/v1/verify is called with:
      curl -X POST http://localhost:8000/api/v1/verify \
        -H "X-API-Key: ${AGENCHECK_API_KEY}" \
        -H "Content-Type: application/json" \
        -d '{
          "customer_id": 1,
          "check_type": "work_history",
          "candidate_name": "Jane Smith",
          "employer_name": "Acme Corporation",
          "contact_phone": "+61412345678",
          "contact_email": "hr@acme.example.com"
        }'
    Then 201 Created is returned with a case_id (capture as $CASE_ID)

    # STEP 2: Verify case created in database
    When the database is queried via docker exec:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT id, customer_id, status FROM cases WHERE id = $CASE_ID"
    Then the case exists with customer_id=1

    # STEP 3: Verify SLA config was resolved from database (not hardcoded)
    When the database is queried for the resolution audit:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT id, customer_id, check_type_id, status, check_steps
         FROM background_check_sequence
         WHERE customer_id=1 AND status='active'
         AND check_type_id=(SELECT id FROM check_types WHERE name='work_history')"
    Then the active sequence exists with 3 check_steps (voice → email → human-review)

    # STEP 4: Verify Prefect flow was triggered (local_mock mode)
    When background_tasks is queried for this case:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT id, task_type, status, context_data, prefect_flow_run_id
         FROM background_tasks WHERE case_id = $CASE_ID ORDER BY created_at"
    Then at least one task record exists
    And the task_type indicates verification dispatch

    # STEP 5: Verify audit trail has sequence metadata
    When the background_tasks audit columns are checked:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT sequence_id, sequence_version, attempt_timestamp
         FROM background_tasks WHERE case_id = $CASE_ID"
    Then sequence_id is NOT NULL (references the active background_check_sequence)
    And sequence_version is NOT NULL (integer >= 1)
    And attempt_timestamp is NOT NULL (TIMESTAMPTZ)

    # Evidence Required:
    #   - curl response from POST /verify showing 201 + case_id
    #   - SQL: cases table shows new case
    #   - SQL: background_check_sequence used for resolution (not hardcoded)
    #   - SQL: background_tasks has task with sequence_id, sequence_version, attempt_timestamp
    #   - Prefect flow_run_id populated (even in local_mock mode)
    #
    # Confidence Scoring:
    #   0.0 — /verify returns error or doesn't create a case
    #   0.2 — Case created but no Prefect flow triggered
    #   0.4 — Flow triggered but uses hardcoded config (not DB resolution)
    #   0.6 — DB config resolved, flow triggered, but audit columns empty
    #   0.8 — Full pipeline: /verify → case → resolve → flow → audit trail (partial metadata)
    #   1.0 — Complete E2E: /verify → case → DB-resolved config → Prefect flow dispatched →
    #          background_tasks has sequence_id + sequence_version + attempt_timestamp

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 2: Frontend-initiated verification (Claude in Chrome)
  # ─────────────────────────────────────────────────────────────────

  @claude-in-chrome @e2e
  Scenario: Manager submits work history check from frontend UI through full pipeline
    # STEP 1: Navigate to verification submission page
    When Claude in Chrome navigates to http://localhost:5002
    And Claude in Chrome navigates to the verification submission page (if it exists in the UI)

    # STEP 2: Fill in verification details via Claude in Chrome
    When Claude in Chrome fills in the work history verification form:
      | field          | value                |
      | customer_id    | 1                    |
      | check_type     | work_history         |
      | candidate_name | John Doe             |
      | employer_name  | Test Corp            |
      | contact_phone  | +61400000000         |
      | contact_email  | hr@test.example.com  |
    And Claude in Chrome clicks "Submit"

    # STEP 3: Verify the submission reached the backend
    When the network requests are inspected via read_network_requests
    Then a POST request was made to /api/v1/verify
    And the response status is 201

    # STEP 4: Verify DB state matches the frontend submission
    When the database is queried for the latest case:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT id, customer_id, status FROM cases ORDER BY id DESC LIMIT 1"
    Then a new case exists with customer_id=1

    # Evidence Required:
    #   - Claude in Chrome screenshot of submission form
    #   - Network capture showing POST /verify with 201
    #   - SQL showing new case in database
    #
    # Confidence Scoring:
    #   0.0 — No verification submission page exists in the frontend
    #   0.3 — Page exists but form doesn't call /verify
    #   0.5 — Form calls /verify but submission fails (validation error)
    #   0.7 — Submission succeeds, case created, but no Prefect flow triggered
    #   1.0 — Complete: frontend form → /verify → case → Prefect flow → audit trail

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 3: Verify client-specific config flows through /verify
  # ─────────────────────────────────────────────────────────────────

  @api
  Scenario: /verify with client_reference uses client-specific SLA config
    Given customer_id=1 has a client-specific sequence for "Fortune 500 Corp" with:
      | step               | max_attempts | retry_intervals |
      | voice-verification | 8            | [1, 2, 4, 8]   |

    When POST /api/v1/verify is called with client_reference:
      curl -X POST http://localhost:8000/api/v1/verify \
        -H "X-API-Key: ${AGENCHECK_API_KEY}" \
        -H "Content-Type: application/json" \
        -d '{
          "customer_id": 1,
          "check_type": "work_history",
          "client_reference": "Fortune 500 Corp",
          "candidate_name": "John Executive",
          "employer_name": "Fortune 500 Corp",
          "contact_phone": "+61400000001"
        }'
    Then 201 Created is returned with a case_id

    When background_tasks is queried for this case
    Then the sequence_id references the Fortune 500 Corp sequence (not the default)
    And the resolved config has max_attempts=8 (not 5)

    # Evidence Required:
    #   - curl response from /verify with client_reference
    #   - SQL: background_tasks.sequence_id points to client-specific row
    #
    # Confidence Scoring:
    #   0.0 — client_reference field not accepted by /verify endpoint
    #   0.3 — Field accepted but ignored (always resolves to default)
    #   0.5 — client_reference passed to resolver but resolver ignores it
    #   0.7 — Full chain: /verify → resolver → client-specific config used
    #   1.0 — Complete: client_reference flows through all layers, audit trail
    #          references correct sequence, max_attempts=8 confirmed
