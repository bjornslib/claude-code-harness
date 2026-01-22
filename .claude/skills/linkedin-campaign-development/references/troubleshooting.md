# Troubleshooting Guide

Common issues and solutions when running LinkedIn campaign development.

---

## Enrichment Issues (Phase 1)

### Can't Find Identity Signal

**Symptom:** Lead has minimal About section, no recommendations, generic career history.

**Solutions:**
1. **Check recent activity** - Posts may reveal personality/values
2. **Company research** - Their role at company may reveal identity
3. **Industry publications** - Search for articles/quotes by them
4. **Perplexity deep search** - `"[Name]" "[Company]" interview OR quote OR profile`

**If still nothing:**
- Flag lead as "low enrichment"
- Use company-focused approach as fallback
- Consider deferring lead

### Stale Profile Data

**Symptom:** Profile shows old role, company no longer exists, or dates don't match.

**Solutions:**
1. **Cross-reference sources** - Check company website, news articles
2. **Look for recent activity** - If posting recently, profile may just be outdated
3. **Perplexity verification** - `[Name] current role [Year]`

**If clearly outdated:**
- Mark lead as "needs verification"
- Don't include in current campaign

### Too Much Information

**Symptom:** Lead has extensive profile with multiple compelling facts.

**Solutions:**
1. **Apply hierarchy** - Own words > Reputation > Purpose > Achievement
2. **Pick ONE best fact** - Resist temptation to stack
3. **Save extras for follow-up** - Document in enrichment for Message 2

---

## Message Crafting Issues (Phase 2)

### Em-Dash Slippage

**Symptom:** Messages contain `-` instead of semicolons.

**Cause:** LLM default writing style.

**Fix:**
1. Add explicit instruction: "Use semicolons (;) to connect thoughts, NEVER em-dashes (-)"
2. Post-processing find/replace: `—` → `;` or ` - ` → `; `
3. Review each batch for this pattern

### Generic AI Opportunities

**Symptom:** Messages use vague opportunities like "improve efficiency" or "streamline operations."

**Cause:** Insufficient enrichment or lazy templating.

**Fix:**
1. Return to enrichment - what SPECIFIC challenge do they face?
2. Make domain-specific: "predict equipment failures" not "improve maintenance"
3. Review campaign brief examples for inspiration

### Role Mismatch

**Symptom:** AI opportunity assumes wrong level of responsibility (CEO "handling queries").

**Cause:** Not thinking about what the PERSON does vs what their TEAM does.

**Fix:**
1. CEO/COO → Strategic oversight, visibility, decision support
2. Director → Department optimization, team enablement
3. Manager → Operational efficiency, direct execution

**Reframe examples:**
- Wrong: "handle routine queries" → Right: "single dashboard view"
- Wrong: "process applications" → Right: "spot bottlenecks before they impact"
- Wrong: "write reports" → Right: "instant insight synthesis"

### Message Too Long

**Symptom:** Message exceeds 2-3 sentence guideline.

**Fix:**
1. Remove any stacked facts
2. Simplify observation (one clause, not two)
3. Shorten AI opportunity question
4. Target: 250-300 characters total

---

## Quality Assurance Issues (Phase 3)

### Perplexity Returns "Can't Verify"

**Symptom:** Perplexity unable to confirm fact from the message.

**Possible causes:**
1. Fact is from private profile section (recommendations only visible when logged in)
2. Fact is paraphrased beyond recognition
3. Fact is outdated/incorrect

**Solutions:**
1. Use more verifiable facts (job changes, awards, recent posts)
2. Quote exactly when possible
3. Cross-reference with Sales Navigator data

### Pilot Review Delays

**Symptom:** User hasn't responded to pilot review request.

**Solutions:**
1. Present shorter format - 3 leads instead of 5
2. Offer specific questions vs open review
3. Provide deadline: "Need approval by [date] to send on schedule"

### Inconsistent User Feedback

**Symptom:** User approves some approaches but not others without clear pattern.

