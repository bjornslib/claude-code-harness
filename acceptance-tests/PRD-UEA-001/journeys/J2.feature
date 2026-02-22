# Journey J2: Work History Check Triggers Prefect Flow with DB-Backed Config
#
# CROSS-LAYER: HTTP (API /verify) → Service (check_sequence_service) → PostgreSQL
#              → Prefect (verification_orchestrator) → Channel Dispatch → Audit Trail
# BUSINESS OUTCOME: When a customer submits a work history verification request,
#   the system resolves the SLA config from the database (not hardcoded defaults)
#   and executes the Prefect verification flow with the customer's configured sequence.
#
# EXECUTION ENVIRONMENT:
#   Backend:  Docker app-server (feature branch) on http://localhost:8000
#   Database: Docker app-postgres on port 5434 (migration 035 applied)
#   Prefect:  Docker prefect-server on port 4200 (PREFECT_DISPATCH_MODE=local_mock)
#   Tests:    curl for API calls, docker exec psql for DB queries
#
# BLIND: This test is invisible to the S3 operator and its workers.

@journey @prd-uea-001 @J2 @api @prefect @db
Feature: J2 — Work history verification uses DB-backed SLA configuration

  Background:
    Given the backend API Docker container is running at http://localhost:8000 (feature branch)
    And PostgreSQL Docker container has migration 035 applied
    And an active work_history sequence exists for customer_id=1 with:
      | step             | max_attempts | retry_intervals |
      | voice-verification | 5          | [2, 4, 24, 48]  |
      | email-outreach     | 3          | [24, 72, 120]   |
      | human-review       | 1          | []               |
    And PREFECT_DISPATCH_MODE=local_mock is set (safe for testing)

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 1: /verify triggers flow with DB-resolved config
  # ─────────────────────────────────────────────────────────────────

  @api @smoke
  Scenario: POST /verify creates case and resolves SLA config from database
    # LAYER 1: API — Submit verification request
    When POST /api/v1/verify is called with:
      | field          | value                |
      | customer_id    | 1                    |
      | check_type     | work_history         |
      | candidate_name | Jane Smith           |
      | employer_name  | Acme Corporation     |
      | contact_phone  | +61412345678         |
      | contact_email  | hr@acme.example.com  |
    Then 201 Created is returned with a case_id

    # LAYER 2: Service — Config resolution hits database
    When the resolve_check_sequence service is invoked for this case
    Then it queries background_check_sequence WHERE check_type_id=(SELECT id FROM check_types WHERE name='work_history') AND customer_id=1 AND status='active'
    And it returns the 3-step sequence (voice → email → human-review)
    And matched_at equals "default" (no client_reference provided)

    # LAYER 3: Prefect — Flow uses resolved config (not hardcoded)
    When the verification_orchestrator_flow executes for this case
    Then it receives the resolved check_steps from the database
    And it does NOT use DEFAULT_SLA_CONFIGS from sla_config.py as primary source
    And the first channel dispatched is "voice-verification" (from DB config)

    # LAYER 4: Database — Audit trail records sequence metadata
    When the background_tasks table is queried for this case
    Then at least one task record exists with:
      | field             | expected                          |
      | sequence_id       | UUID matching the active sequence |
      | sequence_version  | 1 (or current version)            |
      | attempt_timestamp | NOT NULL (TIMESTAMPTZ set)        |

    # Evidence Required:
    #   - API response from POST /verify showing case_id
    #   - SQL: SELECT * FROM background_check_sequence WHERE customer_id=1 AND status='active'
    #   - grep verification_orchestrator.py for "resolve_check_sequence" import and call
    #   - SQL: SELECT sequence_id, sequence_version, attempt_timestamp FROM background_tasks WHERE case_id=X
    #
    # Confidence Scoring:
    #   0.0 — /verify endpoint doesn't exist or doesn't call resolve_check_sequence
    #   0.2 — resolve_check_sequence exists but verification_orchestrator still uses hardcoded config
    #   0.4 — Flow calls resolve_check_sequence but falls through to system fallback every time
    #   0.6 — DB config resolved and used. Audit trail partially populated (sequence_id set but version NULL)
    #   0.8 — Full flow: API → resolve → Prefect dispatch → audit trail. Minor: attempt_timestamp not set
    #   1.0 — Complete E2E: /verify → resolve from DB → Prefect uses resolved steps →
    #          background_tasks has sequence_id + sequence_version + attempt_timestamp

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 2: System fallback when no DB config exists
  # ─────────────────────────────────────────────────────────────────

  @api
  Scenario: New customer with no DB sequence falls back to system defaults
    Given customer_id=999 has NO rows in background_check_sequence
    When POST /api/v1/verify is called for customer_id=999 with check_type=work_history
    Then the case is created successfully (201)

    When resolve_check_sequence is called for customer_id=999
    Then it falls through all 3 tiers (no client match, no customer default, no system=customer_id=1 match)
    And returns the SYSTEM_DEFAULT_SEQUENCE constant
    And matched_at equals "system_fallback"
    And the default sequence matches PRD section 6.3:
      | step               | max_attempts | retry_intervals   |
      | voice-verification | 5            | [2, 4, 24, 48]    |
      | email-outreach     | 3            | [24, 72, 120]     |
      | human-review       | 1            | []                |

    When the Prefect flow executes with the system fallback config
    Then it proceeds normally using the fallback values
    And PREFECT_DISPATCH_MODE=local_mock continues to work

    # Evidence Required:
    #   - SQL: SELECT COUNT(*) FROM background_check_sequence WHERE customer_id=999 → 0
    #   - services/check_sequence_service.py: SYSTEM_DEFAULT_SEQUENCE constant
    #   - grep for "system_fallback" in resolution logic
    #   - API call /api/v1/check-sequence/resolve?customer_id=999&check_type=work_history
    #
    # Confidence Scoring:
    #   0.0 — No fallback: missing DB config causes 500 error
    #   0.3 — Falls back but to wrong defaults (different from PRD 6.3)
    #   0.5 — Correct fallback values but matched_at not set to "system_fallback"
    #   0.7 — Full fallback with correct values and matched_at. local_mock works.
    #   1.0 — Complete: 3-tier exhaustion → system fallback → correct values →
    #          Prefect runs normally → local_mock operational

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 3: sla_config.py wired to check_sequence_service
  # ─────────────────────────────────────────────────────────────────

  @api @db
  Scenario: load_sla_config uses resolve_check_sequence instead of hardcoded defaults
    # This tests the specific integration point: sla_config.py should now
    # delegate to check_sequence_service.resolve_check_sequence()
    When the source code of prefect_flows/flows/tasks/sla_config.py is examined
    Then load_sla_config() calls resolve_check_sequence() or check_sequence_service
    And DEFAULT_SLA_CONFIGS is used ONLY as the system fallback (not primary)
    And fetch_customer_sla_override() either calls the service or is replaced

    When the source code of prefect_flows/bridge/prefect_bridge.py is examined
    Then mock_resolve_sla_config() is replaced or wrapped by resolve_sla_config()
    And the new function calls CheckSequenceService().resolve_check_sequence()
    And it falls back to the mock function on DB connection failure

    # Evidence Required:
    #   - grep sla_config.py for "resolve_check_sequence" or "check_sequence_service"
    #   - grep prefect_bridge.py for "resolve_sla_config" replacing "mock_resolve_sla_config"
    #   - import chain: prefect_bridge → check_sequence_service → database
    #
    # Confidence Scoring:
    #   0.0 — Both files unchanged from hardcoded originals
    #   0.3 — One file updated but not the other
    #   0.5 — Both import the service but still use hardcoded values as primary
    #   0.7 — Both properly delegate to service with hardcoded as fallback
    #   1.0 — Complete integration: service is primary, hardcoded is fallback only,
    #          try/except handles DB unavailability gracefully
