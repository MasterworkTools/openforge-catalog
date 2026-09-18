# OpenForge Catalog Implementation Plan

## Overview

This document outlines the implementation strategy for the major enhancements to the OpenForge Catalog system, prioritized for sequential development to minimize risk and maintain system stability.

## Phase 1: Database Migration and Versioning Infrastructure

### Priority: CRITICAL
### Timeline: 2-3 weeks
### Dependencies: None

#### 1.1 Database Schema Updates

**Add new fields to blueprints table:**
```sql
ALTER TABLE blueprints ADD COLUMN consolidated_paths text[];
ALTER TABLE blueprints ADD COLUMN deprecated boolean DEFAULT false;
ALTER TABLE blueprints ADD COLUMN successor_id uuid;

-- Indexes for performance
CREATE INDEX idx_blueprints_deprecated ON blueprints(deprecated);
CREATE INDEX idx_blueprints_successor ON blueprints(successor_id);
CREATE INDEX idx_blueprints_md5 ON blueprints(file_md5);
```

**Create openscad_source table:**
```sql
CREATE TABLE openscad_source (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id uuid NOT NULL REFERENCES blueprints(id) ON DELETE CASCADE,
    openscad text NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_openscad_source_blueprint_id ON openscad_source(blueprint_id);

-- Trigger for automatic updated_at timestamp updates
CREATE TRIGGER update_openscad_source_updated_at
BEFORE UPDATE ON openscad_source
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Create tag priorities table:**
```sql
CREATE TABLE tag_priorities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_category text NOT NULL,
    tag_value text NOT NULL,
    priority_score integer NOT NULL DEFAULT 0,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    UNIQUE(tag_category, tag_value)
);

CREATE INDEX idx_tag_priorities_category ON tag_priorities(tag_category);
CREATE INDEX idx_tag_priorities_score ON tag_priorities(priority_score DESC);
```

#### 1.2 Incremental Scanner Updates

**Modify dropbox_scanner to output comparison data:**
- Generate filename+MD5 pairs for comparison
- Track file paths for consolidation detection
- Export structured data for loader consumption

**Enhance fixtures loader:**
- Fetch existing blueprint filename+MD5 pairs from database
- Implement comparison logic:
  - Same filename+MD5: metadata-only updates
  - New MD5, existing filename: deprecation + new version creation
  - Missing filename, existing MD5: path consolidation
  - Missing MD5: mark as deprecated
  - New filename+MD5: flag for manual review

#### 1.3 CLI Administrative Tools

**Build review interface:**
- List files without successors vs new files
- Implement scoring algorithm:
  - Levenshtein distance for filenames
  - Path element overlap scoring
  - Tag similarity comparison
- Interactive CLI for confirming predecessor/successor relationships

**Duplicate detection tool:**
- Search for same filename, different MD5
- Generate reports for manual review
- CLI interface for batch operations

#### 1.4 Migration Strategy

**Phase 1a: Add fields without changing workflow**
- Deploy schema changes
- Populate consolidated_paths for existing files
- Test new fields with existing data

**Phase 1b: Switch to incremental loading**
- Deploy new scanner and loader logic
- Run first incremental load with careful monitoring
- Validate no data loss occurred

**Success Criteria:**
- Zero data loss during migration
- Incremental loads complete successfully
- Historical file relationships properly established
- CLI tools functional for edge case management

## Phase 2: Documentation System Implementation

### Priority: HIGH
### Timeline: 2 weeks
### Dependencies: Phase 1 complete

#### 2.1 Database Schema for Documentation

**Create new blueprint_documentation table:**
```sql
-- Create documentation_type_enum for extensibility
CREATE TYPE documentation_type_enum AS ENUM ('changelog');

-- New blueprint_documentation table
CREATE TABLE blueprint_documentation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id uuid NOT NULL REFERENCES blueprints(id) ON DELETE CASCADE,
    document text NOT NULL,
    document_type documentation_type_enum NOT NULL DEFAULT 'changelog',
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_blueprint_documentation_blueprint_id ON blueprint_documentation(blueprint_id);
CREATE INDEX idx_blueprint_documentation_type ON blueprint_documentation(document_type);

-- Trigger for automatic updated_at timestamp updates
CREATE TRIGGER update_blueprint_documentation_updated_at
BEFORE UPDATE ON blueprint_documentation
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 2.2 Documentation Types and Structure

**Documentation types (extensible enum):**
- `changelog` - File version change descriptions (initial type)

**Text-based documentation:**
- Simple text field for changelog entries
- Future extensibility for additional documentation types
- Direct relationship to blueprints via blueprint_id

#### 2.3 Documentation API Implementation

**Core endpoints:**
```typescript
// Blueprint documentation
GET /api/blueprints/{blueprint_id}/documentation
Response: {
  documentation: BlueprintDocumentation[]
}

// Create changelog for specific blueprint
POST /api/blueprints/{blueprint_id}/documentation
Body: {
  document: string,
  document_type: 'changelog'
}

// Update specific documentation entry
PUT /api/blueprints/{blueprint_id}/documentation/{doc_id}
DELETE /api/blueprints/{blueprint_id}/documentation/{doc_id}
```

#### 2.4 Frontend Documentation Interface

**Blueprint documentation display:**
- Simple text display for changelog entries
- List of documentation entries by type
- Edit mode for authenticated admin users

**Admin documentation editor:**
- Simple text editor for changelog entries
- Documentation type selection (extensible)
- Direct association with blueprints

#### 2.5 Initial Content Migration

**Test with blueprint changelogs:**
- Create changelog documentation for ~20 existing blueprints
- Establish changelog patterns and templates
- Test simple text documentation system
- Validate direct blueprint association

