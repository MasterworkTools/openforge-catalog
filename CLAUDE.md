# Claude Code Assistant Instructions

This file contains important information for Claude Code when working on the OpenForge Catalog project.

## Test Commands

See language-specific CLAUDE.md files:
- Python/Backend tests: `openforge/CLAUDE.md`
- JavaScript/Frontend tests: `src/CLAUDE.md`

## Important Guidelines

1. **Always run tests** after making code changes (see language-specific CLAUDE.md files)
- **Before committing, always run `pytest tests` and `npm test`**
2. **Check linting** before committing
3. **Follow language-specific guidelines** in `openforge/CLAUDE.md` and `src/CLAUDE.md`

## API Guidelines

- Always assume that when you want to hit the api, make a relative call to /api. Never encode the base of the url.

## Linting and Testing Requirements

### When modifying files during a task:

#### Python files (.py):
- Run: `ruff check --fix <file>` and `ruff format <file>`
- This ensures code quality and consistent formatting

#### JavaScript/TypeScript files (.js, .jsx, .ts, .tsx):
- Run: `npm run lint -- --fix <file>`
- Run: `npm run type-check`
- Run related tests: `npx jest --findRelatedTests <file>`

### Before committing changes:

You MUST run the complete test suite and ensure all checks pass:

1. **Python tests**:
   - `pytest tests/`
   - `pytest integration_tests/` (Flask must be running on port 5328)

2. **JavaScript tests**:
   - `npm test`

3. **Linting checks**:
   - `npm run lint`
   - `npm run type-check`
   - `ruff check .`

4. **Pre-commit hooks**:
   - The pre-commit hooks will run automatically, but you should ensure they pass

## Flask Health Check

Before running integration tests, verify Flask is running by checking:
```bash
curl http://localhost:5328/health
```

If Flask is not running, integration tests will fail. Flask can be started with:
```bash
npm run flask-dev
```

## Project Overview

OpenForge Catalog is a content management system for the OpenForge project - a comprehensive system of 3D printable modular dungeon terrain created by Devon Jones. The catalog manages:
- **12,000+ STL files** (~1,400 unique designs)
- **Modular terrain system** compatible with Dwarven Forge and other systems
- **Multiple connection systems**: OpenForge, OpenLOCK, Dragonlock, magnetic, etc.
- **Various textures**: dungeon_stone, cave, cut_stone, tudor, towne, etc.
- **Patreon-supported project** providing free STLs to the community

### OpenForge Domain Concepts
- **Blueprints**: Either individual STL models or compositions of multiple parts
- **Tiles**: Basic dungeon floor/wall pieces (1x1 to 4x4 sizes)
- **Connection Systems**: How tiles physically connect (magnets, clips, topless, etc.)
- **Textures**: Visual themes for tiles (stone types, wood, sewer, etc.)
- **Build Types**: Construction variants (topless, magnetic, LED-compatible)
- **Tag Hierarchy**: Systematic categorization (shape|wall|corner, size|width|2)

The system uses:
- Backend: Python/Flask with PostgreSQL
- Frontend: Next.js with TypeScript (compiled to static React)
- Storage: Cloudflare R2 for file storage

## Current Development Status

### Phase 2 (Documentation System) - Nearly Complete
- ✅ Database schema with documentation tables
- ✅ Backend API endpoints for documentation
- ✅ Frontend documentation viewing and editing
- ✅ Session-based authentication
- ⚠️ Deprecated objects manager needs API endpoint

## Common Tasks

### Running the Development Environment
```bash
npm run dev              # Starts both Next.js and Flask
npm run flask-dev       # Flask only
npm run next-dev        # Next.js only
```

**Note:** Both the frontend (Next.js) and backend (Flask) run in development mode with hot-reloading enabled. Changes to code are automatically picked up without needing to restart the servers.

### Database Operations
See `openforge/CLAUDE.md` for database-specific operations.

### Adding New Features
1. Create database migration if needed
2. Implement backend API endpoints
3. Add frontend components
4. Write tests for both backend and frontend
5. Run all tests and linting

## Key File Locations
See language-specific CLAUDE.md files for detailed file locations:
- Backend/Python files: `openforge/CLAUDE.md`
- Frontend/JavaScript files: `src/CLAUDE.md`

## Developer Preferences

For language-specific coding preferences and patterns, see:
- Python/Backend: `openforge/CLAUDE.md`
- JavaScript/Frontend: `src/CLAUDE.md`

## Code Organization Philosophy

### Function Complexity and Cognitive Load

**Core Principle**: Functions should be describable with as few uses of "and" or "or" as possible.

- **Single Screen Rule**: Generally, a function should be viewable on a single screen to keep cognitive load down
- **Helper Functions**: Use private/helper functions extensively to extract specific tasks
  - Python: Use `_function_name()` for private helpers
  - JavaScript/React: Use custom hooks or helper functions
- **Pragmatic Exceptions**: Larger functions are acceptable when breaking them up would genuinely complicate rather than simplify
- **Test for Complexity**: If you're describing what a function does and you use multiple "and"s or "or"s, it's probably doing too much

**Examples**:
- ❌ "This component handles state AND rendering AND keyboard events AND mouse drag events" - too many responsibilities
- ✅ "This component manages sprite viewer state and delegates event handling to custom hooks"
- ❌ "This function validates input AND transforms data AND saves to database" - should be 3 functions
- ✅ "This function validates and saves user data (validation is a prerequisite for saving, so it's cohesive)"

