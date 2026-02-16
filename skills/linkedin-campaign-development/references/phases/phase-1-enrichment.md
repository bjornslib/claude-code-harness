# Phase 1: Lead Enrichment

## Purpose

Gather the 4 dimensions of data needed to write Identity-First messages. This phase is about COLLECTING information, not writing messages yet.

## The 4 Enrichment Dimensions

### 1. Individual Profile (WHO they are)

**Primary Sources:**
- LinkedIn About section (their own words describing themselves)
- LinkedIn recommendations (what others say about them)
- Career trajectory (pivots that reveal values)
- Self-descriptions and philosophy statements

**What to Capture:**
- Their self-defined identity ("captain, coach and cheerleader")
- Values revealed by career choices
- Reputation themes from recommendations
- Unique positioning (only person doing X)

**Identity Signals Hierarchy (Best to Worst):**
1. **Their Own Words** - Quotes from About section
2. **Their Reputation** - What recommendations say
3. **Their Purpose** - Career pivots revealing values
4. **Unique Achievements** - Only they can claim
5. **Recent Activity** - Posts, articles, engagement

### 2. Recent Activity (CURRENT focus)

**What to Look For:**
- Posts in last 30-90 days
- Articles published
- Job changes
- Hiring activity
- Speaking engagements
- Award announcements

**Why This Matters:**
Current activity signals what's top of mind. A CEO posting about AI integration is more receptive than one posting about golf.

### 3. Company Context (WHERE they operate)

**What to Capture:**
- Company size and stage
- Industry challenges
- Recent news (acquisitions, expansions, challenges)
- Competitive positioning
- Geographic reach

**Best Practice:** Focus on one specific, evidence-based company fact.

### 4. AI Opportunity Mapping (BRIDGE to offer)

**The Question:**
"Given who they are and what they're dealing with, what AI opportunity would resonate?"

**Strong AI Opportunities:**
- Specific to their domain
- Connected to their current challenges
- Framed as questions, not assertions
- Make them the hero who could bring it to life
- Single, focused opportunity per lead

## Pre-Batch Setup (Efficiency Optimization)

Before visiting individual profiles, prepare the batch for maximum efficiency.

### Step 0: Extract All Profile URLs

From Sales Navigator search results, extract ALL profile URLs upfront:

```
1. Open search results page
2. For each visible lead, extract:
   - First name, Last name
   - Company, Title
   - Sales Navigator profile URL
3. Scroll to load more results
4. Repeat until batch complete (e.g., 25 leads)
5. Save to: ./workspace/campaign-{name}/batches/batch_XXX/leads_extracted.json
```

**Why:** Eliminates returning to search results between profile visits. Navigate URL-to-URL directly.

### Step 0b: Pre-Warm Company Research (Parallel)

Spawn company research agents for ALL leads BEFORE visiting profiles:

```python
# Extract unique companies from leads
companies = [lead["company"] for lead in leads]
unique_companies = list(set(companies))

# Spawn research agents in parallel
for company in unique_companies:
    Task(
        subagent_type="general-purpose",
        model="haiku",
        prompt=f"""Research {company} for lead campaign enrichment.

Gather:
1. Company size, industry, stage
2. Recent news (last 6 months)
3. Known challenges or opportunities
4. AI/digital transformation activity

Use Perplexity and Brave Search. Do NOT use browser tools.
Output: JSON with fields: size, industry, recentNews, challenges, aiActivity"""
    )
```

**Why:** Company research runs in background while profile visits proceed sequentially. Results ready when profiles complete.

**Expected Savings:** 30-50% time reduction (research no longer in critical path).

---

## Research Workflow

### Step 1: LinkedIn Profile Deep Read (Optimized)

**MANDATORY: Capture About Section First**

Before extracting any other data, capture the About section verbatim:

1. Navigate to profile
2. Locate About section (below headline)
3. Click "see more" if truncated
4. Copy ENTIRE text to `aboutSection.raw`
5. Extract mission statement if present

For detailed extraction process, see `references/about-section-extraction.md`.

**Single-Read Pattern:** Extract all profile data with minimal navigation.

```
For each profile URL from Step 0:
1. navigate(profile_url)
2. read_page(depth=15, filter="all") - Gets full accessibility tree
3. Scroll once to trigger lazy-loaded content
4. Extract from tree: About, Experience, Education, Skills, Interests
5. Save immediately to leads_extracted.json
6. Navigate directly to next URL (no search return)
```