**Success Criteria:**
- Documentation system handles text changelogs correctly
- Blueprint documentation association works properly
- Admin interface allows efficient content creation
- System ready for additional documentation types in future phases

## Phase 3: Tag Priority System and Default Population

### Priority: HIGH
### Timeline: 1-2 weeks
### Dependencies: Phase 2 complete

#### 3.1 Priority System Implementation

**Populate tag_priorities table:**
```sql
-- Example priority data
INSERT INTO tag_priorities (tag_category, tag_value, priority_score) VALUES
('texture', 'dungeon_stone', 100),
('connection', 'openforge', 90),
('build', 'topless', 80),
('connection', 'magnetic', 70),
('connection', 'flex', 60);
```

#### 3.2 Default Population Logic

**Backend implementation:**
- Create service to resolve blueprint defaults based on priorities
- Implement constraint satisfaction with priority weighting
- Ensure all blueprint constraints are met by default selections

**API endpoint:**
```typescript
GET /api/blueprints/{id}/defaults
Response: {
  parts: {
    [partName]: {
      blueprint_id: string,
      tags: string[],
      confidence: number
    }
  }
}
```

#### 3.3 Frontend Integration

**Update blueprint composition UI:**
- Pre-populate part selections on blueprint load
- Maintain existing constraint validation
- Add visual indicators for default vs custom selections

**Success Criteria:**
- Blueprints load with working defaults 90%+ of the time
- Default selection respects all blueprint constraints
- User can still override defaults normally
- Performance impact minimal

## Phase 4: Component Swapping System

### Priority: HIGH
### Timeline: 2 weeks
### Dependencies: Phase 3 complete

#### 4.1 Backend API Development

**Component alternatives endpoint:**
```typescript
POST /api/blueprints/component-alternatives
Body: {
  blueprint_id: string,
  current_parts: { [partName]: string }, // blueprint IDs
  swap_tag: string // e.g., "texture|dungeon_stone"
}
Response: {
  alternatives: {
    [tagValue]: {
      available: boolean,
      affected_parts: string[], // part names that would change
      preview_parts: { [partName]: string } // new blueprint IDs
    }
  }
}
```

**Implementation details:**
- Query all parts with the target tag category
- Test constraint satisfaction for each alternative
- Return only valid swaps that maintain blueprint integrity

#### 4.2 Frontend Swap Interface

**UI Components:**
- Swap buttons next to major tag categories (texture, connection, etc.)
- Dropdown/modal showing available alternatives
- Preview of affected parts before confirming swap
- Batch update of all affected parts

**UX Flow:**
1. User clicks "Swap Texture" button
2. Modal shows available textures with part counts
3. User selects new texture
4. Preview shows which parts will change
5. User confirms, all applicable parts update

**Success Criteria:**
- Swap operations complete in <2 seconds
- All blueprint constraints maintained after swap
- Clear visual feedback about what will change
- Intuitive UI that doesn't overwhelm users

## Phase 5: Authentication System

### Priority: MEDIUM-HIGH
### Timeline: 2-3 weeks
### Dependencies: Phase 4 complete

#### 5.1 Database Schema for Users

```sql
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    role text NOT NULL DEFAULT 'user',
    patreon_tier patreon_tier_enum, -- Tier-based permissions determined by ENUM value
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

CREATE TABLE user_identities (
    provider text NOT NULL, -- 'patreon' or 'google'
    provider_id text NOT NULL, -- OAuth provider's user ID
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Clean up OAuth links when user is deleted
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (provider, provider_id)
);

CREATE INDEX idx_user_identities_user_id ON user_identities(user_id);
```

#### 5.2 OAuth Integration

**Patreon OAuth:**
- Register application with Patreon
- Implement OAuth flow with tier detection
- Sync supporter list and tier levels
- Set up webhook for tier changes

**Google OAuth:**
- Configure Google OAuth application
- Implement standard OAuth 2.0 flow
- Handle account linking scenarios

#### 5.3 Session Management

**JWT-based sessions:**
- Implement secure token generation
- Store minimal user data in tokens
- Set appropriate expiration and refresh logic

#### 5.4 Role-Based Access Control

**Initial roles:**
- Admin: Full access to all features
- Patron: Enhanced features based on tier
- User: Standard read access

**Frontend integration:**
- Conditional feature rendering based on role
- Graceful degradation for unauthenticated users
- Clear messaging about patron benefits

**Success Criteria:**
- OAuth flows work reliably for both providers
- Patreon tier detection accurate and automatic
- Role-based features properly gated
- No degradation of anonymous user experience

## Phase 6: File History and Changelog Interface

### Priority: MEDIUM
### Timeline: 1-2 weeks
### Dependencies: Phase 2 complete (documentation system)

#### 6.1 Changelog Integration with Documentation System

**Changelog as documentation type:**
- Use `documentation_type: 'changelog'`
- Link changelogs to blueprint versions via blueprint_documentation
- Support markdown formatting with image references
- Namespace changelog images separately from instructions

**Enhanced blueprint schema:**
```sql
-- Remove simple changelog text field from Phase 1
ALTER TABLE blueprints DROP COLUMN IF EXISTS changelog;

-- Changelogs handled via existing documentation relationships
-- with documentation_type = 'changelog'
```

#### 6.2 Backend API Extensions

**History endpoints with documentation:**
```typescript
GET /api/blueprints/{blueprint_id}/history
Response: {
  versions: {
    id: string,
    created_at: string,
    changelog_docs: BlueprintDocumentation[], // document_type='changelog'
    file_size: number,
    deprecated: boolean,
    successor_id?: string
  }[]
}

// Create changelog for specific version
POST /api/blueprints/{blueprint_id}/documentation
Body: {
  document: string, // text content
  document_type: 'changelog'
}
```

#### 6.3 Frontend History Interface

