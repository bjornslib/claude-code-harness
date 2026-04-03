# PRD: Employer Contact Search for Work History Checks

**Product**: AgenCheck
**Feature**: Employer Contact Research & Outreach for Work History Verification
**Author**: Bjorn Schliebitz (CPTO)
**Status**: Draft
**Last updated**: 2026-04-04

---

## 1. Problem statement

Work history verification requires contacting a candidate's previous employer to confirm employment details (job title, dates, responsibilities, reason for leaving, etc.). Today, this is a manual, time-consuming process where verification associates:

- Receive limited contact information from the background check company's client (often just a company name, sometimes a phone number)
- Manually research employer HR/Payroll contacts using search engines and ChatGPT
- Make phone calls, navigate IVRs, get transferred between departments
- Send emails and wait days or weeks for responses
- Track all attempts across multiple spreadsheets and CRM entries
- Repeat the cycle for 30–50 checks per day, with 90–95% of cases requiring multiple follow-up attempts

Cases routinely take 15+ business days. Some stretch beyond 3 months. The manual research phase typically yields only 1–2 contacts, and verification teams need exhaustive contact lists for compliance reporting — they must demonstrate they've tried all reasonable avenues before closing a check as "unable to verify."

### Core insight

The employer contact search problem for work history is structurally identical to the university contact search for education verification. The same infrastructure (AI-powered research, multi-channel outreach, transcript-aware retry logic) applies. The key differences are:

- **Target department**: HR, Payroll, or Finance — not a registrar's office
- **Contact classification**: Contacts are either "general" (department/reception) or "named POC" (specific person with system access)
- **Validation mechanism**: Contact validation happens during the call itself — when we confirm the person has access to HR/Payroll records, they become a validated POC

---

## 2. Solution overview

An AI-powered employer contact research and outreach pipeline that:

1. **Researches** the employer to build an exhaustive contact list before any outreach
2. **Classifies** contacts as general or named POC
3. **Calls and emails** contacts in a configurable sequence, with full context carried across attempts
4. **Validates** contacts during the call — if the person on the line has HR/Payroll system access, validation and the work history check happen in the same conversation
5. **Stores** every call recording + transcript and makes prior context available to the voice agent on each subsequent attempt
6. **Routes** call outcomes to the appropriate next action (retry, reschedule, alternate contact, escalation)

---

## 3. Flow architecture

### 3.1 End-to-end flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                      CHECK DATA RECEIVED                                │
│  From customer: candidate name, employer name, dates, job title,       │
│  optionally: phone number, contact name, website URL, city/country     │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   EMPLOYER CONTACT RESEARCH                             │
│                                                                        │
│  ALWAYS runs first, regardless of whether a phone number was provided. │
│                                                                        │
│  Inputs:                                                               │
│  - Employer name, city/country, website URL (if provided)              │
│  - Any existing contact details from customer                          │
│                                                                        │
│  Outputs (exhaustive list):                                            │
│  - Phone numbers (main line, HR direct, reception)                     │
│  - Email addresses (HR, payroll, info@, careers@)                      │
│  - Named contacts (with titles where available)                        │
│  - Website contact forms (if any)                                      │
│  - Source attribution for each contact                                 │
│  - Confidence score per contact                                        │
│                                                                        │
│  Stores all discovered contacts in the employer_contacts table.        │
│  Classifies each as: general | named_poc                               │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    OUTREACH SEQUENCE                                    │
│                                                                        │
│  Configurable per customer via background_check_sequence table.        │
│  Default: call_attempt → email_outreach → call_retry → email_reminder  │
│                                                                        │
│  For each step:                                                        │
│  1. Select next contact from prioritised list                          │
│  2. Dispatch call and/or email (parallel where applicable)             │
│  3. Route based on call outcome (see §3.3)                             │
│  4. On max attempts for this step → advance to next step               │
│  5. Store audio + transcript per call                                  │
│  6. Make full prior context available to voice agent                   │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    CALL OUTCOME ROUTING                                 │
│                                                                        │
│  Right person (HR/Payroll with system access):                         │
│    → Validate POC → Run work history check in same call                │
│    → result_status: verified | completed_discrepancies                 │
│                                                                        │
│  Reschedule requested by contact:                                      │
│    → Store scheduled task in background_tasks                          │
│    → Send calendar invite via SendGrid                                 │
│    → result_status: callback_requested                                 │
│                                                                        │
│  Contact is away (e.g. "out for lunch"):                               │
│    → Schedule callback at suggested time                               │
│    → Store scheduled task + send calendar invite                       │
│    → result_status: callback_requested                                 │
│                                                                        │
│  Alternate contact details received:                                   │
│    → Store new contact in employer_contacts                            │
│    → Schedule call ASAP to new contact                                 │
│    → result_status: alternate_contact_received                         │
│                                                                        │
│  No answer / unreachable:                                              │
│    → Increment attempt count                                           │
│    → If < max_attempts: retry with backoff (2h, 4h, 24h, 48h)         │
│    → If >= max_attempts: advance to next step in sequence              │
│    → result_status: no_answer                                          │
│                                                                        │
│  Voicemail left:                                                       │
│    → Schedule retry with backoff                                       │
│    → result_status: voicemail_left                                     │
│                                                                        │
│  Wrong number / refused / unable to help:                              │
│    → Mark contact as invalid                                           │
│    → Try next alternate contact                                        │
│    → If no alternates remain: requires_review                          │
│    → result_status: wrong_number | refused | unable_to_verify          │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Contact classification

