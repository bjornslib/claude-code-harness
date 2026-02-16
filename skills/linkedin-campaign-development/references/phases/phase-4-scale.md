# Phase 4: Scale

## Purpose

Apply the approved approach from Phase 3 to all remaining leads. This phase is about efficient execution while maintaining quality.

## Pre-Scale Checklist

Before scaling, confirm:
- [ ] Pilot messages approved in Phase 3
- [ ] Patterns documented from user feedback
- [ ] Revision approach agreed for any flagged items
- [ ] Batch structure planned

## Batch Processing Strategy

### Recommended Batch Size

| Total Leads | Batch Size | Reasoning |
|-------------|------------|-----------|
| < 20 | All at once | Manageable in single pass |
| 20-50 | 10 per batch | Balance between efficiency and quality |
| 50-100 | 15-20 per batch | Larger batches, spot-check quality |
| 100+ | 20-25 per batch | Maximum manageable batch |

### Subagent Delegation Pattern

For each batch, delegate to general-purpose agent:

```markdown
Process leads [X] through [Y] following the approved Identity-First approach.

## Approved Patterns (from Phase 3)
{paste patterns documented from pilot review}

## Instructions
For each lead:
1. Review enrichment data from Phase 1
2. Apply Identity-First message pattern:
   - Lead with WHO they are (identity signal)
   - Use semicolon connection
   - End with role-appropriate AI opportunity question
3. Write message rationale

## Quality Checks
- Single fact only (no stacking)
- Semicolons, not em-dashes
- Question ending ("what if..." or "do you think...")
- Role-appropriate AI opportunity
- No marketing speak

## Save Pattern
After each lead, save to: output/batch_XXX/messages_draft.json

## Output Format
{
  "firstName": "...",
  "lastName": "...",
  "personalisedMessage": "...",
  "messageRationale": "..."
}
```

### Incremental Save Protocol

**Critical**: Save after EVERY lead processed to prevent data loss.

```python
# Pattern for each lead
def process_lead(lead, batch_file):
    # 1. Generate message
    message = create_identity_first_message(lead)

    # 2. Read existing batch
    existing = read_json(batch_file)

    # 3. Append new lead
    existing.append(message)

    # 4. Write back immediately
    write_json(batch_file, existing)
```

### Parallel Processing

If using multiple agents for large campaigns:

```
Agent 1: Leads 1-25   → output/batch_001/
Agent 2: Leads 26-50  → output/batch_002/
Agent 3: Leads 51-75  → output/batch_003/
```

**Important**: Each agent writes to separate batch file to avoid conflicts.

## Quality Spot-Checks

### Per-Batch Validation

After each batch, spot-check 20%:

1. Select 3-4 random messages from batch
2. Quick Perplexity validation (can batch together)
3. Check for pattern drift:
   - Are messages still Identity-First?
   - Any em-dash slippage?
   - Role alignment maintained?

### Red Flags to Catch Early

| Pattern | Issue | Fix |
|---------|-------|-----|
| Multiple semicolons | Over-structured | Simplify to one |
| "Impressed by..." | Praise-heavy | Use observation instead |
| Team-level opportunity | Role mismatch | Elevate to strategic |
| Same AI opportunity repeated | Lazy templating | Customize per lead |

## Handling Edge Cases

### Leads with Minimal Enrichment

If enrichment data is thin:

1. **Flag for additional research** - Use Perplexity to find more
2. **Use company context** - If individual data scarce, lean on company
3. **Acknowledge limitation** - Some leads may need to be deferred

### Leads with Multiple Strong Facts

If multiple compelling facts available:

1. **Pick the BEST one** - Don't stack
2. **Save others for follow-up** - Note in enrichment for Message 2
3. **Choose identity over achievement** - WHO over WHAT

### Industry-Specific Adjustments

Apply patterns from pilot feedback:

```markdown
## Industry Adjustments (from Phase 3)

Mining/Resources:
- Emphasize operational efficiency
- Downtime and contract language resonates

Healthcare/NDIS:
- Focus on participant outcomes
- Compliance awareness important

Legal/Professional Services:
- Complexity and routing language works
- Transformation angle for change leaders
```

## Progress Tracking

### Batch Status Template

```markdown
## Batch [X] Status

- Leads: [start] to [end]
- Status: [pending/in_progress/complete]
- Messages drafted: [count]
- Spot-check passed: [yes/no]
- Issues found: [list any]

### Leads Processed
| # | Name | Company | Status |
|---|------|---------|--------|
| 1 | ... | ... | Complete |
| 2 | ... | ... | Complete |
```

### Campaign Progress

```markdown
## Overall Campaign Progress

- Total leads: [X]
- Phase 1 (Enrichment): Complete
- Phase 2 (Message Crafting): [X/Y] batches
- Phase 3 (QA): Complete (pilot approved)
- Phase 4 (Scale): In Progress
  - Batch 1: Complete (25 leads)
  - Batch 2: In Progress (12/25)
  - Batch 3: Pending
```

## Output: All Messages Drafted

After Phase 4, you should have:

```
output/
├── batch_001/
│   └── messages_draft.json (25 leads)
├── batch_002/
│   └── messages_draft.json (25 leads)
├── batch_003/
│   └── messages_draft.json (25 leads)
└── all_leads_status.json (tracking)
```

## Common Scaling Issues

1. **Pattern Drift** - Later batches diverge from approved approach
   - Fix: Re-reference Phase 3 patterns each batch

2. **Context Exhaustion** - Agent forgets instructions mid-batch
   - Fix: Smaller batches, clearer instructions

3. **Templating Creep** - Messages become formulaic
   - Fix: Emphasize variety in openers and AI opportunities

4. **Spot-Check Skip** - Rush to complete without validation
   - Fix: Mandatory 20% check per batch

## Next Phase

Once all batches are processed and spot-checks passed, proceed to **Phase 5: Finalize** for merge and final user review.
