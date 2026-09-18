# Phase 1.2: Fixtures System Enhancement Implementation Plan

## Overview
Enhance the fixtures loading system to support incremental updates, versioning, and change detection as specified in Phase 1 of the implementation plan. This builds on the completed incremental scanner functionality.

## Current System Analysis

### ✅ **Existing Capabilities**
- **Full replacement**: `clear_db()` wipes all data before loading
- **Schema validation**: Validates blueprint and tag description fixtures
- **MD5 conflict handling**: `rescue_md5_conflict=True` in `insert_blueprint`
- **File support**: JSON and YAML fixtures
- **Error handling**: Detailed validation error reporting

### 🔧 **Required Enhancements for Phase 1**

#### 1. Database Schema Updates
**New fields needed in blueprints table:**
```sql
ALTER TABLE blueprints ADD COLUMN consolidated_paths text[];
ALTER TABLE blueprints ADD COLUMN deprecated boolean DEFAULT false;
ALTER TABLE blueprints ADD COLUMN successor_id uuid;

-- Indexes for performance
CREATE INDEX idx_blueprints_successor ON blueprints(successor_id);
CREATE INDEX idx_blueprints_md5 ON blueprints(file_md5);
```

#### 2. Incremental Loading Logic
**Replace `clear_db()` with comparison logic:**
- Fetch existing blueprint filename+MD5 pairs from database
- Compare with fixture data using change detection logic
- Only update records that have actually changed
- Handle deprecation and versioning relationships

**Change Detection Logic:**
- **Same filename+MD5**: metadata-only updates (tags, config, images)
- **New MD5, existing filename**: deprecation + new version creation with predecessor/successor links
- **Missing filename, existing MD5**: path consolidation (update consolidated_paths)
- **Missing MD5**: mark as deprecated with `deprecated: true`
- **New filename+MD5**: create new record or link to deprecated predecessor

#### 3. Enhanced CLI Interface
**Update `bin/fixtures` with new options:**
```python
@click.option("--incremental", is_flag=True, help="Enable incremental loading mode")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--update", help="Specify fixture file for incremental update")
@click.option("--compare-only", is_flag=True, help="Show comparison results only")
```

#### 4. New Classes and Functions

**`IncrementalFixturesLoader` class:**
```python
class IncrementalFixturesLoader:
    def __init__(self, conn: connection, verbose: bool = False):
        self.conn = conn
        self.verbose = verbose
        self.existing_blueprints = self._load_existing_blueprints()

    def _load_existing_blueprints(self) -> Dict[str, Dict]:
        """Load existing blueprints from database for comparison."""

    def compare_fixture_data(self, fixture_data: List[Dict]) -> ComparisonResult:
        """Compare fixture data with existing database records."""

    def apply_incremental_changes(self, changes: ComparisonResult, dry_run: bool = False):
        """Apply incremental changes to database."""

    def create_deprecation_entry(self, blueprint_id: str, successor_id: str = None):
        """Mark blueprint as deprecated with optional successor."""

    def create_version_relationship(self, successor_id: str):
        """Create predecessor/successor relationship between blueprints."""
```

**`ComparisonResult` class:**
```python
class ComparisonResult:
    def __init__(self):
        self.added = []      # New blueprints
        self.modified = []   # Updated blueprints
        self.deprecated = [] # Deprecated blueprints
        self.consolidated = [] # Path consolidation updates
        self.errors = []     # Processing errors
```

#### 5. Enhanced `_munge_blueprint()` Function
**Update to handle new fields:**
```python
def _munge_blueprint(data: dict):
    bp = {}
    bp["blueprint_type"] = data["type"]
    bp["blueprint_name"] = data.get("name")
    bp["blueprint_config"] = data.get("config", {})

    # NEW: Phase 1 fields
    bp["deprecated"] = data.get("deprecated", False)
    bp["successor_id"] = data.get("successor_id")
    bp["consolidated_paths"] = data.get("consolidated_paths", [])

    if "file_metadata" in data:
        if not bp["blueprint_name"]:
            bp["blueprint_name"] = data["file_metadata"]["file"]
        bp["file_md5"] = data["file_metadata"]["md5"]
        bp["file_size"] = data["file_metadata"]["size"]
        bp["file_name"] = data["file_metadata"]["file"]
        bp["full_name"] = data["file_metadata"]["full_name"]
        bp["file_modified_at"] = data["file_metadata"]["file_modified_at"]
        bp["storage_address"] = data["file_metadata"].get("storage_address")
    return bp
```

