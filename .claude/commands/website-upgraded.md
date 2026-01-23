# Website Upgraded - End-to-End UX Improvement Pipeline

Transform any website URL into implementation-ready specifications through a comprehensive 3-stage automated pipeline.

## Overview

**Input Required:** Website URL only

**Output Produced:**
- Comprehensive UX audit report with prioritized recommendations
- Visual design concept mockups for improvements
- Implementation-ready specifications (Briefs, Research, JSONC Specs)

**Handoff:** Specifications are ready for `frontend-dev-expert` agent or human developer to implement.

## Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 0: Setup (ask user for output directory)                  │
│ ─────────────────────────────────────────────────────────────── │
│ • Ask user where to write all outputs                           │
│ • Default: ./workspace/{site-name}-improvements/                │
│ • Create directory structure                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: UX Audit (website-ux-audit skill)                      │
│ ─────────────────────────────────────────────────────────────── │
│ • Fetch and analyze the website                                 │
│ • Capture screenshots (desktop + mobile)                        │
│ • Run PageSpeed Insights performance analysis                   │
│ • Generate UX report with Tier 1/2/3 recommendations            │
│ Output: ux-audit-{site}/00-main-report.md + section reports     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Design Concepts (website-ux-design-concepts skill)     │
│ ─────────────────────────────────────────────────────────────── │
│ • Extract Tier 1 (implementable now) recommendations            │
│ • Generate design prompts for each improvement                  │
│ • Create visual mockup images using Gemini Pro                  │
│ Output: design-concepts/{section}-mockup.png files              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: Implementation Specs (design-to-code skill, Steps 1-3) │
│ ─────────────────────────────────────────────────────────────── │
│ • Generate PRD-style brief from each mockup                     │
│ • Research components (shadcn, Magic UI, existing patterns)     │
│ • Create JSONC specifications with component mapping            │
│ Output: specs/{section}-brief.md, specs/{section}-spec.jsonc    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ HANDOFF: Ready for Implementation                               │
│ ─────────────────────────────────────────────────────────────── │
│ • Spawn frontend-dev-expert agent with JSONC specs              │
│ • Or hand off to human developer                                │
│ • Specs include: components, sources, install commands          │
└─────────────────────────────────────────────────────────────────┘
```

## Execution

### Quick Start
```
/website-upgraded https://example.com
```

### With Options
```
/website-upgraded https://example.com --sections=homepage,navigation --resolution=2K
```

## Detailed Execution Steps

### Stage 0: Setup

**FIRST ACTION** - Before any analysis, ask the user where to write outputs.

**Use AskUserQuestion:**
```
Question: "Where should I save the UX audit reports, design mockups, and implementation specs?"
Header: "Output Dir"
Options:
1. "./workspace/{site-name}-improvements/" (Recommended) - Create in local workspace directory
2. "./output/{site-name}/" - Create in output directory
3. "Specify custom path" - Provide a different location
```

**Extract site name from URL:**
- `https://preemploymentdirectory.com` → `preemploymentdirectory`
- `https://www.example.edu/page` → `example`
- `https://sub.domain.org` → `domain`

**Create directory structure:**
```bash
OUTPUT_DIR="./workspace/{site-name}-improvements"
mkdir -p "$OUTPUT_DIR"/{ux-audit,design-concepts,specs}/{screenshots,performance}
```

**Directory structure created:**
```
workspace/{site-name}-improvements/
├── ux-audit/
│   ├── 00-main-report.md
│   ├── 01-homepage.md
│   ├── screenshots/
│   │   ├── homepage-desktop.png
│   │   └── homepage-mobile.png
│   └── performance/
│       └── pagespeed-results.json
├── design-concepts/
│   ├── navigation-draft.png
│   ├── navigation-final.png
│   └── ...
└── specs/
    ├── navigation-brief.md
    ├── navigation-research.md
    └── navigation-spec.jsonc
```

**Confirm with user:**
```
Output directory: ./workspace/{site-name}-improvements/

All reports, mockups, and specs will be saved here.
Proceed with UX audit?
```

---

### Stage 1: UX Audit

