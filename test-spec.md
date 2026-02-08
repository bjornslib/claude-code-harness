# Work History Verification - Phase 1: Enterprise Readiness

**Version**: 1.0
**Date**: 2026-02-05
**Parent**: [Gap Analysis (Uber-Epic)](work-history-mvp-gap-analysis.md)
**Status**: Ready for Task Master Parsing

---

## Overview

**Objective**: Enable email-first workflow with unified verification page, allowing verifiers to choose how they complete employment verification checks.

**Timeline**: 2-3 weeks
**Dependencies**: None (can start immediately)

---

## Epics

### Epic 1.1: Configuration Backend + API (GAP 1)

**Description**: Implement backend persistence and API endpoints for customer workflow configuration (previously called "SLA configuration").

**User Stories**:
1. As a customer admin, I can configure default contact method (CALL_FIRST or EMAIL_FIRST) for my organization
2. As a customer admin, I can create client-specific overrides (e.g., "ACME-9921" always uses EMAIL_FIRST)
3. As the system, I can look up the correct configuration at case dispatch time

**Technical Requirements**:

1. **Database Schema**
   ```sql
   CREATE TABLE customer_workflow_configs (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     customer_id UUID NOT NULL REFERENCES customers(id),
     client_reference VARCHAR(255) NULL,  -- NULL = default config
     primary_method VARCHAR(20) NOT NULL CHECK (primary_method IN ('CALL_FIRST', 'EMAIL_FIRST')),
     max_retries INTEGER DEFAULT 5,
     retry_interval_hours INTEGER[] DEFAULT '{2, 4, 24, 48}',
     fallback_method VARCHAR(20) NULL,
     human_agent_email VARCHAR(255) NULL,
     human_agent_timezone VARCHAR(50) DEFAULT 'Australia/Melbourne',
     created_at TIMESTAMPTZ DEFAULT NOW(),
     updated_at TIMESTAMPTZ DEFAULT NOW(),
     UNIQUE(customer_id, client_reference)
   );
   ```

2. **API Endpoints**
   - `POST /api/v1/workflow-config` - Create configuration
   - `GET /api/v1/workflow-config/{customer_id}` - Get all configs for customer
   - `GET /api/v1/workflow-config/{customer_id}/resolve?client_ref=X` - Resolve effective config
   - `PUT /api/v1/workflow-config/{id}` - Update configuration
   - `DELETE /api/v1/workflow-config/{id}` - Delete configuration

3. **Integration Points**
   - Modify `dispatch_work_history_call.py` to lookup config before scheduling
   - Config resolution: client-specific → customer default → system default

**Acceptance Criteria**:
- [ ] Database migration creates table with proper constraints
- [ ] API endpoints pass integration tests
- [ ] Dispatch workflow uses resolved configuration
- [ ] Workflow Matrix UI can save/load configurations (frontend integration)

**Files to Create/Modify**:
- `database/migrations/030_workflow_configurations.sql` (new)
- `agencheck-support-agent/models/workflow_config.py` (new)
- `agencheck-support-agent/api/routers/workflow_config.py` (new)
- `agencheck-communication-agent/helpers/dispatch_work_history_call.py` (modify)

---

### Epic 1.2: Email-First Workflow Selection (GAP 2)

**Description**: Implement the email-first workflow path where verifiers receive an email with a link to the verification page instead of receiving a phone call.

**User Stories**:
1. As the system, when primary_method=EMAIL_FIRST, I send an email instead of scheduling a call
2. As a verifier, I receive a professional email with a secure link to complete the verification
3. As a verifier, I can choose to complete via form, receive immediate voice call, or schedule callback

**Technical Requirements**:

1. **Email Dispatch Logic**
   ```python
   async def dispatch_verification_request(case_id: str, config: WorkflowConfig):
       if config.primary_method == "EMAIL_FIRST":
           token = generate_secure_token(case_id)
           await send_verification_email(
               verifier_email=contact.email,
               token=token,
               candidate_name=case.candidate_name,
               company_name=case.employer_name
           )
           # Schedule email retry if no response
           await schedule_email_followup(case_id, config.retry_interval_hours)
       else:
           # Existing call-first logic
           await schedule_verification_call(case_id, config)
   ```

