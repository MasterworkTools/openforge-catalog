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
merge to `main` deploys the image it just built. The sync uploads the frontend to a
per-sha prefix and then promotes it to `current/`, which is what CloudFront serves, so the
deploy is live without touching openforge-infra-frontend. Release PRs get a plan comment from the
`Production Plan` workflow.

**Nothing in the production pipeline applies database migrations yet.** Staging
does it automatically (see below); production is the same two resources and the
same job, to be copied across once staging has run it a few times
(`openforge_catalog-jag`). Until then, for production, the workflow builds the
image, applies tofu and syncs the frontend; it never runs `bin/db_update up`. So
a release carrying a schema change deploys code that is newer than the database,
and the endpoints touching the new schema return an unhandled 500 until someone
migrates by hand on the bastion. The order is **`bin/db_update up` on the bastion, from a checkout of the ref
being released, then merge to
`main`, then `bin/upload_fixture <fixture>` for any fixtures the release needs.**

The fixtures go last, not in the middle: `bin/upload_fixture` POSTs to
`${OPENFORGE_BASE_URL}/api/admin/fixtures`, which is the *deployed* app, so before
the merge it is still `main`'s image — and an older image will misclassify a
fixture format it does not know rather than reject it cleanly. The ref matters and fails silently if you get it wrong:
`bin/db_update up` iterates the schema versions **in the checkout**, so from a
`main` checkout that predates a release you are about to make, it finds none of
that release's new versions, applies nothing, prints nothing and exits 0 — after
which the merge lands in exactly the 500 this paragraph exists to prevent. Check
out the ref being released, not `main`. The window between the migration and the
fixture load is benign: the new image against an empty table
answers `404 {"guides": []}`, which the page renders as "none yet" rather than as
an error.

**There is no pending schema gap as of the 0.8.1 release** (2026-09-29): `main`
carries 18 and 19, applied by hand during the 0.8.0 release. An earlier version of
this paragraph said "the pending gap is schema 18 and 19, since `main` is still at
17", which was true as of PR #246 and is not now — so do not read it as a standing
instruction. The way to know for a given release is
`git diff --stat origin/main origin/test -- openforge/db/schema/`, tip to tip: empty
means no migration is needed. (Note the three-dot form diffs against the merge base,
which is stale here because releases are squash-merged, and will list schema files
that both branches already have.)

Runtime secrets live in Secrets Manager
(`openforge-catalog/production/app`, created once by `scripts/create-app-secret.sh`), never
in the repo; the database password is read at cold start from `DB_SECRET_ARN` so the
RDS-managed secret may rotate. Prerequisites, once per account: the app secret, and the
repo-level GitHub secret `AWS_ROLE_ARN_PRODUCTION` = openforge-infra's
`deploy_role_arns["openforge-catalog"]` (read by both the `production` and `production-plan`
environments).

### Staging infrastructure (`terraform/environments/staging`)

A merge to `test` deploys staging the whole way:
**docker-build → tofu-apply (migration function) → migrate → tofu-apply → frontend-deploy**,
each gated on the last, so neither the API image nor the frontend is ever promoted
in front of a schema that cannot serve it.

**Why the apply is split in two.** `aws_lambda_function` waits for
`LastUpdateStatus=Successful`, so a single apply puts the new API image live *before*
the migration runs — `/api/*` serving new code against the old schema, which is the
unhandled 500 `openforge_catalog-jag` exists to describe. The first apply is
`-target`ed at the migration function alone; the second promotes everything else.
The chicken-and-egg (the function must exist before it can be invoked) is why it
cannot be one apply with the migration first.

**The one-time adoption apply is done by hand**, as a full apply, because
`imports.tf` adopts live resources and the app secret must exist first. The split
above is the steady state after that.

**The split moves which side is ahead, it does not remove the window.** Between the
migration and the second apply, the *database* is ahead and the **old** API image is
still serving. Every migration in the tree today is additive, so that is free — but a
`DROP COLUMN` or a `RENAME` would break the code that was working a moment ago, which
is harder to spot than a new column the old code ignores. So schema changes want
expand/contract: add and backfill in one release, stop using the old shape, remove it
in a later one. This matters beyond staging, because the plan is to copy this job to
production. Layered on openforge-infra's staging state exactly as production is, and
kept diffable against `../production` — the two should differ only in account,
environment name, bucket prefix, and the migration function.

