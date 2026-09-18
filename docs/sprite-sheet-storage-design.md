# Multi-Angle Sprite Sheet Storage Design

## Overview

This document defines the R2 storage structure for multi-angle STL thumbnail sprite sheets. Instead of storing 10 separate thumbnail images per model, we generate a single sprite sheet PNG containing all angles in a grid layout.

## Storage Path Structure

### Sprite Sheets
- **Path**: `sprites/{md5[:6]}/{md5}.png`
- **Example**: `sprites/a1b2c3/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.png`

### Legacy Single Thumbnails (existing)
- **Path**: `thumbnails/{md5[:6]}/{md5}.png`
- **Example**: `thumbnails/a1b2c3/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.png`

### Directory Rationale
- Using `sprites/` directory separates multi-angle sprites from legacy single thumbnails
- The `{md5[:6]}` prefix provides sharding (prevents too many files in single directory)
- Using file MD5 for naming ensures content addressing and deduplication

## Sprite Sheet Layout

### Grid Configuration
- **Dimensions**: 2 rows × 5 columns
- **Tile size**: 512×512 pixels (square)
- **Total sprite size**: 2560×1024 pixels
- **Format**: PNG with transparency

### Grid Layout (2×5)
```
┌──────┬──────┬──────┬──────┬──────┐
│  0   │  1   │  2   │  3   │  4   │  Row 0
│      │      │      │      │      │
├──────┼──────┼──────┼──────┼──────┤
│  5   │  6   │  7   │  8   │  9   │  Row 1
│      │      │      │      │      │
└──────┴──────┴──────┴──────┴──────┘
```

## Camera Angles

### 10 Isometric-Perspective Angles

All angles use isometric-style 3/4 perspective (not flat orthographic) to maintain depth perception.

Camera angles are arranged in 45-degree increments around the model for even coverage without redundant views.

#### Angle Definitions

| Index | Name | Description | Camera Position | Notes |
|-------|------|-------------|-----------------|-------|
| 0 | front | Front view | `(0, -4, 2)` | Default angle, 0° |
| 1 | front-right | Front-right diagonal | `(3, -3, 2)` | 45° from front |
| 2 | right | Right side view | `(4, 0, 2)` | 90° |
| 3 | back-right | Back-right diagonal | `(3, 3, 2)` | 135° |
| 4 | back | Back view | `(0, 4, 2)` | 180° |
| 5 | back-left | Back-left diagonal | `(-3, 3, 2)` | 225° |
| 6 | left | Left side view | `(-4, 0, 2)` | 270° |
| 7 | front-left | Front-left diagonal | `(-3, -3, 2)` | 315° |
| 8 | top | Top-down view | `(0, -2, 5)` | Elevated perspective |
| 9 | bottom | Bottom-up view | `(0, -2, -3)` | Lower perspective |

**Configuration**: 8 horizontal angles at 45° increments + 2 vertical angles for comprehensive coverage.

## Database Storage

Sprite metadata is stored in the `images` table using the `sprite_metadata` JSONB column:

```json
{
  "grid_rows": 2,
  "grid_cols": 5,
  "tile_size": 512,
  "angles": [
    {
      "index": 0,
      "name": "front-iso",
      "camera_pos": [2, -4, 2]
    },
    {
      "index": 1,
      "name": "back-iso",
      "camera_pos": [-2, 4, 2]
    },
    // ... 8 more angles
  ],
  "default_angle": 0
}
```

### Default Angle Behavior
- First angle in array (index 0) is the default unless `default_angle` is explicitly set
- Admins can change the default angle per model
- Default angle is what displays initially in the UI

## Generation Workflow

### Local File Handling
1. Generate 10 individual tiles locally using stl-thumb with different `--cam-pos` values
2. Combine tiles into a single sprite sheet PNG using image processing library
3. Upload sprite sheet to R2
4. **Delete all local files** (sprite sheet and individual tiles)
5. Update database with sprite metadata

### Upload Optimization
- Check R2 listing cache before generation
- Skip sprite generation if file already exists with matching MD5
- Regenerate if model MD5 has changed (file was modified)
- Use existing S3 key cache infrastructure for efficient batch operations

## Backward Compatibility

### Migration Strategy
- Legacy single thumbnails remain in `thumbnails/` directory
- New sprite sheets stored in `sprites/` directory
- `sprite_metadata` column is nullable (NULL for legacy thumbnails)
- Frontend can check for sprite_metadata presence and fall back to single thumbnail
- No need to regenerate all legacy thumbnails immediately

### Image Type Tracking
- `images.image_type` enum distinguishes between 'thumbnail' and 'documentation'
- Sprite sheets use `image_type = 'thumbnail'` with `sprite_metadata` populated
- Legacy thumbnails use `image_type = 'thumbnail'` with `sprite_metadata = NULL`

## Frontend Integration

### Sprite Sheet Extraction
Frontend JavaScript can extract individual angles using CSS background-position:

```javascript
// Example: Display angle at index N
const tileSize = 512;
const cols = 5;
const row = Math.floor(N / cols);
const col = N % cols;
const bgX = -col * tileSize;
const bgY = -row * tileSize;

element.style.backgroundImage = `url(${spriteUrl})`;
element.style.backgroundPosition = `${bgX}px ${bgY}px`;
element.style.width = `${tileSize}px`;
element.style.height = `${tileSize}px`;
```

### Interactive Controls
- Drag to rotate between angles
- Keyboard navigation (arrow keys)
- Click hotspots for specific angles
- Smooth transitions between angles

## Performance Considerations

### File Size
- 2560×1024 PNG sprite sheet ≈ 2-3MB (with compression)
- Significantly smaller than 10 separate files (10MB+)
- Single HTTP request instead of 10
- Better browser caching

### R2 Bandwidth
- Cloudflare R2 offers free egress (no bandwidth charges)
- Larger file size acceptable given bandwidth is free
- Reduces API call overhead

### Generation Cost
- stl-thumb must render 10 times per model
- Use during batch processing (file scanner), not on-demand
- Phased rollout: test subset before bulk backfill

## Testing Strategy

### Phased Rollout
1. Generate sprites for small test subset (~100 models)
2. Verify sprite quality and file sizes
3. Test frontend rendering and interaction
4. Adjust camera positions if needed
5. Bulk backfill for all models

### Quality Checks
- Visual inspection of generated sprites
- Verify all 10 angles are distinct and useful
- Confirm grid alignment is pixel-perfect
- Test sprite extraction in browser

## References

- Database schema: `openforge/db/schema/version_16.py`
- stl-thumb documentation: https://github.com/unlimitedbacon/stl-thumb
- stl-thumb default size: 1024×768 (overridden to 512×512 square)
- stl-thumb default camera: `(2, -4, 2)`