When a check is submitted, any contacts (from the customer or from research) are classified:

```
┌─────────────────────────────────────────────────────────┐
│  CONTACT CLASSIFICATION                                  │
│                                                         │
│  GENERAL (no named individual):                         │
│  - "HR Department" + phone number                       │
│  - "Main reception" + phone number                      │
│  - info@ or hr@ email address                           │
│  - Website contact form URL                             │
│                                                         │
│  NAMED POC (specific individual):                       │
│  - "Jane Smith, HR Manager" + phone/email               │
│  - Must have a person's name AND at least one of:       │
│    phone number, email address                          │
│                                                         │
│  EXCEPTION for named POC:                               │
│  - CEO, Founder, Managing Director may also serve       │
│    as a valid POC if the employer is small enough that   │
│    they have direct access to employment records        │
│                                                         │
│  VALIDATED POC (confirmed during call):                 │
│  - Person confirmed they have access to HR/Payroll      │
│    or Finance systems                                   │
│  - Validation + check can happen in the same call       │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Call outcome state transitions

```
                        ┌──────────────┐
                        │  Call attempt │
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐──────────────────┐
              ▼                ▼                ▼                  ▼
     ┌────────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐
     │  Right      │   │  Reschedule  │  │  Alternate │   │  No answer / │
     │  person     │   │  requested   │  │  contact   │   │  unreachable │
     │  reached    │   │              │  │  received  │   │              │
     └──────┬─────┘   └──────┬───────┘  └─────┬──────┘   └──────┬───────┘
            │                │                │                  │
            ▼                ▼                ▼                  ▼
     ┌────────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐
     │  Validate   │   │  Schedule    │  │  Schedule  │   │  Retry with  │
     │  POC →      │   │  future task │  │  call ASAP │   │  backoff OR  │
     │  run check  │   │  + send cal  │  │  to new    │   │  advance to  │
     │  in same    │   │  invite via  │  │  contact   │   │  next step   │
     │  call       │   │  SendGrid    │  │            │   │              │
     └──────┬─────┘   └──────┬───────┘  └─────┬──────┘   └──────┬───────┘
            │                │                │                  │
            ▼                ▼                ▼                  ▼
     ┌────────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐
     │  check:     │   │  check:      │  │  check:    │   │  check:      │
     │  completed  │   │  awaiting_   │  │  in_       │   │  in_progress │
     │             │   │  callback    │  │  progress  │   │  or          │
     │  result:    │   │              │  │            │   │  requires_   │
     │  verified   │   │  result:     │  │  result:   │   │  review      │
     │             │   │  callback_   │  │  alternate │   │              │
     │             │   │  requested   │  │  _contact  │   │  result:     │
     │             │   │              │  │  _received │   │  no_answer   │
     └────────────┘   └──────────────┘  └────────────┘   └──────────────┘
