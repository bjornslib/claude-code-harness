# Guardian Acceptance Test Scenarios: PRD-UEA-001
# Workflow Config & SLA Engine
#
# BLIND VALIDATION: These tests are stored in the config repo (claude-harness-setup),
# NOT in the implementation repo. The S3 operator and its workers never see this rubric.
#
# PRD Source: documentation/prds/phase-1.1/phase1-ue-a-workflow-config-sla.md (1727 lines)

# ============================================================================
# FEATURE 1: Epic A1 — Config Backend & Resolution (Weight: 0.30)
# ============================================================================

Feature: Epic A1 — Config Backend & Resolution
  Weight: 0.30
  Description: Database schema, CRUD API, sequence resolution, Clerk RBAC, multi-tenancy

  Scenario: database_schema_migration_035
    Given the agencheck-support-agent database
    When migration 035 is applied
    Then a check_types table exists with columns (id SERIAL PK, name VARCHAR(50) UNIQUE, display_name VARCHAR(100), description TEXT, created_at TIMESTAMPTZ)
    And check_types is seeded with at least: work_history, education, criminal, reference
    And a background_check_sequence table exists with columns (id UUID PK, check_type_id INTEGER FK, customer_id INTEGER FK, client_reference VARCHAR nullable, status VARCHAR, version INTEGER, check_steps JSONB, notes TEXT, created_at, updated_at, created_by)
    And background_tasks table has new columns: sequence_id UUID FK, sequence_version INTEGER, attempt_timestamp TIMESTAMPTZ
    And a partial unique index enforces one active sequence per (check_type_id, customer_id, client_reference) WHERE status='active'
    And seed data creates default work_history sequences for all existing customers using subquery pattern (SELECT id FROM check_types WHERE name = 'work_history')

    # Confidence Scoring Guide:
    # 0.0 — No migration file exists, no new tables
    # 0.2 — Migration file exists but has syntax errors or missing tables
    # 0.4 — check_types table exists but background_check_sequence is missing or wrong. OR uses VARCHAR enum instead of FK to check_types
    # 0.6 — Both tables exist with correct columns, but seed data uses string literals instead of subquery, or partial unique index missing
    # 0.8 — Tables, seed data, and indexes all correct. Minor issues like missing COMMENT statements or background_tasks ALTER not applied
    # 1.0 — Complete migration: both tables, correct FKs, partial unique index, subquery seed pattern, background_tasks ALTER, all COMMENT statements
    #
    # Evidence to Check:
    #   - database/migrations/035_*.sql (migration file)
    #   - grep for "CREATE TABLE.*check_types" and "CREATE TABLE.*background_check_sequence"
    #   - grep for "REFERENCES check_types(id)" (FK pattern, NOT VARCHAR)
    #   - grep for "WHERE status = 'active'" (partial unique index)
    #   - grep for "SELECT id FROM check_types WHERE name" (subquery seed pattern)
    #   - grep for "ALTER TABLE background_tasks" (audit trail columns)
    #
    # Red Flags:
    #   - check_type VARCHAR(50) CHECK (check_type IN (...)) instead of FK to check_types table
    #   - INSERT with string literal IDs instead of subquery
    #   - Missing partial unique index (allows duplicate active sequences)
    #   - Missing background_tasks ALTER (no audit trail)
    #   - Using TEXT instead of JSONB for check_steps

  Scenario: crud_api_endpoints
    Given the FastAPI application is running
    When the check sequence API endpoints are examined
    Then POST /api/v1/check-sequence creates a new sequence with proper validation
    And GET /api/v1/check-sequence lists sequences with pagination (customer_id required, optional check_type/status/client_reference/page/limit)
    And GET /api/v1/check-sequence/{id} returns a single sequence
    And GET /api/v1/check-sequence/resolve returns the effective sequence with resolution_chain and matched_at fields
    And PUT /api/v1/check-sequence/{id} creates new version (archives old, version bump)
    And DELETE /api/v1/check-sequence/{id} archives (soft-delete only, 204 response)
    And all endpoints use Pydantic models: CheckSequenceCreate, CheckSequenceUpdate, CheckSequenceResponse, CheckSequenceResolution

    # Confidence Scoring Guide:
    # 0.0 — No router file exists, no API endpoints
    # 0.2 — Router file exists with imports but empty route handlers
    # 0.4 — Some endpoints defined (e.g., GET only) but missing POST/PUT/DELETE or /resolve
    # 0.6 — All 6 endpoints exist and handle happy path. Missing validation, pagination, or resolution chain
    # 0.8 — All endpoints work with proper Pydantic models, pagination, resolve endpoint returns resolution_chain. Minor gaps in error handling (409 on duplicate, 403 on unauthorized)
    # 1.0 — Complete CRUD + resolve with full error handling (400, 403, 409), Pydantic validation, pagination, resolution chain with matched_at field, proper HTTP status codes
    #
    # Evidence to Check:
    #   - api/routers/check_sequence.py (router file)
    #   - models/check_sequence.py (Pydantic models: CheckTypeEnum, CheckStep, CheckSequenceCreate, etc.)
    #   - services/check_sequence_service.py (business logic)
    #   - main.py for router registration
    #   - tests/test_check_sequence_api.py
    #
    # Red Flags:
    #   - Router defined but not registered in main.py
    #   - POST returns 200 instead of 201
    #   - DELETE does hard delete (DROP) instead of soft-delete (archive)
    #   - PUT does in-place update instead of version+archive pattern
    #   - /resolve endpoint missing or returns raw DB row instead of CheckSequenceResolution model
    #   - No check_type validation against CheckTypeEnum

  Scenario: sequence_resolution_logic
    Given sequences exist for customer_id=1 with:
      - Default sequence (client_reference IS NULL, status='active')
      - Client-specific sequence (client_reference='Fortune 500 Corp', status='active')
    When GET /api/v1/check-sequence/resolve is called with customer_id=1, check_type=work_history, client_ref='Fortune 500 Corp'
    Then the client-specific sequence is returned (NOT the default)
    And resolution_chain includes ["client_specific:Fortune 500 Corp", "default"]
    And matched_at equals "client_specific"
    When GET /api/v1/check-sequence/resolve is called with customer_id=1, check_type=work_history (no client_ref)
    Then the default sequence is returned
    And matched_at equals "default"
    When GET /api/v1/check-sequence/resolve is called for a customer with no sequences
    Then the system fallback is returned (hardcoded defaults matching PRD section 6.3)
    And matched_at equals "system_fallback"

    # Confidence Scoring Guide:
    # 0.0 — No resolution logic exists
    # 0.2 — Function signature exists but always returns hardcoded default
    # 0.4 — Queries DB but only checks default (no client-specific lookup)
    # 0.6 — Client > default chain works but no system fallback
    # 0.8 — Full 3-tier resolution works. Resolution chain and matched_at populated. Minor issue: no caching
    # 1.0 — Full resolution with caching (5-min TTL), resolution chain, matched_at, system fallback matches PRD defaults exactly
    #
    # Evidence to Check:
    #   - services/check_sequence_service.py: resolve_check_sequence() function
    #   - The 3-tier lookup: client_reference match → NULL client_reference → SYSTEM_DEFAULT_SEQUENCE
    #   - SYSTEM_DEFAULT_SEQUENCE constant matches PRD section 6.3 (voice-verification 5 retries [2,4,24,48], email-outreach 3 retries [24,72,120], human-review 1 attempt)
    #   - tests/test_check_sequence_resolution.py
    #
    # Red Flags:
    #   - Only queries by customer_id (ignores client_reference)
    #   - System fallback has different values than PRD section 6.3
    #   - resolution_chain is hardcoded instead of built dynamically
    #   - No handling for check_type parameter (only works for work_history)

  Scenario: rbac_enforcement
    Given Clerk authentication is integrated
    When a staff-level user tries POST /api/v1/check-sequence
    Then 403 Forbidden is returned
    When a manager-level user tries POST /api/v1/check-sequence
    Then 201 Created is returned (sequence created successfully)
    When a staff-level user tries GET /api/v1/check-sequence
    Then 200 OK is returned (read-only access allowed)

    # Confidence Scoring Guide:
    # 0.0 — No authentication on any endpoint
    # 0.2 — Authentication required but no role checking (any authenticated user can CRUD)
    # 0.4 — Role checking exists but wrong roles (e.g., 'admin' only, not 'manager')
    # 0.6 — Correct role checking on write endpoints. Read endpoints properly allow staff access
    # 0.8 — Full RBAC: staff=read, manager=create/edit, admin=delete. Uses Clerk's out-of-the-box RBAC
    # 1.0 — Full RBAC with proper 403 responses, Clerk integration tested, edge cases handled (expired tokens, revoked roles)
    #
    # Evidence to Check:
    #   - Depends decorator on router functions: require_role(['manager', 'admin', 'superuser'])
    #   - utils/clerk_auth.py for get_current_user, require_role
    #   - Tests with different role levels
    #
    # Red Flags:
    #   - Custom authorization layer instead of Clerk's out-of-the-box RBAC
    #   - Depends() missing on write endpoints
    #   - Hardcoded user IDs instead of Clerk role checking