**Version history modal:**
- Timeline view of file versions
- Changelog entries for each version
- Download links for specific versions
- Visual diff indicators where possible

**Admin changelog interface:**
- List of files needing changelog entries
- Inline editing for changelog text
- Bulk operations for similar changes

#### 6.4 Search Filtering Updates

**Hide deprecated versions:**
- Update all search queries to filter deprecated=false by default
- Add admin option to include deprecated versions
- Maintain deep links to specific versions

**Success Criteria:**
- Users can easily access and understand file history
- Deprecated versions properly hidden from normal searches
- Admin workflow for changelog management efficient
- Historical data preserved and accessible

## Phase 7: OpenSCAD Customizer Integration

### Priority: MEDIUM
### Timeline: 1 week
### Dependencies: Phase 5 complete (for parameter passing)

#### 7.1 Blueprint Metadata Updates

**Populate openscad_source table:**
- Identify blueprints with customizable versions
- Map to corresponding OpenSCAD files
- Create openscad_source records linked to blueprints

#### 7.2 Deep Linking Implementation

**Tag-to-parameter mapping:**
- Design flexible system for tag interpretation
- Implement per-customizer transformation logic
- Handle missing or invalid tag combinations

**URL generation:**
```typescript
GET /api/blueprints/{blueprint_id}/customize-url
Response: {
  customizer_url: string,
  parameters: { [key: string]: any }
}
```

#### 7.3 Frontend Integration

**Customize button:**
- Show only for blueprints with openscad_source
- Generate deep link with current tag configuration
- Open in new tab/window to customizer

**Success Criteria:**
- Customize buttons appear for appropriate blueprints
- Deep links successfully pre-populate customizer
- Tag-to-parameter mapping works for common cases
- Integration feels seamless to users

## NEW Phase 8: Patron Voting and Request System

### Priority: HIGH
### Timeline: 3-4 weeks
### Dependencies: Phase 5 complete (authentication system)

#### 8.1 Voting System Database Schema

**POLICY: All created_by and updated_by columns must use ON DELETE SET NULL to preserve audit trail while allowing user deletion. user_id fields that represent ownership (votes, requests) use ON DELETE CASCADE to clean up user data when accounts are deleted.**

