# Journey J3: Client-Specific Override Takes Precedence in 3-Tier Resolution
#
# CROSS-LAYER: HTTP (API) → Service (3-tier resolution) → PostgreSQL → Prefect
# BUSINESS OUTCOME: When a VIP client (e.g., "Fortune 500 Corp") submits a verification,
#   the system uses the client-specific SLA override — not the customer default and not
#   the system fallback. This is the core differentiator that enables enterprise customization.
#
# EXECUTION ENVIRONMENT:
#   Backend:  Docker app-server (feature branch) on http://localhost:8000
#   Database: Docker app-postgres on port 5434 (migration 035 applied)
#   Tests:    curl for API calls, docker exec psql for DB queries
#
# BLIND: This test is invisible to the S3 operator and its workers.

@journey @prd-uea-001 @J3 @api @db @resolution
Feature: J3 — Client-specific SLA override takes precedence in resolution chain

  Background:
    Given the backend API Docker container is running at http://localhost:8000 (feature branch)
    And PostgreSQL Docker container has migration 035 applied
    And customer_id=1 has TWO active work_history sequences:
      | client_reference   | max_attempts (voice) | retry_intervals (voice) |
      | NULL (default)     | 5                    | [2, 4, 24, 48]          |
      | Fortune 500 Corp   | 8                    | [1, 2, 4, 8]            |
    And PREFECT_DISPATCH_MODE=local_mock is set

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 1: Client-specific override wins over default
  # ─────────────────────────────────────────────────────────────────

  @api @smoke
  Scenario: Resolve with client_ref returns client-specific config, not default
    # LAYER 1: API — Resolution endpoint with client_ref
    When GET /api/v1/check-sequence/resolve is called with:
      | param       | value              |
      | customer_id | 1                  |
      | check_type  | work_history       |
      | client_ref  | Fortune 500 Corp   |
    Then 200 OK is returned
    And the resolved_sequence has client_reference="Fortune 500 Corp"
    And the voice-verification step has max_attempts=8 (not 5)
    And the voice-verification step has retry_intervals=[1, 2, 4, 8] (not [2, 4, 24, 48])
    And matched_at equals "client_specific"
    And resolution_chain includes ["client_specific:Fortune 500 Corp", "default"]

    # LAYER 2: Database — Verify both sequences exist and correct one was selected
    When the database is queried:
      SELECT id, client_reference, check_steps->0->>'max_attempts' as voice_max
      FROM background_check_sequence
      WHERE customer_id=1 AND check_type_id=(SELECT id FROM check_types WHERE name='work_history') AND status='active'
    Then 2 rows are returned (one default, one client-specific)
    And the client-specific row was the one returned by the API

    # Evidence Required:
    #   - API response from /resolve with client_ref=Fortune 500 Corp
    #   - SQL showing both active sequences for customer_id=1
    #   - resolution_chain field in response
    #
    # Confidence Scoring:
    #   0.0 — /resolve endpoint doesn't exist or ignores client_ref
    #   0.3 — Endpoint exists but always returns default (ignores client_reference filter)
    #   0.5 — Returns client-specific when exact match, but resolution_chain not populated
    #   0.7 — Full 3-tier with correct precedence. resolution_chain and matched_at correct
    #   1.0 — Complete: client > default > system, resolution_chain built dynamically,
    #          matched_at accurate, check_steps from correct sequence

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 2: Without client_ref, falls to customer default
  # ─────────────────────────────────────────────────────────────────

  @api
  Scenario: Resolve without client_ref returns customer default
    When GET /api/v1/check-sequence/resolve is called with:
      | param       | value        |
      | customer_id | 1            |
      | check_type  | work_history |
    Then 200 OK is returned
    And the resolved_sequence has client_reference=null
    And the voice-verification step has max_attempts=5 (customer default)
    And matched_at equals "default"
    And resolution_chain includes ["default"]

    # Evidence Required:
    #   - API response showing default config (not client-specific)
    #   - matched_at="default" in response

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 3: Prefect flow receives client-specific config
  # ─────────────────────────────────────────────────────────────────

  @api @prefect
  Scenario: Verification for Fortune 500 Corp uses faster retry intervals
    # LAYER 1: API — Submit verification with client context
    When POST /api/v1/verify is called with:
      | field            | value                |
      | customer_id      | 1                    |
      | check_type       | work_history         |
      | client_reference | Fortune 500 Corp     |
      | candidate_name   | John Executive       |
      | employer_name    | Fortune 500 Corp     |
    Then 201 Created is returned with a case_id

    # LAYER 2: Service → Prefect — Config resolved from DB
    When the Prefect verification_orchestrator_flow runs for this case
    Then it uses max_attempts=8 for voice-verification (from client-specific config)
    And retry intervals are [1, 2, 4, 8] hours (faster than default's [2, 4, 24, 48])

    # LAYER 3: Database — Audit trail references client-specific sequence
    When background_tasks is queried for this case
    Then the sequence_id matches the Fortune 500 Corp sequence (not the default)
    And sequence_version matches the client-specific sequence's version

    # Evidence Required:
    #   - /verify call with client_reference
    #   - prefect_bridge.py passing client_ref to resolve_sla_config
    #   - background_tasks.sequence_id pointing to client-specific row
    #
    # Confidence Scoring:
    #   0.0 — client_reference is never passed from /verify to the resolution service
    #   0.3 — client_reference passed but resolve ignores it (always returns default)
    #   0.5 — Resolution correct but Prefect flow doesn't receive the client-specific config
    #   0.7 — Full chain: /verify → resolve (client-specific) → Prefect → audit trail
    #   1.0 — Complete: client_reference flows through all layers, Prefect uses correct intervals,
    #          audit trail points to correct sequence

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 4: Multi-tenancy isolation — customer A can't see B's configs
  # ─────────────────────────────────────────────────────────────────

  @api @db
  Scenario: Customer isolation — config queries are scoped by customer_id
    Given customer_id=2 has its own active work_history sequence
    When GET /api/v1/check-sequence?customer_id=1 is called
    Then only customer_id=1 sequences are returned (never customer_id=2)

    When GET /api/v1/check-sequence/resolve?customer_id=1&check_type=work_history is called
    Then the resolved sequence belongs to customer_id=1

    # LAYER: Database — Verify all queries include customer_id scoping
    When the source code of check_sequence_service.py is examined
    Then ALL SQL queries include "customer_id = $N" as a WHERE clause
    And no query uses f-string interpolation for customer_id (parameterized only)

    # Evidence Required:
    #   - grep check_sequence_service.py for all SQL queries
    #   - Verify each query has customer_id parameter
    #   - grep for f"... customer_id =" (should find NONE — only $N params)
    #
    # Confidence Scoring:
    #   0.0 — No customer_id filtering on queries
    #   0.3 — Some queries filter, others don't
    #   0.5 — All filter but some use f-string interpolation (SQL injection risk)
    #   0.7 — All parameterized with customer_id scoping
    #   1.0 — Complete: all queries parameterized, customer_id scoped, no f-strings,
    #          tested with multi-customer scenarios