# ============================================================================
# FEATURE 2: Epic A4 — Frontend Workflow Matrix UI (Weight: 0.25)
# ============================================================================

Feature: Epic A4 — Frontend Workflow Matrix UI
  Weight: 0.25
  Description: Complete existing /check-sla-configuration page, wire to backend, Clerk RBAC

  Scenario: frontend_page_renders_data
    Given the frontend at /check-sla-configuration exists (25+ existing components)
    And the backend check-sequence API is running
    When an admin user navigates to /check-sla-configuration
    Then the page renders without errors
    And existing check sequences are loaded from the API (not mock data)
    And sequences are displayed per check type with the V32 grid layout
    And the scope selector allows switching between default and client-specific views
    And the SLAHeader, SLACheckTypeGridV32, and SLAFooter components render correctly

    # Confidence Scoring Guide:
    # 0.0 — Page crashes or shows blank content. No API integration
    # 0.2 — Page renders static/mock data. No real API calls. Store uses hardcoded state
    # 0.4 — Page makes API calls but fails (CORS, wrong URL, missing auth). Some components render
    # 0.6 — Page loads data from API. Grid shows sequences. Some components broken or unstyled
    # 0.8 — Page fully renders with API data. Grid, header, footer all work. Scope selector switches views. Minor UX issues
    # 1.0 — Complete integration: API data loads, grid renders per check type, scope selector works, mobile fallback active, draft restoration works, smooth UX
    #
    # Evidence to Check:
    #   - agencheck-support-frontend/app/check-sla-configuration/page.tsx
    #   - stores/workflowMatrixStore.ts — does it call real API or use mock data?
    #   - lib/api/check-sequence.ts — API client for check sequence endpoints
    #   - _components/SLACheckTypeGridV32.tsx — does it render real data?
    #   - Browser: navigate to http://localhost:5002/check-sla-configuration
    #
    # Red Flags:
    #   - workflowMatrixStore.ts still uses hardcoded mock data
    #   - API client file doesn't exist (lib/api/check-sequence.ts)
    #   - fetch() calls use wrong base URL or missing auth headers
    #   - Grid component renders empty state even when API returns data

  Scenario: frontend_crud_wired_to_backend
    Given the admin is on /check-sla-configuration
    When the admin clicks to edit a check sequence
    Then an editor modal/form opens showing current check_steps
    And the admin can modify step order, add/remove steps, change retry intervals
    When the admin saves the changes
    Then a PUT /api/v1/check-sequence/{id} request is sent to the backend
    And the UI updates to show the new version
    And unsaved changes dialog works (prevents accidental navigation)

    # Confidence Scoring Guide:
    # 0.0 — No edit functionality exists. Components are display-only
    # 0.2 — Edit modal exists but doesn't load current data from API
    # 0.4 — Edit modal loads data but save button doesn't call API or calls wrong endpoint
    # 0.6 — Full edit flow works: load → modify → save → API call. But no optimistic updates, no error handling, no unsaved changes protection
    # 0.8 — Complete edit flow with error handling, loading states, unsaved changes dialog. Minor: drag-and-drop not implemented (OK per PRD — "Coming Soon")
    # 1.0 — Complete edit flow with all quality: error handling, loading states, optimistic updates, unsaved changes dialog, version display, toast notifications on save
    #
    # Evidence to Check:
    #   - _components/EditStepModal.tsx — does it call PUT API?
    #   - _components/AddStepModal.tsx, AddStepButton.tsx — do they call POST?
    #   - _components/UnsavedChangesDialog.tsx — is it wired to store dirty state?
    #   - _components/SequenceCard.tsx — does it show version number?
    #   - Network tab: verify PUT/POST requests go to correct API endpoints
    #
    # Red Flags:
    #   - Edit modal saves to local state only (no API call)
    #   - PUT request sends wrong payload format (doesn't match CheckSequenceUpdate model)
    #   - Version number not displayed or not incremented after save
    #   - UnsavedChangesDialog exists but never triggered (missing beforeunload handler)

  Scenario: frontend_rbac_enforcement
    Given a staff-level user (not manager) is logged in via Clerk
    When they navigate to /check-sla-configuration
    Then they can view check sequences (read-only)
    And edit/create/delete buttons are hidden or disabled
    When a manager-level user is logged in
    Then edit/create/delete functionality is available

    # Confidence Scoring Guide:
    # 0.0 — No role checking on frontend. All users see all buttons
    # 0.2 — Role is checked but incorrectly (wrong role names, inverted logic)
    # 0.4 — Role checking hides buttons but API calls still work for unauthorized users (frontend-only check)
    # 0.6 — Frontend hides buttons based on Clerk role AND backend returns 403 for unauthorized API calls
    # 0.8 — Full RBAC: frontend role-based UI hiding + backend enforcement. Staff sees read-only view. Manager sees full CRUD
    # 1.0 — Complete RBAC with graceful error messages, role-based navigation, proper Clerk integration, tested with multiple role levels
    #
    # Evidence to Check:
    #   - useUser() or useAuth() from Clerk in page.tsx or store
    #   - Conditional rendering based on user.role in component tree
    #   - SLAHeader or SLAFooter showing/hiding action buttons based on role
    #   - API client sending Clerk token in Authorization header
    #
    # Red Flags:
    #   - No Clerk imports in any frontend component
    #   - Role check only in one place (e.g., page.tsx) but not propagated to child components
    #   - API calls made without auth headers (Clerk token not attached)


