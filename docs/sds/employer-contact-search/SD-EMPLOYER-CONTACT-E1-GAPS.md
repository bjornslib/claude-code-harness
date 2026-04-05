---
title: "Employer Contact Research Agent — Quality Gap Closure"
description: "Solution design for closing quality gaps identified during E2E testing of the DSPy employer contact researcher"
version: "1.0.0"
last-updated: 2026-04-05
status: active
type: sd
grade: authoritative
prd_id: PRD-EMPLOYER-CONTACT-001
---

# SD-EMPLOYER-CONTACT-E1-GAPS: Quality Gap Closure

## 1. Context

The employer contact research agent (PRD-EMPLOYER-CONTACT-001 E1) was implemented via a 30-node pipeline. The core architecture works: DSPy ReAct agent with Perplexity + web search tools, per-observation extraction, ChainOfThought deduplication, Predict classification. Live E2E testing against 5 real Australian employers revealed quality gaps that this SD addresses.

### E2E Test Results (Current State)

| Employer | Contacts | Named | Known Email Found | Known Phone Found | Known Manager Found |
|----------|----------|-------|-------------------|-------------------|---------------------|
| Kresta Blinds | 6 | 3 (directors) | krestacommercial@ (partial) | (08) 6370 2614 | No (Samantha Bradshaw) |
| SICE ANZ | 9 | 3 (management) | anzsice@, anzsicedpo@, anzsicecsr@ | +61 3 8256 6900 | No (Alex Xu) |
| Vanguard Investments | 12 | 8 (HR team + sales) | adviserservices@, institutional@ | 4 numbers | No (Adam Mariani) |
| Premier Proline | 4 | 1 (trades) | proline@hydroil.com.au | (08) 8347 1700 | No (Jaime Macdonald) |
| Medatech Australia | 4 | 0 | sales@medatech.com.au (exact!) | +61 (03) 9329 7355 (exact!) | No (David Linke) |

**Pattern**: Phone/email discovery is strong. Named HR/payroll contacts are weak — the agent finds directors and public-facing staff but not the specific HR/payroll people who handle employment verification.

---

## 2. Gap Inventory

### GAP-A: ExtractContacts lacks few-shot examples
**Priority**: P1 (directly improves extraction quality)
**Current**: `dspy.Predict(ExtractContacts)` has no demos. The classifier has `CLASSIFIER_EXAMPLES` demos that improved classification significantly.
**Fix**: Add 4+ `dspy.Example` objects to `self.extract_contacts.demos` showing correct extraction from Perplexity response text. Include examples of: named person with title+email+phone, department-only contact, contact form URL detection, and phone number formatting.
**Effort**: Small (1-2 hours)

### GAP-B: No fetch_url tool for ReAct agent
**Priority**: P1 (biggest quality uplift potential)
**Current**: ReAct agent can only search via Perplexity API (which synthesizes web content). It cannot visit specific pages (e.g., kresta.com.au/showroom/qld/ which has QLD-specific phone numbers, or team/about pages with named HR staff).
**Fix**: Add a `fetch_url(url: str) -> str` async tool that fetches a URL and returns its text content (stripped HTML). Register alongside perplexity_search and web_search. The agent decides which URLs to visit based on Perplexity's citations.
**Implementation**: Use `aiohttp` to fetch the URL, `BeautifulSoup` or simple regex to strip HTML tags, return first 3000 chars. Rate limit to max 3 fetches per research run.
**Effort**: Medium (2-4 hours)

### GAP-C: Filter contacts without phone or email before classification
**Priority**: P2 (reduces noise, improves classifier accuracy)
**Current**: Named contacts without any phone or email (e.g., "Mingming Zhang, Executive Director" with no contact details) are passed to the classifier and end up as T7 named_poc — useless for outreach.
**Fix**: After extraction and before classification, discard contacts where `name is not None` but `phone is None AND email is None`. Keep anonymous contacts if they have phone or email (department lines).
**Effort**: Small (30 min)

### GAP-D: Logfire observability spans
**Priority**: P2 (essential for production monitoring)
**Current**: No Logfire instrumentation on DSPy module calls. Can't track latency, token usage, or tool call patterns per step.
**Fix**: Add `logfire.span()` around each DSPy call:
- `researcher.research()`: span per ReAct iteration (tool name, query, response length)
- `deduplicator.deduplicate()`: span with input/output contact counts
- `classifier.classify_and_prioritise()`: span with named_poc/general counts
- `extract_contacts`: span with extraction count per observation
**Effort**: Medium (2-3 hours)