#### 6. Updated `load_fixtures()` Function
**Support both full replacement and incremental modes:**
```python
def load_fixtures(conn: connection, alt: str, files: list = None,
                 incremental: bool = False, dry_run: bool = False):
    ffiles = files if files is not None else find_fixtures(alt)

    if incremental:
        loader = IncrementalFixturesLoader(conn, verbose=True)
        for f in ffiles:
            data = _load_data(f)
            blueprint_result = _is_blueprint_fixture(data)
            if blueprint_result.is_valid:
                changes = loader.compare_fixture_data(data)
                if dry_run:
                    print_comparison_results(changes)
                else:
                    loader.apply_incremental_changes(changes)
            else:
                print(f"Validation failed for {f}")
                for error in blueprint_result.errors:
                    print(error)
                raise ValueError(f"File {f} does not match blueprint fixture format")
    else:
        # Existing full replacement logic
        with conn.cursor(row_factory=dict_row) as curs:
            clear_db(curs)
            conn.commit()
            # ... existing logic ...
```

## Implementation Steps

### Step 1: Database Schema Updates
1. Create migration script for new fields
2. Update `blueprint_sql` module to handle new fields
3. Add indexes for performance
4. Test with existing data

### Step 2: Core Incremental Logic
1. Implement `IncrementalFixturesLoader` class
2. Add `ComparisonResult` class
3. Implement change detection logic
4. Add deprecation and versioning support

### Step 3: CLI Enhancements
1. Update `bin/fixtures` with new options
2. Add dry-run functionality
3. Implement comparison reporting
4. Maintain backward compatibility

### Step 4: Integration and Testing
1. Update `load_fixtures()` to support incremental mode
2. Test with existing fixture files
3. Validate change detection accuracy
4. Performance testing with large datasets

## Success Criteria

### Technical Requirements
- ✅ Zero data loss during incremental updates
- ✅ Accurate change detection (no false positives/negatives)
- ✅ Proper handling of deprecation and versioning
- ✅ Performance improvement over full replacement
- ✅ Backward compatibility with existing fixtures

### User Experience
- ✅ Clear reporting of changes in dry-run mode
- ✅ Intuitive CLI interface
- ✅ Helpful error messages for validation failures
- ✅ Progress indicators for large updates

## Integration with Existing Systems

### Incremental Scanner Integration
- Use same change detection logic as `IncrementalScanner`
- Consistent handling of MD5 changes and deprecation
- Shared validation and error handling patterns

### Database Integration
- Leverage existing `blueprint_sql` functions
- Maintain transaction integrity
- Use existing tag and image handling logic

### Schema Validation
- Extend existing validation for new fields
- Maintain compatibility with current fixture formats
- Add validation for versioning relationships

## Error Handling and Edge Cases

### Database Conflicts
- Handle concurrent updates gracefully
- Maintain referential integrity for predecessor/successor relationships
- Rollback on validation failures

### Data Consistency
- Validate that deprecated entries have successors when appropriate
- Ensure consolidated_paths contains valid paths
- Check for circular references in versioning relationships

### Performance Considerations
- Batch database operations for large updates
- Use efficient queries for existing data comparison
- Implement progress reporting for long-running operations

### Transaction and Error Handling Requirements

#### Fail-Fast Behavior
- **No exception catching**: Any error should immediately terminate the operation
- **Immediate rollback**: Database transaction should be rolled back on any error
- **Clear error messages**: Provide specific error information for debugging

#### All-or-Nothing Database Operations
- **Transaction wrapping**: All database operations must be wrapped in transactions
- **Automatic rollback**: Any error triggers automatic transaction rollback
- **No partial updates**: Either all changes succeed or none do

#### Implementation Requirements
```python
# Example transaction handling pattern
with conn.transaction():
    # All database operations here
    # Any exception will trigger rollback
    loader.apply_incremental_changes(changes)
```

#### Error Conditions That Trigger Rollback
- Schema validation failures
- Database constraint violations
- Missing required data (file_metadata, etc.)
- Invalid fixture file formats
- Network or connection errors
- Any unhandled exceptions during processing

#### Error Reporting
- Provide clear error messages with context
- Include file path and line number where possible
- Log validation errors before raising exceptions
- Maintain error state for debugging

## Future Enhancements (Phase 2+)

### Manual Review Interface
- CLI tools for connecting new files to deprecated predecessors
- Scoring algorithm for automatic relationship detection
- Interactive confirmation for edge cases

### Advanced Versioning
- Support for multiple predecessors/successors
- Branching and merging of blueprint versions
- Historical change tracking

### Performance Optimizations
- Parallel processing for large fixture files
- Caching of comparison results
- Incremental validation (only validate changed records)
