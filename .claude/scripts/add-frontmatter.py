#!/usr/bin/env python3
"""Add missing frontmatter fields (title, status) to documentation files.

Handles three cases:
1. Files with frontmatter missing both title and status
2. Files with frontmatter missing only status (e.g., react rules with title already)
3. Files with NO frontmatter at all (adds complete block)

Title is derived from: existing 'name' field > first H1 heading > filename.
"""

import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # .claude/

def humanize_filename(filename: str) -> str:
    """Convert filename to human-readable title."""
    name = filename.replace('.md', '').replace('SKILL', '').strip('-_ ')
    # Handle UPPER_CASE
    if '_' in name and name == name.upper():
        return name.replace('_', ' ').title()
    # Handle kebab-case
    if '-' in name:
        return name.replace('-', ' ').title()
    # Handle camelCase/PascalCase
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name).title()

def derive_title(filepath: Path, frontmatter_dict: dict, content_after: str) -> str:
    """Derive a title from available sources."""
    # 1. Use existing 'name' field
    if 'name' in frontmatter_dict:
        name = frontmatter_dict['name'].strip()
        # Humanize: "backend-solutions-engineer" -> "Backend Solutions Engineer"
        return name.replace('-', ' ').replace('_', ' ').title()

    # 2. Use first H1 heading
    h1_match = re.search(r'^#\s+(.+)$', content_after, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    # 3. Fallback to filename
    return humanize_filename(filepath.name)

def parse_frontmatter(content: str):
    """Parse YAML frontmatter, return (frontmatter_text, rest_of_file, fields_dict)."""
    if not content.startswith('---'):
        return None, content, {}

    # Find closing --- (use [ \t]* instead of \s* to avoid consuming blank lines)
    end_match = re.search(r'\n---[ \t]*\n', content[3:])
    if not end_match:
        return None, content, {}

    end_pos = end_match.end() + 3
    fm_text = content[4:end_match.start() + 3]  # Between the --- markers
    rest = content[end_pos:]  # Preserves any blank line after closing ---

    # Simple field extraction (not full YAML parsing)
    fields = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key = line.split(':', 1)[0].strip()
            val = line.split(':', 1)[1].strip()
            fields[key] = val

    return fm_text, rest, fields

def process_file(filepath: Path, dry_run: bool = False) -> str | None:
    """Process a single file. Returns action taken or None if no change needed."""
    content = filepath.read_text(encoding='utf-8')

    fm_text, rest, fields = parse_frontmatter(content)

    has_title = 'title' in fields
    has_status = 'status' in fields

    if has_title and has_status:
        return None  # Nothing to do

    if fm_text is not None:
        # Has frontmatter but missing fields
        lines = fm_text.split('\n')
        additions = []

        if not has_title:
            title = derive_title(filepath, fields, rest)
            additions.append(f'title: "{title}"')

        if not has_status:
            additions.append('status: active')

        # Insert additions after last existing field
        new_fm = '\n'.join(lines + additions)
        new_content = f'---\n{new_fm}\n---\n{rest}'

        action = f"added {'+'.join(f for f in ['title', 'status'] if f not in fields)}"
    else:
        # No frontmatter at all
        title = derive_title(filepath, {}, content)
        new_content = f'---\ntitle: "{title}"\nstatus: active\n---\n\n{content}'
        action = "added full frontmatter"

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return action

def main():
    dry_run = '--dry-run' in sys.argv

    # Collect all target files
    targets = []

    # 1. Agent files
    agent_dir = BASE / 'agents'
    if agent_dir.exists():
        targets.extend(agent_dir.glob('*.md'))

    # 2. Output styles
    os_dir = BASE / 'output-styles'
    if os_dir.exists():
        targets.extend(os_dir.glob('*.md'))

    # 3. Skill SKILL.md files (recursive)
    skills_dir = BASE / 'skills'
    if skills_dir.exists():
        targets.extend(skills_dir.rglob('SKILL.md'))

    # 4. React best practices rules
    rules_dir = BASE / 'skills' / 'react-best-practices' / 'references' / 'rules'
    if rules_dir.exists():
        targets.extend(rules_dir.glob('*.md'))

    # 5. Skill reference/example files mentioned in report
    ref_file = BASE / 'skills' / 'skill-development' / 'references' / 'skill-creator-original.md'
    if ref_file.exists():
        targets.append(ref_file)

    # 6. Documentation directory
    doc_dir = BASE / 'documentation'
    if doc_dir.exists():
        targets.extend(doc_dir.glob('*.md'))

    # Deduplicate
    targets = sorted(set(targets))

    # Process
    fixed = 0
    skipped = 0
    for filepath in targets:
        rel = filepath.relative_to(BASE)
        action = process_file(filepath, dry_run=dry_run)
        if action:
            print(f"  {'[DRY] ' if dry_run else ''}FIXED {rel}: {action}")
            fixed += 1
        else:
            skipped += 1

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{mode}: {fixed} files fixed, {skipped} already OK, {len(targets)} total scanned")

if __name__ == '__main__':
    main()
