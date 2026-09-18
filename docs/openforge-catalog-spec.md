# OpenForge Catalog: Comprehensive Technical Specification (Updated)

## Project Overview

The OpenForge Catalog is a sophisticated content management and discovery system for Devon Jones' OpenForge project - a popular Patreon-funded collection of 3D printable dungeon tiles for tabletop RPGs. The catalog manages over 12,000 STL files with complex tag-based relationships and enables users to discover, compose, and download compatible tile sets.

## Current System Status

### Production State
- **Version**: 0.4.1 currently deployed
- **Content Scope**: Multiple textures (dungeon_stone, cave, towne, sewer, metal, wood, etc.) - well beyond initial "Dungeon Stone only" MVP
- **Database Strategy**: Full replacement on each deploy (no persistent data across deployments yet) - **PLANNED FOR REPLACEMENT**
- **User System**: Read-only public access; no authentication implemented - **PLANNED FOR IMPLEMENTATION**
- **API Security**: Admin endpoints protected by deploy-time secret API key

### Architecture Foundation

#### Core Data Model
The system uses a unified **"blueprint"** entity that handles both individual models (STL files) and compositions (collections of parts):

- **Models**: Blueprints with `blueprint_type: 'model'` that include a concrete STL file
- **Blueprints**: Blueprints with `blueprint_type: 'blueprint'` that define composition patterns

**Key Design Decision**: Originally envisioned separate Models and Blueprints tables, but discovered ~100% overlap in functionality. Models are essentially blueprints that ship with concrete STL implementations.

#### Database Schema (PostgreSQL) - **UPDATED**
```sql
-- Core entity (handles both models and blueprint compositions)
blueprints: id, blueprint_name, blueprint_type, config (jsonb), file_md5, file_size,
           file_name, storage_address, search_text, created_at, updated_at,
           -- NEW FIELDS:
           consolidated_paths (text[]),     -- All filesystem locations for this file
           deprecated (boolean),            -- Whether this version is deprecated
           successor_id (uuid),             -- Points to newer version if deprecated
           created_by (uuid),               -- User who created this blueprint
           updated_by (uuid)                -- User who last updated this blueprint

-- Tag system (pipe-delimited hierarchical tags)
tags: id, blueprint_id, tag (text[]), created_by, updated_by, created_at, updated_at
tag_descriptions: id, tag (text[]), description, created_by, updated_by, created_at, updated_at

-- Media associations
images: id, image_name, image_url, created_by, updated_by, created_at, updated_at
blueprint_images: blueprint_id, image_id (many-to-many)

-- Documentation (direct blueprint association)
blueprint_documentation: id, blueprint_id, document, document_type (documentation_type_enum), created_at, updated_at

-- OpenSCAD source files
openscad_source: id, blueprint_id, openscad, created_at, updated_at

-- NEW: User management and authentication
users: id, email, role, patreon_tier (patreon_tier_enum), created_at, updated_at
user_identities: provider, provider_id, user_id, created_at, updated_at

-- NEW: Default preferences for blueprint composition
tag_priorities: id, tag_category, tag_value, priority_score, created_by, updated_by, created_at, updated_at

-- NEW: Tier-based permissions and limits
tier_permissions: id, tier_name (patreon_tier_enum), bonus_votes_per_cycle, max_requests_per_month, can_vote_specific_questions, created_by, updated_by, created_at, updated_at

-- NEW: Patron voting and request system
voting_cycles: id, cycle_name, start_date, end_date, status, created_by, updated_by, created_at, updated_at
voting_questions: id, question_name, question_description, question_type, category, cycle_id, status, kanban_position, created_by, updated_by, created_at, updated_at
voting_items: id, item_name, item_description, details (jsonb), question_id, created_by, updated_by, created_at, updated_at
patron_votes: id, user_id, voting_question_id, voting_item_id, cycle_id, vote_weight, created_at, updated_at
patron_requests: id, user_id, request_title, request_description, priority_level, status, kanban_position, created_by, updated_by, created_at, updated_at -- priority_level: normal, high, urgent - affects processing order
gap_analysis_reports: id, report_name, base_set_tags (text[]), comparison_sets (jsonb), missing_items (jsonb), report_date, reviewed, created_by, updated_by, created_at, updated_at
```

#### Tag System Architecture
Tags use pipe-delimited hierarchical structure: `category|subcategory|detail`

**Examples**:
- `texture|dungeon_stone`
- `shape|wall`
- `size|width|2`
- `connection|openforge`
- `component|door|arched`

**Tag Categories**:
- **Build**: Underlying system (separate_wall, wall_on_tile, s2w, thick_wall)
- **Component**: Functional elements (arrow_slit, door, window, torch)
- **Connection**: Mechanical systems (dragonlock, openlock, openforge, magnetic, side, pegs)
- **Decoration**: Visual themes (air, earth, fire, water, demon, celtic_knot)
- **Interface**: Multi-part relationships
- **Part**: Component definitions
- **Scatter**: Non-tile objects (barrels, statues)
- **Shape**: Physical geometry (wall, base, floor, corner, square)
- **Size**: Dimensions (width|2, depth|4, openlock|A)
- **Texture**: Surface appearance (dungeon_stone, cave, towne, sewer)