**Core voting tables:**
```sql
-- ENUM types for voting system
CREATE TYPE voting_cycle_status AS ENUM ('active', 'closed', 'archived');
CREATE TYPE voting_item_type AS ENUM ('tile_set', 'specific_tile', 'feature');
CREATE TYPE voting_item_status AS ENUM ('voting', 'selected', 'in_progress', 'complete');
CREATE TYPE patron_request_priority AS ENUM ('normal', 'high', 'urgent');
CREATE TYPE patron_request_status AS ENUM ('requested', 'under_review', 'approved', 'in_progress', 'complete', 'rejected');
CREATE TYPE patreon_tier_enum AS ENUM ('Bronze', 'Silver', 'Gold', 'Platinum');

-- Voting cycles (monthly)
-- Each cycle represents a monthly voting period with automatic reset on the 1st of each month
-- Cycles are archived rather than deleted to preserve historical voting data
CREATE TABLE voting_cycles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_name text NOT NULL, -- e.g., "March 2025" - human-readable cycle identifier
    start_date date NOT NULL, -- When voting opens for this cycle
    end_date date NOT NULL, -- When voting closes for this cycle
    status voting_cycle_status NOT NULL DEFAULT 'active', -- active, closed, archived
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Voting questions (e.g., "What tile set should we work on next?")
-- Questions group related voting items together and define the voting context
-- Each question can have multiple voting items as options
CREATE TABLE voting_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question_name text NOT NULL, -- e.g., "What tile set should we work on next?"
    question_description text, -- Detailed explanation of what the question is asking
    question_type voting_item_type NOT NULL, -- tile_set, specific_tile, feature - determines voting mechanics
    category text, -- texture category for grouping (e.g., "dungeon_stone", "cave") - optional grouping
    cycle_id uuid REFERENCES voting_cycles(id) ON DELETE RESTRICT, -- Prevent accidental deletion of voting data
    status voting_item_status NOT NULL DEFAULT 'voting', -- Current kanban status of this question
    kanban_position integer DEFAULT 0, -- Position within the kanban board for this status
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Voting items (options within each question)
-- Each voting item represents one option that patrons can vote for within a question
-- Items can be hierarchical: tile_sets can have child specific_tiles
CREATE TABLE voting_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_name text NOT NULL, -- e.g., "Mausoleum/Crypts", "Desert Stone"
    item_description text, -- Detailed description of what this item represents
    details jsonb, -- structured data about the item (e.g., gap analysis results, rationale)
    question_id uuid NOT NULL REFERENCES voting_questions(id) ON DELETE CASCADE, -- Item belongs to a question
    -- vote_count and cumulative_votes calculated at query time from patron_votes via aggregation queries
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Individual patron votes
-- Each record represents one vote by one user for one voting item in one cycle
-- The voting_question_id is required to enforce the unique constraint (user_id, voting_question_id, cycle_id)
-- which ensures a user can only vote once per question per cycle, even though voting_question_id
-- is technically derivable from voting_item_id via voting_items.question_id
-- vote_weight is captured at voting time to preserve the user's tier-based voting power for that cycle
-- even if their tier changes later (e.g., user downgrades from Gold to Bronze tier)
-- All foreign keys use RESTRICT or CASCADE appropriately to preserve historical voting data
CREATE TABLE patron_votes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Delete votes when user account is deleted
    voting_question_id uuid NOT NULL REFERENCES voting_questions(id) ON DELETE CASCADE, -- Required for unique constraint enforcement
    voting_item_id uuid NOT NULL REFERENCES voting_items(id) ON DELETE CASCADE, -- The specific item being voted for
    cycle_id uuid NOT NULL REFERENCES voting_cycles(id) ON DELETE RESTRICT, -- Prevent vote deletion when cycle is deleted
    vote_weight integer NOT NULL DEFAULT 1, -- Vote weight captured at voting time (base 1 + bonus from tier)
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    UNIQUE(user_id, voting_question_id, cycle_id) -- One vote per question per user per cycle
);

-- Trigger to ensure voting_question_id consistency with voting_item_id
-- Prevents data integrity issues from denormalized question_id field
CREATE OR REPLACE FUNCTION check_vote_question_consistency()
RETURNS TRIGGER AS $$
DECLARE
    item_question_id uuid;
BEGIN
    SELECT question_id INTO item_question_id FROM voting_items WHERE id = NEW.voting_item_id;
    IF item_question_id <> NEW.voting_question_id THEN
        RAISE EXCEPTION 'voting_question_id does not match the question_id of the voting_item_id';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_vote_question_consistency
BEFORE INSERT OR UPDATE ON patron_votes
FOR EACH ROW EXECUTE FUNCTION check_vote_question_consistency();

-- Patron individual requests
-- Individual requests from premium tier patrons outside the voting system
-- These are separate from voting items and have their own kanban workflow
CREATE TABLE patron_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- Delete request when user account is deleted
    request_title text NOT NULL, -- Brief title of the request
    request_description text, -- Detailed description of what the patron is requesting
    priority_level patron_request_priority DEFAULT 'normal', -- normal, high, urgent - affects processing order
    status patron_request_status NOT NULL DEFAULT 'requested', -- Current kanban status
    kanban_position integer DEFAULT 0, -- Position within the kanban board for this status
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Tier-based permissions and limits
-- Defines voting and request capabilities for each Patreon tier
-- Referenced by users.patreon_tier to determine user permissions
CREATE TABLE tier_permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tier_name patreon_tier_enum NOT NULL UNIQUE, -- e.g., "Bronze", "Silver", "Gold" - matches Patreon tier names
    bonus_votes_per_cycle integer DEFAULT 0, -- Additional votes per cycle for premium tiers
    max_requests_per_month integer DEFAULT 0, -- Maximum individual requests per month (0 = no requests allowed)
    can_vote_specific_questions boolean DEFAULT false, -- Whether tier can vote on specific_tile questions
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Gap analysis reports
-- Automated analysis comparing tile sets to identify missing combinations
-- Used to generate voting items and guide development priorities
CREATE TABLE gap_analysis_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_name text NOT NULL, -- Human-readable name for the report
    base_set_tags text[] NOT NULL, -- tags defining the "complete" reference set (e.g., ["texture|dungeon_stone"])
    comparison_sets jsonb NOT NULL, -- sets being compared for gaps (e.g., ["texture|cut_stone", "texture|cave"])
    missing_items jsonb NOT NULL, -- structured data about missing items (e.g., {"size|width|2": ["wall", "corner"]})
    report_date date DEFAULT CURRENT_DATE, -- When the analysis was performed
    reviewed boolean DEFAULT false, -- Whether admin has reviewed and processed this report
    created_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    updated_by uuid REFERENCES users(id) ON DELETE SET NULL, -- POLICY: See section 8.1 for audit trail preservation policy
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

-- Trigger function for automatic updated_at timestamp updates
-- Automatically sets updated_at to current timestamp whenever a row is modified
-- Applied to all tables with updated_at columns to ensure accurate audit trail
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Voting System Performance Indexes
-- These indexes are critical for maintaining sub-second response times for voting operations
-- All indexes optimized for the most common query patterns in the voting system

-- Voting cycle queries
CREATE INDEX idx_voting_cycles_dates ON voting_cycles(start_date, end_date); -- Find active cycles by date range
CREATE INDEX idx_voting_cycles_status ON voting_cycles(status); -- Filter by cycle status (active/closed/archived)

-- Voting question queries
CREATE INDEX idx_voting_questions_cycle ON voting_questions(cycle_id); -- Get all questions for a cycle
CREATE INDEX idx_voting_questions_status ON voting_questions(status); -- Filter questions by kanban status
CREATE INDEX idx_voting_questions_cycle_status ON voting_questions(cycle_id, status); -- Combined filter for active questions in cycle

-- Voting item queries
CREATE INDEX idx_voting_items_question ON voting_items(question_id); -- Get all items for a question

-- Patron vote queries (most critical for performance)
CREATE INDEX idx_patron_votes_user_cycle ON patron_votes(user_id, cycle_id); -- Find user's votes for a cycle
CREATE INDEX idx_patron_votes_question ON patron_votes(voting_question_id); -- Count votes per question
CREATE INDEX idx_patron_votes_item ON patron_votes(voting_item_id); -- Count votes per item
CREATE INDEX idx_patron_votes_question_cycle ON patron_votes(voting_question_id, cycle_id); -- For vote count calculations per cycle
CREATE INDEX idx_patron_votes_user_question ON patron_votes(user_id, voting_question_id); -- Check if user already voted on question

-- Patron request queries
CREATE INDEX idx_patron_requests_user ON patron_requests(user_id); -- Find user's requests
CREATE INDEX idx_patron_requests_status ON patron_requests(status); -- Filter requests by kanban status
CREATE INDEX idx_patron_requests_user_status ON patron_requests(user_id, status); -- Combined filter for user's requests by status

-- User and tier queries
CREATE INDEX idx_users_patreon_tier ON users(patreon_tier); -- For vote weight calculations via JOIN

-- Gap analysis queries
CREATE INDEX idx_gap_analysis_reports_reviewed ON gap_analysis_reports(reviewed); -- Find unreviewed reports

-- Triggers for automatic updated_at timestamp updates
-- Ensures updated_at is always current without application-level timestamp management
-- This prevents missed updates from direct SQL, bulk operations, or forgotten application code
-- Standard pattern for reliable audit trails in PostgreSQL
CREATE TRIGGER update_voting_cycles_updated_at BEFORE UPDATE ON voting_cycles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_voting_questions_updated_at BEFORE UPDATE ON voting_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_voting_items_updated_at BEFORE UPDATE ON voting_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patron_votes_updated_at BEFORE UPDATE ON patron_votes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patron_requests_updated_at BEFORE UPDATE ON patron_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tier_permissions_updated_at BEFORE UPDATE ON tier_permissions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_gap_analysis_reports_updated_at BEFORE UPDATE ON gap_analysis_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### 8.2 Gap Analysis System Implementation

**Gap detection service:**
```typescript
// Service to analyze catalog gaps
class GapAnalysisService {
  async analyzeTextureGaps(baseTexture: string, comparisonTextures: string[]): Promise<GapReport> {
    // Query blueprints with base texture tags
    // Compare with each comparison texture
    // Identify missing combinations (size, shape, connection, etc.)
    // Return structured gap data
  }

