@journey @prd-P1.1-INFRA-001 @J2 @api @db @smoke
Scenario J2: Token lifecycle — generation, multiple accesses, exhaustion

  # This journey exercises the full token lifecycle from creation to exhaustion.
  # It verifies that the access_count enforcement works end-to-end.

  # ---- Step 1: Generate a token with max_uses=3 for testing ----
  # TOOL: direct psql query or API
  Given a verification token is generated for case_id=2
  And the verification_tokens row has max_uses=3 and access_count=0

  # ---- Step 2: Validate 3 times (should succeed) ----
  # TOOL: curl
  When GET /api/v1/verification/{raw_token}/validate is called
  Then response is 200 with {"valid": true}
  And access_count is now 1

  When GET /api/v1/verification/{raw_token}/validate is called again
  Then response is 200 with {"valid": true}
  And access_count is now 2

  When GET /api/v1/verification/{raw_token}/validate is called a third time
  Then response is 200 with {"valid": true}
  And access_count is now 3

  # ---- Step 3: Fourth validation should fail (exhausted) ----
  # TOOL: curl
  When GET /api/v1/verification/{raw_token}/validate is called a fourth time
  Then response is 401 with {"valid": false, "error": "exhausted"}
  And the verification_tokens row status is now 'used'
