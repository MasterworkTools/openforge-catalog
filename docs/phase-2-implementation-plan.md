# Phase 2: Documentation System Implementation Plan

## Overview

This document outlines the implementation strategy for Phase 2 of the OpenForge Catalog system, focusing on the documentation system with support for blueprint documentation, tag documentation, changelog management, and image handling.

## Phase 2: Documentation System Implementation

### Priority: HIGH
### Timeline: 2-3 weeks
### Dependencies: Phase 1 complete

## Database Schema Updates

### 2.1 Documentation Type Enum Extension

**Extend documentation_type_enum to include new types:**
```sql
-- Update the existing enum to include 'instructions'
ALTER TYPE documentation_type_enum ADD VALUE 'instructions';
```

### 2.2 Image Type Support

**Add image_type to images table:**
```sql
-- Create image_type_enum
CREATE TYPE image_type_enum AS ENUM ('thumbnail', 'documentation');

-- Add image_type column to images table
-- NOT NULL DEFAULT 'thumbnail' automatically sets all existing images as thumbnails
ALTER TABLE images ADD COLUMN image_type image_type_enum NOT NULL DEFAULT 'thumbnail';

-- Create index for performance
CREATE INDEX idx_images_type ON images(image_type);
```

### 2.3 Tags Documentation Table

**Create tags_documentation table following blueprint_documentation pattern:**
```sql
-- New tags_documentation table
CREATE TABLE tags_documentation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tag text[] NOT NULL, -- Full tag array (e.g., ["texture", "dungeon_stone"])
    document text NOT NULL,
    document_type documentation_type_enum NOT NULL DEFAULT 'instructions',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_tags_documentation_tag ON tags_documentation USING GIN(tag);
CREATE INDEX idx_tags_documentation_type ON tags_documentation(document_type);

-- Trigger for automatic updated_at timestamp updates
CREATE TRIGGER update_tags_documentation_updated_at
BEFORE UPDATE ON tags_documentation
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 2.4 Session Management Table

**Create sessions table for admin authentication:**
```sql
-- Sessions table for authentication (currently used for admin sessions)
-- Sessions last for 30 days and are automatically cleaned up after expiration
-- To invalidate a compromised session, simply delete the session record
CREATE TABLE sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token_hash text NOT NULL UNIQUE, -- Hashed version of session token for security
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz NOT NULL, -- Set to created_at + 30 days
    last_used_at timestamptz NOT NULL DEFAULT now() -- Updated at most once per hour to avoid performance issues
);

-- Indexes for performance
CREATE INDEX idx_sessions_token ON sessions(session_token_hash);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Trigger function to update last_used_at column (only if more than 1 hour has passed)
CREATE OR REPLACE FUNCTION update_last_used_at_column()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update last_used_at if more than 1 hour has passed since last update
    -- This prevents performance issues from frequent session validations
    IF EXTRACT(EPOCH FROM (now() - OLD.last_used_at)) > 3600 THEN -- 3600 seconds = 1 hour
        NEW.last_used_at := now();
    ELSE
        -- Revert to old value if update happens within the one-hour window
        NEW.last_used_at := OLD.last_used_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic last_used_at updates on UPDATE
CREATE TRIGGER update_sessions_last_used
BEFORE UPDATE ON sessions
FOR EACH ROW EXECUTE FUNCTION update_last_used_at_column();
```

## API Implementation

**Authentication Note:** All protected endpoints accept either:
- API key in request headers: `Authorization: Bearer <api_key>`
- Active session cookie (established via `/api/admin/sessions`)

**Note:** Existing endpoints that currently require API keys will be updated to also accept active session cookies, providing a consistent authentication experience across the entire API.

### 2.5 Blueprint Documentation API

**Core endpoints for blueprint documentation:**
```typescript
// Get all documentation for a blueprint
GET /api/blueprints/{blueprint_id}/documentation
Response: {
  documentation: BlueprintDocumentation[]
}

// Get specific documentation entry
GET /api/blueprints/{blueprint_id}/documentation/{doc_id}
Response: {
  documentation: BlueprintDocumentation
}

// Create documentation for blueprint (requires API key or active session)
POST /api/blueprints/{blueprint_id}/documentation
Body: {
  document: string,
  document_type: 'changelog' | 'instructions'
}
Response: {
  documentation: BlueprintDocumentation
}

