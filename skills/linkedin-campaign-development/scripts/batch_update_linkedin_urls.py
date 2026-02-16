#!/usr/bin/env python3
"""
Batch Update LinkedIn URLs from JSON to CSV

Reads validated LinkedIn URLs from a JSON file and updates corresponding rows
in a CSV file. Part of the LinkedIn Lead Research skill.

Usage:
    # Basic usage - updates CSV in place (paths relative to project root)
    python batch_update_linkedin_urls.py \\
        --csv ./workspace/campaign-{name}/campaign_research_audit.csv \\
        --json ./workspace/campaign-{name}/found_linkedin_urls.json

    # Dry run to preview changes
    python batch_update_linkedin_urls.py \\
        --csv campaign_research_audit.csv \\
        --json found_linkedin_urls.json \\
        --dry-run

    # Create backup before updating
    python batch_update_linkedin_urls.py \\
        --csv campaign_research_audit.csv \\
        --json found_linkedin_urls.json \\
        --backup

    # Custom field names and output file
    python batch_update_linkedin_urls.py \\
        --csv leads.csv \\
        --json urls.json \\
        --first-name-field fname \\
        --last-name-field lname \\
        --url-field linkedin \\
        --output updated_leads.csv

    # Verbose mode
    python batch_update_linkedin_urls.py \\
        --csv campaign_research_audit.csv \\
        --json found_linkedin_urls.json \\
        --verbose
"""

import argparse
import csv
import json
import sys
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime


