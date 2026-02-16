#!/usr/bin/env python3
"""
CSV to Multilead JSON Converter

Converts campaign_research_audit.csv to Multilead API-compatible JSON format.
Part of the LinkedIn Lead Research skill.

Usage:
    # Paths relative to project root - replace {campaign-name} with actual folder name
    python csv_to_multilead_json.py --input ./workspace/campaign-{campaign-name}/campaign_research_audit.csv --output ./workspace/campaign-{campaign-name}/multilead_import.json
    python csv_to_multilead_json.py --input ./workspace/campaign-{campaign-name}/campaign_research_audit.csv --output ./workspace/campaign-{campaign-name}/multilead_import.json --campaign-id 108
    python csv_to_multilead_json.py --input ./workspace/campaign-{campaign-name}/campaign_research_audit.csv --output ./workspace/campaign-{campaign-name}/multilead_import.json --batches 001,002,003
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Optional


def validate_lead(lead: dict) -> tuple[bool, str]:
    """
    Validate that a lead has required fields for Multilead API.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Must have either profileUrl or email
    has_profile = lead.get("profileUrl") and lead["profileUrl"].strip()
    has_email = lead.get("email") and lead["email"].strip()

    if not has_profile and not has_email:
        return False, "Missing both profileUrl and email"

    # Must have personalisedMessage
    if not lead.get("personalisedMessage") or not lead["personalisedMessage"].strip():
        return False, "Missing personalisedMessage"

    # Validate LinkedIn URL format if present
    if has_profile:
        url = lead["profileUrl"].strip()
        if "linkedin.com" not in url.lower():
            return False, f"Invalid LinkedIn URL: {url}"

    return True, ""


def convert_csv_to_multilead_json(
    input_file: str,
    output_file: str,
    campaign_id: Optional[int] = None,
    batches: Optional[list[str]] = None,
    include_metadata: bool = False
) -> dict:
    """
    Convert CSV file to Multilead API-compatible JSON.

    Args:
        input_file: Path to campaign_research_audit.csv
        output_file: Path for output JSON file
        campaign_id: Optional campaign ID to embed in output
        batches: Optional list of batch numbers to include (e.g., ["001", "002"])
        include_metadata: If True, include extra fields for reference

    Returns:
        Summary dict with counts and any errors
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    leads = []
    errors = []
    skipped = 0

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
            # Filter by batch if specified
            if batches and row.get("batchNumber") not in batches:
                skipped += 1
                continue

            # Build Multilead-compatible record
            lead = {
                "firstName": row.get("firstName", "").strip(),
                "lastName": row.get("lastName", "").strip(),
                "personalisedMessage": row.get("personalisedMessage", "").strip(),
            }

            # Add profileUrl if present
            profile_url = row.get("profileUrl", "").strip()
            if profile_url:
                lead["profileUrl"] = profile_url

            # Add email if present (some leads may have email instead of profileUrl)
            email = row.get("email", "").strip()
            if email:
                lead["email"] = email

            # Build occupation from title + company
            title = row.get("currentTitle", "").strip()
            company = row.get("currentCompany", "").strip()
            if title and company:
                lead["occupation"] = f"{title} at {company}"
            elif title:
                lead["occupation"] = title
            elif company:
                lead["occupation"] = company

            # Add phone if present
            phone = row.get("phone", "").strip()
            if phone:
                lead["phone"] = phone

            # Include metadata if requested (useful for audit trail)
            if include_metadata:
                lead["_metadata"] = {
                    "batchNumber": row.get("batchNumber", ""),
                    "processedAt": row.get("processedAt", ""),
                    "companyWebsite": row.get("companyWebsite", ""),
                    "industry": row.get("industry", ""),
                    "problems": row.get("problems", ""),
                    "aiOpportunities": row.get("aiOpportunities", ""),
                }

            # Validate lead
            is_valid, error_msg = validate_lead(lead)
            if not is_valid:
                errors.append({
                    "row": row_num,
                    "firstName": lead.get("firstName", ""),
                    "lastName": lead.get("lastName", ""),
                    "error": error_msg
                })
                continue

            leads.append(lead)

    # Build output structure
    output_data = leads

    # If campaign_id specified, wrap in structure with metadata
    if campaign_id:
        output_data = {
            "campaignId": campaign_id,
            "leads": leads,
            "metadata": {
                "totalLeads": len(leads),
                "sourceFile": str(input_path),
                "batchesIncluded": batches or "all"
            }
        }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Return summary
    return {
        "success": True,
        "totalProcessed": len(leads) + len(errors) + skipped,
        "leadsExported": len(leads),
        "errorsFound": len(errors),
        "skippedByFilter": skipped,
        "errors": errors,
        "outputFile": str(output_path)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert campaign CSV to Multilead API JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_to_multilead_json.py --input campaign_research_audit.csv --output leads.json
  python csv_to_multilead_json.py --input data.csv --output leads.json --campaign-id 108
  python csv_to_multilead_json.py --input data.csv --output leads.json --batches 001,002
  python csv_to_multilead_json.py --input data.csv --output leads.json --include-metadata
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CSV file (campaign_research_audit.csv)"
    )

    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output JSON file (campaign_leads_final.json)"
    )

    parser.add_argument(
        "--campaign-id", "-c",
        type=int,
        default=None,
        help="Optional Multilead campaign ID to embed in output"
    )

    parser.add_argument(
        "--batches", "-b",
        type=str,
        default=None,
        help="Comma-separated batch numbers to include (e.g., 001,002,003)"
    )

    parser.add_argument(
        "--include-metadata", "-m",
        action="store_true",
        help="Include research metadata in output (for audit trail)"
    )

    args = parser.parse_args()

    # Parse batches if provided
    batches = None
    if args.batches:
        batches = [b.strip() for b in args.batches.split(",")]

    try:
        result = convert_csv_to_multilead_json(
            input_file=args.input,
            output_file=args.output,
            campaign_id=args.campaign_id,
            batches=batches,
            include_metadata=args.include_metadata
        )

        # Print summary
        print("\n✅ Conversion complete!")
        print(f"   Leads exported: {result['leadsExported']}")
        print(f"   Errors found: {result['errorsFound']}")
        if result['skippedByFilter'] > 0:
            print(f"   Skipped (batch filter): {result['skippedByFilter']}")
        print(f"   Output file: {result['outputFile']}")

        # Print errors if any
        if result['errors']:
            print("\n⚠️  Errors (leads not exported):")
            for err in result['errors'][:10]:  # Show first 10
                print(f"   Row {err['row']}: {err['firstName']} {err['lastName']} - {err['error']}")
            if len(result['errors']) > 10:
                print(f"   ... and {len(result['errors']) - 10} more errors")

        print("\n📋 Next step: Use with Multilead API skill:")
        print(f"   python add_lead.py --campaign-id [ID] --batch-file {args.output}")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