# ============================================================================
# FEATURE 3: Epic A2 — Prefect Flow Integration (Weight: 0.20)
# ============================================================================

Feature: Epic A2 — Prefect Flow Integration
  Weight: 0.20
  Description: Prefect reads from DB config, configurable retry intervals, audit trail

  Scenario: prefect_reads_db_config
    Given a Prefect parent flow exists for check_work_history
    When a new verification case is created
    Then resolve_check_sequence() is called with customer_id, check_type, and optional client_ref
    And the resolved sequence is used to determine subflow order (not hardcoded DEFAULT_SLA_CONFIGS)
    And the old hardcoded sla_config.py logic is replaced (fetch_customer_sla_override returns real data)

    # Confidence Scoring Guide:
    # 0.0 — Prefect flows still use hardcoded DEFAULT_SLA_CONFIGS from sla_config.py
    # 0.2 — resolve_check_sequence() function exists but is never called from Prefect flows
    # 0.4 — Called from Prefect but falls through to system fallback every time (DB query broken)
    # 0.6 — Works for default sequences. Client-specific resolution not tested in Prefect context
    # 0.8 — Full integration: Prefect flows call resolve_check_sequence(), DB-backed config used, old hardcoded logic is fallback-only
    # 1.0 — Complete: Prefect uses DB config, old sla_config.py updated to use resolve_check_sequence(), mock mode (PREFECT_DISPATCH_MODE=local_mock) still works
    #
    # Evidence to Check:
    #   - prefect_flows/flows/verification_orchestrator.py — does it call resolve_check_sequence()?
    #   - prefect_flows/flows/tasks/sla_config.py — is load_sla_config() updated?
    #   - Does fetch_customer_sla_override() now query background_check_sequence table?
    #   - Is PREFECT_DISPATCH_MODE=local_mock still supported?
    #
    # Red Flags:
    #   - DEFAULT_SLA_CONFIGS still used as primary (not fallback)
    #   - resolve_check_sequence() defined but not imported into Prefect flows
    #   - sla_config.py unchanged from original hardcoded version
    #   - No import of check_sequence_service in any Prefect flow file

  Scenario: retry_intervals_from_sequence
    Given a check sequence has check_steps with specific retry_intervals per step
    When a subflow executes and fails
    Then the retry is scheduled using retry_intervals from the JSONB config (not hardcoded VOICEMAIL_BACKOFF_HOURS)
    And the correct interval is selected based on attempt number (attempt-1 index into array)
    And if attempt exceeds array length, the last interval is used

    # Confidence Scoring Guide:
    # 0.0 — Still using hardcoded VOICEMAIL_BACKOFF_HOURS = [2, 4, 24, 48]
    # 0.3 — Code references retry_intervals from sequence but never actually uses them in scheduling
    # 0.5 — Retry intervals read from sequence for first retry but hardcoded fallback for subsequent
    # 0.7 — Full dynamic retry intervals with correct index calculation. Edge case (exceed array length) handled
    # 1.0 — Dynamic retry intervals, correct indexing, array-overflow handling, background_tasks records actual interval used
    #
    # Evidence to Check:
    #   - grep for "retry_intervals" in Prefect flow files
    #   - grep for "VOICEMAIL_BACKOFF_HOURS" — should be removed or only used as system fallback
    #   - execute_subflow_with_retries() or equivalent function
    #   - utils/background_task_helpers.py — create_retry_task() accepts dynamic intervals
    #
    # Red Flags:
    #   - VOICEMAIL_BACKOFF_HOURS still used as primary retry source
    #   - retry_intervals parameter accepted but ignored (hardcoded values used)
    #   - No tests for dynamic retry interval scheduling

  Scenario: audit_trail_in_background_tasks
    Given a subflow execution creates a background_task record
    When the task is created
    Then it includes sequence_id (UUID FK to background_check_sequence)
    And it includes sequence_version (integer snapshot)
    And it includes attempt_timestamp (TIMESTAMPTZ)
    And these fields are queryable for audit trail purposes

    # Confidence Scoring Guide:
    # 0.0 — background_tasks table not modified, no new columns
    # 0.2 — ALTER TABLE adds columns but Prefect code never populates them
    # 0.4 — Columns exist and some code paths populate them, but not all
    # 0.6 — All subflow executions populate sequence_id, sequence_version, attempt_timestamp
    # 0.8 — Full audit trail with index on (sequence_id, sequence_version) for queries
    # 1.0 — Complete audit trail, indexed, queried in at least one reporting endpoint, tested
    #
    # Evidence to Check:
    #   - background_task_helpers.py: create_background_task() signature includes sequence_id, sequence_version
    #   - All call sites pass these parameters
    #   - Migration 035 includes idx_background_tasks_sequence index
    #
    # Red Flags:
    #   - create_background_task() signature unchanged from original
    #   - sequence_id/sequence_version parameters accepted but set to NULL
    #   - No index on audit trail columns