// Update specific documentation entry (requires API key or active session)
PUT /api/blueprints/{blueprint_id}/documentation/{doc_id}
Body: {
  document: string,
  document_type: 'changelog' | 'instructions'
}
Response: {
  documentation: BlueprintDocumentation
}

// Delete specific documentation entry (requires API key or active session)
DELETE /api/blueprints/{blueprint_id}/documentation/{doc_id}
Response: { success: boolean }
```

### 2.6 Tag Documentation API

**Core endpoints for tag documentation:**
```typescript
// Get documentation for a specific tag
// URL: /api/tags/texture/dungeon_stone/documentation
// Flask router converts "texture/dungeon_stone" to ["texture", "dungeon_stone"] via TagConverter
GET /api/tags/{tag_array}/documentation
Response: {
  documentation: TagDocumentation[]
}

// Get specific tag documentation entry
// URL: /api/tags/texture/dungeon_stone/documentation/123
GET /api/tags/{tag_array}/documentation/{doc_id}
Response: {
  documentation: TagDocumentation
}

// Create documentation for tag (requires API key or active session)
// URL: /api/tags/texture/dungeon_stone/documentation
POST /api/tags/{tag_array}/documentation
Body: {
  document: string,
  document_type: 'instructions'
}
Response: {
  documentation: TagDocumentation
}

// Update specific tag documentation entry (requires API key or active session)
// URL: /api/tags/texture/dungeon_stone/documentation/123
PUT /api/tags/{tag_array}/documentation/{doc_id}
Body: {
  document: string,
  document_type: 'instructions'
}
Response: {
  documentation: TagDocumentation
}

// Delete specific tag documentation entry (requires API key or active session)
// URL: /api/tags/texture/dungeon_stone/documentation/123
DELETE /api/tags/{tag_array}/documentation/{doc_id}
Response: { success: boolean }
```

### 2.7 Image Management API

**Core endpoints for image management:**
```typescript
// Get all documentation images (requires API key or active session)
GET /api/admin/images?type=documentation
Response: {
  images: Image[]
}

// Upload new documentation image (requires API key or active session)
POST /api/admin/images
Body: FormData with file
Response: {
  image: Image
}

// Update image name (requires API key or active session)
PUT /api/admin/images/{image_id}
Body: { image_name: string }
Response: {
  image: Image
}

// Delete image (requires API key or active session)
DELETE /api/admin/images/{image_id}
Response: { success: boolean }
```

### 2.8 Session Management API

**Core endpoints for session management (currently admin-only):**
```typescript
// Create admin session
POST /api/admin/sessions
Body: { api_key: string }
Response: {
  session_token: string,
  expires_at: string
}

// Validate session
GET /api/admin/sessions/validate
Headers: { Authorization: Bearer <session_token> }
Response: {
  valid: boolean,
  expires_at: string
}