**NEW: Tag Priority System**
Default selections for blueprint composition are determined by a configurable priority system:
- `texture|dungeon_stone` - Highest priority (flagship texture)
- `connection|openforge` + `build|topless` + `connection|magnetic` + `connection|flex` - Recommended base configuration
- Priority scores allow for easy reordering and new defaults

### Blueprint Composition System

Blueprints define sophisticated assembly patterns using a tag-based constraint system. The `config` section of each blueprint specifies required parts and their selection criteria through:

- **Part Definitions**: Named components with tag-based requirements
- **Constraint Types**: require, accept, deny, and constrain mechanisms for part selection
  - *Note: This refers to blueprint configuration constraints, distinct from the user-facing search deny tags feature*
- **Dynamic Inheritance**: Parts inherit properties from parent blueprints and sibling selections
- **Fulfillment System**: Parts can satisfy multiple requirements to handle integrated components
- **Real-time Resolution**: Constraints update progressively as users make selections

**NEW: Default Population and Component Swapping**
- Blueprints now auto-populate with default selections based on tag priorities
- Component swap functionality allows users to change tag values (e.g., texture|dungeon_stone → texture|cut_stone) across all applicable parts
- New API endpoint provides available alternatives that maintain blueprint constraint satisfaction

The system handles complex real-world scenarios like doorways that need both wall and floor textures, connection system isolation, and parts that provide multiple functions. Blueprint composition can be recursive, with blueprints referencing other blueprints as parts.

**For detailed blueprint configuration syntax and constraint resolution mechanics, see [config-spec.md](config-spec.md).**

### File Management Pipeline - **SIGNIFICANTLY UPDATED**

#### New Incremental Workflow
1. **File Creation**: STLs created in Dropbox with semantic naming
2. **Scanning**: `dropbox_scanner` tool processes file tree, generates filename+MD5 pairs
3. **Incremental Loading**: `fixtures` tool compares scan results with database:
   - **Same filename+MD5**: Update metadata only (tags, images, instructions)
   - **New MD5 for existing filename**: Deprecate old version, create new with predecessor link
   - **Filename moved, same MD5**: Update location, add to consolidated_paths
   - **MD5 no longer exists**: Mark as deprecated
   - **New filename+MD5**: Create new record or link to deprecated predecessor
4. **Manual Review Interface**: CLI tool for connecting new files to deprecated predecessors using:
   - Levenshtein distance on filenames
   - Path element matching
   - Tag similarity scoring
5. **Tag Inference**: Filenames automatically generate tags for standard tiles
6. **Manual Override**: `metadata.yaml` files provide complex configurations
7. **Thumbnail Generation**: Automated STL rendering (single angle, quality issues)
8. **Storage**: Files uploaded to Cloudflare R2 storage by MD5 hash
9. **Database Update**: Incremental changes only

#### File Versioning Strategy - **ENHANCED**
- **MD5 as Content Identifier**: Files identified by content hash
- **Deprecation with Succession**: Old versions marked deprecated with successor links
- **Path Consolidation**: Multiple file locations tracked in consolidated_paths array
- **Historical Preservation**: All versions preserved in storage and accessible via history interface
- **Changelog System**: Manual documentation of changes per model
- **Path Tombstoning**: Detection of file moves and deletions across scans

#### NEW: Documentation and Knowledge System
- **Text-based Documentation**: Simple text documentation for changelogs
- **Documentation Types**: Extensible enum starting with 'changelog'
- **Direct Blueprint Association**: Documentation directly linked to blueprints
- **Version Changelogs**: Detailed change documentation using blueprint_documentation table
- **Extensible Design**: Ready for additional documentation types in future

#### NEW: Remote Fixture Loading
**Problem Solved**: Previously required SSH access to server to load fixture data into database

**Solution**: API endpoints for remote fixture loading with companion shell script

**API Endpoints**:

1. **`POST /api/admin/fixtures`** - Generic endpoint with auto-detection
   - Automatically identifies fixture type from data structure
   - Convenient for shell script and CLI usage

2. **`POST /api/admin/fixtures/blueprints`** - Blueprint fixtures only
   - Validates blueprint schema before processing
   - Returns 400 if non-blueprint data is sent

3. **`POST /api/admin/fixtures/tag-descriptions`** - Tag description fixtures only
   - Validates tag description schema before processing
   - Returns 400 if non-tag-description data is sent

4. **`POST /api/admin/fixtures/tag-documentation`** - Tag documentation fixtures only
   - Validates tag documentation schema before processing
   - Returns 400 if non-tag-documentation data is sent

**All endpoints support**:
- **Authentication**: API key via `Authorization: Bearer <token>` header
- **Request Body**: Raw fixture file content (JSON or YAML)
- **Query Parameters**:
  - `dry_run=true` - Preview changes without applying
  - `verbose=true` - Enable debug output
- **Transaction Safety**: All-or-nothing processing with automatic rollback on errors
- **Response Format**:
  ```json
  {
    "success": true,
    "added": [...],
    "modified": [...],
    "deprecated": [...],
    "consolidated": [...],
    "errors": [],
    "output": ["captured log messages"]
  }
  ```

**Shell Script**: `bin/upload_fixture`
- Reads `OPENFORGE_API_TOKEN` from `.env` file
- Takes fixture path relative to `openforge/db/fixtures/`
- Supports `--dry-run` and `--verbose` flags
- Auto-detects content type from file extension
- Defaults to localhost for development, configurable via `OPENFORGE_BASE_URL` env var
- Pretty-prints JSON responses with color-coded output
- Example usage:
  ```bash
  ./bin/upload_fixture blueprints/dungeon_stone.json
  ./bin/upload_fixture blueprints/cave.json --dry-run --verbose
  OPENFORGE_BASE_URL=https://staging.openforge.tools ./bin/upload_fixture blueprints/bases.json
  ```