# ============================================================================
# FEATURE 4: Epic A3 — Reminder Sequences (GAP 13) (Weight: 0.15)
# ============================================================================

Feature: Epic A3 — Reminder Sequences (GAP 13)
  Weight: 0.15
  Description: Text file templates, template service, automated follow-up tasks

  Scenario: email_templates_exist
    Given the codebase has a templates directory
    When examining prefect_flows/templates/work_history/
    Then email_first_contact.txt exists with Subject line and body containing variables: {employer_name}, {candidate_name}, {verifier_name}, {case_id}, {callback_number}
    And email_reminder_1.txt exists with appropriate follow-up content

    # Confidence Scoring Guide:
    # 0.0 — No templates directory exists
    # 0.2 — Directory exists but files are empty or placeholder
    # 0.4 — One template file exists with some content but missing variables
    # 0.6 — Both template files exist with correct variables. Content is reasonable but may not match PRD example exactly
    # 0.8 — Templates match PRD specification. All 5 required variables present. Professional tone
    # 1.0 — Templates complete, well-formatted, all variables, Subject line included, matches PRD example closely
    #
    # Evidence to Check:
    #   - prefect_flows/templates/work_history/email_first_contact.txt
    #   - prefect_flows/templates/work_history/email_reminder_1.txt
    #   - grep for "{employer_name}", "{candidate_name}", "{verifier_name}", "{case_id}", "{callback_number}"
    #
    # Red Flags:
    #   - Templates stored in database instead of filesystem (wrong for MVP)
    #   - Template variables use different syntax (e.g., {{var}} instead of {var})
    #   - Missing Subject line in email templates

  Scenario: template_rendering_service
    Given a template service exists
    When load_template("work_history", "email_first_contact") is called
    Then the template text is loaded from the filesystem
    When render_template(template, variables) is called with valid variables
    Then all {variable_name} placeholders are replaced with actual values

    # Confidence Scoring Guide:
    # 0.0 — No template service exists
    # 0.3 — Service file exists but functions are stubs (pass/TODO)
    # 0.5 — load_template works but render_template has no variable replacement
    # 0.7 — Both functions work correctly. Basic error handling for missing files
    # 1.0 — Complete service with error handling, missing variable warnings, path validation, unit tests
    #
    # Evidence to Check:
    #   - services/template_service.py
    #   - load_template() and render_template() functions
    #   - Tests for template loading and rendering
    #
    # Red Flags:
    #   - Uses Jinja2 or Mako instead of simple string replacement (over-engineered for MVP)
    #   - No error handling for missing template files
    #   - Template path is hardcoded (not constructed from check_type + template_name)

  Scenario: automated_followup_tasks
    Given a check sequence has retry_intervals configured
    When a verification attempt fails and retry is needed
    Then an automated follow-up task is created in background_tasks
    And the task is scheduled for the correct retry interval from the sequence
    And reminders stop when case status changes to completed/cancelled

    # Confidence Scoring Guide:
    # 0.0 — No automated follow-up logic
    # 0.3 — Follow-up task creation code exists but uses hardcoded intervals
    # 0.5 — Uses dynamic intervals from sequence but doesn't check case status
    # 0.7 — Dynamic intervals, case status check, proper background_task creation
    # 1.0 — Complete: dynamic intervals, case status check, multiple channels, proper cleanup on completion/cancellation
    #
    # Evidence to Check:
    #   - Prefect flow code that creates retry/follow-up tasks
    #   - Case status check before scheduling retry
    #   - background_task_helpers.py create_retry_task() usage
    #
    # Red Flags:
    #   - Follow-up tasks created but never executed (no scheduler pickup)
    #   - Case status not checked (retries continue after case completion)
    #   - Uses asyncio.sleep instead of background_tasks for scheduling


