---
title: "Guides"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Campaign Guides

Combined reference for Perfect Future Customer (PFC) criteria and CSV schema.

---

## Part 1: Perfect Future Customer (PFC) Criteria

### Inclusion Criteria

**Ideal Lead Profile:**
- COO, CEO, or senior executive (Director+) at SME/Mid-sized business
- Company size: 50-500 employees (typical)
- Australia/New Zealand based (primary market)
- Decision-making authority for operations or strategy
- Indicators of growth mindset or transformation interest

**Strong Signals:**
- Recent activity about AI, digital transformation, or innovation
- Hiring for operational or technical roles
- Speaking at industry events
- Published thought leadership
- Awards or recognition for innovation/leadership

### Exclusion Criteria

**Automatic Exclusions:**
- Consultants/advisors (not end customers)
- Competitors (AI consulting, digital agencies)
- Too junior (Manager level without decision authority)
- Too large (Enterprise 5000+ employees)
- Not target geography

**Yellow Flags (Review Carefully):**
- Unclear current role (may have moved)
- No recent activity (profile may be stale)
- Company in obvious distress (layoffs, restructuring)
- Industry misalignment with offer

### Industry Prioritization

**Tier 1 (High Priority):**
- Mining and Resources
- Healthcare and NDIS
- Financial Services
- Professional Services (Legal, Accounting)

**Tier 2 (Good Fit):**
- Manufacturing
- Logistics and Transport
- Retail (mid-sized chains)
- Real Estate/Property

**Tier 3 (Evaluate Case by Case):**
- Education
- Government
- Not-for-profit
- Agriculture

---

## Part 2: CSV Schema

### Primary Output File: ./workspace/campaign-{name}/campaign_research_audit.csv

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| firstName | string | Lead's first name | "Greg" |
| lastName | string | Lead's last name | "Barclay" |
| company | string | Current company name | "Slater and Gordon Lawyers" |
| title | string | Current job title | "Transformation Director" |
| linkedInUrl | string | Full LinkedIn profile URL | "https://linkedin.com/in/..." |
| personalisedMessage | string | Personalized observation (2 sentences) | "Noticed your 10 transformation certifications. Impressive work." |
| messageRationale | string | Why this approach was chosen | "Led with transformation expertise..." |
| personalisationHooks | string | Enrichment data gathered | "10 certifications including Stanford..." |
| qaStatus | string | Quality assurance status | "approved" / "revision_required" |
| validationNotes | string | Notes from Perplexity/user review | "Fact confirmed, role aligned" |

### Status Tracking File: ./workspace/campaign-{name}/all_leads_master.csv

| Field | Type | Description | Values |
|-------|------|-------------|--------|
| firstName | string | Lead's first name | - |
| lastName | string | Lead's last name | - |
| company | string | Current company | - |
| status | string | Pipeline status | "new", "enriched", "drafted", "approved", "sent", "responded" |
| phase | string | Current workflow phase | "phase-1" through "phase-5" |
| batch | string | Batch assignment | "batch_001", etc. |
| lastUpdated | string | ISO timestamp | "2025-12-16T10:30:00Z" |
| notes | string | Any tracking notes | - |

### Batch File Format: ./workspace/campaign-{name}/batches/batch_XXX/leads_enriched.json

```json
[
  {
    "firstName": "Greg",
    "lastName": "Barclay",
    "company": "Slater and Gordon Lawyers",
    "title": "Transformation Director",
    "linkedInUrl": "https://linkedin.com/in/gregbarclay",
    "enrichment": {
      "individualProfile": "10 professional certifications...",
      "recentActivity": "Company underwent CEO transition...",
      "companyContext": "Major Australian law firm...",
      "aiOpportunities": [
        "Predict case complexity from intake",
        "Analyze transformation readiness"
      ]
    }
  }
]
```

### Batch File Format: ./workspace/campaign-{name}/batches/batch_XXX/messages_draft.json

```json
[
  {
    "firstName": "Greg",
    "lastName": "Barclay",
    "company": "Slater and Gordon Lawyers",
    "title": "Transformation Director",
    "linkedInUrl": "https://linkedin.com/in/gregbarclay",
    "personalisedMessage": "Noticed your 10 transformation certifications including Stanford Innovation. Real commitment to the craft.",
    "messageRationale": "FACT: 10 transformation certifications - verified from careerHighlights. CLOSER: 'Real commitment to the craft' - fits continuous learning pattern.",
    "personalisationHooks": "10 professional certifications including Stanford Innovation..."
  }
]
```