**Solutions:**
1. Ask for explicit criteria: "What specifically didn't work about this one?"
2. Create A/B options: "Do you prefer approach A or B?"
3. Document the pattern for scaling

---

## Scaling Issues (Phase 4)

### Context Exhaustion

**Symptom:** Agent forgets instructions mid-batch, quality degrades.

**Solutions:**
1. Reduce batch size (10-15 instead of 25)
2. Include quality checklist in EVERY batch instruction
3. Reference Phase 2 message-crafting guide explicitly

### Pattern Drift

**Symptom:** Later messages don't match approved pilot style.

**Solutions:**
1. Include 2-3 approved examples in batch instructions
2. Mandatory spot-check after each batch
3. Compare first and last message in each batch

### Incremental Save Failures

**Symptom:** Data loss when context runs out mid-batch.

**Solutions:**
1. Explicitly instruct: "Save after EACH lead, not at end"
2. Use separate batch files per agent if parallel processing
3. Check batch file exists and has content before proceeding

---

## Finalization Issues (Phase 5)

### Encoding Issues in CSV

**Symptom:** Characters like `Ã¢Â€Â™` appear in exported CSV.

**Cause:** Mixing UTF-8 and Latin-1 encoding.

**Fix:**
```python
# Read with fallback
try:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    with open(file, 'r', encoding='latin-1') as f:
        content = f.read()

# Common replacements
replacements = {
    'Ã¢Â\x80Â\x99': "'",
    'Ã¢Â\x80Â\x94': "-",
    'â€™': "'",
    'â€"': "-",
}
for old, new in replacements.items():
    content = content.replace(old, new)

# Write as UTF-8
with open(file, 'w', encoding='utf-8') as f:
    f.write(content)
```

### Merge Duplicates

**Symptom:** Same lead appears multiple times after merging batches.

**Cause:** Lead was in multiple batch files.

**Fix:**
```python
seen = set()
unique_leads = []
for lead in all_leads:
    key = (lead['firstName'], lead['lastName'], lead['company'])
    if key not in seen:
        seen.add(key)
        unique_leads.append(lead)
```

### Export Format Mismatch

**Symptom:** Tool (Multilead, etc.) rejects import file.

**Solutions:**
1. Check required fields match exactly
2. Verify JSON is valid (use validator)
3. Check for null values in required fields
4. Ensure proper character escaping

---

## General Issues

### Campaign Brief Not Found

**Symptom:** Trying to start campaign but no brief in `campaigns/` directory.

**Fix:**
1. Create brief using template in `examples/campaign-brief-template.md`
2. Include: offer, target persona, value proposition, message templates
3. Save to `campaigns/[campaign-name].md`

### Lost Progress / Context Compacted

**Symptom:** Returning to campaign after break, unsure of status.

**Recovery steps:**
1. Check `output/` for latest batch files
2. Review `all_leads_master.csv` for status
3. Read last batch file to see where processing stopped
4. Resume from appropriate phase

### Subagent Not Following Instructions

**Symptom:** Delegated agent produces wrong format or misses requirements.

**Solutions:**
1. Be more explicit - show exact expected output format
2. Include checklist at end of instructions
3. Reduce scope - smaller batches with clearer focus
4. Use haiku model for validation tasks (faster feedback loop)

---

## Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Em-dashes | Find/replace `—` with `;` |
| TM/R symbols | Remove `(TM)`, `(R)`, `®`, `™` |
| Smart quotes | Replace `'` `"` with `'` `"` |
| Generic opportunity | Add industry/role specificity |
| Stacked facts | Delete to single best fact |
| Too long | Cut to 2 sentences max |
| Role mismatch | Elevate to strategic level |
| Missing enrichment | Perplexity deep search |

---

## When to Escalate to User

Escalate rather than guess when:

1. **Industry unfamiliar** - Ask user for domain guidance
2. **Conflicting signals** - Lead seems both good and bad fit
3. **Sensitive topic** - Company in legal trouble, recent scandal
4. **Strategic decision** - Which approach for entire industry category
5. **No good option** - Can't find compelling angle for lead

Present issue clearly with options for user decision.