**Benefits**:
- No SSH access required for fixture loading
- Can load fixtures from local machine to staging/production
- Same incremental loading logic as CLI tool
- Full output visibility via API response
- Safe testing with dry-run mode

**Implementation Notes**:
- **Type-Specific Endpoints**: Each fixture type has its own endpoint with schema validation
  - Prevents accidental uploads of wrong fixture type
  - Clear error messages when fixture doesn't match expected schema
  - Easier to add new fixture types in the future

- **Generic Endpoint**: The `/api/admin/fixtures` endpoint uses heuristics for type detection:
  - Lists → blueprints
  - Dicts with list values → tag documentation
  - Dicts with other values → tag descriptions
  - Convenient for shell script and automated tools
  - May be less precise than type-specific endpoints

- **Future Enhancement**: Add explicit `"fixture_type"` field to fixture file schemas for more robust type detection and validation.

### Authentication and Authorization System - **NEW**

#### OAuth-Only Authentication
- **Patreon OAuth**: Primary integration with automatic tier detection
- **Google OAuth**: Secondary option for non-Patreon users
- **Multiple Provider Support**: Users can link multiple OAuth accounts to single profile
- **No Traditional Registration**: Eliminates need for custom user management

#### Role-Based Access Control
**Initial Implementation**:
- **Admin**: Full system access, can manage all content and users
- **Patron**: Access level based on Patreon tier, potential early access features
- **User**: Basic read access, standard feature set

**Future Expansion**:
- **Content Creator**: Can submit and manage their own blueprints
- **Reviewer**: Can review and approve community submissions
- **Moderator**: Can manage community interactions and content quality

#### Patreon Integration
- Automatic account creation from Patreon supporter list
- Tier-based feature access
- Webhook integration for real-time tier updates
- **Comprehensive Audit Trails**: All content creation and modification tracked by user
- **Multi-provider Identity**: Single user profile can link multiple OAuth accounts

### NEW: Patron Voting and Request System

#### Monthly Voting Cycles
- **Automatic Monthly Reset**: Voting cycles automatically reset on the 1st of each month
- **Cumulative Vote System**: Votes accumulate month-to-month until an item wins, then item moves to "selected" status
  - **Intentional Design**: This mechanism ensures fairness for all patrons over time
  - **Patron Fairness**: Items with consistent but not overwhelming support eventually win
  - **No Vote Decay**: Intentionally allows unpopular items to accumulate votes indefinitely
  - **Democratic Principle**: Every patron's vote contributes to eventual success
  - **Implementation**: Cumulative votes calculated via aggregate queries on patron_votes table across all cycles
  - **Data Preservation**: All historical votes preserved in patron_votes table for cumulative calculations
  - **Winning Items**: When an item wins, its status changes from "voting" to "selected" and it's no longer available for voting
- **Question-Based Voting**: Patrons vote on questions with multiple options
  - **Question Structure**: `voting_questions` table defines questions (e.g., "What tile set should we work on next?")
  - **Item Options**: `voting_items` table contains options for each question (e.g., "Mausoleum/Crypts", "Desert Stone")
  - **Vote Limits**: One vote per question per cycle (patrons select one option per question)
  - **Question Types**: tile_set, specific_tile, feature questions for different categories
- **Real-time Results**: Vote tallies visible to patrons after they submit their votes
- **Vote Modification**: Patrons can change votes until the monthly cycle ends
- **Public Read-Only View**: Non-patrons can view voting results to encourage signup
- **Data Preservation**: Voting cycles archived instead of deleted to preserve historical data

#### Tier-Based Voting Mechanics
- **Base Voting**: All paid patrons can participate in standard voting
- **Bonus Votes**: Higher tiers receive additional votes on specific questions they prioritize
- **Individual Requests**: Premium tiers can submit specific item requests outside the voting system
- **Configurable Limits**: Request limits per tier configurable by admin
- **Experimental Mechanics**: System designed to allow testing of different voting weight algorithms
- **Stored Vote Weight**: Vote weights captured at voting time to preserve historical tier-based voting power
- **Historical Accuracy**: Vote weights remain fixed even if user's tier changes later
- **Cached Results**: Vote tallies cached for performance with invalidation on new votes or vote modifications. User permission caches are invalidated on tier changes.
- **Tier Integrity**: PostgreSQL ENUM type `patreon_tier_enum` ensures users.patreon_tier always contains valid tier values (Bronze, Silver, Gold, Platinum). No foreign key constraint to tier_permissions is used, allowing users to have tier assignments even when no specific permissions are configured for that tier.

#### Security and Data Integrity
- **Vote Ownership**: Users can only create, modify, or delete their own votes
- **Request Ownership**: Users can only create, modify, or delete their own requests
- **Admin Limitations**: Admin users cannot directly modify patron votes or requests
- **Authentication Required**: All voting and request operations require valid authentication
- **Ownership Verification**: All update/delete operations verify resource ownership before allowing changes
- **Historical Vote Weight**: Vote weights captured at voting time, preserve tier-based voting power for that cycle
- **Audit Trail**: All vote and request modifications are logged with user and timestamp
- **Automatic Timestamps**: Database triggers ensure `updated_at` is always current
- **Voting History**: Vote history preserved across all cycles via aggregate queries on patron_votes table - cumulative votes calculated by querying all historical votes for each item