---

## Part 3: Field Guidelines

### personalisedMessage Field

**Character Limit:** 200 characters recommended (brevity wins)

**Structure:**
```
[Observation] + [Reaction/Closer]
```

Two sentences maximum. Follows "Thanks for connecting, {{firstName}}." and precedes AI question.

**Guidelines:**
- Start with "Saw," "Noticed," "Congrats on," "Impressed by"
- Use a short, varied closer (see Phase 2 reference for list)
- Keep to exactly 2 sentences
- Use semicolons or periods to connect thoughts
- Choose ONE compelling fact
- Keep as observation only (questions come in the AI pitch)

### messageRationale Field

**Purpose:** Document WHY this fact and closer were chosen

**Structure:**
```
FACT: {what was observed and source}. CLOSER: {why this closer fits}.
```

**Example:**
```
FACT: Leading Buurtzorg model - verified from careerHighlights showing Executive Director at Buurtzorg Australia for 8+ years. CLOSER: 'Impressive work' - appropriate for healthcare innovation at scale.
```

### personalisationHooks Field

**Purpose:** Store all enrichment data for reference and future messages

**Include:**
- All 4 dimensions from Phase 1 enrichment
- Specific facts that could be used
- URLs or sources if available
- Ideas for follow-up messages

**Format:** Pipe-separated or natural language paragraphs

---

## Part 4: Data Hygiene

### Encoding Standards

- Always save CSV as UTF-8
- Check for mojibake characters before export
- Common issues to fix:
  - `Ã¢Â€Â™` → `'`
  - `Ã¢Â€Â"` → `-`
  - `â€™` → `'`

### Name Formatting

