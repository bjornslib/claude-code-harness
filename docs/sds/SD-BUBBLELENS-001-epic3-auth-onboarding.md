---
title: "SD: BubbleLens Epic 3 - Auth & Onboarding Survey"
description: "Technical design for Clerk authentication, Google OAuth, and demographic onboarding survey"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic3: User Authentication & Onboarding Survey

**Parent PRD**: PRD-BUBBLELENS-P1-001 (Epic 3)
**Epic**: User Authentication & Onboarding Survey
**Worker Type**: `frontend-dev-expert` (UI) + `backend-solutions-engineer` (API)

## Overview

Implement Clerk-based authentication with email and Google OAuth signup, followed by an optional demographic onboarding survey. The survey collects 7 demographic fields (all optional) with strong privacy messaging. Responses are stored anonymously -- no PII linkage. Users can update or delete their profile at any time.

## Architecture

```
src/app/
├── (auth)/
│   ├── sign-in/[[...sign-in]]/
│   │   └── page.tsx            # Clerk SignIn component
│   ├── sign-up/[[...sign-up]]/
│   │   └── page.tsx            # Clerk SignUp component
│   └── layout.tsx              # Auth layout (centered, branded)
├── (dashboard)/
│   ├── onboarding/
│   │   └── page.tsx            # Demographic survey page
│   ├── settings/
│   │   └── profile/
│   │       └── page.tsx        # Profile management (view/update/delete)
│   └── layout.tsx              # Dashboard layout with nav
├── api/
│   ├── profile/
│   │   └── route.ts            # POST, GET, PUT, DELETE demographic profile
│   ├── auth/
│   │   └── extension-token/
│   │       └── route.ts        # GET extension auth token
│   └── webhooks/
│       └── clerk/
│           └── route.ts        # Clerk webhook for user creation
└── middleware.ts                # Clerk auth middleware
```

## Component Design

### Clerk Integration

**Middleware** (`middleware.ts`):
```typescript
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

const isPublicRoute = createRouteMatcher([
  '/',
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/api/webhooks(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect();
  }
});
```

**Clerk Webhook** (`/api/webhooks/clerk/route.ts`):
- Listens for `user.created` event
- Creates a `User` record in the database with `clerkId`
- Returns 200 to confirm receipt

### Onboarding Survey Component

**Survey fields configuration**:
```typescript
interface SurveyField {
  name: string;
  label: string;
  type: 'scale' | 'radio' | 'dropdown' | 'multiselect';
  options: Array<{ value: string; label: string }>;
  optional: boolean;
  sensitive: boolean; // Shows extra privacy note
}

const SURVEY_FIELDS: SurveyField[] = [
  {
    name: 'politicalLeaning',
    label: 'Political Leaning',
    type: 'scale',
    options: [
      { value: '1', label: 'Strong Left' },
      { value: '2', label: 'Left' },
      { value: '3', label: 'Center' },
      { value: '4', label: 'Right' },
      { value: '5', label: 'Strong Right' },
      { value: '0', label: 'Prefer not to say' },
    ],
    optional: true,
    sensitive: false,
  },
  {
    name: 'country',
    label: 'Country / Region',
    type: 'dropdown',
    options: [], // Populated from country list
    optional: true,
    sensitive: false,
  },
  {
    name: 'ageRange',
    label: 'Age Range',
    type: 'radio',
    options: [
      { value: '18-24', label: '18-24' },
      { value: '25-34', label: '25-34' },
      { value: '35-44', label: '35-44' },
      { value: '45-54', label: '45-54' },
      { value: '55+', label: '55+' },
      { value: 'prefer_not_to_say', label: 'Prefer not to say' },
    ],
    optional: true,
    sensitive: false,
  },
  {
    name: 'interests',
    label: 'Primary Interests',
    type: 'multiselect',
    options: [
      { value: 'politics', label: 'Politics' },
      { value: 'tech', label: 'Technology' },
      { value: 'entertainment', label: 'Entertainment' },
      { value: 'sports', label: 'Sports' },
      { value: 'education', label: 'Education' },
      { value: 'news', label: 'News' },
      { value: 'science', label: 'Science' },
      { value: 'music', label: 'Music' },
      { value: 'gaming', label: 'Gaming' },
      { value: 'other', label: 'Other' },
    ],
    optional: true,
    sensitive: false,
  },
  {
    name: 'ethnicity',
    label: 'Ethnicity',
    type: 'multiselect',
    options: [], // Populated from standard categories
    optional: true,
    sensitive: true,
  },
  {
    name: 'gender',
    label: 'Gender',
    type: 'radio',
    options: [
      { value: 'male', label: 'Male' },
      { value: 'female', label: 'Female' },
      { value: 'non_binary', label: 'Non-binary' },
      { value: 'other', label: 'Other' },
      { value: 'prefer_not_to_say', label: 'Prefer not to say' },
    ],
    optional: true,
    sensitive: true,
  },
  {
    name: 'sexualOrientation',
    label: 'Sexual Orientation',
    type: 'radio',
    options: [
      { value: 'straight', label: 'Straight' },
      { value: 'gay', label: 'Gay' },
      { value: 'lesbian', label: 'Lesbian' },
      { value: 'bisexual', label: 'Bisexual' },
      { value: 'other', label: 'Other' },
      { value: 'prefer_not_to_say', label: 'Prefer not to say' },
    ],
    optional: true,
    sensitive: true,
  },
];
```