**Why:** Single `read_page` call captures most data. Direct URL-to-URL navigation maximizes throughput.

**Optimized Flow:**
```
Extract URLs → Profile A (single read) → Profile B (single read) → Profile C...
```

### Step 2: Activity Scan
```
1. Check "Activity" tab for recent posts
2. Look for articles published
3. Note engagement patterns
4. Flag any hiring posts
```

### Step 3: Company Research
```
1. Company LinkedIn page
2. Recent news (Perplexity: "[Company] news 2025")
3. Size, industry, geographic focus
4. Any known challenges or opportunities
```

### Step 4: Opportunity Mapping
```
Given:
- Their identity signals
- Their current focus
- Their company context

Ask: "What AI opportunity would make them think 'they really get me'?"
```

## Subagent Delegation Pattern

For batch enrichment, use general-purpose agents:

```markdown
Research leads [X] through [Y] from the lead list.

For each lead, gather:
1. Individual Profile:
   - Self-description from About section
   - Key themes from recommendations
   - Career pivot insights

2. Recent Activity:
   - Posts/articles in last 90 days
   - Job changes or announcements

3. Company Context:
   - Company size and industry
   - Recent news or developments

4. AI Opportunity Ideas:
   - 2-3 potential angles based on findings

Save results incrementally to: ./workspace/campaign-{name}/batches/batch_XXX/leads_enriched.json

Use this format:
{
  "firstName": "...",
  "lastName": "...",
  "company": "...",
  "title": "...",
  "enrichment": {
    "individualProfile": "...",
    "recentActivity": "...",
    "companyContext": "...",
    "aiOpportunities": ["...", "..."]
  }
}
```

## Validation Checklist

Before moving to Phase 2, verify each lead has:

- [ ] **`aboutSection.raw` is populated (REQUIRED)** - Full About section captured verbatim
- [ ] At least one tier1 or tier2 identity signal exists
- [ ] Selected fact is PERSONAL (not company milestone)
- [ ] Company context sufficient for AI opportunity
- [ ] At least one AI opportunity idea mapped

**If `aboutSection.raw` is empty, return to the profile and capture it.**

For detailed validation rules, see `references/fact-quality-validation.md`.

## Output Format

Use the complete schema defined in `references/json-schema-enrichment.md`.

### Required Structure

```json
{
  "firstName": "Greg",
  "lastName": "Barclay",
  "company": "Slater and Gordon Lawyers",
  "title": "Transformation Director",
  "linkedInUrl": "https://linkedin.com/in/gregbarclay",
  "enrichment": {
    "aboutSection": {
      "raw": "[Full About section verbatim - REQUIRED]",
      "missionStatement": "[Extracted mission if present]"
    },
    "identitySignals": {
      "tier1_ownWords": {
        "fact": "[Quote from About section]",
        "source": "aboutSection",
        "verified": true
      },
      "tier2_reputation": {
        "fact": "Recommended as 'change management leader'",
        "source": "recommendations",
        "verified": true
      },
      "tier3_purpose": {
        "fact": "Career dedicated to organizational transformation",
        "source": "careerHighlights",
        "verified": true
      },
      "tier4_achievements": ["10 professional certifications including Stanford Innovation"],
      "tier5_activity": ["Transformation initiatives ongoing post CEO transition"]
    },
    "companyContext": {
      "size": "1000+",
      "industry": "Legal Services",
      "challenges": ["Post-CEO transition transformation"],
      "recentNews": "CEO transition March 2024"
    },
    "aiOpportunities": [
      {
        "opportunity": "Predict case complexity from intake for routing",
        "connectsTo": "tier1_ownWords",
        "framing": "what if AI could..."
      }
    ]
  },
  "personalisationHooks": "10 certifications including Stanford Innovation | Transformation Director | Recommended as 'change management leader'"
}
```

**CRITICAL:** The `aboutSection.raw` field is REQUIRED. Never proceed to Phase 2 without it.

## Quality Standards

1. **Single compelling fact** - Choose the ONE most powerful insight about the person
2. **Person-centric** - Facts should reveal WHO they are, prioritize individual over company
3. **Compelling framing** - "Known for zero-turnover teams" resonates stronger than tenure alone
4. **Verifiable claims** - Everything should be deducible from their public profile
5. **Focused opportunity** - Map several AI opportunities, select ONE for the message

## Next Phase

Once enrichment is validated, proceed to **Phase 2: Message Crafting** where we apply Identity-First methodology to write the actual messages.