```

---

## 4. Status architecture

### 4.1 Three independent status dimensions

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  CHECK (business-level)         │  What the customer sees              │
│  ─────────────────────          │                                      │
│  .status                        │  pending, in_progress,               │
│                                 │  awaiting_callback, requires_review, │
│                                 │  completed, failed, aborted          │
│  .verification_results (JSONB)  │  Structured outcome with evidence    │
│                                 │                                      │
├─────────────────────────────────┼──────────────────────────────────────┤
│                                                                        │
│  TASK STATUS (technical)        │  Did the dispatch succeed?           │
│  ─────────────────────          │                                      │
│  background_tasks.status        │  pending → processing → completed    │
│                                 │                         → failed     │
│                                 │                         → timeout    │
│                                 │                                      │
├─────────────────────────────────┼──────────────────────────────────────┤
│                                                                        │
│  RESULT STATUS (outcome)        │  What happened in this attempt?      │
│  ──────────────────────         │                                      │
│  background_tasks.result_status │  verified, no_answer, voicemail_left,│
│                                 │  callback_requested, refused,        │
│                                 │  wrong_number, unable_to_verify,     │
│                                 │  alternate_contact_received,         │
│                                 │  max_retries_exceeded                │
│                                 │                                      │
└────────────────────────────────────────────────────────────────────────┘

Relationship:
  result_status ──drives──▶ check.status update
  task.status only tracks whether the email/call dispatch worked (technical)
  check.verification_results is the evidence-backed detail;
  check.status is its summary
```

### 4.2 Check spawns tasks in a chain

```
┌─────────────────────────────────────────────────────────────────┐
│  CHECK (work_history)                                            │
│  .status: in_progress                                            │
│  .verification_results: null (pending)                           │
│  .employer_contact_id: FK → employer_contacts                    │
└───────────┬─────────────────────────────────────────────────────┘
            │ spawns (1 → many)
            ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Task 1       │────▶│  Task 2       │────▶│  Task 3       │
│  research     │     │  call_attempt │     │  email_       │
│               │     │               │     │  outreach     │
│  status:      │     │  status:      │     │  status:      │
│  completed    │     │  completed    │     │  completed    │
│               │     │               │     │               │
│  result:      │     │  result:      │     │  result:      │
│  contacts_    │     │  no_answer    │     │  email_sent   │
│  discovered   │     │               │     │               │
└──────────────┘     └──────────────┘     └──────────────┘
  step 1               step 2               step 3
  seq_step: 1          seq_step: 2          seq_step: 3

  Each task links via previous_task_id / next_task_id
  Each stores its own context_data, result_data JSONB
  Voice tasks also link to sub_threads for transcript storage
```

### 4.3 Result status → check status mapping

```
result_status                    │  check.status          │  next action
─────────────────────────────────┼────────────────────────┼──────────────────────
verified                         │  completed             │  billing, notification
completed_discrepancies          │  completed             │  billing, notification
no_answer / busy                 │  in_progress           │  retry with backoff
voicemail_left                   │  in_progress           │  retry with backoff
callback_requested               │  awaiting_callback     │  schedule task + cal invite
alternate_contact_received       │  in_progress           │  schedule call to new contact
wrong_number                     │  requires_review       │  try next alt contact or escalate
refused                          │  requires_review       │  human escalation
unable_to_verify                 │  requires_review       │  human escalation
max_retries_exceeded             │  failed                │  notify customer
aborted                          │  aborted               │  notify customer (if configured)
```

---

## 5. Employer contact research

### 5.1 Research agent specification