  async generateVotingItems(gapReport: GapReport): Promise<VotingItemSuggestion[]> {
    // Convert gap analysis into aggregated voting items
    // Group related missing items
    // Generate descriptions and rationale
  }
}
```

**CLI gap analysis tool:**
- Compare tag combinations across texture sets
- Generate missing item reports
- Export suggestions for voting item creation
- Batch operations for creating voting items from gap analysis

#### 8.3 Voting Mechanics Implementation

**Security and Ownership Constraints:**
- **Vote Ownership**: Users can only create, modify, or delete their own votes
- **Request Ownership**: Users can only create, modify, or delete their own requests
- **Admin Limitations**: Admin users cannot directly modify patron votes or requests
- **Authentication Required**: All voting and request operations require valid authentication
- **Ownership Verification**: All update/delete operations verify resource ownership before allowing changes

**Core voting service:**
```typescript
class VotingService {
  async submitVote(userId: string, questionId: string, itemId: string, cycleId: string): Promise<void> {
    // Check user eligibility and tier permissions
    // Calculate and store vote_weight based on user's current tier
    // Handle vote changes within cycle (delete old vote for this question, insert new)
    // SECURITY: Ensure user can only vote for themselves
    // Note: Users can vote for one item per question per cycle
  }

  async updateVote(voteId: string, userId: string, newVotingItemId: string): Promise<void> {
    // SECURITY: Verify vote ownership before allowing updates
    // Only allow users to change which item they're voting for
    // vote_weight remains unchanged (preserves historical voting power)
    // Admin users cannot modify patron votes directly
  }

  async deleteVote(voteId: string, userId: string): Promise<void> {
    // SECURITY: Verify vote ownership before allowing deletion
    // Only allow users to delete their own votes
  }

  async archiveVotingCycle(cycleId: string): Promise<void> {
    // Change cycle status to 'archived' instead of deleting
    // This preserves all voting data while preventing new votes
    // Only archived cycles can be safely deleted after manual review
  }

  async getCurrentResults(cycleId: string, userId?: string): Promise<VotingResults> {
    // Calculate vote counts by summing stored vote_weight values from patron_votes
    // Return real-time vote tallies with historical vote weights
    // Include user's current votes if authenticated
    // Respect visibility rules (public read-only vs patron-only details)
    // Cache results for performance with new vote invalidation
  }

  async processMonthlyReset(): Promise<void> {
    // Automated monthly cycle management
    // Close current cycle, start new cycle
    // Archive old cycle data (change status to 'archived', don't delete)
    // Move winning items from "voting" to "selected" status
    // No vote count resets needed - calculated at query time
  }
}
```

**Vote weight capture at voting time:**
- **Stored vote weights**: vote_weight column in patron_votes captures tier-based voting power at time of vote
- **Historical preservation**: Vote weights remain fixed even if user's tier changes later
- **Performance optimization**: Vote counts calculated by summing stored weights, no complex JOINs needed
- **Simplified queries**: Vote aggregation queries are much simpler and faster
- **No race conditions**: Vote weight is captured once and never changes
- **Cached results**: Vote tallies cached for performance with invalidation on new votes
- **Simplified transactions**: Vote operations only need to insert/update/delete patron_votes records

**Example vote count queries:**
```sql
-- Current cycle vote count for an item
-- Calculates both raw vote count and tier-weighted vote count for a specific voting item
-- Uses stored vote_weight to preserve historical tier-based voting power
-- Filter condition in JOIN allows database optimizer to make better choices
SELECT
  vi.id,
  vi.item_name,
  COUNT(pv.id) as vote_count, -- Raw number of votes
  COALESCE(SUM(pv.vote_weight), 0) as weighted_votes -- Sum of stored vote weights
FROM voting_items vi
LEFT JOIN patron_votes pv ON vi.id = pv.voting_item_id
  AND pv.cycle_id IN (SELECT id FROM voting_cycles WHERE status = 'active')
WHERE vi.id = $1
GROUP BY vi.id, vi.item_name;

-- Current cycle vote count for active voting questions only
-- Returns vote counts for all items within a specific question that's still accepting votes
-- Filters out questions that have moved to 'selected', 'in_progress', or 'complete' status
SELECT
  vq.id,
  vq.question_name,
  vi.id as item_id,
  vi.item_name,
  COUNT(pv.id) as vote_count,
  COALESCE(SUM(pv.vote_weight), 0) as weighted_votes
FROM voting_questions vq
LEFT JOIN voting_items vi ON vq.id = vi.question_id
LEFT JOIN patron_votes pv ON vi.id = pv.voting_item_id
  AND pv.cycle_id IN (SELECT id FROM voting_cycles WHERE status = 'active')
