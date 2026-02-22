# PRD-P1.1-INFRA-001 — Guardian Acceptance Tests
# Generated: 2026-02-22 by s3-guardian
# Mode: Blind validation — meta-orchestrators do NOT see this file

# =============================================================================
# F1 — SendGrid Email Client + Mock Mode (weight: 0.20)
# =============================================================================

@feature-F1 @weight-0.20 @code-analysis
Feature: SendGrid Email Client

  Scenario: SendGridEmailClient class exists with correct interface
    Given the utils directory in agencheck-support-agent
    When reading utils/sendgrid_client.py
    Then a class SendGridEmailClient exists
    And it has a method send_verification_email with parameters (to_email, to_name, template_data)
    And the method is decorated as a Prefect task with retries=2
    And it returns an EmailResult dataclass with fields (success, message_id, error)
    And it reads SENDGRID_API_KEY from environment

    # Confidence scoring guide:
    # 1.0 — Class exists with full interface, Prefect task decorator, EmailResult return type, env var consumption
    # 0.5 — Class exists but missing Prefect task decorator, or EmailResult incomplete, or hardcoded API key
    # 0.0 — File missing or class not implemented

    # Evidence to check:
    # - Read utils/sendgrid_client.py
    # - grep for "@task" decorator on send_verification_email
    # - grep for "EmailResult" dataclass definition
    # - grep for "os.getenv.*SENDGRID_API_KEY"
    # - grep for "sendgrid" in requirements.txt

    # Red flags:
    # - API key hardcoded instead of from env var
    # - No retry/error handling
    # - Missing sendgrid dependency in requirements.txt
    # - Class defined but method body is pass/TODO

  Scenario: Mock mode skips SendGrid API calls
    Given SendGridEmailClient is instantiated
    When PREFECT_DISPATCH_MODE is set to "local_mock"
    Then send_verification_email returns EmailResult(success=True, message_id="mock-...", error=None)
    And no HTTP calls are made to SendGrid API

    # Confidence scoring guide:
    # 1.0 — Mock mode check in code, returns mock EmailResult, verified by test
    # 0.5 — Mock mode check exists but untested, or returns wrong mock shape
    # 0.0 — No mock mode support

    # Evidence to check:
    # - grep for "local_mock" or "PREFECT_DISPATCH_MODE" in sendgrid_client.py
    # - Check test files for mock mode test cases
    # - Verify mock return shape matches EmailResult(success=True, message_id=..., error=None)

    # Red flags:
    # - Mock mode makes actual HTTP calls
    # - Mock mode returns different shape than live mode


# =============================================================================
# F2 — JWT Token System (weight: 0.25)
# =============================================================================