The research agent runs **before any outreach** and produces an exhaustive contact list. This is a non-negotiable design decision — verification teams must be able to demonstrate they've explored all reasonable contact avenues for compliance purposes.

**Input data** (from the check submission):

| Field | Required | Example |
|-------|----------|---------|
| employer_name | Yes | "Acme Corp Pty Ltd" |
| country | Yes | "Australia" |
| city | No | "Melbourne" |
| website_url | No | "https://acmecorp.com.au" |
| phone_number | No | "+61 3 9876 5432" |
| contact_name | No | "Jane Smith" |
| contact_email | No | "jane@acmecorp.com.au" |

**Research outputs** (per contact discovered):

| Field | Description |
|-------|-------------|
| contact_name | Person's name (null for general contacts) |
| contact_title | Job title if known (e.g. "HR Manager") |
| department | HR, Payroll, Finance, Reception, General |
| phone_number | Direct or main line |
| email_address | Direct or department email |
| contact_type | `general` or `named_poc` |
| source_url | URL where the contact was found |
| confidence_score | 0.0–1.0 based on source reliability |
| has_contact_form | Boolean — whether the employer website has a contact form |
| contact_form_url | URL of the contact form if applicable |
| notes | Any special instructions (e.g. "ask for ext. 204") |

**Research sources** (in order of reliability):

1. Customer-provided contacts (highest confidence)
2. Employer's official website (About, Contact, Team pages)
3. LinkedIn company page and employees (HR/People titles)
4. Business directories (Yellow Pages, local equivalents)
5. Government company registries (ASIC, ACRA, Companies House)
6. Industry-specific databases

**Research task** creates a `background_task` with:
- `action_type`: `contact_research`
- `result_status`: `contacts_discovered` on success
- `result_data` JSONB: array of discovered contacts + metadata

### 5.2 Contact prioritisation

After research, contacts are prioritised for outreach:

```
Priority 1: Named POC in HR/Payroll with direct phone + email
Priority 2: Named POC in HR/Payroll with phone only
Priority 3: HR department general phone number
Priority 4: Named POC with email only
Priority 5: General reception/main line phone number
Priority 6: Department email addresses (hr@, payroll@, info@)
Priority 7: Website contact form
```

Customer-provided contacts always take the top priority position within their tier.

---

## 6. Outreach sequence

### 6.1 Configurable sequence

The outreach sequence is defined per customer in the `background_check_sequence` table. The system resolves the sequence using 3-tier precedence: client-specific → customer-specific → system default.

**Default work_history employer outreach sequence**:

| Step | step_name | channel_type | delay_hours | max_attempts |
|------|-----------|-------------|-------------|--------------|
| 1 | contact_research | research | 0 | 1 |
| 2 | call_attempt | voice | 0 | 3 |
| 3 | email_outreach | email | 0 | 1 |
| 4 | call_retry | voice | 24 | 2 |
| 5 | email_reminder | email | 48 | 1 |

### 6.2 Business hours gating

Voice steps are gated by the employer's local business hours. Before dispatching a call, the orchestrator calculates `max(sla_delay, time_until_business_hours)` using `calculate_next_business_hour(employer_timezone)`.

### 6.3 Voice agent context

On each call attempt, the voice agent receives the full context from all prior interactions:

- All previous call transcripts (from `sub_threads.all_messages`)
- All previous call outcomes and result_statuses
- Any notes from prior calls (e.g. "receptionist said John is back Tuesday")
- Any new alternate contacts discovered during prior calls
- The current contact being called and their classification

This enables the agent to say things like: "I called earlier and was told Jane in HR would be the right person to speak with — is she available?"

### 6.4 Email templates

Emails are sent via SendGrid with templates selected by step:

| Step | Template | Content |
|------|----------|---------|
| email_outreach | email_first_contact | Introduction, verification request, link to web form |
| email_reminder | email_reminder_1 | Follow-up referencing prior contact attempt |

