# Blueprint Configuration Specification

## Overview

The `config` section of a blueprint defines how that blueprint should be assembled from component parts. It uses a sophisticated tag-based constraint system to guide part selection and ensure compatibility between components.

## Schema Structure

```yaml
config:
  parts:
    - name: string              # Human-readable part identifier
      tags:                     # Constraint system for part selection
        accept: []              # Optional: Hierarchical tag matching
        require: []             # Required: Exact tag matching
        deny: []                # Prohibited: Tags that disqualify parts
        constrain: []           # Dynamic: Inherit from parent/siblings
      fulfills: []              # Optional: Requirements this part satisfies
  fulfills: []                  # Optional: Sibling requirements this blueprint satisfies
```

## Parts Array

The `parts` array defines all components needed to build this blueprint. Each part represents either:
- A **model** (concrete STL file) that satisfies the constraints
- A **blueprint** (composition) that itself contains parts

### Part Name and Properties
```yaml
name: "base"
optional: true    # Optional: Part can be skipped without blocking download
```

**Part Name**:
- Human-readable identifier for the part
- Used in UI for part selection steps
- Referenced by `fulfills` declarations in other parts
- Must be unique within the blueprint's parts array

**Optional Parts**:
- **Default behavior**: All parts are required for download
- **Optional parts**: `optional: true` allows users to skip this part
- **Download enforcement**: Users cannot download until all required parts are selected
- **Use case**: Parts that enhance but aren't essential to the blueprint functionality

## Tag Constraint System

The tag constraint system controls which blueprints/models can be selected for each part. Constraints are evaluated **real-time** as parts are selected, progressively narrowing options for remaining parts.

### Require Constraints
```yaml
require:
  - tag: "shape|base"
  - tag: "size|width|2"
```
- **Exact matching**: Selected part must have these exact tags
- Uses array equality: `['shape', 'base']` matches only `['shape', 'base']`
- Multiple require entries create AND relationship (must have ALL)

### Accept Constraints
```yaml
accept:
  - tag: "shape|wall"
```
- **Hierarchical matching**: Selected part must have these tag elements in these positions
- Allows additional elements: `['shape', 'wall']` matches `['shape', 'wall', 'corner']`
- Useful for matching tag families (any type of wall, regardless of specificity)
- Multiple accept entries create AND relationship

### Deny Constraints
```yaml
deny:
  - tag: "shape|wall"
  - tag: "build|s2w"
```
- **Exclusion matching**: Selected part must NOT have these exact tags
- Uses array equality for exclusion
- Multiple deny entries create OR relationship (exclude if ANY match)

### Constrain System
```yaml
constrain:
  - tag: "texture"
  - tag: "connection"
    siblings: ["wall", "floor"]
    parent: false
  - filter: "connection|side"
  - filter: "connection|openforge"
```

The constrain system enables **dynamic inheritance** of tag requirements from:
1. **Parent blueprint**: The blueprint that contains this part
2. **Sibling parts**: Other parts in the same blueprint that have already been selected

#### Constrain Mechanics
- **Tag prefix matching**: `tag: "texture"` inherits all tags starting with `texture|`
- **Exact match priority**: Tags that exactly match the constraint are always included
- **Specificity filtering**: Among prefix matches, only the most general (shortest) tags are included, excepting exact matches
- **Real-time evaluation**: Constraints update as sibling parts are selected
- **Progressive filtering**: Available options narrow with each selection
- **Single-level scope**: Only looks at immediate parent and siblings, not deeper hierarchy
- **Unique tag prefixes**: Each tag prefix can only appear once in the constrain array

#### Source Control
Tag inheritance sources can be controlled with optional properties:

```yaml
constrain:
  - tag: "texture"
    siblings: ["wall", "base"]  # Only inherit from these specific siblings
    parent: false               # Don't inherit from parent blueprint
```