WHERE vq.id = $1
  AND vq.status = 'voting' -- Only include questions still in voting status
GROUP BY vq.id, vq.question_name, vi.id, vi.item_name;

-- Vote count for a question (all items in the question)
-- Returns vote counts for all items within a question in the active voting cycle
-- Used for current cycle analysis and admin review of voting patterns
SELECT
  vq.id,
  vq.question_name,
  vi.id as item_id,
  vi.item_name,
  COUNT(pv.id) as vote_count,
  COALESCE(SUM(pv.vote_weight), 0) as weighted_votes
FROM voting_questions vq
LEFT JOIN voting_items vi ON vq.id = vi.question_id
LEFT JOIN patron_votes pv ON vi.id = pv.voting_item_id
  AND pv.cycle_id IN (SELECT id FROM voting_cycles WHERE status = 'active')
WHERE vq.id = $1
GROUP BY vq.id, vq.question_name, vi.id, vi.item_name;

-- Cumulative votes across all cycles
-- Calculates total votes for an item across all voting cycles (active, closed, archived)
-- Used for the cumulative voting system where votes persist until an item wins
-- No cycle filtering - includes all historical votes for the item
SELECT
  vi.id,
  vi.item_name,
  COUNT(pv.id) as cumulative_votes,
  COALESCE(SUM(pv.vote_weight), 0) as cumulative_weighted_votes
FROM voting_items vi
LEFT JOIN patron_votes pv ON vi.id = pv.voting_item_id
WHERE vi.id = $1
GROUP BY vi.id, vi.item_name;
```

#### 8.4 Kanban Workflow System

**Workflow management:**
```typescript
// Kanban state management - matches PostgreSQL ENUM types
enum VotingItemStatus {
  VOTING = 'voting',
  SELECTED = 'selected',
  IN_PROGRESS = 'in_progress',
  COMPLETE = 'complete'
}

enum PatronRequestStatus {
  REQUESTED = 'requested',
  UNDER_REVIEW = 'under_review',
  APPROVED = 'approved',
  IN_PROGRESS = 'in_progress',
  COMPLETE = 'complete',
  REJECTED = 'rejected'
}

enum VotingItemType {
  TILE_SET = 'tile_set',
  SPECIFIC_TILE = 'specific_tile',
  FEATURE = 'feature'
}

enum PatronRequestPriority {
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent'
}

enum VotingCycleStatus {
  ACTIVE = 'active',
  CLOSED = 'closed',
  ARCHIVED = 'archived'
}

// Hierarchical voting item structure
interface VotingItem {
  id: string;
  item_name: string;
  item_type: VotingItemType;
  parent_item_id?: string; // null for tile_sets, points to tile_set for specific_tiles
  child_items?: VotingItem[]; // specific tiles within this tile set
}

class KanbanService {
  async updateItemStatus(itemId: string, newStatus: string, position?: number): Promise<void> {
    // Update status and kanban position
    // Handle bidirectional movement (e.g., back to voting if blocked)
    // Maintain position ordering within status
  }

  async getKanbanBoard(type: 'voting' | 'requests'): Promise<KanbanBoard> {
    // Return organized kanban board data
    // Group items by status with position ordering
  }
}
```

#### 8.5 Voting API Implementation

**Complete voting API:**
```typescript
// Voting cycle management
GET /api/voting/current-cycle
Response: { cycle: VotingCycle, items: VotingItem[] }

POST /api/voting/cycles (admin only)
Body: { cycle_name: string, start_date: string, end_date: string }

PUT /api/voting/cycles/{cycle_id} (admin only)
DELETE /api/voting/cycles/{cycle_id} (admin only)

// Voting items
GET /api/voting/items?cycle_id={cycle_id}&status={status}&parent_item_id={parent_id}
Response: { items: VotingItem[], user_votes?: UserVote[] }

POST /api/voting/items (admin only)
Body: { item_name: string, item_description: string, item_type: VotingItemType, parent_item_id?: string, category?: string, details?: object }

PUT /api/voting/items/{item_id} (admin only)
DELETE /api/voting/items/{item_id} (admin only)

// Hierarchical voting queries
GET /api/voting/items/{item_id}/children
Response: { child_items: VotingItem[] }

GET /api/voting/items/{item_id}/parent
Response: { parent_item: VotingItem }

// Voting actions
POST /api/voting/votes
Body: { voting_item_id: string, cycle_id: string }
// SECURITY: User can only vote for themselves (userId from auth token)

PUT /api/voting/votes/{vote_id}
Body: { voting_item_id: string } // Change which item they're voting for
// SECURITY: User can only modify their own votes (verify vote ownership)
// SECURITY: vote_weight is calculated automatically based on user tier, not user-editable

DELETE /api/voting/votes/{vote_id}
// SECURITY: User can only delete their own votes (verify vote ownership)

GET /api/voting/results/{cycle_id}
Response: { results: VotingResults, user_votes?: UserVote[] }

// Patron requests
GET /api/patron-requests
Response: { requests: PatronRequest[] } // filtered by user unless admin

POST /api/patron-requests
Body: { request_title: string, request_description: string, priority_level?: PatronRequestPriority }
// SECURITY: User can only create requests for themselves (userId from auth token)

PUT /api/patron-requests/{request_id}
Body: { request_title?: string, request_description?: string, priority_level?: PatronRequestPriority }
// SECURITY: User can only modify their own requests (verify request ownership)

DELETE /api/patron-requests/{request_id}
// SECURITY: User can only delete their own requests (verify request ownership)

// Admin gap analysis
GET /api/admin/gap-analysis/reports
POST /api/admin/gap-analysis/reports
Body: { base_set_tags: string[], comparison_sets: object }

