---
title: "Phase 2 Message Crafting"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Phase 2: Personalized Observation

## Purpose

Write a brief personalized observation for LinkedIn outreach - two sentences maximum. This shows you've done your homework without pitching anything.

## Context

This message follows "Thanks for connecting, {{firstName}}." and precedes a question about AI plans for 2026. You're speaking with CEOs, CIOs, and C-level executives - be conversational but professional.

## Structure

```
[Observation] + [Reaction/Closer]
```

1. **Observation** - What you noticed about them (specific, factual)
2. **Reaction** - A brief, genuine human response (not flattery)

## Good Closers (Vary These)

- "That's quite the pivot."
- "Bold ambition."
- "That's serious scale."
- "Impressive work."
- "Real commitment to the craft."
- "Takes courage to make that leap."
- "That perspective shapes leadership."
- "That trust is hard to earn."
- "Solid philosophy."
- "Real legacy."
- "Timely work."
- "Interesting crossover."
- "That longevity says something."
- "Well-deserved recognition."
- "Thoughtful approach."

## Examples

| Input Hook | Output |
|------------|--------|
| Pioneer of Buurtzorg nurse-led care model in Australia, revolutionising community care | Noticed you're leading the Buurtzorg nurse-led care model here in Australia. Impressive work. |
| Moved from customer intelligence in gambling to EdTech at Cluey Learning | Noticed you moved from gambling analytics to helping students succeed at Cluey. That's quite the pivot. |
| CFO of the Year Finalist, finance leadership at MILKRUN | Congrats on being a CFO of the Year Finalist. Well-deserved recognition. |
| Built MindSprout to 80+ staff across four regions in disability services | Impressive how you built MindSprout to over 80 staff across four regions. Real scale in disability services. |
| 12-year board commitment to Rosewood Care aged care provider | Impressed by your 12-year board commitment to Rosewood Care. Long-term thinking on Australia's ageing population. |
| Attended Rillet AI in accounting event at SF Tech Week, CFO at Fullstack | Noticed you attended Rillet's event on AI in accounting workflows during SF Tech Week. Good to see CFOs exploring this space. |
| Recent post about AI integration with carrier voice networks at Alianza | Noticed your recent post about AI integration with carrier voice networks at Alianza. Timely work in a fast-moving space. |
| Published Thinking Energy newsletter on energy transition topics | Been reading your Thinking Energy newsletter. Thoughtful content on the energy transition. |

## Rules

1. **Two sentences maximum** - No exceptions
2. **Start with** - "Saw," "Noticed," "Congrats on," "Impressed by," or similar
3. **No questions** - This is an observation, not an inquiry
4. **No AI pitch** - No "what if" statements or opportunity framing
5. **No em dashes** (—) - Dead giveaway of LLM writing
6. **No "which is [adjective]"** - Sounds artificial
7. **Vary closers** - Don't repeat the same closer in a batch
8. **Professional tone** - Appropriate for C-level executives
9. **Sound like a peer** - Acknowledging their work, not flattering them

## Fact Selection Rules

**Select facts in this order - never skip tiers:**

1. **tier1_ownWords** - REQUIRED if About section exists
2. **tier2_reputation** - What recommendations say (if no tier1)
3. **tier3_purpose** - Career pivots revealing values
4. **tier4_achievements** - Unique accomplishments
5. **tier5_activity** - Recent posts (LAST resort)

**Never use company facts for the observation sentence.**

### Company Facts to Avoid

- Employee count ("500 employees")
- Revenue milestones ("$10M ARR")
- Geographic expansion ("6 countries")
- Product metrics ("8M downloads")
- Funding announcements

These don't reveal WHO they are. Any executive at the company could claim them.

### What to Use Instead

- Their mission statement from About section
- How they describe their approach
- Career pivots that reveal values
- What others say about them

For detailed validation rules, see `references/fact-quality-validation.md`.

## Fact Quality Hierarchy

The fact you choose matters more than anything. A boring fact kills the message.

**Best to Worst:**

1. **Their Own Words** - Quote from their About section (REQUIRED if available)
2. **Their Reputation** - What recommendations say about them
3. **Their Purpose/Values** - Career pivots that reveal what they care about
4. **Unique Achievements** - Specific accomplishments only THEY can claim
5. **Recent Activity** - Posts, articles, event attendance (LAST RESORT)

**Compelling facts reveal WHO they are, not just WHAT they did.**

### Red Flags (Block Message Drafting)

Before writing any message, check for these issues:

- [ ] Using company milestone as primary fact
- [ ] Using reaction counts as hook ("119 reactions")
- [ ] Using tenure as primary fact ("20 years")
- [ ] Missing About section in enrichment
- [ ] Company announcement instead of personal post

If any red flag exists, return to Phase 1 enrichment.

## Pre-Send Checklist

Before finalizing each message:

- [ ] Contains only ONE verifiable fact
- [ ] Fact is deducible from their profile data
- [ ] Exactly two sentences
- [ ] No questions
- [ ] No AI pitch or "what if" statements
- [ ] No em dashes
- [ ] No "which is [adjective]" construction
- [ ] Closer varies from previous messages in batch
- [ ] Sounds like genuine peer acknowledgment

## Output Format

```json
{
  "firstName": "Arnold",
  "lastName": "Stroobach",
  "personalisedMessage": "Noticed you're leading the Buurtzorg nurse-led care model here in Australia. Impressive work.",
  "messageRationale": "FACT: Leading Buurtzorg model - verified from careerHighlights showing Executive Director at Buurtzorg Australia for 8+ years. CLOSER: 'Impressive work' - appropriate for healthcare innovation at scale."
}
```

## Quality Standards

1. **Pure observation** - Statement, then reaction; keep questions for the AI pitch
2. **Single fact** - One compelling insight is stronger than many
3. **Natural phrasing** - Use semicolons or periods to connect thoughts
4. **Professional tone** - Match executive communication style
5. **Varied closers** - Rotate through the Good Closers list across the batch
6. **Current relevance** - Focus on recent or defining achievements

## Next Phase

Once observations are drafted, proceed to **Phase 3: Quality Assurance** for validation and pilot review.