#### Gap Analysis and Automated Suggestion System
- **Cross-Set Comparison**: Automated analysis comparing tile sets across textures (e.g., dungeon_stone vs cut_stone)
- **Missing Variant Detection**: Identifies missing sizes, connection types, or component variations
- **Aggregated Suggestions**: System generates reports showing gaps, admin creates aggregated voting items
- **Tag-Based Analysis**: Uses existing tag system to identify patterns and missing combinations
- **Manual Review Workflow**: Admin reviews gap analysis reports before creating voting items

#### Kanban Workflow Management
**Primary Voting Track**:
- **Voting**: Items available for monthly voting
- **Selected**: Items that won monthly vote
- **In Progress**: Items currently being worked on
- **Complete**: Finished items

**Patron Request Track**:
- **Requested**: Individual patron requests
- **Under Review**: Admin reviewing feasibility
- **Approved**: Approved for development
- **In Progress**: Currently being worked on
- **Complete**: Finished requests

**ENUM Types for Data Integrity**:
- `voting_cycle_status`: 'active', 'closed', 'archived'
- `voting_item_type`: 'tile_set', 'specific_tile', 'feature'
- `voting_item_status`: 'voting', 'selected', 'in_progress', 'complete'
- `patron_request_priority`: 'normal', 'high', 'urgent'
- `patron_request_status`: 'requested', 'under_review', 'approved', 'in_progress', 'complete', 'rejected'

**Workflow Features**:
- **Bidirectional Movement**: Items can move backward in workflow (e.g., In Progress → Voting if blocked)
- **Admin Management**: Admin can move items between states via drag-and-drop interface
- **Status Tracking**: Each item tracks current kanban position and status history
- **Integration with Main Catalog**: Completed items automatically link to resulting catalog entries

#### API Design for Voting System
```typescript
// Voting cycle management
GET /api/voting/current-cycle
POST /api/voting/cycles (admin)
PUT /api/voting/cycles/{cycle_id} (admin)

// Voting items and votes
GET /api/voting/items
POST /api/voting/items (admin)
PUT /api/voting/items/{item_id} (admin)
POST /api/voting/votes
PUT /api/voting/votes/{vote_id}
DELETE /api/voting/votes/{vote_id}

// Patron requests
GET /api/patron-requests (filtered by user)
POST /api/patron-requests
PUT /api/patron-requests/{request_id}
DELETE /api/patron-requests/{request_id}

// Gap analysis (admin)
GET /api/admin/gap-analysis/reports
POST /api/admin/gap-analysis/reports
PUT /api/admin/gap-analysis/reports/{report_id}

// Kanban management (admin)
PUT /api/admin/kanban/voting-items/{item_id}/status
PUT /api/admin/kanban/patron-requests/{request_id}/status

// Tier permissions (admin)
GET /api/admin/tier-permissions
PUT /api/admin/tier-permissions/{tier_name}
```

#### Integration with Patreon
- **Automatic Tier Sync**: Real-time webhook integration for tier changes
- **Supporter List Import**: Automated creation of voting items from supporter data
  - **Data Source**: Google Sheets form responses with columns for "What next set do you want to see", "Scatter/encounters", "Got an idea that has yet to get covered, feedback or concerns?", and "New tile type idea"
  - **Voting Item Creation**: Parse form responses to extract:
    - **Tile Set Requests**: "Mausoleum/Crypts", "Limestone Cavern", "Desert Stone", "Crenelated tiles", etc.
    - **Scatter/Encounter Requests**: "9 Layers of Hell", "Inn: Cots/Beds/Chairs/Tables", "Alchemist's Lab", etc.
    - **Feature Requests**: Specific suggestions like "Grass floor tile for outside of buildings", "Inn tables covered with maps/books", etc.
    - **New Tile Types**: Innovative tile concepts from patron feedback
  - **Frequency Analysis**: Count duplicate requests to identify most popular items
  - **Category Classification**: Automatically categorize suggestions into voting_item_type (tile_set, specific_tile, feature)
  - **Manual Review**: Admin reviews aggregated suggestions before creating voting items
- **Monthly Post Generation**: Stretch goal to auto-generate monthly Patreon posts with voting results
- **Tier-Based Feature Gating**: Dynamic feature access based on current Patreon tier

### Performance Characteristics

#### Database Performance
Excellent performance despite complex tag queries using sophisticated SQL with multiple JOINs. **NEW**: Deprecation filtering adds minimal overhead with proper indexing on deprecated flag. Voting system queries optimized with proper indexing on cycle_id, user_id, and status fields.

#### Bottlenecks
- **File Processing**: `dropbox_scanner` performance with 12,000+ files - **IMPROVED** with incremental processing
- **Thumbnail Quality**: Single-angle automated generation produces poor results for complex models
- **Gap Analysis Performance**: Cross-set comparison queries may require optimization for large catalogs

### User Interface - **ENHANCED**

#### Current Features
- **Part Search**: Tag-based filtering with hierarchical categories
  - **Require Tags**: Include items with specific tags (+ button)
  - **Deny Tags**: Exclude items with specific tags (- button in red)
  - **Combined Filtering**: Use both require and deny tags together for precise searches
  - **Deep Link Support**: URLs preserve both require and deny tags for sharing searches
