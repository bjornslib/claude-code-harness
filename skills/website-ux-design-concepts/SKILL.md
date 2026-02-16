---
name: website-ux-design-concepts
description: This skill should be used when the user asks to "create design mockups", "generate UI concepts", "visualize UX improvements", "create wireframes", "design concept images", or needs to generate visual design mockups based on UX recommendations. Uses Gemini 3 Pro Image API for high-quality design generation.
version: 1.0.0
---

# Website UX Design Concepts

Generate visual design mockups and UI concepts based on UX audit recommendations or design briefs using Gemini 3 Pro Image API.

## Overview

This skill transforms text-based UX recommendations into visual design concepts, creating mockup images that can be used as input for the design-to-code workflow.

**Primary use case:** Bridge between UX audit findings and code implementation by generating visual representations of improvements.

## Required Inputs

| Input | Source | Purpose |
|-------|--------|---------|
| Design brief | UX audit Tier 1 recommendations OR user description | What to visualize |
| Existing screenshots (optional) | Captured during UX audit | Reference for editing/improvement |
| Resolution | User preference (default: 1K) | Output quality level |

## Usage

Run the script using absolute path (do NOT cd to skill directory first):

**Generate new design concept:**
```bash
uv run ~/.claude/skills/website-ux-design-concepts/scripts/generate_image.py \
  --prompt "UI mockup: [design description]" \
  --filename "yyyy-mm-dd-hh-mm-ss-concept-name.png" \
  --resolution 1K|2K|4K
```

**Edit existing screenshot to show improvements:**
```bash
uv run ~/.claude/skills/website-ux-design-concepts/scripts/generate_image.py \
  --prompt "Improve this UI: [specific improvements]" \
  --filename "yyyy-mm-dd-hh-mm-ss-improved-name.png" \
  --input-image "path/to/original-screenshot.png" \
  --resolution 2K
```

**Important:** Always run from user's current working directory so images are saved where the user is working.

## Workflow Integration

### From UX Audit → Design Concepts

Transform Tier 1 recommendations into design prompts:

```
UX Audit Recommendation:
"Simplify navigation by consolidating 12 top-level items into 5 categories"

Design Prompt:
"UI mockup: Modern website header with 5-item horizontal navigation bar.
Clean typography, clear hover states, mobile hamburger menu icon visible.
Color scheme: professional blue and white. Style: minimal, modern SaaS."
```

### Parallel Mockup Generation (Recommended)

When working with multiple website sections, **launch parallel sub-agents** for each section:

```python
# Example: Generate mockups for all sections in parallel
sections = ["homepage", "advertise", "knowledge-center", "publications"]

for section in sections:
    Task(
        subagent_type="general-purpose",
        prompt=f"""Generate 1K mockup for {section} page.
Read UX audit: {output_dir}/ux-audit/{section}.md
Extract Tier 1 recommendations and create design prompt.
Generate mockup to: {output_dir}/design-concepts/{section}-mockup.png""",
        run_in_background=True
    )
```

**Why parallel?**
- Process 5+ sections simultaneously
- 1K resolution is sufficient for specs
- Much faster than sequential generation

### Single Section Workflow

For individual sections or iterations:

```bash
uv run ~/.claude/skills/website-ux-design-concepts/scripts/generate_image.py \
  --prompt "<design prompt from Tier 1 recommendations>" \
  --filename "{output_dir}/design-concepts/{section}-mockup.png" \
  --resolution 1K
```

**Note:** 4K resolution is not needed for specification generation. 1K mockups provide sufficient detail for creating briefs and JSONC specs.

## Prompt Engineering for UI Mockups

### Generation Template (New Designs)

```
UI mockup: [component/page type].
Layout: [structure description].
Components: [list key UI elements].
Style: [design aesthetic - modern/minimal/corporate/playful].
Color palette: [primary, secondary, accent colors].
Typography: [font style - clean/bold/elegant].
Special elements: [icons, images, animations].
Avoid: [unwanted elements].
```

### Editing Template (Improve Existing)

```
Improve this UI design:
Change ONLY: [specific improvement].
Keep identical: overall layout, brand colors, existing content.
Add: [new elements if any].
Remove: [elements to simplify].
Style adjustments: [subtle changes].
```

### Example Prompts by UX Issue

**Navigation Improvement:**
```
UI mockup: Website header with simplified navigation.
Layout: Logo left, 5 main nav items center, CTA button right.
Components: Logo placeholder, text links, dropdown indicator, search icon, primary button.
Style: Modern SaaS, clean lines, plenty of whitespace.
Color palette: #1E3A8A primary blue, white background, #3B82F6 hover state.
Typography: Sans-serif, medium weight for nav items.
```

**Hero Section Redesign:**
```
UI mockup: Hero section with strong value proposition.
Layout: Split layout - headline and CTA left, product image right.
Components: H1 headline, subheadline paragraph, two CTA buttons, hero image placeholder.
Style: Bold, confident, enterprise software aesthetic.
Color palette: Dark blue background, white text, orange accent CTAs.
Special elements: Subtle gradient background, floating UI element decorations.
```

**Card Grid Layout:**
```
UI mockup: Feature cards grid section.
Layout: 3-column grid with equal cards, responsive hints.
Components: Icon, heading, description, link for each card.
Style: Minimal, flat design, generous padding.
Color palette: Light gray background, white cards, blue icons.
Typography: Bold headings, regular body text.
```

## Resolution Guide

| Resolution | Use Case | When to Use |
|------------|----------|-------------|
| **1K** (default) | Spec generation | Sufficient for briefs and JSONC specs |
| **2K** | Client review | Higher detail for presentations |
| **4K** | Final assets | Only if high-res deliverables needed |

**Recommendation:** Use 1K for all `/website-upgraded` pipeline mockups. Higher resolutions add generation time without improving spec quality.

## API Configuration

The script checks for API key in this order:
1. `--api-key` argument (highest priority)
2. `.env` file in current working directory
3. `GEMINI_API_KEY` environment variable

**Recommended: Use .env file**
```bash
# Create .env file in your project root
echo 'GEMINI_API_KEY=your-api-key-here' >> .env
```

The script auto-loads `.env` from the directory where you run the command.

**Alternative: Environment variable**
```bash
export GEMINI_API_KEY="your-api-key"
```

## Output Format

- Saves PNG to current directory
- Script outputs full path to generated image
- Images are named with timestamp for versioning
- Do not read image back into context - inform user of saved path

## Preflight Checks

Before running:
```bash
# Check uv is available
command -v uv

# Check API key is set
test -n "$GEMINI_API_KEY"

# If editing, verify input image exists
test -f "path/to/input.png"
```

## Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| `No API key provided` | Missing GEMINI_API_KEY | Set env var or pass --api-key |
| `Error loading input image` | Wrong path | Verify --input-image path |
| `quota/403 errors` | API limits | Check quota or use different key |

## Integration with Workflow Chain

This skill is designed to work in a 3-stage pipeline:

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  website-ux-audit   │───▶│ website-ux-design-  │───▶│   design-to-code    │
│                     │    │      concepts       │    │                     │
│  URL → UX Report    │    │ Recommendations →   │    │ Mockups → React     │
│  + Recommendations  │    │ Visual Mockups      │    │ Components          │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

Use `/website-upgraded` command to execute the full pipeline automatically.