PUT /api/admin/gap-analysis/reports/{report_id}
Body: { reviewed: boolean }

POST /api/admin/gap-analysis/generate-voting-items/{report_id}
Response: { created_items: VotingItem[] }

// Supporter feedback import
POST /api/admin/supporter-import/from-sheets
Body: { sheet_id: string, sheet_name?: string }
Response: { imported_requests: SupporterFeedback[], frequency_analysis: FrequencyAnalysis }

POST /api/admin/supporter-import/create-voting-items
Body: { categorized_requests: CategorizedRequests }
Response: { created_items: VotingItem[] }

// Admin kanban management
PUT /api/admin/kanban/voting-items/{item_id}/status
Body: { status: VotingItemStatus, position?: number }

PUT /api/admin/kanban/patron-requests/{request_id}/status
Body: { status: PatronRequestStatus, position?: number }

GET /api/admin/kanban/board/{type}
Response: { board: KanbanBoard }

// Tier permissions management
GET /api/admin/tier-permissions
PUT /api/admin/tier-permissions/{tier_name}
Body: { bonus_votes_per_cycle: number, max_requests_per_month: number, can_vote_specific_questions: boolean }
```

#### 8.6 Frontend Voting Interface

**Patron voting dashboard:**
- Current voting cycle display with countdown
- Voting items organized by category (tile sets, specific tiles, features)
- Real-time vote tallies with visual progress bars
- User's current votes highlighted with ability to change
- Tier benefits clearly displayed (bonus votes available, etc.)

**Voting item interface:**
- Expandable cards showing item details and rationale
- Gap analysis information where applicable ("Missing from cut_stone: 1x corner wall, 3x straight wall...")
- Vote buttons with weight indicators for premium tiers
- Visual feedback for vote submission and changes

**Patron request interface:**
- Request submission form with character limits
- Personal request history with status tracking
- Monthly request limit display with reset countdown
- Request status updates with kanban position visibility

**Public voting results:**
- Read-only view of current and past voting results
- Encouragement messaging to become a patron
- Clear display of what patrons can influence
- Links to Patreon signup with specific tier benefits

#### 8.7 Admin Voting Management Interface

**Gap analysis dashboard:**
- Generate new gap analysis reports with texture set selection
- Review pending gap analysis reports with missing item lists
- Create aggregated voting items from gap analysis with batch operations
- Historical gap analysis tracking to see evolution over time

**Supporter feedback import dashboard:**
- Import Google Sheets form responses with supporter feedback
- View frequency analysis of most requested items
- Review categorized requests before creating voting items
- Batch creation of voting items from supporter suggestions
- Historical import tracking and feedback evolution

**Kanban management:**
- Drag-and-drop interface for both voting items and patron requests
- Bulk status updates for similar items
- Progress tracking with visual indicators
- Integration with catalog to link completed items to released blueprints

**Voting cycle management:**
- Manual cycle controls (close early, extend deadline)
- Voting participation analytics and tier breakdown
- Item performance tracking (votes per day, cumulative trends)
- Automated monthly reset configuration
- **Cycle archiving**: Change status to 'archived' instead of deletion
- **Data preservation**: Archived cycles retain all voting data for historical analysis

**Tier permission configuration:**
- Adjust bonus votes per tier with live preview of impact
- Set request limits with usage tracking
- Configure special permissions for experimental features
- A/B testing framework for voting mechanics

#### 8.8 Patreon Integration Enhancements

**Supporter List Import System:**
```typescript
interface SupporterFeedback {
  timestamp: string;
  nextCompletion: string;
  nextSetRequest: string;
  scatterEncounters: string;
  feedback: string;
  newTileIdea: string;
}

class SupporterImportService {
  async importFromGoogleSheets(sheetId: string): Promise<ImportResult> {
    // Parse Google Sheets data with columns:
    // - "What next set do you want to see" → tile_set requests
    // - "Scatter/encounters" → scatter/encounter requests
    // - "Got an idea that has yet to get covered, feedback or concerns?" → feature requests
    // - "New tile type idea" → new tile type concepts
  }

  async analyzeFrequency(requests: string[]): Promise<FrequencyAnalysis> {
    // Count duplicate requests to identify popularity
    // Group similar requests (e.g., "Mausoleum/Crypts" variations)
    // Return top requested items with counts
  }

  async categorizeRequests(requests: string[]): Promise<CategorizedRequests> {
    // Automatically classify into voting_item_type:
    // - tile_set: Complete tile sets (Mausoleum/Crypts, Desert Stone)
    // - specific_tile: Individual tile types (Grass floor, Inn tables)
    // - feature: System improvements (MEGA folder, metric standardization)
  }

  async createVotingItems(categorizedRequests: CategorizedRequests): Promise<VotingItem[]> {
    // Generate voting items from analyzed requests
    // Create detailed descriptions from original feedback
    // Note: Vote counts calculated at query time, not stored
  }
}

// Example data structure from Google Sheets:
// Row 2: "Mausoleum/Crypts (Lots of grottos for bodies, urns, etc)" → tile_set
// Row 89: "Inn tables covered with maps, books, scrolls..." → specific_tile
// Row 97: "MEGA folder like mz4250, searchable, organized..." → feature
```

**Automated monthly post generation (stretch goal):**
```typescript
class PatreonPostService {
  async generateMonthlyPost(cycleId: string): Promise<PatreonPost> {
    // Compile voting results with winning items
    // Generate summary of work completed from previous month
    // Create formatted post with links back to catalog
    // Include participation statistics and thanks
  }