- **Blueprint Assembly**: Step-by-step part selection with constraint-based filtering
- **Visual Feedback**: 3D thumbnail previews throughout interface
- **Download System**: Individual file downloads with deep linking support
- **Tag Documentation**: Tooltip help system with tag descriptions

#### NEW Features
- **Default Population**: Blueprints auto-populate with recommended parts
- **Component Swapping**: Buttons to swap tag categories across all parts
- **File History**: Interface to view version history and changelogs
- **Customization Integration**: Direct links to OpenSCAD customizer for parametric models
- **Authentication Flow**: OAuth login with role-based feature access

#### NEW: Voting and Request Interface
- **Voting Dashboard**: Dedicated tab showing current voting cycle with real-time results
- **Monthly Calendar**: Visual representation of voting cycles and deadlines
- **Item Details**: Expandable voting items showing gap analysis details and rationale
- **Hierarchical Display**: Tile sets shown with expandable specific tile options
- **Two-Level Voting Interface**: Separate voting sections for tile sets and specific tiles
- **Tier Benefits**: Clear display of voting benefits per Patreon tier
- **Request Submission**: Form for premium patrons to submit individual requests
- **Status Tracking**: Personal view of submitted requests and their kanban status
- **Public Results**: Read-only voting results visible to encourage Patreon signup

#### NEW: Admin Voting Management
- **Gap Analysis Interface**: Tool to review automated gap analysis reports
- **Voting Item Creation**: Form to create aggregated voting items from gap analysis
- **Kanban Management**: Drag-and-drop interface for managing both voting and request workflows
- **Tier Configuration**: Interface to adjust voting mechanics and request limits per tier
- **Cycle Management**: Tools to manually control voting cycles if needed
- **Analytics Dashboard**: Voting participation metrics and trend analysis

#### User Experience Flow - **IMPROVED**
1. **Optional Login**: OAuth authentication for enhanced features
2. Browse blueprints or search by tags (deprecated versions hidden)
3. **NEW**: Access voting dashboard to participate in monthly votes (patrons only)
4. Select blueprint for assembly - **now pre-populated with defaults**
5. **NEW**: Use component swap buttons for quick texture/style changes
6. Fine-tune parts step-by-step with guided filtering
7. **NEW**: Access customization for parametric models (via openscad_source table)
8. Review final part list with thumbnails
9. Download individual STL files or **NEW**: view file history
10. **NEW**: Submit individual requests (premium patrons)

### Advanced Features

#### Base Generator (WebAssembly OpenSCAD) - **ENHANCED**
- **Parametric Customization**: Web-based tile base generation
- **Real-time Preview**: 3D rendering before STL export
- **NEW: Deep Linking**: Direct integration from catalog with tag pre-population
- **NEW: Blueprint Integration**: openscad_source table links blueprints to customizable versions
- **Limitations**: Boolean reliability issues with textured surfaces
- **Future**: Blender + Geometry Nodes for complex textured parametric generation

#### API Design - **EXPANDED**
RESTful API with comprehensive CRUD operations:
- `/api/blueprints` - Blueprint management
- `/api/blueprints/{blueprint_id}/tags` - Tag management
- `/api/blueprints/tags` - Advanced tag querying with pagination
  - Supports `require` tags (include items with these tags)
  - Supports `deny` tags (exclude items with these tags)
  - Supports `accept` tags (optional tags for flexible matching)
- **NEW**: `/api/blueprints/component-alternatives` - Component swapping alternatives
- `/api/images` - Image management
- `/api/tag-descriptions` - Tag documentation
- **NEW**: `/api/auth` - OAuth authentication endpoints
- **NEW**: `/api/blueprints/{blueprint_id}/history` - File version history
- **NEW**: `/api/blueprints/{blueprint_id}/documentation` - Blueprint documentation management
- **NEW**: `/api/admin/duplicates` - Administrative duplicate detection
- **NEW**: `/api/admin/fixtures` - Remote fixture loading with auto-detection
- **NEW**: `/api/admin/fixtures/blueprints` - Blueprint fixture loading
- **NEW**: `/api/admin/fixtures/tag-descriptions` - Tag description fixture loading
- **NEW**: `/api/admin/fixtures/tag-documentation` - Tag documentation fixture loading
- **NEW**: `/api/voting/*` - Complete voting system API
- **NEW**: `/api/patron-requests/*` - Patron request management
- **NEW**: `/api/admin/gap-analysis/*` - Gap analysis and reporting

## Roadmap and Development Priorities - **UPDATED**

### Immediate Implementation (Current Cycle)
1. **Incremental Database Updates** - Replace full refresh with versioning system
2. **CLI Administrative Tools** - Manual review interface and duplicate detection
3. **Documentation System** - Markdown instructions with tag-based composition and image support
4. **Default Population System** - Tag priorities and auto-population
5. **Component Swapping API** - Backend support for alternative tag suggestions

### Next Phase
1. **OAuth Authentication System** - Patreon and Google integration
2. **File History Interface** - User-facing version history with rich changelog documentation
3. **Component Swapping UI** - Frontend implementation of swap buttons
4. **OpenSCAD Deep Linking** - Integration with parametric customizer

