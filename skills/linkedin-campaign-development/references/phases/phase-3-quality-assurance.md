# Phase 3: Quality Assurance

## Purpose

Validate messages through two complementary methods:
1. **Perplexity Full-Context Check** - AI sense-check with complete context
2. **Pilot User Review** - Human review of ~5 representative leads

## Part 1: Perplexity Full-Context Validation

### Why Full Context Matters

Previous approach: Send only the message for validation.
**Problem**: Perplexity couldn't evaluate if the fact was accurate or the opportunity was relevant.

New approach: Send enrichment + message + campaign brief together.
**Benefit**: Perplexity can validate factual accuracy AND strategic alignment.

### Perplexity Prompt Template

```markdown
I'm validating a personalized LinkedIn outreach message. Please check:

1. **Factual Accuracy**: Is the observation about this person accurate based on their profile?
2. **Role Alignment**: Does the AI opportunity match their actual role and responsibilities?
3. **Identity-First Quality**: Does the message focus on WHO they are, not just WHAT they did?
4. **Tone Check**: Does it sound conversational (coffee shop) or like marketing copy?

## Lead Information
- Name: {firstName} {lastName}
- Title: {title}
- Company: {company}

## Enrichment Data
{paste full enrichment from Phase 1}

## Proposed Message
{paste personalized message}

## Campaign Context
- Offer: AI Profit Multiplier Accelerator
- Target: COO/CEO-level executives at SME/Mid-sized businesses
- Goal: Book discovery calls

## Specific Questions
1. Is the fact I'm leading with verifiable from their public profile?
2. Does the AI opportunity make sense for their role (not their team's role)?
3. Any red flags or improvements you'd suggest?
```

### What to Look For in Perplexity Response

**Green Flags (Proceed):**
- Fact confirmed as accurate
- Role alignment validated
- Tone assessed as conversational
- No factual concerns

**Yellow Flags (Review):**
- Slight role mismatch (CEO vs team responsibility)
- Fact is old (2021 achievement in 2025)
- Opportunity is generic

**Red Flags (Revise):**
- Factual inaccuracy
- Wrong company or title
- Significant role mismatch
- Marketing speak detected

### Batch Validation Pattern

For efficiency, validate in groups of 5-10:

```markdown
I'm validating 5 LinkedIn outreach messages. For each, check:
1. Factual accuracy
2. Role alignment
3. Identity-First quality
4. Tone (conversational vs marketing)

[Lead 1]
Name: ...
Enrichment: ...
Message: ...

[Lead 2]
...
```

### Flagging for Revision

Create a revision list for any messages that fail validation:

```json
{
  "firstName": "Anna",
  "lastName": "Peters",
  "issue": "AI opportunity implies CEO handles queries directly",
  "currentMessage": "...",
  "suggestedFix": "Reframe to dashboard/visibility rather than query handling"
}
```

## Part 2: Pilot User Review

### Purpose

Human review catches things AI misses:
- Cultural nuances
- Industry-specific language
- Strategic alignment with sales approach
- "Would I actually send this?" gut check

### Pilot Selection Criteria

Select ~5 leads that represent:
- Different industries
- Different seniority levels
- Different identity types (own words, reputation, achievement)
- Any borderline cases from Perplexity check

### Review Format

Present to user:

```markdown
## Pilot Review: [Lead Name]

**Profile Summary:**
- Title: [title] at [company]
- Identity Signal: [what we're leading with]

**Enrichment Highlights:**
[2-3 bullet summary of key findings]

**Proposed Message:**
> [full message]

**Rationale:**
[why we chose this fact and this AI opportunity]

**Questions for Review:**
1. Does this feel like something you'd send?
2. Any industry-specific concerns?
3. Should we adjust the AI opportunity?
```

### User Feedback Integration

Based on user feedback, categorize responses:

| Feedback | Action |
|----------|--------|
| "Perfect, send it" | Mark approved |
| "Minor tweak needed" | Apply edit, mark approved |
| "Wrong approach" | Flag for complete rewrite |
| "Good pattern, scale it" | Note pattern for Phase 4 |

### Approval Threshold

Before proceeding to Phase 4:
- At least 4/5 pilot messages approved
- Any patterns from feedback documented
- Revision approach for flagged leads agreed

## QA Checklist

### Perplexity Validation Complete
- [ ] All messages checked with full context
- [ ] Factual accuracy confirmed for each
- [ ] Role alignment validated
- [ ] Flagged messages listed for revision

### Pilot Review Complete
- [ ] 5 representative leads reviewed with user
- [ ] User feedback incorporated
- [ ] Patterns documented for scaling
- [ ] Approval to proceed to Phase 4

### Revisions Applied
- [ ] Flagged messages revised
- [ ] Revised messages re-validated
- [ ] All messages meet Identity-First criteria

## Output: Approved Message Set

After QA, you should have:

```json
{
  "approvedMessages": [
    {
      "firstName": "...",
      "lastName": "...",
      "personalisedMessage": "...",
      "qaStatus": "approved",
      "validationNotes": "Perplexity confirmed, user approved"
    }
  ],
  "pendingRevision": [
    {
      "firstName": "...",
      "lastName": "...",
      "currentMessage": "...",
      "revisionNeeded": "...",
      "qaStatus": "revision_required"
    }
  ],
  "patternsForScaling": [
    "User preferred X approach for industry Y",
    "Avoid Z phrasing for executive level"
  ]
}
```

## Common QA Issues

1. **Stale Facts** - Achievement from 4+ years ago
   - Fix: Find more recent activity or career evolution

2. **Role Confusion** - Opportunity for their team, not them
   - Fix: Elevate to strategic/oversight level

3. **Generic Opportunities** - "Improve efficiency"
   - Fix: Make domain-specific

4. **Multiple Facts** - Stacking observations
   - Fix: Pick the single best one

5. **Marketing Tone** - Reads like a sales pitch
   - Fix: Simplify language, add genuine curiosity

## Next Phase

Once QA is complete and user has approved the pilot, proceed to **Phase 4: Scale** to apply the approved approach to remaining leads.
