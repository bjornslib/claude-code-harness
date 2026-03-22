---
title: "Contact Person Name Split"
description: "Split contact_name into first/middle/last name fields across the verification stack"
version: "1.0.0"
last-updated: 2026-03-22
status: active
type: prd
grade: authoritative
prd_id: PRD-CONTACT-NAME-SPLIT-001
---

# PRD-CONTACT-NAME-SPLIT-001: Contact Person Name Split

## Problem Statement

The employer contact person is currently stored as a single `contact_name` string (e.g., "Jane Smith"). This prevents:
1. Addressing verifiers by first name in emails ("Dear Jane" vs "Dear Jane Smith")
2. Proper name display in the voice agent greeting
3. Data quality for contact deduplication
4. CRM integration requiring structured name fields

## User Stories

- As an operator, I want to enter the contact person's first, middle, and last name separately so that our emails address them personally.
- As a verifier, I want to receive an email that says "Dear Bjorn" not "Dear Bjorn Verifier" so it feels professional and personal.
- As the voice agent, I want to greet the verifier by their first name for a natural conversation opening.

## Requirements

### Must Have
1. Frontend form collects first_name, middle_name (optional), last_name for each contact person
2. Backend canonical model `EmployerContactPerson` stores first/middle/last separately
3. `university_contacts` table stores name components
4. Prefect email templates use `first_name` for greeting ("Dear {first_name}")
5. Backward compatibility: existing single-name records continue to work

### Should Have
6. Voice agent addresses verifier by first name
7. Display name reconstruction: `{first_name} {middle_name} {last_name}`.strip()
8. Generated TypeScript types auto-update

### Nice to Have
9. Name parsing for existing data migration ("Jane Smith" → first="Jane", last="Smith")

## Epics

### E1: Canonical Model Update
Update `EmployerContactPerson` in `models/work_history.py` with first/middle/last fields. Keep `contact_name` as computed property for backward compat.

### E2: Frontend Form & API Proxy
Split contact person input into 3 fields. Update Zod schema. Update `route.ts` proxy to map split fields.

### E3: Database & Storage
Update `university_contacts` table (migration). Transform `additional_contacts` JSONB. Update `background_tasks.context_data` writer.

### E4: Email & Voice Personalization
Update Prefect email template to use `first_name`. Update voice agent greeting.

## Acceptance Criteria
- [ ] New case form shows first/middle/last name fields for contacts
- [ ] Email sent to verifier addresses them by first name
- [ ] Voice agent greets verifier by first name
- [ ] Existing cases with single `contact_name` still work
- [ ] `university_contacts` stores name components