@feature-F2 @weight-0.25 @api-required
Feature: JWT Token System

  Scenario: TokenGenerator produces valid RS256 JWT with correct claims
    Given utils/token_generator.py exists
    When TokenGenerator.generate(case_id, customer_id) is called
    Then it returns a GeneratedToken with (raw_token, token_hash, expires_at)
    And the raw_token decodes as RS256 JWT with claims sub=case_id and exp=7_days_from_now
    And the token_hash is SHA-256 hex digest of the raw_token string
    And JWT_PRIVATE_KEY is read from environment (not hardcoded)

    # Confidence scoring guide:
    # 1.0 — Generator exists, RS256 signing, SHA-256 hash, correct claims, env var for key
    # 0.5 — Generator exists but uses HS256 instead of RS256, or wrong claim names
    # 0.0 — File missing or generator not implemented

    # Evidence to check:
    # - Read utils/token_generator.py — verify ALGORITHM = "RS256"
    # - Check payload contains "sub" and "exp" claims
    # - Verify SHA-256 hash: hashlib.sha256(raw_token.encode()).hexdigest()
    # - grep for "os.getenv.*JWT_PRIVATE_KEY"
    # - Check PyJWT in requirements.txt

    # Red flags:
    # - HS256 algorithm (symmetric — less secure for this use case)
    # - Raw token stored in DB instead of hash
    # - Private key read from file path instead of env var
    # - No expiry claim in JWT

  Scenario: TokenValidator validates tokens and enforces access limits
    Given utils/token_validator.py exists
    When TokenValidator.validate(raw_token) is called
    Then it verifies JWT signature using JWT_PUBLIC_KEY
    And it looks up token_hash in verification_tokens table
    And it checks status is 'active' (not 'expired', 'revoked')
    And it checks access_count < max_uses
    And it increments access_count and updates last_accessed_at on success

    # Confidence scoring guide:
    # 1.0 — All 5 checks implemented, access_count incremented, returns ValidationResult
    # 0.5 — Signature + DB lookup work but access_count not enforced
    # 0.0 — File missing or validator not implemented

    # Evidence to check:
    # - Read utils/token_validator.py
    # - Verify jwt.decode() uses RS256 algorithm
    # - Verify DB query uses token_hash (not raw token)
    # - Verify UPDATE query increments access_count
    # - Check error returns for each failure mode

    # Red flags:
    # - Raw token stored/queried (security issue)
    # - No access_count enforcement (unlimited token reuse)
    # - Missing DB update on successful validation

  Scenario: Token validation returns correct errors for each failure mode
    Given the token validator is wired up
    When testing each failure path
    Then expired JWT returns error="expired"
    And revoked token record returns error="revoked"
    And access_count >= max_uses returns error="exhausted"
    And unknown token hash returns error="not_found"
    And invalid signature returns error="invalid_signature"

    # Confidence scoring guide:
    # 1.0 — All 5 error paths implemented and return correct error strings
    # 0.5 — 3-4 error paths work, 1-2 missing or return wrong string
    # 0.0 — Generic error handling only (no differentiation)

    # Evidence to check:
    # - Read validator code for each error path
    # - Check tests for each error scenario
    # - Verify error string values match PRD spec exactly

    # Red flags:
    # - Generic "invalid" error for all failure modes
    # - Missing "exhausted" check (access_count ignored)
    # - Bare except catching all JWT errors as same type

  Scenario: GET /api/v1/verification/{token}/validate endpoint works
    Given the API router is registered
    When calling GET /api/v1/verification/{valid_token}/validate
    Then response is 200 with {"valid": true, "case_id": ..., "customer_id": ...}
    And calling with expired token returns 401 with {"valid": false, "error": "expired"}

    # Confidence scoring guide:
    # 1.0 — Endpoint registered, returns correct JSON for both valid and invalid tokens
    # 0.5 — Endpoint exists but wrong response format or missing error differentiation
    # 0.0 — Endpoint not implemented

    # Evidence to check:
    # - grep for "/api/v1/verification" in api/routers/ directory
    # - Check router is included in main app
    # - Read the endpoint handler code
    # - Check for Pydantic response model

    # Red flags:
    # - Endpoint requires Clerk authentication (should be public for employer access)
    # - Returns 200 for all cases (even invalid tokens)
    # - Missing from router registration


# =============================================================================
# F3 — Database Migrations (weight: 0.15)
# =============================================================================

@feature-F3 @weight-0.15 @api-required
Feature: Database Migrations 043 and 044

  Scenario: Migration 043 creates verification_tokens table
    Given the local Docker PostgreSQL is running
    When migration 043 is applied
    Then table verification_tokens exists
    And columns include: id (UUID PK), token_hash (VARCHAR UNIQUE), case_id (FK to cases), customer_id (FK to customers), status (CHECK constraint), access_count, max_uses, expires_at
    And partial indexes exist on status='active' and expires_at WHERE status='active'

    # Confidence scoring guide:
    # 1.0 — Table exists with all columns, FKs, CHECK constraint, partial indexes
    # 0.5 — Table exists but missing CHECK constraint or partial indexes
    # 0.0 — Migration file missing or table not created

    # Evidence to check:
    # - ls database/migrations/043_verification_tokens.sql
    # - psql -c "\d verification_tokens" — verify columns and FKs
    # - psql -c "\di verification_tokens" — verify indexes
    # - Check CHECK constraint on status column

    # Red flags:
    # - token_hash not UNIQUE (allows duplicate tokens)
    # - case_id or customer_id missing FK constraint
    # - No CHECK on status (allows arbitrary strings)
    # - customer_id type mismatch with customers.id

  Scenario: Migration 044 creates email_events table
    Given migration 043 has been applied
    When migration 044 is applied
    Then table email_events exists
    And columns include: id (SERIAL PK), message_id (VARCHAR NOT NULL), case_id (FK to cases), event_type (VARCHAR), event_timestamp (TIMESTAMPTZ), event_data (JSONB)
    And indexes exist on case_id, message_id, and event_type

    # Confidence scoring guide:
    # 1.0 — Table exists with all columns, FK, all 3 indexes
    # 0.5 — Table exists but missing 1-2 indexes
    # 0.0 — Migration file missing or table not created

    # Evidence to check:
    # - ls database/migrations/044_email_events.sql
    # - psql -c "\d email_events" — verify columns
    # - psql -c "\di email_events" — verify all 3 indexes

    # Red flags:
    # - message_id allows NULL (can't correlate webhook events)
    # - case_id missing FK (data integrity risk)
    # - No index on message_id (slow webhook lookups)