// Delete session (logout)
DELETE /api/admin/sessions
Headers: { Authorization: Bearer <session_token> }
Response: { success: boolean }
```

**Session management implementation:**
```python
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SessionService:
    def create_session(self, api_key: str) -> Dict:
        """Create new session (30 days duration, currently admin-only)."""
        # Verify API key matches environment variable (constant-time comparison)
        # Raises KeyError at runtime if ADMIN_API_KEY is not set (fail-fast behavior)
        if not secrets.compare_digest(api_key, os.environ['ADMIN_API_KEY']):
            raise ValueError("Invalid API key")

        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        session_token_hash = hashlib.sha256(session_token.encode()).hexdigest()

        # Set expiration to 30 days from now
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        # Store hash in database
        session_id = self.db.insert_session(session_token_hash, expires_at)

        return {
            "session_token": session_token,
            "expires_at": expires_at.isoformat()
        }

    def validate_session(self, session_token: str) -> Optional[Dict]:
        """Validate session token and update last_used_at (throttled by trigger). Returns safe session data if valid."""
        try:
            session_token_hash = hashlib.sha256(session_token.encode()).hexdigest()

            # First validate the session exists and is not expired
            session = self.db.get_session_by_hash(session_token_hash)
            if not session or session['expires_at'] < datetime.now(timezone.utc):
                return None

            # If valid, trigger an UPDATE to refresh last_used_at (throttled by trigger)
            # This UPDATE will be caught by the trigger which only updates if >1 hour has passed
            try:
                self.db.update_session_last_used(session_token_hash)
            except Exception as update_error:
                # Log the error but don't fail validation - the session is still valid
                # The last_used_at update is a performance optimization, not critical
                logger.warning(f"Failed to update session last_used_at: {update_error}")

            # Return safe session data (exclude sensitive fields like session_token_hash)
            return {
                'id': session['id'],
                'created_at': session['created_at'],
                'expires_at': session['expires_at'],
                'last_used_at': session['last_used_at']
            }

        except Exception as e:
            # Log the error and fail validation gracefully
            logger.error(f"Session validation failed: {e}")
            return None

    def delete_session(self, session_token: str) -> bool:
        """Delete session (logout). To invalidate compromised sessions, simply delete the record."""
        try:
            session_token_hash = hashlib.sha256(session_token.encode()).hexdigest()
            return self.db.delete_session_by_hash(session_token_hash)
        except Exception as e:
            logger.error(f"Session deletion failed: {e}")
            return False

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (run periodically)."""
        try:
            return self.db.delete_expired_sessions()
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0

# Database methods for session management
class SessionDatabase:
    def get_session_by_hash(self, session_token_hash: str) -> Optional[Dict]:
        """Get session by token hash."""
        # SELECT * FROM sessions WHERE session_token_hash = %s

    def update_session_last_used(self, session_token_hash: str) -> bool:
        """Update last_used_at for session (triggers throttled update)."""
        # UPDATE sessions SET last_used_at = now() WHERE session_token_hash = %s
        # This UPDATE will be caught by the trigger which only updates if >1 hour has passed

    def validate_session_hash(self, session_token_hash: str) -> bool:
        """Legacy method - use get_session_by_hash + update_session_last_used instead."""
        # Deprecated: Use the new validation flow above
```

### 2.9 Changelog History API

**Endpoint for retrieving changelog history:**
```typescript
// Get changelog history for blueprint (recursive successor search)
GET /api/blueprints/{blueprint_id}/changelog-history?limit=10&offset=0
Response: {
  changelogs: {
    blueprint_id: string,
    blueprint_name: string,
    changelog: string | null, // null if blueprint has no changelog documentation
    created_at: string | null, // null if no changelog documentation
    version_info: {
      deprecated: boolean,
      successor_id?: string
    }
  }[],
  has_more: boolean,
  total_count: number
}
```

## Backend Implementation

### 2.10 Database Schema Migration

**Create migration script (version_09.py):**
```python
@SchemaVersionDecorator(9)
class SchemaVersion9(SchemaBase):
    def up_impl(self, curs: cursor):
        self.extend_documentation_type_enum(curs)
        self.add_image_type_support(curs)
        self.create_tags_documentation_table(curs)
        self.create_sessions_table(curs)
        self.migrate_existing_images(curs)

    def down_impl(self, curs: cursor):
        self.drop_sessions_table(curs)
        self.drop_tags_documentation_table(curs)
        self.remove_image_type_support(curs)
        # Note: PostgreSQL doesn't support dropping ENUM values
        # The 'instructions' value will remain in documentation_type_enum
        # This is acceptable as it doesn't break existing functionality
```

### 2.11 SQL Functions

**Create SQL functions for documentation operations:**
```sql
-- Function to get changelog history recursively
CREATE OR REPLACE FUNCTION get_blueprint_changelog_history(
    blueprint_id uuid,
    max_depth integer DEFAULT 10
) RETURNS TABLE (
    blueprint_id uuid,
    blueprint_name text,
    changelog text,
    created_at timestamptz,
    depth integer,
    successor_id uuid,
    deprecated boolean
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE changelog_chain AS (
        -- Start with the current blueprint
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            bd.document,
            bd.created_at,
            0 as depth,
            b.deprecated
        FROM blueprints b
        LEFT JOIN blueprint_documentation bd ON b.id = bd.blueprint_id
            AND bd.document_type = 'changelog'
        WHERE b.id = $1

        UNION ALL

        -- Follow successor chain
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            bd.document,
            bd.created_at,
            cc.depth + 1,
            b.deprecated
        FROM blueprints b
        LEFT JOIN blueprint_documentation bd ON b.id = bd.blueprint_id
            AND bd.document_type = 'changelog'
        INNER JOIN changelog_chain cc ON b.id = cc.successor_id
        WHERE cc.depth < $2 AND cc.successor_id IS NOT NULL
    )
    SELECT
        cc.id,
        cc.blueprint_name,
        cc.document,
        cc.created_at,
        cc.depth,
        cc.successor_id,
        cc.deprecated
    FROM changelog_chain cc
    ORDER BY depth ASC, created_at DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql;
```

### 2.12 Backend Services

**Flask routing with custom tag converter:**
```python
from werkzeug.routing import BaseConverter

# Custom converter for tag arrays
class TagConverter(BaseConverter):
    def to_python(self, value):
        # Convert "texture/dungeon_stone" to ["texture", "dungeon_stone"]
        return value.split('/')

    def to_url(self, value):
        # Convert ["texture", "dungeon_stone"] to "texture/dungeon_stone"
        return '/'.join(value)

# Register the converter
app.url_map.converters['tag'] = TagConverter

# Route definitions
# Note: Service layer will accept either tag arrays or pipe-delimited strings
# based on compatibility with existing code and database operations
@app.route('/api/tags/<tag:tag_array>/documentation')
def get_tag_documentation(tag_array):
    # tag_array is already ["texture", "dungeon_stone"]
    # Pass the array directly to the service layer for better consistency
    return get_tag_documentation_service(tag_array)

@app.route('/api/tags/<tag:tag_array>/documentation/<doc_id>')
def get_tag_documentation_entry(tag_array, doc_id):
    return get_tag_documentation_entry_service(tag_array, doc_id)

@app.route('/api/tags/<tag:tag_array>/documentation', methods=['POST'])
def create_tag_documentation(tag_array):
    return create_tag_documentation_service(tag_array, request.json)

@app.route('/api/tags/<tag:tag_array>/documentation/<doc_id>', methods=['PUT'])
def update_tag_documentation(tag_array, doc_id):
    return update_tag_documentation_service(tag_array, doc_id, request.json)

@app.route('/api/tags/<tag:tag_array>/documentation/<doc_id>', methods=['DELETE'])
def delete_tag_documentation(tag_array, doc_id):
    return delete_tag_documentation_service(tag_array, doc_id)
```

**Create documentation service classes:**
```python
class DocumentationService:
    def get_blueprint_documentation(self, blueprint_id: str) -> List[Dict]:
        """Get all documentation for a blueprint."""

    def get_tag_documentation(self, tag_array: List[str]) -> List[Dict]:
        """Get documentation for a specific tag.

        Args:
            tag_array: A tag array (e.g., ["texture", "dungeon_stone"]) from the Flask route
        """

    def create_blueprint_documentation(self, blueprint_id: str, data: Dict) -> Dict:
        """Create new documentation for a blueprint."""

    def create_tag_documentation(self, tag_array: List[str], data: Dict) -> Dict:
        """Create new documentation for a tag.

        Args:
            tag_array: A tag array (e.g., ["texture", "dungeon_stone"]) from the Flask route
            data: Documentation data
        """

    def get_changelog_history(self, blueprint_id: str, limit: int = 10, offset: int = 0) -> Dict:
        """Get recursive changelog history for a blueprint."""

class ImageService:
    def upload_documentation_image(self, file_data: bytes, filename: str) -> Dict:
        """Upload new documentation image to S3."""

    def get_documentation_images(self) -> List[Dict]:
        """Get all documentation images."""

    def update_image_name(self, image_id: str, new_name: str) -> Dict:
        """Update image name."""

class SessionService:
    def create_session(self, api_key: str) -> Dict:
        """Create new admin session."""

    def validate_session(self, session_token: str) -> bool:
        """Validate session token."""

    def delete_session(self, session_token: str) -> bool:
        """Delete session (logout)."""
```

## Frontend Implementation

### 2.13 Blueprint Detail Page Updates

**Add tabbed interface to blueprint detail page:**
```typescript
// Blueprint detail page with tabs
interface BlueprintDetailTabs {
  info: BlueprintInfoTab;        // Existing blueprint information
  documentation?: DocumentationTab; // Blueprint + tag documentation
  changelog?: ChangelogTab;      // Changelog history
}

// Documentation tab component
const DocumentationTab = ({ blueprint }: { blueprint: Blueprint }) => {
  const [blueprintDocs, setBlueprintDocs] = useState<Documentation[]>([]);
  const [tagDocs, setTagDocs] = useState<Documentation[]>([]);

  // Load blueprint documentation
  // Load documentation from all blueprint tags
  // Render combined documentation with markdown support
};

// Changelog tab component
const ChangelogTab = ({ blueprint }: { blueprint: Blueprint }) => {
  const [changelogs, setChangelogs] = useState<ChangelogEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);

  // Load changelog history with pagination
  // Support "Load More" functionality
};
```

### 2.14 Admin Interface

**Create admin interface at `/admin`:**
```typescript
// Admin layout with session management
const AdminLayout = ({ children }: { children: ReactNode }) => {
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState('');

  // Session management
  // API key input and validation
  // Protected route wrapper
};

// Admin navigation
const AdminNavigation = () => {
  return (
    <nav>
      <Link to="/admin/blueprints">Blueprint Documentation</Link>
      <Link to="/admin/tags">Tag Documentation</Link>
      <Link to="/admin/images">Image Management</Link>
      <Link to="/admin/deprecated">Deprecated Objects</Link>
    </nav>
  );
};
```

### 2.15 Documentation Editor

**Create documentation editor component using @uiw/react-md-editor:**

**Note:** For Next.js applications, use dynamic import to avoid SSR issues:
```typescript
import dynamic from "next/dynamic";
const MDEditor = dynamic(
  () => import("@uiw/react-md-editor"),
  { ssr: false }
);
```
```typescript
import MDEditor from '@uiw/react-md-editor';
import "@uiw/react-md-editor/markdown-editor.css";
import "@uiw/react-markdown-preview/markdown.css";

const DocumentationEditor = ({
  blueprintId,
  tagArray,
  documentType
}: DocumentationEditorProps) => {
  const [content, setContent] = useState('');
  const [images, setImages] = useState<Image[]>([]);
  const [showImagePicker, setShowImagePicker] = useState(false);
  const editorRef = useRef<any>(null);

  // Custom image upload handler for MDEditor
  const handleImageUpload = async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/admin/images', {
      method: 'POST',
      body: formData
    });

    const { image } = await response.json();
    return image.url; // Return URL for markdown insertion
  };

  // Insert image markdown using the editor's API
  const insertImageMarkdown = (image: Image) => {
    const imageMarkdown = `![${image.image_name}](${image.url})`;

    // Use the editor's built-in API for text insertion
    if (editorRef.current && editorRef.current.api) {
      editorRef.current.api.replaceSelection(imageMarkdown);
    }
  };

  return (
    <div className="documentation-editor">
      <MDEditor
        ref={editorRef}
        value={content}
        onChange={setContent}
        preview="edit"
        height={400}
        onDrop={handleImageUpload}
        textareaProps={{
          placeholder: "Enter documentation content...",
        }}
        commands={[
          // Custom image picker command
          {
            name: 'image-picker',
            keyCommand: 'image-picker',
            buttonProps: { 'aria-label': 'Insert image from library' },
            icon: <ImageIcon />,
            execute: () => setShowImagePicker(true),
            value: () => setShowImagePicker(true)
          }
        ]}
      />

      {showImagePicker && (
        <ImagePicker
          onSelect={(image) => {
            insertImageMarkdown(image);
            setShowImagePicker(false);
          }}
          onClose={() => setShowImagePicker(false)}
        />
      )}
    </div>
  );
};

const ImagePicker = ({
  onSelect,
  onClose
}: {
  onSelect: (image: Image) => void;
  onClose: () => void;
}) => {
  const [images, setImages] = useState<Image[]>([]);
  const [filter, setFilter] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    // Load documentation images
    fetch('/api/admin/images?type=documentation')
      .then(res => res.json())
      .then(data => setImages(data.images))
      .catch(e => console.error("Failed to load documentation images:", e));
  }, []);

  const filteredImages = images.filter(img =>
    img.image_name.toLowerCase().includes(filter.toLowerCase())
  );

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/admin/images', {
        method: 'POST',
        body: formData
      });
      const { image } = await response.json();
      setImages(prev => [image, ...prev]);
      // Don't auto-select - let user click to select the uploaded image
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="image-picker-modal">
      <div className="image-picker-header">
        <input
          type="text"
          placeholder="Search images..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <input
          type="file"
          accept="image/*"
          onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
          disabled={uploading}
        />
      </div>

      <div className="image-grid">
        {filteredImages.map(image => (
          <div
            key={image.id}
            className="image-item"
            onClick={() => onSelect(image)}
          >
            <img src={image.url} alt={image.image_name} />
            <span>{image.image_name}</span>
          </div>
        ))}
      </div>

      <button onClick={onClose}>Close</button>
    </div>
  );
};
```

### 2.16 Deprecated Objects Interface

**Create deprecated objects management page:**
```typescript
const DeprecatedObjectsPage = () => {
  const [deprecatedObjects, setDeprecatedObjects] = useState<DeprecatedObject[]>([]);

  // Load all deprecated objects with successor_id
  // Display in table format
  // Link to changelog creation
};

const ChangelogCreationPage = ({
  deprecatedBlueprint,
  successorBlueprint
}: ChangelogCreationProps) => {
  const [changelog, setChangelog] = useState('');

  // Show both blueprints side by side
  // Navigation through successor chain
  // Changelog creation form
};
```

## Implementation Steps

### Step 1: Database Schema Updates (Week 1)
1. Create migration script (version_09.py)
2. Extend documentation_type_enum
3. Add image_type support to images table
4. Create tags_documentation table
5. Create admin_sessions table
6. Test migration with existing data

### Step 2: Backend API Implementation (Week 1-2)
1. Implement documentation service classes
2. Create blueprint documentation API endpoints
3. Create tag documentation API endpoints
4. Create image management API endpoints
5. Create session management API endpoints
6. Implement changelog history API
7. Add API key authentication middleware

### Step 3: Frontend Admin Interface (Week 2)
1. Create admin layout with session management
2. Implement API key authentication flow
3. Create documentation editor component
4. Create image management interface
5. Create deprecated objects interface
6. Add markdown rendering with image support

### Step 4: Frontend Integration (Week 2-3)
1. Update blueprint detail page with tabbed interface
2. Implement documentation tab with blueprint + tag docs
3. Implement changelog tab with pagination
4. Add image picker to documentation editor
5. Test end-to-end functionality

### Step 5: Testing and Polish (Week 3)
1. Test all API endpoints
2. Test admin authentication flow
3. Test documentation creation and editing
4. Test image upload and management
5. Test changelog history display
6. Performance testing and optimization

## Success Criteria

### Technical Requirements
- ✅ Documentation system supports both blueprint and tag documentation
- ✅ Markdown rendering with image support works correctly
- ✅ Changelog history displays recursively through successor chain
- ✅ Admin authentication with session management functions properly
- ✅ Image upload and management works seamlessly
- ✅ API endpoints properly enforce authentication requirements

### User Experience Requirements
- ✅ Blueprint detail pages show documentation and changelog in organized tabs
- ✅ Admin interface provides intuitive documentation editing experience
- ✅ Image picker allows easy selection of documentation images
- ✅ Deprecated objects interface enables efficient changelog creation
- ✅ Session management provides secure admin access

### Integration Requirements
- ✅ Documentation system integrates with existing blueprint and tag systems
- ✅ Image system extends existing image functionality
- ✅ Fixture loader properly sets image types for new images
- ✅ API follows existing patterns and conventions
- ✅ Frontend integrates seamlessly with existing blueprint detail pages

## Risk Management

### Potential Risks
1. **Markdown Security**: XSS vulnerabilities in markdown rendering
   - **Mitigation**: Use secure markdown parser with sanitization

2. **Image Storage**: S3 upload failures or storage issues
   - **Mitigation**: Implement retry logic and error handling

3. **Session Security**: Session token vulnerabilities
   - **Mitigation**: Use secure token generation and proper expiration

4. **Performance**: Large changelog history causing slow page loads
   - **Mitigation**: Implement proper pagination and caching

### Rollback Plan
- Database migrations can be rolled back using existing down_impl methods
- Frontend changes can be reverted to previous version
- API endpoints can be disabled via feature flags if needed

## Future Enhancements (Phase 3+)

### Documentation Search
- Full-text search across documentation content
- Tag-based documentation filtering

### Documentation Templates
- Predefined templates for common documentation types
- Template library for consistent documentation

### Documentation Analytics
- Track documentation usage and effectiveness
- Identify gaps in documentation coverage

### Advanced Image Management
- Image optimization and resizing
- Image metadata management
- Bulk image operations

This implementation plan provides a comprehensive roadmap for Phase 2, ensuring the documentation system meets all requirements while maintaining system stability and user experience quality.
