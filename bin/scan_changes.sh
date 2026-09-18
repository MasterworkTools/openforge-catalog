#!/bin/bash

# Scan for changes across all JSON fixture files
# Usage: ./bin/scan_changes.sh [--verbose]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIXTURES_DIR="$PROJECT_ROOT/openforge/db/fixtures/blueprints"

# Default to not verbose
VERBOSE_FLAG=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE_FLAG="--verbose"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--verbose]"
            exit 1
            ;;
    esac
done

# Find all JSON files in fixtures directory and process them safely
file_count=0

while IFS= read -r -d '' fixture_file; do
    ((file_count++))

    # Extract the base name for display
    fixture_name=$(basename "$fixture_file" .json)

    echo "=== $fixture_name ==="

    # Run the incremental scanner in dry-run mode
    python "$PROJECT_ROOT/bin/dropbox_scanner" --update "$fixture_file" --dry-run $VERBOSE_FLAG

    echo
done < <(find "$FIXTURES_DIR" -name "*.json" -type f -print0 | sort -z)

# Check if any files were found
if [ $file_count -eq 0 ]; then
    echo "No JSON fixture files found in $FIXTURES_DIR"
    exit 1
fi