  async postToPatreon(post: PatreonPost): Promise<void> {
    // Use Patreon API to create new post
    // Handle posting scheduling and formatting
    // Track posted cycles to avoid duplicates
  }
}
```

**Enhanced tier synchronization:**
- Real-time webhook processing for tier changes
- **Cache invalidation**: When a user's tier changes, caches related to their permissions (e.g., ability to vote, request limits) should be invalidated, not historical vote results
- **Historical vote preservation**: Vote weights remain fixed at the time of voting, unaffected by later tier changes
- Request limit adjustments on tier upgrades/downgrades
- Historical tracking of tier changes for analytics

#### 8.9 Performance and Monitoring

**Vote aggregation optimization:**
- Vote aggregation by summing pre-calculated `vote_weight` from `patron_votes` table
- Cached vote totals with invalidation on new votes or vote changes
- Read replicas for voting result queries
- Query-time aggregation with optimized indexes for performance

**Real-time updates:**
- WebSocket connections for live vote result updates
- Event-driven architecture for vote submission notifications
- Optimistic UI updates with conflict resolution
- Graceful fallback to polling for WebSocket failures

**Analytics and monitoring:**
- Voting participation tracking by tier and time
- Gap analysis effectiveness metrics
- Request completion rate monitoring
- System performance monitoring during high-traffic voting periods

#### 8.10 Testing Strategy for Voting System

**Unit testing:**
- Vote weighting calculations
- Gap analysis algorithms
- Cumulative vote management
- Tier permission enforcement

**Integration testing:**
- End-to-end voting workflows
- Patreon webhook processing
- Monthly cycle reset automation
- Kanban state transitions

**Load testing:**
- High-traffic voting scenarios (end of month rush)
- Real-time update performance under load
- Database performance with large vote datasets
- Cache invalidation and refresh performance

**User acceptance testing:**
- Voting UI usability across devices
- Admin workflow efficiency
- Gap analysis accuracy validation
- Public view effectiveness for conversion

**Success Criteria:**
- Voting system supports 1000+ concurrent users during peak times
- Vote submission completes in <1 second 95% of the time
- Gap analysis identifies relevant missing items with 95% accuracy
- Monthly cycle reset completes automatically without manual intervention
- Admin kanban operations complete in <500ms
- Real-time vote updates reach users within 2 seconds
- Patreon tier sync processes within 30 seconds of webhook receipt
- **SECURITY**: Zero instances of users modifying other users' votes or requests
- **SECURITY**: All ownership verification checks pass 100% of the time

## Risk Management and Rollback Plans

### Phase 1 Risks
**Risk**: Data loss during migration
**Mitigation**: Full database backups, staged rollout, extensive testing
**Rollback**: Restore from backup, revert to old loading process

### Phase 2-3 Risks
**Risk**: Performance degradation from complex queries
**Mitigation**: Database indexing, query optimization, caching
**Rollback**: Feature flags to disable new functionality

### Phase 4-5 Risks
**Risk**: OAuth integration failures
**Mitigation**: Thorough testing with multiple accounts, error handling
**Rollback**: Graceful fallback to anonymous access

### Phase 6-7 Risks
**Risk**: UI complexity overwhelming users
**Mitigation**: Progressive disclosure, user testing, clear documentation
**Rollback**: Feature flags to hide new interfaces

### NEW Phase 8 Risks
**Risk**: Voting system performance degradation during peak usage
**Mitigation**: Load testing, caching strategy, read replicas, WebSocket fallbacks
**Rollback**: Feature flags to disable real-time updates, fallback to polling

**Risk**: Gap analysis producing irrelevant or confusing suggestions
**Mitigation**: Manual review workflow, admin approval process, feedback collection
**Rollback**: Disable automatic gap analysis, manual voting item creation only

**Risk**: Voting mechanics perceived as unfair or confusing
**Mitigation**: Clear documentation, transparent vote weight display, feedback channels
**Rollback**: Reset to simple one-vote-per-patron mechanics

**Risk**: Patreon integration breaking due to API changes
**Mitigation**: Error handling, manual fallback processes, monitoring alerts
**Rollback**: Manual tier management, disable automatic sync

## Testing Strategy

### Automated Testing
- Unit tests for all new backend logic
- Integration tests for OAuth flows
- Database migration tests with real data subsets
- API endpoint testing for new functionality
- **NEW**: Voting system load testing and vote aggregation accuracy tests

### Manual Testing
- Full workflow testing for each phase
- Cross-browser testing for frontend changes
- Performance testing with production data volumes
- User acceptance testing for major UX changes
- **NEW**: Voting workflow testing across multiple user tiers and scenarios

### Monitoring and Observability
- Database performance monitoring during migration
- Error tracking for new API endpoints
- User behavior analytics for new features
- System health monitoring throughout rollout
- **NEW**: Voting system performance monitoring and participation analytics

## Success Metrics

### Technical Metrics
- Zero data loss during migration
- <10% performance degradation in worst case
- >95% uptime during transition periods
- OAuth success rate >98%
- **NEW**: Voting system response time <1 second for 95% of operations
- **NEW**: Monthly cycle reset automation 100% success rate

### User Experience Metrics
- Default population works for >90% of blueprints
- Component swapping completes in <2 seconds
- User authentication friction minimal
- Historical data access intuitive and fast
- **NEW**: >80% patron participation in monthly voting
- **NEW**: <5% user confusion rate for voting interface

### Business Metrics
- Increased user engagement with new features
- Patron conversion improvements
- Reduced support requests
- Positive community feedback
- **NEW**: Voting-driven development reduces manual priority decisions by 70%
- **NEW**: Gap analysis accuracy improves development efficiency
- **NEW**: Patron request system increases tier upgrade conversion by 20%

This implementation plan provides a structured approach to delivering significant enhancements while maintaining system stability and user experience quality, now including a comprehensive patron voting and request system that strengthens community engagement and development prioritization.