**Invoke:** `Skill("website-ux-audit")`

**Write outputs to:** `{OUTPUT_DIR}/ux-audit/`

1. **Discovery Phase**
   - Fetch homepage and map site structure
   - Identify all major sections
   - Capture screenshots (desktop: 1440px, mobile: 375px)
   - Run PageSpeed Insights

2. **Analysis Phase**
   - Evaluate visual design, IA, content, interactions
   - Assess mobile experience and accessibility
   - Review performance metrics

3. **Reporting Phase**
   - Generate main report with executive summary
   - Create section-specific reports
   - Categorize all recommendations into Tier 1/2/3

**Checkpoint:** Review Tier 1 recommendations with user before proceeding

### Stage 2: Design Concepts

**Invoke:** `Skill("website-ux-design-concepts")`

**Write outputs to:** `{OUTPUT_DIR}/design-concepts/`

#### 2.1 Identify All Sections

From the UX audit, list all major website sections:
```bash
ls -1 {OUTPUT_DIR}/ux-audit/*.md | grep -v "00-main-report" | sed 's|.*/||' | sed 's|.md||'
```

Example sections:
- homepage
- advertise
- background-screening-companies
- knowledge-center
- publications
- suppliers-providers

#### 2.2 Launch Parallel Mockup Generation

**CRITICAL:** Each sub-agent MUST invoke `Skill("website-ux-design-concepts")` to follow the structured workflow.

```python
# Launch parallel Task agents for each section
for section in sections:
    Task(
        subagent_type="general-purpose",
        prompt=f"""Generate a 1K design mockup for the {section} page.

**IMPORTANT: First invoke Skill("website-ux-design-concepts") to load the mockup generation workflow.**

Then follow the skill's workflow:

1. Read the UX audit: {OUTPUT_DIR}/ux-audit/{section}.md
2. Extract Tier 1 recommendations
3. Transform into design prompt using the skill's prompt templates
4. Generate 1K mockup using the skill's script:

uv run .claude/skills/website-ux-design-concepts/scripts/generate_image.py \\
  --prompt "[design prompt based on Tier 1 recommendations]" \\
  --filename "{OUTPUT_DIR}/design-concepts/{section}-mockup.png" \\
  --resolution 1K

Report the generated filename when complete.""",
        run_in_background=True
    )
```

**Why parallel + skill invocation?**
- 5+ sections can be processed simultaneously
- Skill provides structured prompt templates
- Each agent follows consistent workflow
- 1K resolution is sufficient for specification generation

#### 2.3 Collect Results

After all agents complete, verify outputs:
```bash
ls -la {OUTPUT_DIR}/design-concepts/*.png
```

Expected output:
```
{OUTPUT_DIR}/design-concepts/
├── homepage-mockup.png
├── advertise-mockup.png
├── background-screening-companies-mockup.png
├── knowledge-center-mockup.png
├── publications-mockup.png
└── suppliers-providers-mockup.png
```

**Checkpoint:** Review mockups with user before specification generation

### Stage 3: Implementation Specs

**Write outputs to:** `{OUTPUT_DIR}/specs/`

#### 3.1 Identify All Mockups

List all generated mockups from Stage 2:
```bash
ls -1 {OUTPUT_DIR}/design-concepts/*.png
```

#### 3.2 Launch Parallel Brief Generation

**CRITICAL:** Each sub-agent MUST invoke `Skill("design-to-code")` to follow the structured workflow.

```python
# Launch parallel Task agents for brief generation
mockups = glob("{OUTPUT_DIR}/design-concepts/*-mockup.png")

for mockup in mockups:
    section = extract_section_name(mockup)  # e.g., "homepage" from "homepage-mockup.png"

    Task(
        subagent_type="general-purpose",
        prompt=f"""Generate implementation brief for {section} page.

**IMPORTANT: First invoke Skill("design-to-code") to load the structured workflow.**

Then follow Steps 1-3 from the skill:

Step 1 - Brief Generation:
- Read the mockup image: {mockup}
- Generate PRD-style brief following the skill's template
- Save to: {OUTPUT_DIR}/specs/{section}-brief.md

Step 2 - Component Research:
- Search codebase patterns (Explore agent)
- Query Magic UI components
- Check shadcn availability
- Save to: {OUTPUT_DIR}/specs/{section}-research.md

Step 3 - JSONC Specification:
- Transform brief to JSONC spec
- Map components to sources
- Include install commands
- Save to: {OUTPUT_DIR}/specs/{section}-spec.jsonc

**STOP at Step 3** - Do not implement (Step 4).""",
        run_in_background=True
    )
```