# =============================================================================
# F4 — SendGrid Webhook Handler (weight: 0.15)
# =============================================================================

@feature-F4 @weight-0.15 @api-required
Feature: SendGrid Webhook Handler

  Scenario: Webhook processes delivery events correctly
    Given the webhook handler is registered at POST /webhooks/sendgrid/events
    When a valid SendGrid event payload is received
    Then events are stored in the email_events table
    And events are published to Redis Streams "verification-events" key
    And supported event types include: delivered, open, click, bounce, dropped, deferred

    # Confidence scoring guide:
    # 1.0 — Handler stores events in DB, publishes to Redis, handles all 6 event types
    # 0.5 — Events stored in DB but no Redis publish, or only 2-3 event types handled
    # 0.0 — Handler not implemented or returns placeholder

    # Evidence to check:
    # - Read api/routers/sendgrid_webhooks.py
    # - grep for "email_events" INSERT query
    # - grep for "redis" or "xadd" for stream publish
    # - Check all 6 event types are handled (not just "delivered")
    # - Verify router is included in api/webhooks/__init__.py

    # Red flags:
    # - Only handles "delivered" event, ignores bounce/dropped
    # - No Redis publish (downstream flows can't react to events)
    # - Handler exists but not registered in __init__.py
    # - Uses raw body parsing instead of Pydantic model

  Scenario: Webhook rejects requests with invalid signatures
    Given the webhook handler expects signed requests
    When a request arrives with invalid X-Twilio-Email-Event-Webhook-Signature
    Then the handler returns HTTP 403
    And no events are stored in the database

    # Confidence scoring guide:
    # 1.0 — Signature verification implemented using EventWebhook helper, returns 403 on failure
    # 0.5 — Signature check exists but always passes, or returns wrong status code
    # 0.0 — No signature verification (accepts any request)

    # Evidence to check:
    # - grep for "EventWebhook" or "verify_signature" in sendgrid_webhooks.py
    # - grep for "SENDGRID_WEBHOOK_VERIFICATION_KEY" env var
    # - Check HTTPException(status_code=403) is raised on verification failure

    # Red flags:
    # - Signature verification commented out or behind feature flag
    # - SENDGRID_WEBHOOK_VERIFICATION_KEY hardcoded
    # - Returns 200 even on invalid signature (silent acceptance)


# =============================================================================
# F5 — Email Outreach Flow + Channel Dispatch Wiring (weight: 0.15)
# =============================================================================

@feature-F5 @weight-0.15 @code-analysis
Feature: Email Outreach Flow and Channel Dispatch Wiring

  Scenario: email_outreach_flow orchestrates token generation and email sending
    Given prefect_flows/flows/email_outreach.py exists
    When reading the flow definition
    Then it is decorated with @flow(name="email_outreach_flow")
    And it calls TokenGenerator.generate() for JWT token creation
    And it calls SendGridEmailClient.send_verification_email()
    And it stores the token hash in verification_tokens table
    And it stores the message_id for webhook correlation

    # Confidence scoring guide:
    # 1.0 — Flow exists, calls generator + client, stores token + message_id, handles errors
    # 0.5 — Flow exists but missing token storage or message_id correlation
    # 0.0 — File missing or flow is a placeholder

    # Evidence to check:
    # - Read prefect_flows/flows/email_outreach.py
    # - grep for "TokenGenerator" and "SendGridEmailClient" imports
    # - Verify _store_token and _store_message_id helper functions exist
    # - Check error handling for token generation failure and send failure

    # Red flags:
    # - No error handling (bare try/except or no try at all)
    # - Token generated but not stored in DB
    # - message_id not recorded (can't correlate webhook events)
    # - Still a placeholder (returns not_implemented)

  Scenario: channel_dispatch.py no longer returns not_implemented for email
    Given the channel dispatch task exists
    When reading _dispatch_email_verification
    Then it calls email_outreach_flow (not a placeholder)
    And the old return {"status": "not_implemented"} is removed

    # Confidence scoring guide:
    # 1.0 — Dispatch calls email_outreach_flow, placeholder removed, proper parameters passed
    # 0.5 — Dispatch updated but still has fallback to not_implemented
    # 0.0 — Placeholder unchanged

    # Evidence to check:
    # - Read prefect_flows/flows/tasks/channel_dispatch.py
    # - grep for "not_implemented" — should return nothing
    # - grep for "email_outreach_flow" import and call

    # Red flags:
    # - "not_implemented" string still in the function
    # - email_outreach_flow imported but not called
    # - Parameters don't match flow signature

  Scenario: Email outreach returns same shape as voice subflow
    Given the email outreach flow returns a result
    When comparing against voice subflow return shape
    Then the return dict has keys: "success" (bool), "result_status" (str), "outcome" (dict|None)

    # Confidence scoring guide:
    # 1.0 — Return shape exactly matches {"success": bool, "result_status": str, "outcome": dict|None}
    # 0.5 — Returns a dict but with different key names or missing "outcome"
    # 0.0 — Returns completely different structure

    # Evidence to check:
    # - Read all return statements in email_outreach_flow
    # - Compare key names with voice subflow (channel_dispatch.py _dispatch_voice_verification)
    # - Verify "success" is bool, "result_status" is descriptive string, "outcome" is dict or None

    # Red flags:
    # - Extra keys not present in voice subflow return shape
    # - "status" instead of "result_status"
    # - Missing "outcome" key in error cases


