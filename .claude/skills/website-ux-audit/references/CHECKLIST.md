---
title: "Checklist"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# UX Audit Checklist

Use this checklist during the audit process to ensure comprehensive coverage and proper tier classification.

---

## Phase 1: Data Gathering

### Site Exploration
- [ ] Homepage fetched and analysed
- [ ] Main navigation sections identified
- [ ] Site map documented
- [ ] All major section landing pages fetched
- [ ] Representative subpages fetched (1-2 per section)

### Screenshots Collected
- [ ] Homepage (desktop)
- [ ] Homepage (mobile)
- [ ] Mobile navigation open state
- [ ] Each major section landing page
- [ ] Key interactive elements (forms, search, filters)
- [ ] Any areas of specific concern

### Performance Data
- [ ] PageSpeed Insights run (mobile)
- [ ] PageSpeed Insights run (desktop)
- [ ] Core Web Vitals recorded
- [ ] Opportunities list captured
- [ ] Diagnostics list captured

---

## Phase 2: Analysis

### Visual Design Assessment
- [ ] Typography evaluated (fonts, hierarchy, readability)
- [ ] Colour palette assessed (cohesion, contrast, brand)
- [ ] Layout analysed (whitespace, density, grid)
- [ ] Imagery reviewed (quality, loading, relevance)
- [ ] Consistency checked across pages

### Information Architecture Assessment
- [ ] Navigation systems mapped
- [ ] Navigation clarity evaluated
- [ ] Content hierarchy assessed
- [ ] Labelling reviewed for clarity
- [ ] Duplicate/conflicting paths identified
- [ ] Orphaned content identified

### Content Quality Assessment
- [ ] Date currency checked (look for outdated references)
- [ ] Broken links/images noted
- [ ] Content gaps identified
- [ ] Readability assessed
- [ ] Marketing vs. utility balance evaluated

### Functionality Assessment
- [ ] Search functionality tested (if present)
- [ ] Forms evaluated
- [ ] Filters/sorting evaluated (if present)
- [ ] CTAs mapped and assessed
- [ ] User flows traced

### Technical Assessment
- [ ] PageSpeed scores evaluated
- [ ] Mobile responsiveness checked
- [ ] Obvious accessibility issues noted
- [ ] SEO foundations checked (headings, meta, URLs)

---

## Phase 3: Recommendation Classification

### Tier 1 Validation Checklist
For each recommendation classified as Tier 1, verify:

- [ ] Can be implemented using **existing** site content
- [ ] Does NOT require information from site owner
- [ ] Does NOT require access to backend systems
- [ ] Does NOT require new content creation (only reorganisation)
- [ ] Does NOT require third-party integration
- [ ] Does NOT require business decisions not yet made
- [ ] Wireframes use real content visible on current site
- [ ] Component specs can be fulfilled with available data

**If any checkbox fails → Reclassify as Tier 2**

### Tier 2 Documentation Checklist
For each Tier 2 recommendation, document:

- [ ] Specific information needed (not vague)
- [ ] Why this information isn't available from public site
- [ ] Who would provide this information
- [ ] Questions are actionable (site owner can answer directly)
- [ ] What can proceed once information is received

**Example of good Tier 2 documentation:**
```
Blocked by: Newsletter subscriber count
Questions for site owner:
1. How many active subscribers does The Background Buzz have?
2. How many subscribers does The Global Background Screener have?
3. Are you comfortable displaying these numbers publicly?

Design can proceed once we know:
- Actual subscriber counts
- Approval for public display
```

**Example of bad Tier 2 documentation:**
```
Blocked by: Need more information
Questions: What should this section contain?
```

### Tier 3 Validation Checklist
For each Tier 3 recommendation, verify:

- [ ] Requires NEW functionality (not just redesign)
- [ ] Requires ongoing operational commitment OR
- [ ] Requires significant new content creation OR
- [ ] Requires third-party integration OR
- [ ] Requires user authentication OR
- [ ] Requires architectural changes
- [ ] Dependencies are clearly documented
- [ ] Complexity explanation is provided