2. **Token Generation**
   - Secure, URL-safe token
   - 7-day expiry
   - One-time use or limited uses
   - Store in `verification_tokens` table

3. **Fallback Logic**
   - Track email opens/clicks via SendGrid webhooks (optional)
   - After max_retries with no response → fallback to CALL (if configured)

**Acceptance Criteria**:
- [ ] EMAIL_FIRST config triggers email send instead of call
- [ ] Token is secure and expires correctly
- [ ] Email links to unified verification page
- [ ] Retry logic works for unanswered emails
- [ ] Fallback to call works when configured

**Files to Create/Modify**:
- `agencheck-support-agent/models/verification_token.py` (new)
- `agencheck-support-agent/utils/token_generator.py` (new)
- `agencheck-communication-agent/helpers/dispatch_work_history_call.py` (modify)
- `database/migrations/031_verification_tokens.sql` (new)

---

### Epic 1.3: SendGrid Email Templates (GAP 7)

**Description**: Create professional, branded email templates for verification requests.

**User Stories**:
1. As a verifier, I receive a clear, professional email explaining what's needed
2. As a verifier, I can easily click through to the verification page
3. As AgenCheck, our branding is consistent and trustworthy

**Technical Requirements**:

1. **Email Template Structure**
   ```
   Subject: Employment Verification Request - [Candidate Name]

   Dear [Verifier Name/HR Department],

   AgenCheck has received an employment verification request for
   [Candidate Name] regarding their tenure at [Company Name].

   Please click the secure link below to respond:
   [BUTTON: Complete Verification]

   Link expires in 7 days.

   You can:
   • Complete the verification form online (2-3 minutes)
   • Speak with our AI verification assistant
   • Schedule a callback at your preferred time

   Questions? Contact support@agencheck.com

   ---
   AgenCheck Pty Ltd
   Automated Employment Verification
   ```

2. **SendGrid Integration**
   - Use SendGrid Dynamic Templates
   - Track delivery, opens, clicks
   - Handle bounces gracefully

**Acceptance Criteria**:
- [ ] Email template created in SendGrid
- [ ] Dynamic fields populate correctly
- [ ] Email renders well on mobile and desktop
- [ ] Click tracking works
- [ ] Unsubscribe link included (CAN-SPAM compliance)

**Files to Create/Modify**:
- `agencheck-support-agent/utils/sendgrid_client.py` (extend)
- `agencheck-support-agent/templates/verification_request.html` (new)
- SendGrid Dynamic Template (configure in dashboard)

---

### Epic 1.4: Unified Verification Page (GAP 8)

**Description**: Refactor the existing /verify-call/ page to support both form and voice modes at `/verify/work-history/[token]`.

**User Stories**:
1. As a verifier in form mode, I can fill out verification fields myself
2. As a verifier in form mode, I always see "Receive Support" to get voice help
3. As a verifier in voice mode, I interact with the AI assistant in-browser
4. As a verifier, I can switch from form to voice mode at any time
5. As a verifier, I can schedule a callback instead of completing now

**Technical Requirements**:

1. **URL Structure**
   - `/verify/work-history/[token]?mode=form` - Default for email links
   - `/verify/work-history/[token]?mode=voice` - When "Call Now" or "Receive Support" clicked

2. **Form Mode Components**
   ```tsx
   // Form fields based on verify_fields from case
   <VerificationForm
     verifyFields={case.verify_fields}
     candidateClaims={case.verification_metadata.employment}
     onSubmit={handleFormSubmission}
   />

   // Always visible
   <ReceiveSupportButton onClick={() => setMode('voice')} />

   // Alternative
   <ScheduleCallbackButton onClick={() => showScheduler()} />
   ```

3. **Voice Mode**
   - Reuse existing LiveKit integration from verify-call/
   - Same live_form pattern for real-time display
   - Connect to room, launch voice agent

4. **Mode Switching**
   - Form → Voice: Click "Receive Support", URL changes to ?mode=voice
   - Voice → Form: Not supported (once voice starts, complete via voice)

5. **Form Submission API**
   ```python
   @router.post("/api/v1/verification/{token}/submit")
   async def submit_verification_form(
       token: str,
       form_data: VerificationFormSubmission
   ):
       # Validate token
       # Map form fields to verification_results
       # Trigger PostCheckProcessor
   ```