# =============================================================================
# F6 — Railway Prefect Deployment (weight: 0.10)
# =============================================================================

@feature-F6 @weight-0.10 @hybrid
Feature: Railway Prefect Deployment

  Scenario: Prefect server health check passes on Railway
    Given the Prefect server is deployed to Railway
    When calling GET /api/health on the Railway internal URL
    Then the response includes {"status": "healthy"}

    # Confidence scoring guide:
    # 1.0 — Prefect server deployed, health check responds, internal networking works
    # 0.5 — Deployment configuration exists but not yet deployed or health check untested
    # 0.0 — No Railway deployment configuration

    # Evidence to check:
    # - Check for railway/ directory with env example files
    # - Check for Dockerfile.prefect-worker updates (COPY instead of volume mounts)
    # - Check railway/README.md deployment procedure
    # - If Railway accessible: curl prefect-server health endpoint

    # Red flags:
    # - Dockerfile still uses volume mounts (won't work on Railway)
    # - No env example files for Railway services
    # - No deployment documentation

  Scenario: Dockerfile.prefect-worker uses COPY instead of volume mounts
    Given the Dockerfile.prefect-worker exists
    When reading the Dockerfile
    Then it uses COPY directives for flow code (prefect_flows/, utils/, models/, services/)
    And it does NOT use VOLUME or rely on bind mounts
    And it installs dependencies from requirements.txt

    # Confidence scoring guide:
    # 1.0 — Dockerfile has all COPY directives, requirements install, no volume assumptions
    # 0.5 — Some COPY directives but missing key directories (e.g., models/ or services/)
    # 0.0 — Dockerfile unchanged from local Docker Compose version

    # Evidence to check:
    # - Read Dockerfile.prefect-worker
    # - grep for "COPY.*prefect_flows" "COPY.*utils" "COPY.*models" "COPY.*services"
    # - grep for "VOLUME" — should not be present
    # - Check RUN pip install line

    # Red flags:
    # - VOLUME directive present
    # - Missing COPY for utils/ or models/ (runtime ImportError)
    # - No requirements.txt install

  Scenario: Railway environment variables properly configured
    Given Railway env example files exist
    When reading the variable references
    Then PREFECT_API_URL uses Railway internal networking (*.railway.internal)
    And DATABASE_URL references app-postgres via Railway variable syntax
    And REDIS_URL uses redis.railway.internal
    And JWT keys and SendGrid vars are documented

    # Confidence scoring guide:
    # 1.0 — All env vars documented, Railway variable reference syntax used, internal networking
    # 0.5 — Partial documentation, some vars missing or using localhost
    # 0.0 — No Railway-specific env configuration

    # Evidence to check:
    # - Read railway/prefect-server.env.example and railway/prefect-worker.env.example
    # - Check for ${{service-name.VARIABLE}} Railway syntax
    # - Verify internal URLs use .railway.internal suffix
    # - Check .env.example updated with all new vars

    # Red flags:
    # - URLs pointing to localhost (won't work on Railway)
    # - Missing Railway variable reference syntax
    # - JWT keys or SendGrid vars not documented
