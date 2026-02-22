# Journey J1: Admin Configures SLA via Frontend → Saves to PSQL via API
#
# CROSS-LAYER: Browser (Frontend) → HTTP (API) → PostgreSQL (Storage)
# BUSINESS OUTCOME: A customer admin can configure their SLA policy through the
#   web UI and have it persist in the database for use by Prefect flows.
#
# EXECUTION ENVIRONMENT:
#   Frontend: npm run dev (feature branch) on http://localhost:5002
#   Backend:  Docker app-server (feature branch) on http://localhost:8000
#   Database: Docker app-postgres on port 5434 (migration 035 applied)
#   Browser:  Claude in Chrome (chrome-devtools MCP) — NOT Playwright, NOT Jest
#
# BLIND: This test is invisible to the S3 operator and its workers.

@journey @prd-uea-001 @J1 @frontend @api @db @claude-in-chrome
Feature: J1 — Admin configures SLA via frontend and persists to database

  Background:
    Given the frontend dev server is running at http://localhost:5002 (npm run dev, feature branch)
    And the backend API Docker container is running at http://localhost:8000 (feature branch)
    And PostgreSQL Docker container has migration 035 applied (check_types + background_check_sequence tables exist)
    And a manager-level user is authenticated via Clerk
    And a default work_history sequence exists for customer_id=1
    And browser automation uses Claude in Chrome (chrome-devtools MCP tools)

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 1: Full save flow — Claude in Chrome navigates UI → API → PSQL
  # ─────────────────────────────────────────────────────────────────

  @claude-in-chrome @smoke
  Scenario: Manager edits SLA config in frontend and change persists in database
    # TOOL: Claude in Chrome — navigate to the SLA config page
    When Claude in Chrome navigates to http://localhost:5002/check-sla-configuration
    Then the page renders without JavaScript errors (check console via read_console_messages)
    And the SLACheckTypeGridV32 component is visible in the DOM
    And the grid displays check types loaded from the API (not mock data)
    And a data source indicator shows "live" (not "cached" or "mock")

    # TOOL: Claude in Chrome — interact with the edit modal
    When Claude in Chrome clicks the edit trigger for "voice-verification" channel under "work_history"
    Then the ChannelEditModal is visible with current configuration values
    When Claude in Chrome changes the max_attempts input from 5 to 7
    And Claude in Chrome clicks the "Save" button
    Then a loading spinner appears briefly (Loader2 component)
    And a toast notification shows "Configuration saved" (sonner library)
    And the modal closes

    # TOOL: Claude in Chrome — verify network request via read_network_requests
    When the network requests are inspected via read_network_requests
    Then a PATCH or PUT request was made to /api/v1/check-sequence/{id}
    And the request payload includes max_attempts=7
    And the response status is 200

    # TOOL: Direct DB query — verify persistence
    When the database is queried via docker exec:
      docker exec agencheck-support-agent-app-postgres-1 psql -U agencheck -d agencheck -c
        "SELECT id, version, status, check_steps FROM background_check_sequence
         WHERE customer_id=1 AND check_type_id=(SELECT id FROM check_types WHERE name='work_history')
         ORDER BY version DESC LIMIT 2"
    Then a row exists with version >= 2 (new version created)
    And the check_steps JSONB contains a voice-verification step with max_attempts=7
    And the previous version has status='archived'

    # Evidence Required:
    #   - Claude in Chrome screenshot of SLACheckTypeGridV32 showing live data
    #   - Network request capture showing PUT/PATCH with 200 response
    #   - SQL query result showing version bump and archived old version
    #
    # Confidence Scoring:
    #   0.0 — Page doesn't render or shows mock data only
    #   0.3 — Page renders API data but save button doesn't call backend
    #   0.5 — Save calls API but DB shows in-place update (no versioning)
    #   0.7 — Full flow works: UI → API → DB with versioning. Missing toast or spinner
    #   1.0 — Complete: UI renders live data, save triggers PUT/PATCH, DB shows version bump,
    #          toast confirmation, loading spinner, archived old version

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 2: RBAC enforcement across layers
  # ─────────────────────────────────────────────────────────────────

  @claude-in-chrome
  Scenario: Staff user sees read-only view — edit buttons hidden, API returns 403
    # TOOL: Claude in Chrome — navigate as staff user
    Given a staff-level user is authenticated via Clerk
    When Claude in Chrome navigates to http://localhost:5002/check-sla-configuration
    Then the page renders check sequence data (read-only view)
    And the "New Check Type" button in SLAHeader is NOT visible in the DOM
    And the "Delete" button is NOT visible
    And edit triggers on channels are hidden or disabled

    # TOOL: curl — verify API-level RBAC
    When a direct PUT /api/v1/check-sequence/{id} request is made with staff credentials:
      curl -X PUT http://localhost:8000/api/v1/check-sequence/1 \
        -H "Authorization: Bearer ${CLERK_STAFF_TEST_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{"check_steps": [...]}'
    Then the API returns 403 Forbidden
    And the database is unchanged

    # Evidence Required:
    #   - Claude in Chrome screenshot showing read-only state (no edit/delete buttons)
    #   - curl response showing 403 for staff-level write attempt
    #
    # Confidence Scoring:
    #   0.0 — No RBAC at all — all users see all buttons
    #   0.3 — Frontend hides buttons but API allows staff writes
    #   0.5 — Frontend + API both enforce RBAC but with wrong role names
    #   0.7 — Correct RBAC: staff=read-only in UI + 403 from API
    #   1.0 — Full RBAC: UI role guards via useCheckSequenceAuth(), API 403,
    #          Clerk token properly forwarded in Authorization header

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 3: Add new step via modal → persists as new step in DB
  # ─────────────────────────────────────────────────────────────────

  @claude-in-chrome
  Scenario: Manager adds a new email-outreach step via AddStepModal
    # TOOL: Claude in Chrome
    When Claude in Chrome navigates to http://localhost:5002/check-sla-configuration
    And Claude in Chrome clicks the "Add Step" button for the work_history check type
    Then the AddStepModal is visible
    When Claude in Chrome fills in the form:
      | field           | value           |
      | subflow_name    | email-outreach  |
      | max_attempts    | 3               |
      | retry_intervals | 24, 72, 120     |
    And Claude in Chrome clicks "Save"
    Then a toast notification confirms the save
    And the grid refreshes to show the new step

    # TOOL: Direct DB query — verify persistence
    When the database is queried for the active work_history sequence
    Then the check_steps JSONB array includes an email-outreach entry
    And the entry has max_attempts=3 and retry_intervals=[24, 72, 120]

    # Confidence Scoring:
    #   0.0 — AddStepModal doesn't exist or doesn't call API
    #   0.3 — Modal exists, saves to Zustand store only (no API call)
    #   0.5 — Modal calls API but creates a new sequence instead of updating existing
    #   0.7 — Correct: modal saves via saveToBackendV32(), DB updated
    #   1.0 — Complete: modal save, toast, grid refresh, DB has correct JSONB entry
