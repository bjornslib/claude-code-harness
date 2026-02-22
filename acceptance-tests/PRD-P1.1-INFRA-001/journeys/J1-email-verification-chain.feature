@journey @prd-P1.1-INFRA-001 @J1 @api @db @smoke
Scenario J1: Email dispatch sends verification email and tracks delivery via webhook

  # This journey verifies the full email send → webhook → DB chain.
  # It runs in mock mode (PREFECT_DISPATCH_MODE=local_mock) to avoid needing
  # a live SendGrid API key. The chain validates that:
  # 1. email_outreach_flow generates a token and "sends" (mock) an email
  # 2. A verification token row is stored in the DB
  # 3. The webhook handler accepts and stores an event
  # 4. The token validation endpoint works

  # ---- Step 1: Trigger email dispatch via Prefect flow (mock mode) ----
  # TOOL: curl or httpx
  Given PREFECT_DISPATCH_MODE is set to "local_mock"
  When a case with case_id=1 and customer_id exists in the database
  And email_outreach_flow is invoked for case_id=1 with to_email="test@example.com"
  Then the flow returns {"success": true, "result_status": "email_sent", "outcome": {...}}

  # ---- Step 2: Verify token stored in database ----
  # TOOL: direct psql query
  And the verification_tokens table has a row with case_id=1
  And that row has status='active' and access_count=0
  And the token_hash is a 64-character hex string (SHA-256)

  # ---- Step 3: Simulate webhook delivery event ----
  # TOOL: curl
  When POST /webhooks/sendgrid/events is called with a mock delivered event for the message_id
  Then the endpoint returns 200
  And the email_events table has a row with event_type='delivered' and the correct case_id

  # ---- Step 4: Validate token via endpoint ----
  # TOOL: curl
  When GET /api/v1/verification/{raw_token}/validate is called
  Then the response is 200 with {"valid": true, "case_id": 1}
  And the verification_tokens row now has access_count=1