The email contains a link to `/verify-check/{task_uuid}` where the employer contact can complete the verification via web form, chat agent, or voice escalation.

### 6.5 Calendar invite (reschedule)

When a call results in a reschedule request (either by the contact or because the contact is unavailable), the system:

1. Creates a `background_task` with `action_type: scheduled_callback`, `status: pending`, and the scheduled datetime stored in `context_data`
2. Sends a calendar invite email via SendGrid with the scheduled date/time
3. The Prefect orchestrator picks up the scheduled task at the appropriate time and dispatches the call

---

## 7. Data model

### 7.1 employer_contacts table

Extends the existing `university_contacts` pattern with `entity_type = 'employer'`.

```
employer_contacts (extends university_contacts concept)
─────────────────────────────────────────────────────────
id                   SERIAL PK
entity_type          VARCHAR(50)      -- 'employer'
employer_name        VARCHAR(255)     -- "Acme Corp Pty Ltd"
country              VARCHAR(100)
city                 VARCHAR(100)
website_url          TEXT
contact_name         VARCHAR(255)     -- null for general contacts
contact_title        VARCHAR(255)     -- "HR Manager"
department           VARCHAR(100)     -- HR, Payroll, Finance, Reception
phone_number         VARCHAR(50)
email_address        VARCHAR(255)
contact_type         VARCHAR(50)      -- 'general' | 'named_poc' | 'validated_poc'
source_url           TEXT
confidence_score     DECIMAL(3,2)
has_contact_form     BOOLEAN
contact_form_url     TEXT
notes                TEXT
verification_status  VARCHAR(50)      -- 'discovered' | 'validated' | 'invalid'
last_verified_at     TIMESTAMPTZ
created_at           TIMESTAMPTZ
updated_at           TIMESTAMPTZ
customer_id          FK → customers
```

### 7.2 New result_status values

Add to the existing `background_tasks.result_status` enum:

- `contacts_discovered` — research task completed, contacts found
- `alternate_contact_received` — call produced a new contact to try
- `callback_requested` — contact or receptionist requested a callback at a specific time
- `contact_validated` — person confirmed as having HR/Payroll system access

### 7.3 New action_type values

Add to the existing `background_tasks.action_type` options:

- `contact_research` — AI research to discover employer contacts
- `scheduled_callback` — a call scheduled for a future date/time
- `calendar_invite` — SendGrid calendar invite dispatch

### 7.4 verification_metadata JSONB structure (on cases)

```json
{
  "employer": {
    "name": "Acme Corp Pty Ltd",
    "country": "Australia",
    "city": "Melbourne",
    "website_url": "https://acmecorp.com.au"
  },
  "candidate": {
    "name": "John Doe",
    "job_title": "Software Engineer",
    "start_date": "2020-01-15",
    "end_date": "2023-06-30",
    "reason_for_leaving": "Resigned"
  },
  "verify_fields": [
    "job_title",
    "dates_of_employment",
    "reason_for_leaving",
    "responsibilities",
    "eligibility_for_rehire"
  ],
  "customer_provided_contacts": [
    {
      "phone_number": "+61 3 9876 5432",
      "contact_name": null
    }
  ]
}
```

---

## 8. Integration with existing Prefect pipeline

### 8.1 Orchestrator changes

The `verification_orchestrator_flow` already supports configurable sequences via `background_check_sequence`. The employer contact search adds:

1. **New `contact_research` step type**: The orchestrator recognises `channel_type: research` and dispatches to the research agent instead of email/voice handlers. This step must complete before subsequent steps execute.

2. **Smart wait awareness**: The existing `smart_wait_for_response_or_timeout` Redis polling works unchanged — if an employer completes the web form during an inter-step delay, the orchestrator detects it and skips remaining steps.

3. **Alternate contact injection**: When a call produces `alternate_contact_received`, the orchestrator stores the new contact and schedules an immediate call attempt to it (inserted as the next step, not appended to the end).