It did not always work this way, and the failure was quiet: until this, `staging.yaml`
pushed the image to ECR and never pointed the function at it, while the frontend job
in the same workflow deployed on every merge. Staging served a current site against a
backend from nine months earlier, and nothing failed to say so.

**Migrations run in a Lambda, not on the runner.** Aurora only accepts connections
from inside the VPC — its security group admits the application and bastion groups
and nothing else — and a GitHub runner is outside it. (Not because the subnets are
private: staging is the *default* VPC and all six subnets are
`MapPublicIpOnLaunch`. The security group is what closes the door.)
`openforge-catalog-migrate` is the *same image* as the API with
`image_config.command` pointing at `openforge/app/migrate.py`, so it is already
inside and already reads `DB_SECRET_ARN` — no second image to keep in step.
Reserved concurrency is 1, so two deploys landing together cannot interleave DDL;
the second is throttled and that deploy fails. The job fails on a `FunctionError`
or any payload without `ok: true`, because `aws lambda invoke` exits 0 for a
function that raised — and it passes `--cli-read-timeout 0`, because botocore's
default 60 s read timeout is well under the function's budget and would fail a
deploy whose migration had actually succeeded.

The handler asserts the schema reached head rather than reporting what it saw. Every
other failure — a migration that does nothing, an empty `get_schema_versions()`, a
version read that fails — produces a payload shaped exactly like a healthy no-op, and
the gate cannot tell them apart. It reports the *set* of versions that landed, because
a before/after maximum cannot describe a version arriving below the head and the
series already has a hole at 15.

**Nothing loads fixtures.** The pipeline deploys schema and code, never data, so a
release needing a new or changed fixture still wants `bin/upload_fixture` (or
`bin/fixtures` from the bastion) by hand afterwards — the same gap the production
paragraph above describes.

**Staging is adopted, not created.** It predates tofu, so `imports.tf` adopts the ALB,
its port-80 listener and rule, the target group, its attachment and the website bucket.
Two things it cannot adopt: the function and its role are named `Openforge-Catalog-API`
and `...-role-ogdz6ix0`, and `function_name` is ForceNew while the deploy role may only
touch IAM named `openforge-catalog-*` — so tofu creates `openforge-catalog-api` fresh
and the old pair is deleted by hand afterwards (`openforge_catalog-rc2`), which is the
rollback until then.

**There is no manual step.** An earlier version of this section said to deregister the
old function from the target group first. Do not: the attachment is imported, so the
apply swaps the target itself. There is still a window, but it is the **apply's own**:
it deregisters the old target before the new function exists, so `/api/*` is down for
the length of that creation — minutes, on the adoption apply only. `imports.tf`
explains it and offers a `-target` split for anyone who wants it smaller.

Prerequisites, once per account: the app secret `openforge-catalog/staging/app`
(`scripts/create-app-secret.sh` — note it generates a **fresh** API_TOKEN and
SECRET_KEY, so decide deliberately whether to preserve the current ones), the
repo-level GitHub secret `AWS_ROLE_ARN_STAGING`, and openforge-infra adding
`openforge-catalog` to staging's `deploy_roles` plus a Secrets Manager VPC endpoint
(`openforge_catalog-44e`). Without that endpoint the Lambda cannot read its password:
`_password_from_secret` sets `connect_timeout=3` with two attempts, so it gives up in
seconds rather than outlasting the function. The **migration** function also sets
`PGCONNECT_TIMEOUT = 120`, matched to a measured ~20 s Aurora resume from
`min_capacity 0`; `use_pool=False` means `psycopg.connect` raises
`ConnectionTimeout` straight out of the handler there. The API sets none, and should
not: its pool catches that exception, logs and reschedules, so the value never reaches
a caller — and psycopg already substitutes its own 130 s default when
`connect_timeout` is absent, so there was never a wait-forever to bound
(`openforge_catalog-15r` covers bounding the API's pool instead).

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
