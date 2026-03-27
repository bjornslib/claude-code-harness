---
title: "Contact Person Name Split — Solution Design"
description: "Technical design for splitting contact_name into structured name fields"
version: "1.0.0"
last-updated: 2026-03-22
status: active
type: sd
grade: authoritative
prd_ref: PRD-CONTACT-NAME-SPLIT-001
---

# SD-CONTACT-NAME-SPLIT-001: Contact Person Name Split

## Architecture Overview

```
Frontend Form (3 fields)
    ↓
API Proxy (route.ts) — maps to canonical model
    ↓
Backend (work_history.py) — EmployerContactPerson { first_name, middle_name, last_name }
    ↓ stored in
cases.verification_metadata → employer.contacts[].{ first_name, middle_name, last_name }
background_tasks.context_data → employer.{ contact_name → first/last }
university_contacts → { first_name, middle_name, last_name } columns or JSONB
    ↓ consumed by
Prefect email flow → "Dear {first_name}"
Voice agent → "Hi {first_name}, I'm calling about..."
```

## Phase 1: Pydantic Model (Epic E1)

### File: `agencheck-support-agent/models/work_history.py`

```python
class EmployerContactPerson(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)

    # Backward compatibility: computed from components
    contact_name: Optional[str] = Field(None, max_length=255, deprecated=True)

    @model_validator(mode='before')
    @classmethod
    def parse_legacy_name(cls, data):
        """If only contact_name provided, split into first/last."""
        if isinstance(data, dict) and data.get('contact_name') and not data.get('first_name'):
            parts = data['contact_name'].strip().split()
            if len(parts) >= 2:
                data['first_name'] = parts[0]
                data['last_name'] = ' '.join(parts[1:])
            elif len(parts) == 1:
                data['first_name'] = parts[0]
        return data

    @property
    def full_name(self) -> str:
        """Reconstruct display name from components."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)
```

### TypeScript regeneration
Run `python scripts/generate_ts_types.py` → auto-updates `lib/types/work-history.generated.ts`

## Phase 2: Frontend & API (Epic E2)

### File: `agencheck-support-frontend/app/checks-dashboard/new/page.tsx`

```typescript
const contactSchema = z.object({
  firstName: z.string().min(1, 'First name required'),
  middleName: z.string().optional(),
  lastName: z.string().min(1, 'Last name required'),
  email: z.string().email().optional().or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  department: z.string().optional(),
  isPrimary: z.boolean().default(false),
});
```

### File: `agencheck-support-frontend/app/api/verify/route.ts`

```typescript
contacts.push({
  first_name: primaryContact.firstName,
  middle_name: primaryContact.middleName || undefined,
  last_name: primaryContact.lastName,
  contact_email: primaryContact.email,
  contact_phone: primaryContact.phone,
});
```

## Phase 3: Database (Epic E3)

### Migration: `database/migrations/054_contact_name_split.sql`

```sql
-- Add structured name columns to university_contacts
ALTER TABLE university_contacts
    ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS middle_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);

-- Migrate existing data: split "name" into first/last
UPDATE university_contacts
SET first_name = split_part(name, ' ', 1),
    last_name = CASE
        WHEN position(' ' IN name) > 0
        THEN substring(name FROM position(' ' IN name) + 1)
        ELSE NULL
    END
WHERE first_name IS NULL AND name IS NOT NULL;
```

## Phase 4: Email & Voice (Epic E4)

### Prefect email template
```python
# In email_outreach_flow.py or similar
contact_first_name = context_data['employer'].get('contact_first_name',
    context_data['employer'].get('contact_name', 'HR Department').split()[0])
email_body = f"Dear {contact_first_name},\n\n..."
```

### Voice agent greeting
```python
# In verification_agents.py CandidateInfo.from_verification_metadata()
primary = metadata.employer.contacts[0] if metadata.employer.contacts else None
contact_first_name = primary.first_name if primary else "there"
# Agent prompt: f"Hi {contact_first_name}, I'm calling from AgenCheck..."
```

## Files Affected (Complete List)

| File | Change |
|------|--------|
| `models/work_history.py` | Split EmployerContactPerson fields |
| `scripts/generate_ts_types.py` | Regenerate TS types |
| `app/checks-dashboard/new/page.tsx` | 3 name fields in contact form |
| `app/api/verify/route.ts` | Map split fields |
| `database/migrations/054_*.sql` | Add columns + migrate data |
| `api/routers/work_history.py` | Update _transform_to_metadata if needed |
| `prefect_flows/flows/tasks/email_outreach.py` | Use first_name in greeting |
| `verification_agents.py` | CandidateInfo.contact_first_name |
| `agent-groq.py` (+ other agent variants) | Greeting uses first_name |

## Backward Compatibility

- `contact_name` field kept as deprecated alias with `model_validator` that auto-splits
- Existing JSONB with `contact_name` continues to work via validator
- `university_contacts.name` column preserved alongside new split columns
- Voice agent falls back to `contact_name` if `first_name` not available

## Implementation Status

| Epic | Status | Date | Commit |
|------|--------|------|--------|
| - | Remaining | - | - |