### NEW: Voting System Implementation
1. **Core Voting Infrastructure** - Database schema, API endpoints, basic voting mechanics
2. **Gap Analysis System** - Automated cross-set comparison and missing item detection
3. **Kanban Workflow Interface** - Admin tools for managing voting items and patron requests
4. **Patron Voting UI** - User-facing voting dashboard with real-time results
5. **Tier-Based Mechanics** - Bonus votes and individual request systems
6. **Patreon Integration** - Automated tier sync and monthly post generation

### Beta Features
- **Advanced Downloads**: Zip file packaging
- **Enhanced Media**: Multiple thumbnail angles, user-submitted photos
- **Administrative Web Interface**: Move from CLI to web-based admin tools
- **Advanced Role Management**: Content creator and reviewer workflows
- **Voting Analytics**: Participation trends and recommendation algorithms

### Version 1.0+ Features
- **Community Contributions**: User-uploaded models with review process
- **External Integration**: Thingiverse, Printables, MakerWorld linking
- **Advanced Customization**: Blender-based parametric generation
- **3D Visualization**: Real-time blueprint assembly preview
- **Advanced Voting Features**: Vote delegation, weighted category preferences

### Long-term Vision
- **Dungeon Planning Tools**: Drag-and-drop dungeon builders with part calculation
- **Inventory Management**: Track printed parts for efficient build planning
- **Advanced Community Features**: Comments, bug tracking, collaborative blueprints
- **Predictive Voting**: AI-powered suggestions based on voting history and catalog gaps
- **Community-Driven Development**: Patron-led feature development and priority setting

## Technical Challenges and Solutions

### Database Migration Strategy
**Challenge**: Moving from full refresh to incremental updates without data loss
**Solution**: Comprehensive comparison system with manual review fallbacks for edge cases

### File Relationship Management
**Challenge**: Tracking file evolution, moves, and duplicates across complex directory structure
**Solution**: MD5-based identity with path consolidation and predecessor/successor linking

### OAuth-Only Authentication
**Challenge**: Users without preferred OAuth providers
**Solution**: Clear messaging about supported providers, focus on primary user base (tabletop gamers)

### Component Swapping Complexity
**Challenge**: Determining valid alternatives that satisfy all blueprint constraints
**Solution**: New API endpoint that validates constraint satisfaction across all affected parts

### NEW: Voting System Challenges

#### Vote Security and Ownership
**Challenge**: Ensuring users cannot modify other users' votes or requests, and that vote weights are preserved accurately
**Solution**: Comprehensive ownership verification in all update/delete operations. Vote weights are captured and stored at the time of voting to preserve historical accuracy, and cannot be modified later. Authentication is required for all voting actions

#### Cumulative Vote Management
**Challenge**: Maintaining vote accumulation across months while handling item modifications
**Solution**: Separate vote tracking per cycle with cumulative calculation, item versioning for changes

#### Gap Analysis Performance
**Challenge**: Cross-set comparison queries may be expensive with large catalogs
**Solution**: Pre-computed analysis with incremental updates, caching of comparison results

#### Tier-Based Voting Fairness
**Challenge**: Balancing voting power across tiers without disenfranchising lower-tier patrons
**Solution**: Configurable bonus systems with caps, transparency in vote weight calculations

#### Real-time Vote Updates
**Challenge**: Providing real-time results without performance degradation
**Solution**: Event-driven updates with WebSocket connections, vote aggregation caching

## Architecture Decisions and Rationale

### Incremental Database Strategy
**Decision**: Implement comprehensive versioning with deprecation rather than selective updates
**Rationale**: Preserves all historical data, supports rollback scenarios, maintains audit trail

### OAuth-Only Authentication
**Decision**: Skip traditional username/password registration entirely
**Rationale**: Reduces maintenance burden, aligns with modern security practices, leverages existing user accounts

### CLI-First Admin Tools
**Decision**: Build command-line tools before web interfaces for administrative functions
**Rationale**: Faster implementation, more powerful for complex operations, can evolve to web later

### Tag Priority System
**Decision**: Configurable priority scoring rather than hardcoded defaults
**Rationale**: Allows evolution of recommendations, supports A/B testing, enables user customization

### NEW: Voting System Architecture Decisions

#### Monthly Auto-Reset
**Decision**: Automatic voting cycle reset on 1st of month rather than manual control
**Rationale**: Predictable schedule for patrons, reduces admin overhead, aligns with Patreon posting cycle

#### Separate Kanban Tracks
**Decision**: Independent workflow management for voting items vs patron requests
**Rationale**: Different lifecycles and management needs, clearer separation of democratic vs individual requests

#### Gap Analysis Integration
**Decision**: Integrate gap analysis with existing tag system rather than separate classification
**Rationale**: Leverages existing robust tagging infrastructure, ensures consistency with catalog organization

#### Public Read-Only Voting Results
**Decision**: Make voting results visible to non-patrons
**Rationale**: Marketing tool to encourage Patreon signup, transparency builds trust, showcases community engagement

## Implementation Notes for Developers

### Database Migrations
- Add new fields with default values for backward compatibility
- Index deprecated flag and successor/predecessor relationships
- Consider partitioning strategy for large historical datasets
- **NEW**: Index voting-related foreign keys and status fields for performance
- **NEW**: Implement cascade deletes carefully for voting data retention

### File Processing Pipeline
- Implement robust comparison logic for filename+MD5 pairs
- Handle edge cases in path consolidation (symbolic links, case sensitivity)
- Build comprehensive scoring system for predecessor/successor matching