#### 3.3 Sub-Agent Skill Requirements

| Stage | Sub-Agent Must Invoke | Purpose |
|-------|----------------------|---------|
| Stage 2 | `Skill("website-ux-design-concepts")` | Mockup generation workflow |
| Stage 3 | `Skill("design-to-code")` | Brief/Research/JSONC workflow |

**Why explicit skill invocation?**
- Ensures sub-agents follow structured workflows
- Loads proper templates and references
- Produces consistent, high-quality outputs
- Avoids freeform responses that miss key steps

#### 3.4 Collect Results

After all agents complete, verify outputs:
```bash
ls -la {OUTPUT_DIR}/specs/
```

Expected per section:
- `{section}-brief.md` - PRD-style requirements
- `{section}-research.md` - Component research report
- `{section}-spec.jsonc` - Implementation specification

**STOP HERE** - Do not proceed to Step 4 (Implementation)

### Handoff for Implementation

After Stage 3, provide handoff options:

```
Pipeline complete! Implementation specs are ready.

Output directory: {OUTPUT_DIR}/
├── ux-audit/         (UX analysis reports + screenshots)
├── design-concepts/  (Visual mockups)
└── specs/            (Implementation specifications)

Spec files ready for implementation:
- {OUTPUT_DIR}/specs/navigation-brief.md
- {OUTPUT_DIR}/specs/navigation-spec.jsonc
- {OUTPUT_DIR}/specs/hero-section-brief.md
- {OUTPUT_DIR}/specs/hero-section-spec.jsonc

Next steps:
1. Spawn frontend-dev-expert agent with these specs
2. Hand off to human developer
3. Review and refine specs before implementation

Would you like me to spawn frontend-dev-expert to implement these specs?
```

## File Structure Output

All outputs are written to the user-selected directory (default: `./workspace/{site-name}-improvements/`):

```
workspace/{site-name}-improvements/
│
├── ux-audit/
│   ├── 00-main-report.md
│   ├── 01-homepage.md
│   ├── 02-navigation.md
│   ├── ...
│   ├── screenshots/
│   │   ├── homepage-desktop.png
│   │   ├── homepage-mobile.png
│   │   └── ...
│   └── performance/
│       └── pagespeed-results.json
│
├── design-concepts/
│   ├── homepage-mockup.png
│   ├── navigation-mockup.png
│   ├── advertise-mockup.png
│   ├── knowledge-center-mockup.png
│   └── ...  (1K resolution, generated in parallel)
│
└── specs/
    ├── navigation-brief.md
    ├── navigation-research.md
    ├── navigation-spec.jsonc
    ├── hero-section-brief.md
    ├── hero-section-research.md
    └── hero-section-spec.jsonc
```

## User Checkpoints

The pipeline pauses for user approval at these points:

1. **After Stage 1:** Review UX audit and Tier 1 recommendations
   - Confirm which improvements to visualize
   - Optionally skip certain recommendations

2. **After Stage 2:** Review design mockups
   - Approve mockups for specification
   - Request revisions if needed
   - Select which mockups to specify

3. **After Stage 3:** Review implementation specs
   - Validate briefs capture design intent
   - Confirm component selections
   - Approve JSONC specs for handoff

4. **Handoff Decision:** Choose implementation path
   - Spawn frontend-dev-expert agent
   - Hand off to human developer
   - Request spec refinements

## Prerequisites

- **Browser automation tools** (for screenshots)
- **GEMINI_API_KEY** in `.env` file (for design generation)
- **uv** (for running Python scripts)