4. **Calendar invite dispatch**: A new task handler for `scheduled_callback` that:
   - Waits until the scheduled time (using business hours gating)
   - Dispatches the call with full prior context
   - Sends a calendar invite email via SendGrid at scheduling time

### 8.2 Voice agent changes

The LiveKit voice agent gains:

1. **Navigation phase awareness**: The `NavigationAgent` already handles initial greetings and routing. For employer calls, it specifically asks for HR, Payroll, or the named contact.

2. **POC validation during call**: When the agent reaches a person, it confirms their role before proceeding to verification questions. If they confirm HR/Payroll access, the `VerificationAgent` takes over and runs the check in the same call.

3. **Transcript context injection**: Prior call transcripts are loaded into the agent's context via `job_metadata`, enabling continuity across attempts.

4. **Structured outcome extraction**: The `CallOutcomeInterpreter` (Claude Haiku) already handles transcript → structured outcome. New outcome types for employer-specific scenarios are added to the interpretation prompt.

---

## 9. Success metrics

| Metric | Current (manual) | Target (automated) |
|--------|-------------------|---------------------|
| Contacts discovered per employer | 1–2 | 8–15 |
| Time to first outreach attempt | 30–60 min | < 5 min (after research) |
| Research time per employer | 15–30 min | < 2 min |
| Follow-up tracking accuracy | Manual spreadsheets | 100% automated |
| Compliance documentation | Partial, manual | Full audit trail |
| Average check turnaround | 15+ business days | Target: 5 business days |

---

## 10. Phased delivery

### Phase 1: Research + call (MVP)

- Employer contact research agent (Perplexity Deep Research API)
- Contact classification (general vs named POC)
- Contact storage in employer_contacts table
- Call dispatch to first prioritised contact
- Basic call outcome routing (verified, no_answer, callback)
- Transcript storage + context injection for retry calls

### Phase 2: Full outreach automation

- Email outreach templates (first contact + reminders)
- Calendar invite dispatch via SendGrid for reschedules
- Alternate contact handling (store + schedule ASAP call)
- Web form (`/verify-check`) adapted for employer verification
- Smart wait with Redis polling for early web form completion

### Phase 3: Intelligence + optimisation

- Contact success pattern learning (which contact types yield fastest results by industry/country)
- Automatic contact form submission where available
- Predictive prioritisation based on historical success rates
- Contact directory enrichment (reuse validated contacts across checks for the same employer)

---

## 11. Out of scope (for now)

- SMS and WhatsApp channels (placeholder implementations exist)
- Direct CRM integration for updating attempts in RIMA (separate browser extension workstream)
- Vendor delegation (sending check to local verification partner)
- Multi-language voice agent support (English only for MVP)
- Automated contact form submission (Phase 3)

---

## 12. Open questions

1. **Research depth threshold**: Should there be a minimum number of contacts discovered before the research task completes, or is it purely time-bounded (e.g. max 2 minutes)?
2. **Contact reuse across checks**: When we verify an employer contact for one candidate, should that contact automatically become a validated POC for subsequent checks against the same employer? What's the TTL?
3. **IVR navigation**: How sophisticated should the voice agent's IVR handling be in Phase 1? Basic DTMF navigation, or full IVR tree traversal?
4. **Contact form detection**: Should the research agent flag websites with contact forms separately, and should we auto-fill them as a parallel outreach channel?

---

## 13. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Prefect orchestrator (sequence-based) | Built | Needs new step type for research |
| LiveKit voice agent (multi-agent) | Built | Needs employer-specific prompts |
| SendGrid email templates | Built | Needs employer outreach templates |
| Redis streams (smart wait) | Built | No changes needed |
| Perplexity Deep Research API | Integrated | Used for education; extend for employer |
| PostCallProcessor (Claude Haiku) | Built | Needs employer-specific outcome types |
| background_check_sequence table | Built | Needs employer default sequence |
| employer_contacts table | New | Schema defined in §7.1 |
| Calendar invite via SendGrid | New | Requires SendGrid calendar attachment |
