#!/bin/bash
# Merge multiple batch JSON files into a single CSV
# Usage: ./merge_csv_batches.sh ./workspace/campaign-{name}/batches/batch_*/messages_draft.json > ./workspace/campaign-{name}/campaign_research_audit.csv

set -e

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed." >&2
    echo "Install with: brew install jq (macOS) or apt install jq (Ubuntu)" >&2
    exit 1
fi

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 batch_file1.json [batch_file2.json ...]" >&2
    echo "Example: $0 ./workspace/campaign-{name}/batches/batch_*/messages_draft.json > ./workspace/campaign-{name}/campaign_research_audit.csv" >&2
    exit 1
fi

# CSV header
echo "firstName,lastName,company,title,linkedInUrl,personalisedMessage,messageRationale,personalisationHooks,qaStatus,validationNotes"

# Process each JSON file
for file in "$@"; do
    if [ ! -f "$file" ]; then
        echo "Warning: File not found: $file" >&2
        continue
    fi

    # Extract leads from JSON and convert to CSV rows
    jq -r '.[] | [
        .firstName // "",
        .lastName // "",
        .company // "",
        .title // "",
        .linkedInUrl // "",
        .personalisedMessage // "",
        .messageRationale // "",
        .personalisationHooks // "",
        .qaStatus // "",
        .validationNotes // ""
    ] | @csv' "$file" 2>/dev/null || {
        echo "Warning: Failed to parse $file" >&2
    }
done