**Acceptance Criteria**:
- [ ] Page loads in form mode by default
- [ ] All verify_fields display as form inputs
- [ ] "Receive Support" button always visible and functional
- [ ] Voice mode launches LiveKit agent correctly
- [ ] Form submission creates proper verification_results
- [ ] Schedule callback shows date/time picker
- [ ] Token validation works (expired, invalid, used)

**Files to Create/Modify**:
- `agencheck-support-frontend/app/verify/work-history/[token]/page.tsx` (new, based on verify-call)
- `agencheck-support-frontend/components/verification/VerificationForm.tsx` (new)
- `agencheck-support-frontend/components/verification/ReceiveSupportButton.tsx` (new)
- `agencheck-support-frontend/components/verification/ScheduleCallback.tsx` (new)
- `agencheck-support-agent/api/routers/verification_check.py` (new)
- Redirect or deprecate old `/verify-call/` route

---

### Epic 1.5: PostCheckProcessor Form Handler (GAP 9)

**Description**: Extend PostCallProcessor to PostCheckProcessor, handling both form submissions and call completions.

**User Stories**:
1. As the system, I process form submissions the same way as call completions
2. As a verifier, I receive the same PDF confirmation regardless of completion method
3. As a customer, I see consistent verification_results structure from both paths

**Technical Requirements**:

1. **Rename and Extend**
   ```python
   class PostCheckProcessor:
       """Handles verification check outcomes from both form and call paths."""

       async def process_call_completion(self, task_id: str, transcript: str):
           """Existing logic - interpret transcript, store results."""
           results = await self._interpret_transcript(transcript)
           await self._finalize_check(task_id, results, source="call")

       async def process_form_submission(self, token: str, form_data: dict):
           """New logic - map form fields directly to results."""
           results = self._map_form_to_results(form_data)
           await self._finalize_check(token, results, source="form")

       async def _finalize_check(self, identifier: str, results: dict, source: str):
           """Common finalization - PDF, email, update case."""
           await self._update_verification_results(identifier, results)
           pdf_url = await self._generate_pdf(identifier, results)
           await self._email_verifier(identifier, pdf_url)
   ```

2. **Form-to-Results Mapping**
   - Direct field mapping (no AI interpretation needed)
   - Validate required fields present
   - Calculate match/discrepancy for each field

3. **Unified Output**
   - Same `verification_results` JSONB structure
   - Same PDF format
   - Same email confirmation

**Acceptance Criteria**:
- [ ] PostCallProcessor renamed to PostCheckProcessor
- [ ] Form submissions create valid verification_results
- [ ] Match/discrepancy calculated correctly for form data
- [ ] PDF generation works for form submissions
- [ ] Email sent to verifier after form submission
- [ ] Existing call processing unchanged

**Files to Create/Modify**:
- Rename `post_call_processor.py` → `post_check_processor.py`
- Add `process_form_submission()` method
- Update all imports/references

---

## Dependencies Between Epics

```
Epic 1.1 (Config) ────┐
                      ├──► Epic 1.2 (Email Workflow)
Epic 1.3 (Templates) ─┘
                              │
                              ▼
                      Epic 1.4 (Unified Page) ◄── Epic 1.5 (PostCheckProcessor)
```

- **1.2 depends on 1.1**: Need config to determine email vs call
- **1.2 depends on 1.3**: Need templates to send emails
- **1.4 depends on 1.2**: Need tokens/links to access page
- **1.4 depends on 1.5**: Need form submission handler

---

## Test Strategy

### Unit Tests
- Config resolution logic
- Token generation/validation
- Form-to-results mapping

### Integration Tests
- Full email-first flow end-to-end
- Form submission through PostCheckProcessor
- Voice mode launch from unified page

### E2E Tests (Browser)
- Load verification page in form mode
- Fill and submit form
- Click "Receive Support" and verify voice agent launches
- Schedule callback flow

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Email delivery rate | >98% |
| Form completion rate | Track baseline |
| Voice support requests | Track baseline |
| Average time to complete (form) | <3 minutes |

---

**Document Prepared By**: Claude Opus (Orchestrator)
**Parent Epic**: Work History MVP Gap Analysis
**Next Phase**: [Phase 2: Contact Intelligence](work-history-phase2-contact-intelligence.md)