def load_linkedin_urls(json_file: Path, verbose: bool = False) -> Dict[str, str]:
    """
    Load LinkedIn URLs from JSON file and create lookup dictionary.

    Args:
        json_file: Path to JSON file with LinkedIn URLs
        verbose: Enable verbose output

    Returns:
        Dictionary mapping "firstName|lastName" to LinkedIn URL
    """
    if verbose:
        print(f"Reading LinkedIn URLs from {json_file}...")

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            found_urls = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: JSON file not found: {json_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {json_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Create lookup dictionary
    url_lookup = {}
    for entry in found_urls:
        if not isinstance(entry, dict):
            continue

        first_name = entry.get('firstName', '').strip()
        last_name = entry.get('lastName', '').strip()
        linkedin_url = entry.get('linkedInUrl', '').strip()

        if first_name and last_name and linkedin_url:
            key = f"{first_name}|{last_name}"
            url_lookup[key] = linkedin_url

    if verbose:
        print(f"Loaded {len(url_lookup)} LinkedIn URLs")

    return url_lookup


def validate_csv_fields(
    fieldnames: List[str],
    first_name_field: str,
    last_name_field: str,
    url_field: str
) -> Tuple[bool, str]:
    """
    Validate that required fields exist in CSV.

    Returns:
        Tuple of (is_valid, error_message)
    """
    missing_fields = []

    if first_name_field not in fieldnames:
        missing_fields.append(first_name_field)
    if last_name_field not in fieldnames:
        missing_fields.append(last_name_field)
    if url_field not in fieldnames:
        missing_fields.append(url_field)

    if missing_fields:
        return False, f"Missing required CSV fields: {', '.join(missing_fields)}"

    return True, ""


def update_csv_with_urls(
    csv_file: Path,
    url_lookup: Dict[str, str],
    first_name_field: str = 'firstName',
    last_name_field: str = 'lastName',
    url_field: str = 'linkedInUrl',
    output_file: Optional[Path] = None,
    dry_run: bool = False,
    backup: bool = False,
    verbose: bool = False
) -> Tuple[int, int]:
    """
    Update CSV file with LinkedIn URLs from lookup dictionary.

    Args:
        csv_file: Path to CSV file to update
        url_lookup: Dictionary mapping name keys to LinkedIn URLs
        first_name_field: Name of first name field in CSV
        last_name_field: Name of last name field in CSV
        url_field: Name of LinkedIn URL field in CSV
        output_file: Optional output file (default: update in place)
        dry_run: If True, don't write changes
        backup: If True, create backup before writing
        verbose: Enable verbose output

    Returns:
        Tuple of (total_rows, updated_rows)
    """
    if verbose:
        print(f"\nReading CSV from {csv_file}...")

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Validate CSV structure
            is_valid, error_msg = validate_csv_fields(
                fieldnames, first_name_field, last_name_field, url_field
            )
            if not is_valid:
                print(f"ERROR: {error_msg}", file=sys.stderr)
                sys.exit(1)

            rows = []
            updated_count = 0

            for row in reader:
                first_name = row.get(first_name_field, '').strip()
                last_name = row.get(last_name_field, '').strip()
                current_url = row.get(url_field, '').strip()
                key = f"{first_name}|{last_name}"

                # Update if we have a URL and field is empty
                if key in url_lookup and not current_url:
                    new_url = url_lookup[key]
                    row[url_field] = new_url
                    updated_count += 1

                    if verbose:
                        print(f"  {'[DRY RUN] ' if dry_run else ''}Updated: {first_name} {last_name} -> {new_url}")

                rows.append(row)

    except FileNotFoundError:
        print(f"ERROR: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Write results
    if not dry_run:
        target_file = output_file or csv_file

        # Create backup if requested
        if backup and target_file == csv_file:
            backup_file = csv_file.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            shutil.copy2(csv_file, backup_file)
            if verbose:
                print(f"\nCreated backup: {backup_file}")

        if verbose:
            print(f"\nWriting updated CSV to {target_file}...")

        try:
            with open(target_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            print(f"ERROR: Failed to write CSV: {e}", file=sys.stderr)
            sys.exit(1)

    return len(rows), updated_count


def main():
    parser = argparse.ArgumentParser(
        description='Batch update LinkedIn URLs from JSON to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required arguments
    parser.add_argument(
        '--csv',
        type=Path,
        required=True,
        help='Path to CSV file to update'
    )
    parser.add_argument(
        '--json',
        type=Path,
        required=True,
        help='Path to JSON file with LinkedIn URLs'
    )

    # Optional field name customization
    parser.add_argument(
        '--first-name-field',
        default='firstName',
        help='Name of first name field in CSV (default: firstName)'
    )
    parser.add_argument(
        '--last-name-field',
        default='lastName',
        help='Name of last name field in CSV (default: lastName)'
    )
    parser.add_argument(
        '--url-field',
        default='linkedInUrl',
        help='Name of LinkedIn URL field in CSV (default: linkedInUrl)'
    )

    # Optional output control
    parser.add_argument(
        '--output',
        type=Path,
        help='Output file path (default: update CSV in place)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without writing to file'
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create timestamped backup before updating'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Validate input files exist
    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)
    if not args.json.exists():
        print(f"ERROR: JSON file not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    # Load LinkedIn URLs
    url_lookup = load_linkedin_urls(args.json, args.verbose)

    if not url_lookup:
        print("WARNING: No LinkedIn URLs found in JSON file", file=sys.stderr)
        sys.exit(0)

    # Update CSV
    total_rows, updated_count = update_csv_with_urls(
        csv_file=args.csv,
        url_lookup=url_lookup,
        first_name_field=args.first_name_field,
        last_name_field=args.last_name_field,
        url_field=args.url_field,
        output_file=args.output,
        dry_run=args.dry_run,
        backup=args.backup,
        verbose=args.verbose
    )

    # Summary
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Summary:")
    print(f"  Total rows in CSV: {total_rows}")
    print(f"  Rows updated: {updated_count}")
    print(f"  Rows with LinkedIn URLs: {total_rows - (total_rows - updated_count)}")

    if args.dry_run:
        print("\n✓ Dry run complete - no changes written")
    else:
        target = args.output or args.csv
        print(f"\n✓ Successfully updated {target}")


if __name__ == '__main__':
    main()