## Example Session

```
User: /website-upgraded https://university-contacts.edu

Claude: Starting Website Upgraded pipeline...

=== STAGE 0: SETUP ===

Where should I save the UX audit reports, design mockups, and implementation specs?

1. ./workspace/university-contacts-improvements/ (Recommended)
2. ./output/university-contacts/
3. Specify custom path

User: Option 1

Claude:
✓ Created output directory: ./workspace/university-contacts-improvements/
  ├── ux-audit/
  ├── design-concepts/
  └── specs/

Proceeding with UX audit...

=== STAGE 1: UX AUDIT ===
[Fetching homepage...]
[Capturing screenshots → workspace/university-contacts-improvements/ux-audit/screenshots/]
[Running PageSpeed Insights...]
[Analyzing site structure...]

✓ UX Audit Complete!

Key Tier 1 Recommendations:
1. Simplify main navigation (12 items → 5 categories)
2. Redesign hero section with clear value proposition
3. Add search functionality
4. Improve mobile navigation

Shall I proceed with generating design concepts for these improvements?

User: Yes, focus on navigation and hero section

=== STAGE 2: DESIGN CONCEPTS ===

Identified 5 sections from UX audit:
- homepage
- admissions
- academics
- contact
- about

Launching 5 parallel sub-agents for mockup generation...

Running 5 Task agents...
├─ Generate homepage mockup · Reading ux-audit/homepage.md
├─ Generate admissions mockup · Reading ux-audit/admissions.md
├─ Generate academics mockup · Reading ux-audit/academics.md
├─ Generate contact mockup · Reading ux-audit/contact.md
└─ Generate about mockup · Reading ux-audit/about.md

[All agents running in parallel...]

✓ Design Concepts Complete!

Generated mockups (1K resolution):
- workspace/university-contacts-improvements/design-concepts/homepage-mockup.png
- workspace/university-contacts-improvements/design-concepts/admissions-mockup.png
- workspace/university-contacts-improvements/design-concepts/academics-mockup.png
- workspace/university-contacts-improvements/design-concepts/contact-mockup.png
- workspace/university-contacts-improvements/design-concepts/about-mockup.png

Shall I proceed with creating implementation specifications?

User: Yes

=== STAGE 3: IMPLEMENTATION SPECS ===
[Analyzing navigation mockup...]
[Generating navigation brief...]
[Researching components for navigation...]
[Creating navigation JSONC spec...]
[Analyzing hero section mockup...]
[Generating hero section brief...]
[Researching components for hero section...]
[Creating hero section JSONC spec...]

✓ Implementation Specs Complete!

Generated specifications:
- workspace/university-contacts-improvements/specs/navigation-brief.md
- workspace/university-contacts-improvements/specs/navigation-research.md
- workspace/university-contacts-improvements/specs/navigation-spec.jsonc
- workspace/university-contacts-improvements/specs/hero-section-brief.md
- workspace/university-contacts-improvements/specs/hero-section-research.md
- workspace/university-contacts-improvements/specs/hero-section-spec.jsonc

=== HANDOFF OPTIONS ===

The pipeline has produced implementation-ready specifications.

Next steps:
1. Spawn frontend-dev-expert agent to implement
2. Hand off to human developer
3. Review and refine specs first

Would you like me to spawn frontend-dev-expert to implement these specs?

User: Yes, implement the navigation first

Claude: Spawning frontend-dev-expert with navigation specs...
[Task(subagent_type="frontend-dev-expert", prompt="Implement navigation component from specs/navigation-spec.jsonc...")]
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Browser tools unavailable | Use provided screenshots or WebFetch fallback |
| GEMINI_API_KEY missing | Add to `.env` file in project root |
| Mockup generation fails | Check API quota, try simpler prompts |
| Component research fails | Fall back to basic shadcn components |

## Related Skills

- `website-ux-audit` - Stage 1 standalone
- `website-ux-design-concepts` - Stage 2 standalone
- `design-to-code` - Stage 3 standalone (Steps 1-3 for specs)
- `frontend-dev-expert` - Implementation agent (post-handoff)