---

## Phase 4: Report Generation

### Main Report
- [ ] Executive summary written
- [ ] Site overview documented
- [ ] Performance summary included
- [ ] Cross-cutting issues identified
- [ ] Section summaries created
- [ ] **Recommendations organised by tier**
- [ ] **Tier 1 items have effort/impact ratings**
- [ ] **Tier 2 items have specific information needs**
- [ ] **Tier 3 items have dependencies documented**
- [ ] Implementation roadmap drafted
- [ ] Design handoff summary completed
- [ ] Information request summary compiled

### Section Reports
For each section report:

- [ ] Current state documented
- [ ] User flows (current and target) mapped
- [ ] **Tier 1 recommendations with wireframes**
- [ ] **Tier 2 recommendations with specific blockers**
- [ ] **Tier 3 recommendations with dependencies**
- [ ] Component specifications completed
- [ ] Page specifications completed
- [ ] Mobile considerations documented
- [ ] Success metrics defined
- [ ] Implementation checklist provided

### Quality Checks
- [ ] All claims grounded in evidence
- [ ] No hallucinated features
- [ ] **Tier classifications are accurate**
- [ ] **Tier 1 items genuinely implementable without external input**
- [ ] **Tier 2 blockers are specific and answerable**
- [ ] Effort estimates realistic
- [ ] Formatting consistent
- [ ] Files properly named
- [ ] Limitations acknowledged

---

## Common Issues Checklist

### Navigation Issues
- [ ] Multiple competing nav systems?
- [ ] Items appearing in multiple locations?
- [ ] Jargon/unclear labels?
- [ ] Broken or outdated links?
- [ ] Deep nesting (>3 levels)?

### Content Issues
- [ ] Dates older than 2 years?
- [ ] "Coming soon" placeholders?
- [ ] Dense text walls?
- [ ] Broken images?
- [ ] External links to defunct sites?

### Search & Discovery
- [ ] Missing search on content-heavy site?
- [ ] No filters on listing pages?
- [ ] Poor search result presentation?

### Mobile Issues
- [ ] Non-responsive elements?
- [ ] Touch targets too small?
- [ ] Horizontal scrolling required?
- [ ] Content hidden on mobile?

### Performance Issues
- [ ] Score below 50?
- [ ] LCP above 4 seconds?
- [ ] CLS above 0.25?
- [ ] Large unoptimised images?
- [ ] Render-blocking resources?

### Trust & Credibility
- [ ] Missing contact information?
- [ ] No social proof/testimonials?
- [ ] Outdated copyright year?
- [ ] Broken SSL?
- [ ] Amateur design elements?

---

## Tier Classification Quick Reference

### Tier 1: Implement Now ✓
- Reorganise existing content
- Add search to existing listings
- Create preview cards from existing data
- Fix broken navigation
- Improve layouts and visual hierarchy
- Add forms using standard patterns
- Simplify existing labels
- Collapse/expand existing content

### Tier 2: Requires Information ⏳
- Display metrics (need actual numbers)
- Show testimonials (need quotes and permission)
- Add accreditation badges (need which companies qualify)
- Display pricing (need rates and approval)
- Consolidate domains (need technical access)
- Add author attribution (need author data)

### Tier 3: Future Enhancements 🔮
- User reviews/ratings system
- Comparison tools with standardised data
- Guided wizards with recommendation logic
- User accounts and saved content
- Third-party integrations
- Self-service purchase flows
- Content hubs requiring editorial process
- ML-powered recommendations

---

## Design Handoff Validation

Before delivering reports, verify the design team can:

- [ ] Understand current state without visiting the site
- [ ] Know which pages need redesign
- [ ] See wireframes for all Tier 1 layouts
- [ ] Understand all required components
- [ ] Know component states (default, hover, error, etc.)
- [ ] Have content inventories showing what exists
- [ ] Understand mobile requirements
- [ ] Begin Tier 1 work immediately
- [ ] Know exactly what questions to ask for Tier 2
- [ ] Have Tier 3 items documented for backlog
