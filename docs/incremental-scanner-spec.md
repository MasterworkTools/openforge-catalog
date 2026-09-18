# Incremental Scanner Update Specification

## Overview
Add `--update` flag to `dropbox_scanner` to enable incremental processing that only calculates MD5s for files that have changed, dramatically improving performance.

## Requirements

### 1. CLI Interface
- Add `--update <fixture_file>` flag to `dropbox_scanner`
- Add `--dry-run` flag for preview mode
- Add `--incremental` flag for outputting only changed data by full_path
- Auto-detect subset path from fixture file content
- Fail fast if fixture file doesn't exist or is invalid

### 2. Fixture File Support
- Support both JSON and YAML formats (auto-detect by extension)
- Schema validation on read/write using existing schemas
- Require `file_metadata` on every element (reject blueprint files)

### 3. Change Detection Logic
For each file in the subset:
- **New files**: Always calculate MD5
- **Existing files**: Compare `file_modified_at`, `size`
  - If any field differs → calculate MD5
  - If all fields match → copy entire `file_metadata` from prior fixture
- **Missing files**: Create deprecation tombstone with `deprecated: true`

**Change Detection for Output**:
A file is considered "updated" if any of the following change:
- MD5 value (due to `file_modified_at` or `size` changes)
- Tags (compare as sets to handle unordered nature)
- Config field

### 4. Subset Auto-detection
- Read fixture file and find common substring in `full_name` fields
- Use this as the subset path for scanning
- Example: `tiles/dungeon_stone` from `tiles/dungeon_stone/floor/...`

### 5. Output Strategy
- **Normal mode**: Write complete updated fixture to standard output (conventionally redirected to `<fixture_file>.next`)
- **Dry-run mode**: Output diff format showing only incremental changes to standard output
- **Incremental mode**: Output only missing, modified, and added data by full_path
- **Deprecation**: Keep original `file_metadata` but add `deprecated: true` field

### 6. Schema Updates
- Add `deprecated: boolean` field to blueprint fixture schema
- Default to `false` for backward compatibility

### 7. Integration
- Update `load_all.sh` to use `--update` flag instead of current approach
- Maintain same output file naming convention (`.next` files)

## Example Usage
```bash
# Update dungeon_stone fixture incrementally (outputs to stdout)
./dropbox_scanner --update ../openforge/db/fixtures/dungeon_stone.json --verbose --upload

# Preview changes without writing files (outputs diff to stdout)
./dropbox_scanner --update ../openforge/db/fixtures/dungeon_stone.json --dry-run

# Output only changed data by full_path
./dropbox_scanner --update ../openforge/db/fixtures/dungeon_stone.json --incremental

# Updated load_all.sh would use --update for each subset (redirected to .next files)
./dropbox_scanner --update ../openforge/db/fixtures/dungeon_stone.json --verbose --upload > ../openforge/db/fixtures/dungeon_stone.json.next
```

## Error Conditions
- Fixture file doesn't exist → error
- Schema validation fails → error
- No `file_metadata` on any element → error
- Cannot determine subset path → error

## Error Handling and Transaction Requirements

### Fail-Fast Behavior
- **No exception catching**: Any error should immediately terminate the operation
- **Immediate rollback**: Database transaction should be rolled back on any error
- **Clear error messages**: Provide specific error information for debugging

### All-or-Nothing Database Operations
- **Transaction wrapping**: All database operations must be wrapped in transactions
- **Automatic rollback**: Any error triggers automatic transaction rollback
- **No partial updates**: Either all changes succeed or none do

### Error Conditions That Trigger Rollback
- Schema validation failures
- Database constraint violations
- Missing required data (file_metadata, etc.)
- Invalid fixture file formats
- Network or connection errors
- Any unhandled exceptions during processing

### Error Reporting
- Provide clear error messages with context
- Include file path and line number where possible
- Log validation errors before raising exceptions
- Maintain error state for debugging

## Implementation Notes
- This is part of Phase 1 of the implementation plan
- Focuses on performance improvement for the scanning workflow
- Maintains backward compatibility with existing fixture formats
- Prepares for the full versioning system in later phases
- Most functionality should be implemented in `openforge/data/` as `dropbox_scanner` is a thin wrapper