### API Versioning
- Maintain backward compatibility for existing endpoints
- Version new endpoints for component swapping and authentication
- Plan for deprecation of admin API key in favor of OAuth
- **NEW**: Design voting API for extensibility with future voting mechanics

### Frontend State Management
- Handle default population without breaking existing user workflows
- Implement optimistic updates for component swapping
- Design authentication flow with minimal user friction
- **NEW**: Implement real-time vote updates with WebSocket fallbacks
- **NEW**: Design voting UI for mobile responsiveness

### NEW: Voting System Implementation Notes

#### Foreign Key Constraints and ENUM Types
- All voting system tables use explicit ON DELETE actions:
  - `patron_votes`: CASCADE for user_id, voting_item_id; RESTRICT for cycle_id (prevent vote deletion when cycle is deleted)
  - `patron_requests`: CASCADE for user_id (delete request when user is deleted), SET NULL for created_by/updated_by (preserve admin audit trail)
  - `voting_questions`: RESTRICT for cycle_id (prevent accidental deletion of voting data), SET NULL for created_by/updated_by
  - `voting_cycles`: SET NULL for created_by/updated_by (preserve cycle history)
  - `tier_permissions`: SET NULL for created_by/updated_by
  - `gap_analysis_reports`: SET NULL for created_by/updated_by
  - `users.patreon_tier`: Uses `patreon_tier_enum` ENUM type for data integrity (no foreign key needed)

- **POLICY**: All `created_by` and `updated_by` columns must use `ON DELETE SET NULL` to preserve audit trail while allowing user deletion

- PostgreSQL ENUM types ensure data integrity:
  - `voting_cycle_status`, `voting_item_type`, `voting_item_status`
  - `patron_request_priority`, `patron_request_status`
  - `patreon_tier_enum` - Ensures valid tier assignments (Bronze, Silver, Gold, Platinum)
  - Prevents invalid status values and improves type safety

- **Automatic Timestamp Updates**: Database triggers automatically update `updated_at` fields on all modifications
  - Reusable trigger function `update_updated_at_column()` applied to all tables
  - Ensures accurate audit trail without application-level timestamp management

#### Vote Aggregation Strategy
- Query-time vote aggregation with optimized indexes for performance
- Cache vote totals with tier change invalidation
- Consider read replicas for voting result queries

#### Gap Analysis Optimization
- Pre-compute common comparison queries
- Use background jobs for expensive analysis operations
- Cache analysis results with invalidation on catalog updates

#### Tier Permission Management
- Design for easy A/B testing of voting mechanics
- Implement feature flags for experimental voting features
- Plan for gradual rollout of tier-based features

## Success Metrics and Goals - **EXPANDED**

### Technical Success Metrics
- **Zero Data Loss**: Migration to incremental updates without losing historical data
- **Performance Maintenance**: No degradation in search/filtering performance with versioning
- **Authentication Adoption**: High OAuth adoption rate, minimal user friction
- **Administrative Efficiency**: CLI tools reduce manual overhead for content management
- **NEW**: **Voting System Performance**: Vote submission and result queries under 1 second
- **NEW**: **Gap Analysis Accuracy**: 95%+ accuracy in identifying relevant missing items

### User Experience Goals
- **Faster Workflow**: Default population reduces time to working blueprint
- **Intuitive Swapping**: Component swap buttons feel natural and predictable
- **Historical Access**: Users can easily access and understand file evolution
- **Seamless Customization**: Direct parametric customization feels integrated
- **NEW**: **Voting Engagement**: 80%+ of eligible patrons participate in monthly voting
- **NEW**: **Request Satisfaction**: Clear communication of patron request status and timeline

### NEW: Business and Community Goals
- **Patreon Growth**: Voting system drives new patron signups and tier upgrades
- **Development Prioritization**: Voting results provide clear guidance for development priorities
- **Community Engagement**: Increased patron interaction and investment in project direction
- **Administrative Efficiency**: Gap analysis reduces manual work in identifying development priorities
- **Transparency**: Public voting results build trust and showcase community-driven development
- **Data Integrity**: Secure voting system maintains trust and prevents manipulation

This updated specification reflects a significant maturation of the OpenForge Catalog system, moving from a read-only prototype to a full-featured content management platform with user authentication, comprehensive versioning, enhanced user experience features, and a sophisticated patron engagement system through voting and requests.

## Design Decisions Considered but Rejected

### Database and Performance

#### Stored Vote Counts
**Considered**: Storing vote_count and cumulative_votes in voting_items table with transaction-based updates
**Decision**: Query-time calculation approach chosen instead
**Rationale**: Avoids race conditions and locking on a central counter. Simplifies vote logic to row inserts/deletes, removing the need for complex transactions. Vote weights are captured at voting time to preserve historical tier status, so query-time aggregation naturally reflects the stored historical weights.

#### Audit Field Indexes
**Considered**: Adding indexes to voting_items.created_by and voting_items.updated_by columns for audit log queries
**Rejected**: Indexes not added for these fields
**Rationale**: Audit queries are rare, indexes have storage and write performance costs, and the benefit doesn't justify the overhead

#### Separate Models and Blueprints Tables
**Considered**: Maintaining separate database tables for individual models vs blueprint compositions
**Rejected**: Unified "blueprint" entity with blueprint_type field
**Rationale**: Discovered ~100% overlap in functionality, models are essentially blueprints with concrete STL implementations