**Survey UI structure**:
1. Privacy banner at top: "Your responses are anonymous and optional. We never link this data to your name or email."
2. Progress indicator (step X of 7, or single scrollable page)
3. Each field with label, input, and "Prefer not to say" option
4. Sensitive fields (ethnicity, gender, sexual orientation) get an additional note: "This helps us understand how algorithms treat different communities"
5. "Submit" button and "Skip for now" link

### Profile Management Page

Located at `/settings/profile`:
- Displays current demographic profile values
- Edit form pre-filled with current values
- "Delete My Profile" button with confirmation dialog
- "Delete All My Data" button (removes user + all feed data) with double confirmation

### Extension Token Endpoint

`GET /api/auth/extension-token`:
- Requires authenticated Clerk session
- Generates a JWT with:
  - `sub`: user's anonymous UUID (NOT Clerk ID)
  - `iss`: `bubblelens`
  - `exp`: 30 days from now
  - `scope`: `extension:capture`
- Signed with a separate secret (`EXTENSION_JWT_SECRET`)

## Data Model

Uses `User` and `DemographicProfile` tables defined in Epic 1 Prisma schema. No additional tables.

**Key constraint**: The `DemographicProfile` table stores ONLY the anonymous UUID as its primary key. The `User` table links UUID to `clerkId`, but no other table references `clerkId`.

## API Design

### `POST /api/profile`
Create demographic profile for the authenticated user.

**Request**:
```json
{
  "politicalLeaning": 2,
  "country": "US",
  "region": "California",
  "ageRange": "25-34",
  "gender": "male",
  "sexualOrientation": "gay",
  "ethnicity": ["white"],
  "interests": ["politics", "tech", "entertainment"]
}
```

**Response**: `201 Created`

**Validation** (Zod):
```typescript
const profileSchema = z.object({
  politicalLeaning: z.number().int().min(0).max(5).optional(),
  country: z.string().max(100).optional(),
  region: z.string().max(100).optional(),
  ageRange: z.enum(['18-24', '25-34', '35-44', '45-54', '55+', 'prefer_not_to_say']).optional(),
  gender: z.enum(['male', 'female', 'non_binary', 'other', 'prefer_not_to_say']).optional(),
  sexualOrientation: z.enum(['straight', 'gay', 'lesbian', 'bisexual', 'other', 'prefer_not_to_say']).optional(),
  ethnicity: z.array(z.string()).optional(),
  interests: z.array(z.string()).optional(),
});
```

### `GET /api/profile`
Retrieve current user's demographic profile.

**Response**: `200 OK` with profile JSON, or `404` if no profile exists.

### `PUT /api/profile`
Update demographic profile. Same schema as POST.

### `DELETE /api/profile`
Delete demographic profile. Returns `204 No Content`.

### `DELETE /api/profile/all`
Delete user account and ALL associated data (profile, feeds, feed items). Returns `204 No Content`. Requires confirmation header: `X-Confirm-Delete: DELETE_ALL_MY_DATA`.

### `GET /api/auth/extension-token`
Returns JWT for Chrome extension authentication. Requires authenticated Clerk session.

**Response**: `200 OK`
```json
{
  "token": "eyJ...",
  "expiresAt": "2026-04-25T00:00:00Z"
}
```

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T3.1 | Clerk SDK integration | `src/middleware.ts`, `src/app/layout.tsx`, `src/app/(auth)/*` | frontend-dev-expert | T1.1 |
| T3.2 | Google OAuth configuration | Clerk dashboard config, `.env` | backend-solutions-engineer | T3.1 |
| T3.3 | Onboarding survey page | `src/app/(dashboard)/onboarding/page.tsx`, `src/components/survey/*` | frontend-dev-expert | T3.1 |
| T3.4 | Profile API routes | `src/app/api/profile/route.ts` | backend-solutions-engineer | T1.3 |
| T3.5 | Profile management page | `src/app/(dashboard)/settings/profile/page.tsx` | frontend-dev-expert | T3.4 |
| T3.6 | Privacy policy page | `src/app/(marketing)/privacy/page.tsx` | frontend-dev-expert | T1.1 |
| T3.7 | Data deletion endpoint | `src/app/api/profile/all/route.ts` | backend-solutions-engineer | T3.4 |
| T3.8 | Onboarding routing logic | `src/middleware.ts`, `src/app/(dashboard)/layout.tsx` | frontend-dev-expert | T3.1, T3.3 |

## Testing Strategy

- **Unit tests**: Zod schema validation (valid/invalid payloads)
- **Unit tests**: Survey component renders all fields, handles skip
- **Integration tests**: Profile CRUD operations via API routes
- **Integration tests**: Clerk webhook creates user record
- **E2E test**: Sign up -> complete survey -> verify profile exists -> update profile -> delete profile

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T3.1 | Not Started | 2026-03-26 |
| T3.2 | Not Started | 2026-03-26 |
| T3.3 | Not Started | 2026-03-26 |
| T3.4 | Not Started | 2026-03-26 |
| T3.5 | Not Started | 2026-03-26 |
| T3.6 | Not Started | 2026-03-26 |
| T3.7 | Not Started | 2026-03-26 |
| T3.8 | Not Started | 2026-03-26 |