## Background Context

### Technical Experience
- **SendGrid Email Infrastructure Architect (2016-2022)**
  - Scaled from 1 billion to 8 billion emails/day
  - Managed infrastructure requiring 600GB peak transit to Google
  - Deep understanding of distributed systems at scale

### Why This Matters
- **Architecture decisions** come from real scale experience
- **Simplicity focus** - knows what complexity costs at scale
- **Performance awareness** - understands when optimization matters (and when it doesn't)
- **Cost consciousness** - has managed massive infrastructure budgets
- **Pragmatic choices** - battle-tested understanding of what actually breaks

## Development Workflow

### Git Branching Strategy

**CRITICAL**: This repository uses an unconventional branching model:

- **`test` branch**: The default branch for all development work
  - This is where all feature development happens
  - All PRs should target this branch by default
  - Changes are tested here before promotion to production

- **`main` branch**: Production deployment branch ONLY
  - Only merge to `main` when ready to deploy to production
  - Do NOT create PRs from `test` → `main` unless explicitly deploying
  - Merging to `main` should be an intentional production release decision

**When working on features**:
1. Create feature branches from `test`
2. Submit PRs targeting `test` (not `main`)
3. Only merge `test` → `main` when ready for production deployment

**Example workflow**:
```bash
# Create feature branch from test
git checkout test
git pull origin test
git checkout -b feature/my-feature

# After development, create PR targeting test
gh pr create --base test --title "feat: my feature"

# Only when ready for production
gh pr create --base main --title "release: deploy to production"
```

### Production infrastructure (`terraform/environments/production`)

The API Lambda, its ALB, and the frontend bucket are OpenTofu in this repo, layered on
openforge-infra's state (network, Aurora, ECR, deploy role). The `Production` workflow
runs `tofu apply -var image_tag=<sha>` after the image push and before the S3 sync, so a
merge to `main` deploys the image it just built. Release PRs get a plan comment from the
`Production Plan` workflow. Runtime secrets live in Secrets Manager
(`openforge-catalog/production/app`, created once by `scripts/create-app-secret.sh`), never
in the repo; the database password is read at cold start from `DB_SECRET_ARN` so the
RDS-managed secret may rotate. Prerequisites, once per account: the app secret, and the
repo-level GitHub secret `AWS_ROLE_ARN_PRODUCTION` = openforge-infra's
`deploy_role_arns["openforge-catalog"]` (read by both the `production` and `production-plan`
environments). Staging's hand-built Lambda and ALB are not yet under tofu.

### Code Review Process
1. **Initial development**: Written in Cursor
2. **PR creation**: Push to GitHub
3. **Gemini review**: Automated code review
4. **Review iteration**: Fix issues between Cursor and Gemini
5. **Claude integration**: When passed to Claude for review fixes:
   - **Be skeptical of Gemini's suggestions** - Claude has much more context
   - **Consider project philosophy** - Gemini may suggest "best practices" that don't fit
   - **Respect existing patterns** - Don't break conventions for minor improvements
   - **Pragmatic approach** - Not every suggestion needs implementation

### Architecture & Infrastructure Constraints
1. **Cost-conscious serverless architecture** (Patreon-funded with small budget)
   - Frontend: React app compiled statically (no Next.js SSR), served from S3
   - Backend: Single AWS Lambda function running Flask
   - Database: PostgreSQL on serverless (connection pooling critical)
   - File storage: Cloudflare R2 (S3-compatible) for free egress

2. **Design implications**:
   - Minimize Lambda cold starts (keep package size small)
   - Be mindful of database connections (serverless Postgres has limits)
   - Avoid features that require persistent state or long-running processes
   - Static frontend means no server-side rendering or API routes in Next.js
   - Optimize for cost: batch operations, efficient queries, minimal Lambda invocations
   - Use Cloudflare R2 for all file storage (never S3 directly)

## Communication Preferences

1. **Question-asking behavior**:
   - When Devon starts a line of questions, continue asking follow-up questions until all necessary details are clear
   - Don't stop after one or two questions - be thorough in gathering requirements
   - Keep asking until satisfied that the task is fully understood

### OpenForge-Specific Considerations
1. **File Management & Creator Workflow**:
   - **Creator-first design**: System must handle Devon's natural Blender workflow
   - **Zero manual data entry**: Automated metadata extraction from filenames/paths
   - **Resilient to changes**: Files move, get renamed, and edited during design
   - **Dropbox as source of truth**: Folders serve both patrons and the catalog
   - **MD5-based tracking**: Content addressing handles file moves gracefully
   - **Incremental updates**: Scanner detects changes without manual intervention
   - **Semantic filenames**: Encode metadata to avoid manual tagging overhead

2. **Why This Architecture**:
   - Manual data entry (like Thingiverse) was killing the project
   - System adapts to creator workflow, not vice versa
   - Automated scanning/tagging enables focus on 3D design
   - File moves and edits are natural part of the creative process

3. **User Expectations**:
   - Community expects free access to basic content
   - Power users need sophisticated filtering and composition tools
   - Backward compatibility is important (existing links shouldn't break)
   - Clear documentation helps users choose from overwhelming options
