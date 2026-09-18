"""
Test constants for integration tests.

This module defines constants used across all integration tests to ensure:
1. Consistent test data formatting
2. Safe cleanup operations that don't accidentally delete legitimate data
3. Easy identification of test data in the database
"""

# Unique prefix for all test data to prevent accidental deletion of legitimate data
# This prefix should be unique enough to never match production/development data
TEST_DATA_PREFIX = "__test__"

# Test document templates
TEST_DOCUMENT_TEMPLATES = {
    "changelog": f"{TEST_DATA_PREFIX} changelog entry",
    "instructions": f"{TEST_DATA_PREFIX} instructions",
    "update": f"{TEST_DATA_PREFIX} updated entry",
    "delete": f"{TEST_DATA_PREFIX} entry for deletion",
    "auth": f"{TEST_DATA_PREFIX} document without auth",
    "invalid_type": f"{TEST_DATA_PREFIX} document with invalid type",
    "large": f"{TEST_DATA_PREFIX} large document",
    "empty": "",  # Truly empty string for testing empty content validation
    "multiple_1": f"{TEST_DATA_PREFIX} first multiple entry",
    "multiple_2": f"{TEST_DATA_PREFIX} second multiple entry",
    "debug": f"{TEST_DATA_PREFIX} debug documentation",
    "legitimate_markdown": f"""{TEST_DATA_PREFIX} Documentation

This is **bold text** and *italic text*.

## Features
- Feature 1
- Feature 2
- Feature 3

### Code Example
```python
def hello_world():
    print("Hello, World!")
```

[Link to documentation](https://example.com)

![Image description](https://example.com/image.jpg)

> This is a blockquote with important information.

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
| Data 3   | Data 4   |
""",
}