# ============================================================================
# FEATURE 5: Cross-Cutting — Versioning, Security & Caching (Weight: 0.10)
# ============================================================================

Feature: Cross-Cutting — Versioning, Security & Caching
  Weight: 0.10
  Description: Sequence versioning, multi-tenancy isolation, caching

  Scenario: sequence_versioning
    Given an active check sequence exists with version=1
    When PUT /api/v1/check-sequence/{id} is called with updated check_steps
    Then the original sequence is archived (status='archived')
    And a new sequence is created with version=2 and status='active'
    And active cases continue using their original sequence (via background_tasks.sequence_id FK)
    And the new version becomes the default for new cases

    # Confidence Scoring Guide:
    # 0.0 — PUT does in-place update (no versioning)
    # 0.3 — Versioning attempted but old version not archived or new version not created
    # 0.5 — Archive + new version works but version number not incremented correctly
    # 0.7 — Full versioning: archive old, create new with version+1, active cases unaffected
    # 1.0 — Complete versioning with proper FK references, tested edge cases (concurrent updates, version gaps)
    #
    # Evidence to Check:
    #   - PUT handler in api/routers/check_sequence.py
    #   - Transaction handling (archive + create must be atomic)
    #   - background_tasks.sequence_id FK remains valid after archive
    #
    # Red Flags:
    #   - PUT modifies the existing row in-place (no new version created)
    #   - Version number always 1 (never incremented)
    #   - No transaction (archive could succeed but create could fail, leaving no active sequence)

  Scenario: security_and_multitenancy
    Given multiple customers exist in the system
    When customer A requests configs
    Then only customer A's configs are returned (never customer B's)
    And all database queries include customer_id scoping
    And all queries use parameterized SQL (no f-string interpolation)

    # Confidence Scoring Guide:
    # 0.0 — No customer_id filtering on queries
    # 0.3 — Some queries filter by customer_id but not all
    # 0.5 — All queries filter by customer_id but some use f-string interpolation (SQL injection risk)
    # 0.7 — All queries parameterized and customer_id scoped. No cross-tenant access possible
    # 1.0 — Complete: parameterized queries, customer_id scoping, tested with multi-tenant scenarios, no hardcoded IDs
    #
    # Evidence to Check:
    #   - All SQL queries in check_sequence_service.py use $1, $2 parameters (not f-strings)
    #   - All API endpoints derive customer_id from authenticated user context
    #   - Tests verify cross-tenant access is blocked
    #
    # Red Flags:
    #   - Any f"SELECT ... WHERE customer_id = {customer_id}" pattern
    #   - API endpoints accept customer_id as query param without validation against auth context
    #   - No test for cross-tenant isolation