**Siblings Control**:
- **Default behavior**: If unset, considers all sibling parts
- **Specific siblings**: `siblings: ["wall", "floor"]` only inherits from named siblings
- **No siblings**: `siblings: []` inherits from no siblings
- **Validation**: Invalid sibling names cause errors

**Parent Control**:
- **Default behavior**: `parent: true` (inherits from parent blueprint)
- **Disable parent**: `parent: false` excludes parent tags from inheritance
- **Combine with siblings**: Can be used together for precise source control

#### Filter Mechanism
- **Selective removal**: `filter: "connection|side"` removes tags starting with `connection|side|`
- **Prevents contamination**: Stops unwanted tag inheritance between different systems
- **Mixed with constrain**: Filter entries are embedded within the constrain array
- **Applied after inheritance**: First inherit matching tags, then remove filtered prefixes
- **No source control**: Filter entries cannot have `siblings` or `parent` properties

### Constraint Resolution Example
```yaml
# Parent blueprint has: texture|dungeon_stone, connection|openforge
# Sibling "wall" selected with: texture|dungeon_stone, connection|openforge|female
# Sibling "floor" selected with: texture|dungeon_stone|block, connection|side, connection|side|openlock

parts:
  - name: "base"
    tags:
      require:
        - tag: "shape|base"
      constrain:
        - tag: "texture"        # Available: texture|dungeon_stone, texture|dungeon_stone|block
          siblings: ["wall"]    # Restrict to wall: texture|dungeon_stone (exact + most general)
        - tag: "connection|side" # Available: connection|side, connection|side|openlock
          parent: false         # From floor only: connection|side (exact) + connection|side|openlock (most general prefix)
        - filter: "connection|openforge"  # Remove openforge variants

# Final constraints: shape|base + texture|dungeon_stone + connection|side + connection|side|openlock
```

### Constraint Conflicts
When multiple siblings provide conflicting constraints (e.g., `texture|stone` vs `texture|wood`), both constraints are applied, potentially resulting in no valid options. This indicates an incompatible part combination.

## Fulfills System

The fulfills system allows parts to declare that they already satisfy requirements that would normally need separate parts.

### Part-Level Fulfills
```yaml
parts:
  - name: "right wall"
    tags:
      require:
        - tag: "shape|wall"
    fulfills:
      - part: "base"
```

- **Scope**: Only affects child parts of the fulfilling part
- **No sibling impact**: Does not affect sibling parts with the same name
- **Use case**: When a part inherently includes functionality (e.g., walls that include their own base)

### Blueprint-Level Fulfills
```yaml
config:
  parts:
    - name: "grate (right)"
      tags:
        require:
          - tag: "interface|grate"
    - name: "grate (left)"
      tags:
        require:
          - tag: "interface|grate"
  fulfills:
    - part: "column"
    - part: "left wall"
    - part: "right wall"
```

- **Scope**: Affects sibling parts when this blueprint is selected as a part in a larger composition
- **Multi-part fulfillment**: Can fulfill multiple sibling requirements simultaneously
- **Use case**: When a blueprint provides functionality that would normally require separate parts (e.g., integrated grate that includes structural elements)

### Fulfillment Conflict Resolution
Both part-level and blueprint-level fulfills can exist in the same blueprint and work together. However, conflicts are handled through **dynamic validation**:

- **Conflict detection**: Multiple sources cannot fulfill the same requirement
- **Real-time resolution**: When a fulfilling part is selected, conflicting parts are automatically removed from available options
- **Automatic deselection**: Previously selected conflicting parts are automatically deselected
- **Selection order independence**: Most recent selection "wins" and resolves conflicts automatically

## Resolution Process

### Part Selection Flow
1. **Initial filtering**: Apply require, accept, and deny constraints
2. **Constraint inheritance**: Apply constrain rules based on parent and selected siblings
3. **Filter application**: Remove filtered tag prefixes
4. **Option presentation**: Show filtered list to user
5. **Selection impact**: Update constraints for remaining parts
6. **Recursive resolution**: If selected part is a blueprint, resolve its internal parts independently