- First name: Capitalize first letter
- Last name: Capitalize first letter (handle McName, O'Name correctly)
- No trailing spaces
- No titles (Dr., Mr., etc.) unless specifically required

### Company Formatting

- Use official company name
- Include legal suffix if commonly used (Pty Ltd, Limited)
- No quotes around name
- Handle ampersands consistently (& not "and")

### URL Formatting

- Full URL including https://
- No tracking parameters
- Verify URL resolves before including

---

## Part 5: Quality Gates

### Phase 1 → Phase 2 Gate

Lead MUST have:
- [ ] At least one identity signal captured
- [ ] Company context sufficient for AI opportunity
- [ ] Current/relevant data point

### Phase 2 → Phase 3 Gate

Message MUST have:
- [ ] Single fact (not stacked)
- [ ] Exactly 2 sentences (observation + closer)
- [ ] No questions
- [ ] No AI pitch or "what if" statements
- [ ] No em dashes
- [ ] No "which is [adjective]" construction
- [ ] Closer varies from previous messages
- [ ] No encoding issues

### Phase 4 → Phase 5 Gate

Batch MUST have:
- [ ] 100% leads processed
- [ ] Spot-check passed
- [ ] No pattern drift

### Phase 5 → Export Gate

Campaign MUST have:
- [ ] User approval received
- [ ] Revisions applied
- [ ] Encoding verified
- [ ] Export format validated

---

## Part 6: Browser-Based Lead Research

### Recommended Tool: Claude in Chrome ✅

**Validated Jan 2026:** Claude in Chrome outperforms browser-mcp for LinkedIn profile extraction.

| Feature | browser-mcp | Claude in Chrome |
|---------|-------------|------------------|
| Navigation | ✅ Works | ✅ Works |
| Click Reliability | ⚠️ Timeout errors | ✅ Stable |
| Data Extracted | Basic + Experience | **All + Education + Skills** |
| Stability | ⚠️ Had timeout error | ✅ No errors |
| Screenshot | ✅ Available | ✅ With ID tracking |

**Why Claude in Chrome wins:**
- Extracts MORE data (Education, Skills sections)
- More stable (no timeout errors)
- Uses existing logged-in session
- No LinkedIn bot detection issues

### Claude in Chrome Workflow

**Prerequisites:**
- User logged into LinkedIn Sales Navigator
- Claude in Chrome extension active

**Workflow:**
1. `tabs_context_mcp` - Get browser context
2. `navigate` - Go to lead's LinkedIn profile
3. `read_page` - Extract profile data
4. `computer` with `screenshot` - Capture visual evidence (optional)
5. Process extracted data into personalization hooks
6. Generate observation using Phase 2 format

**Key Profile Sections to Extract:**

| Section | Use For | Fact Quality |
|---------|---------|--------------|
| **About** | Their own words | Best |
| **Experience** | Career pivots, tenure | Good |
| **Activity** | Recent posts, events | Good |
| **Education** | Background, credentials | Supporting |
| **Skills** | Endorsement counts | Supporting |
| **Recommendations** | What others say | Good |

**Extraction Template:**
```json
{
  "aboutSection": "Direct quote from About",
  "careerHighlights": "Key roles and transitions",
  "recentActivity": "Posts, articles, events",
  "education": "Degrees, institutions",
  "topSkills": "Skill (endorsements)",
  "personalisationHooks": "Specific facts for messaging"
}
```

### Example Extraction

```json
{
  "aboutSection": "On a mission to bring smiles by empowering businesses...",
  "careerHighlights": "CEO at ZELLIS for 10+ years, Former eBay executive",
  "recentActivity": "Posted about automotive industry digital evolution",
  "education": "Monash University - BBUS Marketing (1989-1993)",
  "topSkills": "Account Management (41), Marketing (36), Management (31)",
  "personalisationHooks": "Mission-driven CEO, ecommerce specialist, chocolate side business"
}
```

### Manual Research Fallback

If Claude in Chrome extension is unavailable:
1. User manually browses Sales Navigator
2. Copy/paste key sections into chat
3. Agent processes into enrichment format
4. Generate observation from provided data

---

## Part 7: Parallelization Rules

### Critical Constraint: Browser-Based Tasks Cannot Parallelize

**Rule:** Claude in Chrome operations MUST be sequential. Only one browser session can be active at a time.

| Task Type | Parallelizable? | Tool |
|-----------|-----------------|------|
| LinkedIn profile visits | ❌ NO | Claude in Chrome |
| Screenshot capture | ❌ NO | Claude in Chrome |
| Tab navigation | ❌ NO | Claude in Chrome |
| Company research | ✅ YES | Perplexity, Brave Search |
| News lookup | ✅ YES | Perplexity, Brave Search |
| Industry analysis | ✅ YES | Perplexity, Brave Search |
| AI opportunity mapping | ✅ YES | Subagents |

### Optimal Workflow Pattern

**Hybrid Sequential-Parallel Approach:**

```
1. [Sequential] Visit LinkedIn profile via Claude in Chrome
   → Extract: About, Experience, Education, Skills, Activity

2. [Parallel] While processing next LinkedIn profile, spawn subagents for:
   → Company research (Perplexity)
   → Industry news (Brave Search)
   → AI opportunity mapping

3. [Sequential] Visit next LinkedIn profile
   → Merge results from parallel research

4. Repeat until batch complete
```

### Subagent Delegation for Research

When spawning research subagents, use `general-purpose` type with explicit instructions:

```markdown
Research [Company Name] for lead campaign enrichment.

Gather:
1. Company problems/challenges (from news, industry analysis)
2. AI/digital transformation opportunities
3. Customer experience gaps
4. Recent news (funding, leadership changes, expansion)

Use Perplexity and Brave Search. Do NOT use browser tools.

Output format: JSON with fields: problems, aiOpportunities, cxGaps, recentNews
```

### Efficiency Optimizations

#### Pre-Warming Company Research

**Pattern:** Spawn all company research at batch start, collect results at batch end.

```
Batch Start (T=0):
├── Extract all leads from search (25 leads)
├── Identify unique companies (typically 20-25)
├── Spawn haiku agents for each company (parallel)
│   ├── Agent 1: Research Company A
│   ├── Agent 2: Research Company B
│   └── Agent N: Research Company N
└── Begin sequential profile visits

Profile Visits (T=1 to T=N):
├── Visit Profile 1 (browser - sequential)
├── Visit Profile 2 (browser - sequential)
└── ... continue while research runs in background

Batch End (T=N+1):
├── Collect all research agent outputs
├── Merge research into lead records
└── Save enriched batch
```

**Expected Time Savings:** 30-50%

#### Single-Read Profile Extraction

**Pattern:** Use `read_page` with appropriate depth instead of multiple clicks.

```
Instead of:
  click(About) → read → click(Experience) → read → click(Skills) → read

Do:
  read_page(depth=15, filter="all") → extract all sections
```

**Expected Time Savings:** 15-20%

#### Direct URL Navigation

**Pattern:** Navigate profile-to-profile without returning to search.

```
Instead of:
  Search → Profile A → Back → Search → Profile B → Back → Search...

Do:
  Extract URLs upfront → Profile A → Profile B → Profile C...
```

**Expected Time Savings:** 10-15%

#### Combined Efficiency Impact

| Optimization | Savings | Cumulative |
|-------------|---------|------------|
| Pre-warm research | 30-50% | 30-50% |
| Single-read extraction | 15-20% | 45-60% |
| Direct URL navigation | 10-15% | 50-65% |

---

## Part 8: Mutual Connection Prioritization

### Ranking Hierarchy (Best to Worst)

When evaluating mutual connections for warm introductions:

| Rank | Connection Type | Why It's Strong |
|------|-----------------|-----------------|
| 1 | **Worked at same company** | Shared professional context, likely collaborated |
| 2 | Same industry, senior role | Industry credibility, peer-level respect |
| 3 | Shared education (same school) | Alumni networks, shared experience |
| 4 | Shared group membership | Common interests, professional community |
| 5 | Generic 2nd connection | Weakest - just in network |

### "Same Company" Detection

When reviewing mutual connections in Sales Navigator:
1. Check the mutual connection's current company
2. Check their previous companies in Experience section
3. Cross-reference with lead's company history
4. **Best match:** Both worked at same company at overlapping time periods

### Using Mutual Connections in Messages

If strong mutual connection exists:
- Consider mentioning in connection request
- Do NOT mention generic mutual connections (looks automated)
- Only reference if you'd genuinely ask for intro

**Good:** "I noticed we both know [Name] from their time at [Shared Company]"
**Bad:** "We have 12 mutual connections" (sounds automated)

---

## Part 9: Enrichment Schema Reference

### Core Documentation Files

For complete JSON schema and validation workflows, consult these reference files:

| File | Purpose | When to Use |
|------|---------|-------------|
| **`references/json-schema-enrichment.md`** | Complete JSON schema with field-by-field documentation | Phase 1 enrichment, understanding required data structure |
| **`references/about-section-extraction.md`** | Step-by-step About section capture process | Before visiting profiles, during profile extraction |
| **`references/fact-quality-validation.md`** | Pre-draft validation workflow and red flags | Before Phase 2, quality gate checkpoints |

### Key Schema Concepts

**aboutSection (REQUIRED)**

The About section is the highest-quality identity signal. Every lead MUST have `aboutSection.raw` populated before proceeding to Phase 2.

```json
{
  "aboutSection": {
    "raw": "Full About text verbatim (REQUIRED)",
    "missionStatement": "Extracted mission/purpose if present"
  }
}
```

**Tiered Identity Signals**

Identity signals are ranked by quality:

| Tier | Type | Quality | Example |
|------|------|---------|---------|
| 1 | Their Own Words | **Best** | Quote from About section |
| 2 | Their Reputation | Good | What recommendations say |
| 3 | Their Purpose | Good | Career pivot revealing values |
| 4 | Unique Achievements | Acceptable | Only they can claim |
| 5 | Recent Activity | **Last Resort** | Posts, events |

**Selection Rule:** Always use the highest available tier. Never skip tiers.

**Company Facts vs Personal Facts**

| Use for Messages | Never Use for Messages |
|------------------|------------------------|
| Their own words (tier1) | Employee count |
| Career pivots (tier3) | Revenue milestones |
| Personal achievements | Geographic expansion |
| What others say about them | Funding announcements |

### Validation Checkpoints

**Phase 1 → Phase 2 Gate (Updated)**

Before writing any message, verify:
- [ ] `aboutSection.raw` is populated (REQUIRED)
- [ ] At least one tier1 or tier2 identity signal exists
- [ ] Selected fact is PERSONAL (not company milestone)
- [ ] Fact is verifiable from public profile data

**Red Flags (Block Message Drafting)**

If any of these exist, return to enrichment:
- Company milestone as primary fact
- Reaction counts as hook ("119 reactions")
- Tenure as primary fact ("20 years")
- Missing About section
- Company announcement instead of personal post

For detailed validation workflows, see `references/fact-quality-validation.md`
