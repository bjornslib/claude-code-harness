# PRD-P1.1-FIXES-001 — Guardian Acceptance Tests
# Generated: 2026-02-22 by s3-guardian
# Mode: Blind validation — meta-orchestrators do NOT see this file

# =============================================================================
# F1 — Fix 13 Test Collection Errors (weight: 0.45)
# =============================================================================

@feature-F1 @weight-0.45 @code-analysis
Feature: Test Collection Error Fixes

  Scenario: All 13 test files collect without errors
    Given the agencheck-support-agent test suite exists
    When pytest --collect-only is run on the full test directory
    Then 0 collection errors are reported
    And the exit code is 0 (or warnings-only)

    # Confidence scoring guide:
    # 1.0 — `pytest --collect-only` reports 0 errors, all 13 files addressed
    # 0.5 — Some errors fixed but 1-3 remain; OR files deleted that should have been fixed
    # 0.0 — 4+ collection errors remain; OR original errors unchanged

    # Evidence to check:
    # - `cd agencheck-support-agent && pytest tests/ --collect-only 2>&1 | grep "ERROR"`
    # - Count of "ERROR collecting" lines must be 0
    # - Compare against baseline: 13 errors pre-fix

    # Red flags:
    # - Any remaining ImportError in collection output
    # - Test files deleted that had salvageable tests (files 4-13 should be FIXED, not deleted)
    # - New collection errors introduced by the fixes

  Scenario: Standalone debug scripts deleted (files 1-3)
    Given the test suite directory exists
    When checking for the 3 standalone debug scripts
    Then tests/eddy_test_suite/test_debug_direct.py does NOT exist
    And tests/eddy_test_suite/test_debug_system_comprehensive.py does NOT exist
    And tests/eddy_test_suite/test_phase3_llm_debug.py does NOT exist

    # Confidence scoring guide:
    # 1.0 — All 3 files deleted
    # 0.5 — 1-2 deleted, 1 remains
    # 0.0 — None deleted

    # Evidence to check:
    # - `ls tests/eddy_test_suite/test_debug_*.py tests/eddy_test_suite/test_phase3_*.py 2>&1`
    # - Should return "No such file" for all 3

    # Red flags:
    # - Files renamed instead of deleted
    # - Files moved to another directory instead of deleted
    # - Git shows the deletions but files still exist on disk

  Scenario: Import paths corrected to existing symbols
    Given the 10 files marked for import fixes (files 4-13) still exist
    When checking each file's imports
    Then test_async_history_loading.py does NOT import THREADS_DIR
    And test_generate_response_node_validation.py imports UniversityContact from utils.contact_models
    And test_retrieve_node_citation_integration.py imports CitationMetadata from utils.contact_models
    And test_university_validation_workflow_routing.py imports UniversityContact from utils.contact_models
    And test_validate_university_name_node.py uses get_university_validation_agent() factory
    And test_vector_store_save_load.py imports UniversityDataJSONEncoder (not DateTimeJSONEncoder)
    And test_eddy_validate_migration_validation.py imports safe_convert_citations_for_storage from eddy_validate.workflow

    # Confidence scoring guide:
    # 1.0 — All 10 files have correct imports verified by grep
    # 0.5 — 7-9 files correct, 1-3 still have wrong imports
    # 0.0 — Fewer than 7 files fixed

    # Evidence to check:
    # For each file, grep for the OLD import and the NEW import:
    # - `grep "from.*history_manager.*import.*THREADS_DIR" tests/test_async_history_loading.py` → should return nothing
    # - `grep "from utils.contact_models import UniversityContact" tests/test_generate_response_node_validation.py` → should match
    # - `grep "get_university_validation_agent" tests/test_validate_university_name_node.py` → should match factory call
    # - `grep "UniversityDataJSONEncoder" tests/test_vector_store_save_load.py` → should match

    # Red flags:
    # - Files that import from the correct module but wrong symbol name
    # - Files that use `import *` to avoid explicit symbol references
    # - New imports that don't resolve (swapped one broken import for another)

  Scenario: No regressions in existing passing tests
    Given the test suite collected successfully
    When running the full pytest suite
    Then the number of passing tests is >= the pre-fix baseline
    And no previously-passing test now fails

    # Confidence scoring guide:
    # 1.0 — Full test run shows same or more passes, 0 new failures
    # 0.5 — 1-2 new failures that appear related to import changes
    # 0.0 — 3+ new failures OR test count significantly decreased

    # Evidence to check:
    # - `pytest tests/ --tb=short 2>&1 | tail -5` — summary line
    # - Compare "X passed" count against known baseline
    # - Check for "FAILED" lines that reference files 4-13

    # Red flags:
    # - Test count dropped significantly (tests deleted instead of fixed)
    # - New assertion errors in files that were "fixed"
    # - Import fixes that changed test behavior (wrong symbol imported)


# =============================================================================
# F2 — client_id FK Migration (weight: 0.30)
# =============================================================================