### Hierarchical Resolution
- **Single-level constraints**: Each blueprint level resolves independently
- **No constraint tunneling**: Parent constraints don't affect grandchild selections
- **Independent fulfillment**: Each blueprint level handles its own fulfills declarations

## Implementation Architecture

The blueprint configuration system is split between frontend and backend responsibilities:

### Frontend Responsibilities
- **Constraint Resolution**: Processes `constrain` entries to compute inherited tags from parent and siblings
- **Fulfillment Logic**: Handles all `fulfills` declarations for UI state management
- **Dynamic Constraints**: Combines base constraints (accept/require/deny) with computed constraints from inheritance
- **Conflict Resolution**: Automatically deselects conflicting parts when fulfillment conflicts occur
- **Progressive Filtering**: Updates available options in real-time as parts are selected

### Backend Responsibilities
- **Constraint Enforcement**: Only understands and enforces accept/require/deny constraints
- **Tag Querying**: `/api/blueprint/tags/` endpoint filters blueprints based on provided constraints
- **No Fulfillment Awareness**: Backend has no knowledge of fulfills declarations
- **No Constraint Computation**: Backend does not process constrain entries or tag inheritance

### API Interaction Flow
1. **Frontend computes final constraints**: Processes constrain entries and current selections to generate accept/require/deny arrays
2. **API call**: Frontend sends computed constraints to `/api/blueprint/tags/`
3. **Backend filtering**: Backend returns matching blueprints (paginated, typically 20 results) and available tag options
4. **UI updates**: Frontend uses results to update available selections and constraint options for remaining parts

This separation allows the backend to remain stateless while the frontend handles the complex interactive constraint resolution process.

## Common Patterns

### Basic Part Requirements
```yaml
parts:
  - name: "base"
    tags:
      require:
        - tag: "shape|base"
        - tag: "size|width|2"
      deny:
        - tag: "build|s2w"  # Exclude specific build systems
```

### Texture Coordination
```yaml
parts:
  - name: "wall"
    tags:
      require:
        - tag: "shape|wall"
  - name: "base"
    tags:
      require:
        - tag: "shape|base"
      constrain:
        - tag: "texture"  # Match wall's texture
```

### Connection System Isolation
```yaml
parts:
  - name: "floor"
    tags:
      constrain:
        - tag: "connection"
        - filter: "connection|side"  # Don't inherit wall-specific connections
```

### Integrated Components
```yaml
parts:
  - name: "integrated_wall"
    tags:
      require:
        - tag: "shape|wall"
        - tag: "component|integrated"
    fulfills:
      - part: "base"  # This wall includes its own base

config:
  fulfills:
    - part: "column"
    - part: "floor"   # This entire blueprint replaces column and floor
```

### Complex Fulfillment
```yaml
# Blueprint that can replace multiple parts in a corner wall assembly
config:
  parts:
    - name: "grate (right)"
      tags:
        require:
          - tag: "interface|grate"
    - name: "grate (left)"
      tags:
        require:
          - tag: "interface|grate"
  fulfills:
    - part: "column"      # Replaces structural column
    - part: "left wall"   # Includes left wall functionality
    - part: "right wall"  # Includes right wall functionality
```

## Design Principles

### Flexibility vs Complexity
The constraint system handles **inherent complexity** of the domain where physical objects have multiple independent properties that interact in nuanced ways. The system provides mechanisms to handle edge cases through filters and fulfills rather than oversimplifying the model.

### Progressive Disclosure
Real-time constraint evaluation guides users through complex decisions by eliminating invalid options at each step, making the assembly process feel intuitive despite underlying complexity.

### Hierarchical Independence
Each blueprint level resolves its constraints independently, preventing constraint complexity from spiraling out of control while still enabling sophisticated compositions.

### Extensibility
The tag-based approach allows new constraint types and mechanisms to be added as new edge cases are discovered, without breaking existing blueprints.
