# Example Prompts for Website UX Audit Skill

These example prompts demonstrate how to invoke and work with this skill effectively.

---

## Basic Audit Request

```
Please conduct a UX audit of https://example.com/

The site is a B2B directory for [industry]. The main users are [user type] 
looking to find [what they're looking for].

I've attached screenshots of:
- Homepage (desktop and mobile)
- Main navigation expanded
- A few key section pages
```

---

## Detailed Audit Request with Context

```
I need a comprehensive UX audit of https://example.com/

ABOUT THE SITE:
- Purpose: Online marketplace for vintage furniture
- Launched: 2018
- Current issues: High bounce rate, low conversion to inquiry

PRIMARY USERS:
1. Interior designers searching for unique pieces
2. Homeowners looking for statement furniture
3. Dealers listing inventory

KEY SECTIONS TO ANALYSE:
- Homepage
- Search/browse experience
- Product detail pages
- Seller dashboard
- Contact/inquiry forms

SCREENSHOTS ATTACHED:
[homepage-desktop.png]
[homepage-mobile.png]
[search-results.png]
[product-page.png]
[mobile-nav.png]

Please also run PageSpeed Insights and incorporate those findings.

OUTPUT NEEDED:
- Main report with overall findings
- Separate section reports for each major area
- Recommendations organised by tier (implement now / needs info / future)
- Component and page specs ready for design handoff
```

---

## Quick Assessment Request

```
Can you do a quick UX review of https://example.com/?

I don't need full section reports - just the main findings and top 10 
recommendations. Focus on:
- Navigation issues
- Mobile experience
- Any obvious quick wins (Tier 1 items)

Here's a screenshot of the homepage: [attached]
```

---

## Audit with Design Handoff Focus

```
Please audit https://example.com/ with a focus on design handoff.

I need reports that my design team can use to begin work immediately on 
Tier 1 items without waiting for additional information.

For each section, include:
- Wireframes showing proposed layouts
- Component specifications with all states
- Content inventories showing what exists vs what's needed
- Clear separation of what can be built now vs what needs input

The designers should be able to start work on Monday with just these reports.
```

---

## Audit Focused on Implementation Planning

```
We're planning a redesign of https://our-site.com/

Please audit the current site and produce reports structured for sprint planning:

1. Tier 1 items should be ready to convert to development tickets
2. Tier 2 items should include the exact questions we need answered
3. Tier 3 items should be documented for our product roadmap

Include effort estimates (Low/Medium/High) for each Tier 1 recommendation 
so we can plan sprints appropriately.
```

---

## Competitive Analysis Request

```
Please audit these three competitor sites:
1. https://competitor-a.com
2. https://competitor-b.com  
3. https://competitor-c.com

All are in the [industry] space. I want to understand:
- What each does well (patterns to adopt)
- Common UX patterns across all three
- Unique approaches worth considering
- Issues we should avoid

For each site, categorise findings as:
- Tier 1: Patterns we could implement immediately
- Tier 2: Features that would need research/data
- Tier 3: Advanced features for future consideration
```

---

## Section-Specific Deep Dive

```
I've already seen your initial audit. Can you go deeper on the 
[specific section] of https://example.com/?

Specifically I need:
- Detailed component specifications for all UI elements
- Wireframes for desktop, tablet, and mobile
- Complete interaction documentation
- All Tier 1 items fully specified for immediate build

This section is our highest-traffic area and the redesign priority.
```

---

## Follow-Up: Clarifying Tier 2 Items

After receiving an audit, you might ask:

```
Thanks for the audit. For the Tier 2 items, I now have answers:

2.1 Audience metrics: 15,000 monthly visitors, 8,500 newsletter subscribers
2.2 Testimonials: Yes, we have permission from 3 advertisers
2.3 Pricing: Approved to show "starting from" ranges

Can you update the relevant section reports to move these to Tier 1 
with complete specifications now that we have the information?
```

---

## Follow-Up: Prioritisation Questions

```
Looking at your Tier 1 recommendations, we can only tackle 5 items 
this sprint. Based on effort vs impact, which 5 would you prioritise?

Also, are there any Tier 2 items where, if we got the information 
this week, they would become higher priority than the Tier 1 items?
```

---

## Follow-Up: Converting to Tickets

```
Can you convert the Tier 1 items from the [Section Name] report into 
a format suitable for JIRA tickets?

For each item, provide:
- Title
- Description
- Acceptance criteria
- Effort estimate (story points: 1/2/3/5/8)
- Dependencies on other tickets
```

---

## Requesting Specific Output Formats

```
Please conduct the UX audit with recommendations formatted as:

TIER 1 (Implement Now):
- Grouped by section
- Each item with: title, description, wireframe, effort, impact

TIER 2 (Needs Information):
- Formatted as a questionnaire I can send to the site owner
- Each question linked to which recommendations it unblocks

TIER 3 (Future):
- Formatted as product roadmap items with dependencies
```

---

## Notes for Best Results

**DO provide:**
- Site URL and basic context
- Screenshots (especially mobile and navigation states)
- Information about target users
- Known pain points or concerns
- Whether you need design handoff detail or high-level findings

**DO specify:**
- If you have constraints on what you can implement (technical, budget, time)
- If certain sections are higher priority than others
- If you already have answers to common Tier 2 questions

**DON'T assume:**
- Claude can see visual styling from HTML alone
- Claude has access to your analytics
- Claude knows your business constraints
- All Tier 1 recommendations are equally important for your situation

**ITERATE:**
The first audit provides a foundation. Ask follow-up questions to:
- Go deeper on specific sections
- Get more detailed wireframes
- Convert Tier 2 to Tier 1 once you have information
- Prioritise within tiers
- Format for your specific workflow

---

## Understanding the Tiers

### Tier 1: Implement Now
These recommendations can be actioned immediately by a design and development team without any additional input. All wireframes use existing content, all components can be built with available data.

**Why this matters:** Your team can start work on Monday without waiting for anyone.

### Tier 2: Requires Information
These recommendations are blocked by specific information that must come from the site owner or stakeholders. The reports document exactly what questions need answering.

**Why this matters:** You know exactly what to ask, and once answered, these become Tier 1.

### Tier 3: Future Enhancements
These are strategic improvements requiring significant new development, ongoing operations, or major decisions. They inform the product roadmap but aren't immediate implementation candidates.

**Why this matters:** You have a documented backlog for future planning.