### GAP-E: Classifier tuning for Grok LM
**Priority**: P3 (quality of life)
**Current**: Classifier with Grok 4.1 Fast sometimes classifies named people as "general" (e.g., Yosu Zubizarreta at SICE). The demos help but Grok may need stronger instruction or model-specific tuning.
**Fix**: Test with different LMs for classification step (Claude Sonnet via `dspy.context(lm=...)` — may be more accurate than Grok for structured JSON classification). Also consider using `dspy.ChainOfThought` instead of `dspy.Predict` for classification to force reasoning.
**Effort**: Small (1-2 hours experimentation)

### GAP-F: Deduplication strategy
**Priority**: P3 (currently skipped)
**Current**: Dedup via DSPy ChainOfThought is inconsistent — sometimes inflates contact count, sometimes over-merges. Currently skipped in E2E testing.
**Fix**: Two options:
1. **Deterministic dedup**: Simple Python-based dedup by (email, phone) exact match + fuzzy name match (Levenshtein). No LM needed.
2. **Hybrid**: Deterministic first pass (exact email/phone match), then DSPy ChainOfThought for fuzzy cases only (same person different name format).
**Recommendation**: Start with option 1 (deterministic). Only add LM-based fuzzy dedup if needed.
**Effort**: Medium (2-3 hours)

### GAP-G: Service.py type mapping completion
**Priority**: P2 (required for DB integration)
**Current**: `_to_employer_contact()` and `_to_additional_contact()` converters exist but haven't been tested with live data + DB. The `EntityType` import and field mapping need verification against the actual `models/contacts.py` schema.
**Fix**: Run integration test with live DB (or dry_run with type validation). Fix any remaining field mismatches.
**Effort**: Small (1-2 hours)

### GAP-H: Known contact discovery
**Priority**: P3 (research quality ceiling)
**Current**: The agent doesn't find specific known contacts (Samantha Bradshaw at Kresta, Alex Xu at SICE). These people likely appear on LinkedIn, RocketReach, or company websites but Perplexity's search doesn't surface them.
**Fix**: This ties to GAP-B (fetch_url). If the agent can visit LinkedIn profiles or company team pages cited by Perplexity, it may discover specific named contacts. Also consider adding a LinkedIn search tool (requires Pinchtab MCP for authenticated access).
**Effort**: Large (depends on GAP-B + potential LinkedIn integration)

---

## 3. Implementation Sequence

```
Phase 1 (Quick wins, 1 session):
  GAP-C: Filter contacts without phone/email     (30 min)
  GAP-A: ExtractContacts demos                    (1-2 hours)
  GAP-F: Deterministic dedup                      (2-3 hours)

Phase 2 (Quality uplift, 1-2 sessions):
  GAP-B: fetch_url tool for ReAct                 (2-4 hours)
  GAP-G: Service.py type mapping + DB test        (1-2 hours)
  GAP-E: Classifier LM tuning                     (1-2 hours)

Phase 3 (Observability + stretch):
  GAP-D: Logfire spans                            (2-3 hours)
  GAP-H: Known contact discovery (LinkedIn)       (depends on tooling)
```

---

## 4. Success Criteria

After Phase 1+2 completion, the following E2E benchmarks should be met:

| Metric | Current | Target |
|--------|---------|--------|
| Contacts per employer | 4-12 | 5-15 |
| Named contacts with phone or email | 0-2 | 2-5 |
| Known email recovery rate | 40% (2/5) | 60%+ |
| Known phone recovery rate | 80% (4/5) | 90%+ |
| Contacts with no phone AND no email | 30-50% | <10% (filtered) |
| named_poc classification accuracy | ~60% | >85% |
| Research time per employer | 80-130s | <120s |

## Implementation Status

| Gap | Status | Date |
|-----|--------|------|
| GAP-A | Planned | - |
| GAP-B | Planned | - |
| GAP-C | Planned | - |
| GAP-D | Planned | - |
| GAP-E | Planned | - |
| GAP-F | Planned | - |
| GAP-G | Planned | - |
| GAP-H | Planned | - |