#### Traditional Username/Password Authentication
**Considered**: Implementing custom user registration and password management
**Rejected**: OAuth-only authentication (Patreon + Google)
**Rationale**: Reduces maintenance burden, aligns with modern security practices, leverages existing user accounts, eliminates password reset complexity

#### Foreign Key Constraint for Tier Permissions
**Considered**: Adding foreign key constraint from users.patreon_tier to tier_permissions.tier_name
**Rejected**: Using only ENUM validation without foreign key constraint
**Rationale**: Allows users to have tier assignments even when no specific permissions are configured for that tier. ENUM provides sufficient data integrity validation without being overly restrictive.

### Voting System Design

#### Manual Voting Cycle Control
**Considered**: Admin-controlled voting cycle start/end dates
**Rejected**: Automatic monthly reset on 1st of month
**Rationale**: Predictable schedule for patrons, reduces admin overhead, aligns with Patreon posting cycle, eliminates human error

#### Vote Decay System
**Considered**: Implementing vote decay over time to prevent unpopular items from accumulating indefinitely
**Rejected**: No vote decay, cumulative votes persist until item wins
**Rationale**: Ensures fairness for all patrons over time, democratic principle that every vote contributes to eventual success, simpler mechanics

#### Stored Vote Weights
**Considered**: Dynamic weight calculation at query time based on a user's current tier.
**Decision**: Vote weights are captured and stored in `patron_votes.vote_weight` at the time of voting.
**Rationale**: Vote weights captured at voting time preserve historical accuracy when user tiers change, eliminates complex JOINs for vote aggregation, and ensures vote power remains fixed for the voting cycle.

#### Single-Level Voting
**Considered**: Simple one-vote-per-item voting system
**Rejected**: Two-level hierarchical voting (tile sets + specific tiles)
**Rationale**: Allows more granular patron input, better development prioritization, reflects real-world development process

#### Private Voting Results
**Considered**: Making voting results visible only to patrons
**Rejected**: Public read-only voting results for non-patrons
**Rationale**: Marketing tool to encourage Patreon signup, transparency builds trust, showcases community engagement

### File Management

#### Selective Database Updates
**Considered**: Updating only changed fields during incremental loading
**Rejected**: Full replacement with comprehensive versioning and deprecation
**Rationale**: Preserves all historical data, supports rollback scenarios, maintains audit trail, simpler logic

#### Hardcoded Tag Priorities
**Considered**: Hardcoded default selections for blueprint composition
**Rejected**: Configurable priority scoring system
**Rationale**: Allows evolution of recommendations, supports A/B testing, enables user customization, more flexible

#### Web-First Admin Tools
**Considered**: Building web-based admin interface from the start
**Rejected**: CLI-first approach for administrative functions
**Rationale**: Faster implementation, more powerful for complex operations, can evolve to web later, better for automation

#### Type-Specific Fixture Endpoints
**Implemented**: Both generic and type-specific endpoints for fixture loading:
- `POST /api/admin/fixtures` - Auto-detects fixture type
- `POST /api/admin/fixtures/blueprints` - Blueprint fixtures only
- `POST /api/admin/fixtures/tag-descriptions` - Tag description fixtures only
- `POST /api/admin/fixtures/tag-documentation` - Tag documentation fixtures only

**Rationale**:
- Type-specific endpoints provide schema validation and clear error messages
- Generic endpoint provides convenience for automated tools (shell script, CI/CD)
- Both approaches coexist - use type-specific for web UI, generic for automation

**Future Enhancement**:
- Add explicit `"fixture_type"` field to fixture file schemas for even more robust validation
- This would eliminate the need for heuristic-based type detection in the generic endpoint

### User Experience

#### Required Authentication
**Considered**: Requiring login for all catalog features
**Rejected**: Optional authentication with graceful degradation
**Rationale**: Maintains accessibility for anonymous users, reduces friction, allows gradual feature discovery

#### Complex Component Swapping
**Considered**: Advanced UI with detailed constraint visualization and manual part selection
**Rejected**: Simple swap buttons with preview and confirmation
**Rationale**: Intuitive for users, faster workflow, reduces cognitive load, covers 90% of use cases

#### Real-time 3D Blueprint Assembly
**Considered**: WebGL-based real-time 3D preview of assembled blueprints
**Rejected**: Static thumbnails with step-by-step assembly guidance
**Rationale**: Significant development complexity, performance concerns, existing thumbnail system adequate for most users

### Integration and External Systems

#### Multiple OAuth Providers
**Considered**: Supporting Facebook, Twitter, Discord, and other OAuth providers
**Rejected**: Patreon + Google only
**Rationale**: Covers primary user base, reduces integration complexity, focuses on most relevant providers for tabletop gaming community

#### External Platform Integration
**Considered**: Direct integration with Thingiverse, Printables, MakerWorld for model hosting
**Rejected**: Self-hosted file storage with Cloudflare R2
**Rationale**: Maintains control over user experience, avoids dependency on external platform changes, better performance

#### Advanced Parametric Generation
**Considered**: WebAssembly-based Blender integration for complex parametric generation
**Rejected**: OpenSCAD-based customizer with deep linking
**Rationale**: OpenSCAD already proven for this use case, simpler implementation, adequate for current customization needs