@feature-F2 @weight-0.30 @api-required
Feature: client_id FK Migration (Local DB)

  Scenario: Migration applied — client_id column exists with FK constraint
    Given the local Docker PostgreSQL is running on port 5434
    When querying the background_check_sequence table schema
    Then a column named client_id of type INTEGER exists
    And client_id has a FK constraint referencing clients(id)
    And the column client_reference does NOT exist

    # Confidence scoring guide:
    # 1.0 — `\d background_check_sequence` shows client_id with FK, no client_reference
    # 0.5 — client_id added but client_reference not dropped (both exist)
    # 0.0 — client_reference still exists, client_id not added

    # Evidence to check:
    # - `psql -h localhost -p 5434 -U agencheck -d agencheck -c "\d background_check_sequence"`
    # - Look for: `client_id | integer | | | ` with FK constraint line
    # - Verify: NO line containing `client_reference`

    # Red flags:
    # - client_id exists but without FK constraint (just a bare integer column)
    # - client_reference renamed to client_id without proper FK (just a column rename)
    # - Migration file exists but was not applied to local DB

  Scenario: Indexes recreated with client_id
    Given the migration has been applied
    When querying indexes on background_check_sequence
    Then idx_bcs_resolution_lookup uses client_id (not client_reference)
    And uq_bcs_customer_type_step_active uses COALESCE(client_id, 0) (not client_reference)
    And no index references client_reference

    # Confidence scoring guide:
    # 1.0 — Both indexes exist with client_id, verified via \di or pg_indexes
    # 0.5 — One index recreated, one missing or still references client_reference
    # 0.0 — Indexes not recreated or still reference client_reference

    # Evidence to check:
    # - `psql ... -c "\di+ background_check_sequence"` or
    # - `SELECT indexdef FROM pg_indexes WHERE tablename = 'background_check_sequence'`
    # - Each index definition should contain `client_id`, NOT `client_reference`

    # Red flags:
    # - Old indexes not dropped (duplicate indexes with old + new columns)
    # - Unique constraint missing (allows duplicate step_order per client)
    # - COALESCE uses wrong default (e.g., COALESCE(client_id, -1) instead of 0)


# =============================================================================
# F3 — Application Code Updates (weight: 0.15)
# =============================================================================

@feature-F3 @weight-0.15 @code-analysis
Feature: Application Code Updates for client_id

  Scenario: All Python code references updated from client_reference to client_id
    Given the agencheck-support-agent codebase
    When searching for client_reference in Python files
    Then grep -r "client_reference" --include="*.py" returns 0 matches
    And grep -r "client_id" --include="*.py" returns matches in expected files

    # Confidence scoring guide:
    # 1.0 — Zero occurrences of client_reference in any .py file; client_id present in service/model/bridge files
    # 0.5 — 1-3 residual client_reference occurrences (e.g., in comments or migration scripts)
    # 0.0 — client_reference still used in service logic, Pydantic models, or queries

    # Evidence to check:
    # - `grep -rn "client_reference" --include="*.py" agencheck-support-agent/`
    # - `grep -rn "client_id" services/check_sequence_service.py models/check_sequence.py`
    # - Check prefect_flows/bridge/prefect_bridge.py and prefect_flows/flows/tasks/sla_config.py

    # Red flags:
    # - client_reference in active query strings (SQL injection risk if string-based)
    # - Pydantic model still has `client_reference: Optional[str]`
    # - Method signatures still accept client_reference parameter

  Scenario: Pydantic models use client_id as Optional[int]
    Given the Pydantic model files for check_sequence exist
    When reading the model definitions
    Then client_id is typed as Optional[int] (not Optional[str])
    And no field named client_reference exists in any model

    # Confidence scoring guide:
    # 1.0 — Model file shows `client_id: Optional[int]` with no client_reference field
    # 0.5 — client_id added but typed as str, or client_reference not removed
    # 0.0 — Model unchanged from original

    # Evidence to check:
    # - Read the Pydantic model file (likely models/check_sequence.py or similar)
    # - grep for "client_id.*Optional.*int" and "client_reference"

    # Red flags:
    # - `client_id: Optional[str]` — wrong type, should be int
    # - Both fields present (old not removed)
    # - No validator on client_id to check FK exists


# =============================================================================
# F4 — Planning Document Updates (weight: 0.10)
# =============================================================================

@feature-F4 @weight-0.10 @code-analysis
Feature: Planning Document Updates

  Scenario: All PRD and planning documents updated from client_reference to client_id
    Given the documentation directories exist
    When searching for client_reference in markdown/text files
    Then grep -r "client_reference" documentation/prds/ returns 0 matches
    And grep -r "client_reference" .taskmaster/docs/ returns 0 matches

    # Confidence scoring guide:
    # 1.0 — Zero occurrences of client_reference in any planning doc
    # 0.5 — 1-3 residual occurrences (e.g., in changelog or historical notes)
    # 0.0 — UE-A PRD still contains client_reference in Migration 035 SQL or resolution logic

    # Evidence to check:
    # - `grep -rn "client_reference" documentation/prds/ .taskmaster/docs/`
    # - Specifically check UE-A PRD Section 5.1 (Migration 035) and Section 5.4/6.3 (resolution logic)
    # - Check P1.1 manual testing doc

    # Red flags:
    # - UE-A PRD Migration 035 still shows VARCHAR(255) client_reference
    # - Resolution logic still says "WHERE client_reference = $3"
    # - Seed data examples still use client_reference string values
