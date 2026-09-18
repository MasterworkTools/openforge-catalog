# Python/Backend-Specific Claude Instructions

This file contains Python and backend-specific instructions for Claude Code when working on the OpenForge Catalog backend.

## Python Tests
Always run these after making changes to Python code:
```bash
pytest tests/                  # Run unit tests
pytest integration_tests/      # Run integration tests
```

## Key File Locations
- API routes: `openforge/app/index.py`
- Database models: `openforge/db/sql/`
- Database migrations: `openforge/db/schema/version_*.py`
- Backend tests: `tests/` and `integration_tests/`

## Python Code Style

### 1. Follow PEP 8
All Python code must adhere to PEP 8 style guidelines:
- Use 4 spaces for indentation (never tabs)
- Maximum line length of 79 characters for code, 72 for docstrings/comments
- Use snake_case for functions and variables
- Use UPPER_CASE for constants
- Use CamelCase for classes
- Two blank lines between top-level definitions
- One blank line between method definitions

### 2. Functional-style procedural programming
- Prefer procedural functions over classes/OOP
- Use private functions (`_function_name`) extensively to break down logic
- Keep functions small with single responsibilities
- Minimize side effects - functions should be as pure as practical
- Be skeptical of functions that do multiple things ("and"/"or" in descriptions)
- Pragmatically allow larger functions when it's genuinely simpler
- Design for testability - small, focused functions are easier to test

### 3. Unit Testing Philosophy
- **Critical for agentic coding success** - comprehensive tests enable confident refactoring
- Test the PURPOSE/CONTRACT of code, not implementation details
- Focus on: "What should this function accomplish?" not "How does it do it?"
- Tests should survive refactoring if the function's purpose remains the same
- Use descriptive test names that explain the scenario being tested
- Prefer testing public interfaces over private functions
- Mock external dependencies but test the actual business logic

### 4. PostgreSQL & Database Access
- **Use psycopg3 tools**: Always use `sql.SQL()`, `sql.Literal()`, `sql.Identifier()` instead of string formatting
- **ORM is the devil**: Direct SQL gives control and performance
- **Embrace complex SQL**: Window functions, CTEs, and advanced queries are good
- **Performance matters**: Write efficient queries that the database can optimize
- **Don't hide from SQL**: The database is powerful, use it fully

### 5. Error Handling & Logging Philosophy
- **Fail fast**: Raise exceptions immediately - don't paper over errors
- **No silent failures**: Especially in CLI tools processing large datasets
- **Exceptions to console**: Let errors bubble up to where they can be seen
- **Rationale**: Hidden errors in large batch operations lead to data corruption
- **Pattern**: Use `werkzeug.exceptions.NotFound` in SQL → catch in routes → proper HTTP status

### 6. Security Patterns
- **Content sanitization**: All user input sanitized before storage
- **Whitelist approach**: Only allow known-safe HTML tags/attributes
- **CSRF protection**: Applied to all state-changing operations
- **Constant-time comparison**: Use `secrets.compare_digest()` for tokens
- **Length limits**: Prevent DoS via massive inputs

### 7. Data Transformation Architecture
- **Clear layer separation**: API format ↔ database format
- **Transformation functions**: `_munge_blueprint()`, `_convert_config()`
- **Naming convention**: `blueprint_config` (API) vs `config` (DB)
- **Private functions**: Handle all data munging/transformation

### 8. Testing Infrastructure
- **Test helpers**: Factory functions like `create_test_blueprint()`
- **Assertion helpers**: `assert_blueprint_matches()` for consistency
- **Separation**: Unit tests in `tests/`, integration tests in `integration_tests/`
- **Fixtures**: YAML/JSON test data files with consistent structure
- **Transaction rollback**: Tests don't pollute database

## Database Operations
```bash
bin/db_update up        # Run migrations
bin/fixtures            # Load fixtures
```

## Unix Philosophy & Tooling
- **Embrace Unix principles** - Small, focused tools that do one thing well
- Command-line tools go in `bin/` directory
- Tools should be pipeable and composable
- Use standard Unix conventions (exit codes, stderr for errors, etc.)
- Cron jobs, pipe chains, and traditional Unix approaches are preferred

## HTTP/REST API Design
- **Follow HTTP RFCs strictly**
- Return 404 for empty collections (not 200 with empty array)
- It's acceptable to return `{"items": []}` with 404 status
- Use proper HTTP status codes semantically
- Follow REST principles for resource design

## API Authentication
- Uses either API keys or session cookies
- Session-based auth for admin interface
- API keys for programmatic access
