"""
Pytest tests for Authentication and Error Handling.
"""

from .test_constants import TEST_DOCUMENT_TEMPLATES


class TestAuthentication:
    """Test authentication requirements."""

    def test_blueprint_documentation_requires_auth(
        self, api_client_no_auth, test_blueprint_id
    ):
        """Test that blueprint documentation operations require authentication."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["auth"],
            "document_type": "changelog",
        }

        # Test POST without auth
        response = api_client_no_auth.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        assert response.status_code == 401

        # Test PUT without auth
        response = api_client_no_auth.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/test-id", data=test_doc
        )
        assert response.status_code == 401

        # Test DELETE without auth
        response = api_client_no_auth.delete(
            f"/api/blueprints/{test_blueprint_id}/documentation/test-id"
        )
        assert response.status_code == 401

    def test_tag_documentation_requires_auth(self, api_client_no_auth):
        """Test that tag documentation operations require authentication."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["auth"],
            "document_type": "instructions",
        }

        # Test POST without auth
        response = api_client_no_auth.post(
            "/api/tags/test/tag/documentation", data=test_doc
        )
        assert response.status_code == 401

        # Test PUT without auth
        response = api_client_no_auth.patch(
            "/api/tags/test/tag/documentation/test-id", data=test_doc
        )
        assert response.status_code == 401

        # Test DELETE without auth
        response = api_client_no_auth.delete("/api/tags/test/tag/documentation/test-id")
        assert response.status_code == 401

    def test_read_operations_dont_require_auth(
        self, api_client_no_auth, test_blueprint_id, test_tag_documentation
    ):
        """Test that read operations don't require authentication."""
        # Test GET blueprint documentation without auth
        # Note: This may return 404 if the blueprint has no documentation
        # (per API standard)
        response = api_client_no_auth.get(
            f"/api/blueprints/{test_blueprint_id}/documentation"
        )
        assert response.status_code in [200, 404]  # 200 if has docs, 404 if no docs

        # Test GET changelog history without auth
        response = api_client_no_auth.get(
            f"/api/blueprints/{test_blueprint_id}/changelog-history"
        )
        assert response.status_code == 200

        # Test GET all documentation without auth
        response = api_client_no_auth.get(
            f"/api/blueprints/{test_blueprint_id}/all-documentation"
        )
        assert response.status_code == 200

        # Test GET tag documentation without auth
        response = api_client_no_auth.get(
            "/api/tags/texture/dungeon_stone/documentation"
        )
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_blueprint_id_format(self, api_client):
        """Test handling of invalid blueprint ID format."""
        invalid_ids = [
            "invalid-uuid",
            "not-a-uuid",
            "123",
            "abc-def-ghi-jkl-mno-pqr-stu-vwx-yz",
        ]

        for invalid_id in invalid_ids:
            response = api_client.get(f"/api/blueprints/{invalid_id}/documentation")
            assert (
                response.status_code == 400
            ), f"Expected 400 for invalid ID: {invalid_id}"

        # Test empty string separately (results in 400 due to invalid UUID format)
        response = api_client.get("/api/blueprints//documentation")
        assert response.status_code == 400, "Expected 400 for empty blueprint ID"

    def test_invalid_tag_format(self, api_client):
        """Test handling of invalid tag format."""
        # Test with various invalid tag formats and their expected responses
        test_cases = [
            ("invalid-tag-format", 400),  # Invalid format should return 400
            (
                "tag/with/multiple/slashes",
                404,
            ),  # Multiple slashes; 404 likely from no data found
            ("", 404),  # Empty tag should return 404 (route not found)
            ("single_tag_without_slash", 400),  # Missing slash should return 400
        ]

        for invalid_tag, expected_status in test_cases:
            response = api_client.get(f"/api/tags/{invalid_tag}/documentation")
            status = response.status_code
            assert (
                status == expected_status
            ), f"Expected {expected_status} for tag: {invalid_tag}, got {status}"

    def test_invalid_json_in_post(self, api_client, test_blueprint_id):
        """Test handling of invalid JSON in POST requests."""
        # Test with malformed JSON
        headers = {"Content-Type": "application/json"}

        # Test with invalid JSON structure
        invalid_data = {"invalid": "json", "missing": "required_fields"}
        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation",
            data=invalid_data,
            headers=headers,
        )
        assert response.status_code == 400

    def test_missing_required_fields(self, api_client, test_blueprint_id):
        """Test handling of missing required fields."""
        # Test missing document field
        incomplete_data = {"document_type": "changelog"}
        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=incomplete_data
        )
        assert response.status_code == 400

        # Test missing document_type field
        incomplete_data = {"document": TEST_DOCUMENT_TEMPLATES["changelog"]}
        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=incomplete_data
        )
        # document_type defaults to "changelog" which is valid
        assert response.status_code == 201

    def test_nonexistent_resources(self, api_client):
        """Test handling of requests to non-existent resources."""
        # Test non-existent blueprint documentation
        response = api_client.get(
            "/api/blueprints/00000000-0000-0000-0000-000000000000/documentation"
        )
        assert (
            response.status_code == 404
        )  # Should return 404 when no documentation exists

        # Test non-existent tag documentation
        response = api_client.get("/api/tags/nonexistent/tag/documentation")
        assert (
            response.status_code == 404
        )  # Should return 404 when no documentation exists

        # Test non-existent documentation ID for update
        update_doc = {"document": "Updated document", "document_type": "changelog"}
        response = api_client.patch(
            "/api/blueprints/00000000-0000-0000-0000-000000000000/documentation/00000000-0000-0000-0000-000000000001",
            data=update_doc,
        )
        assert response.status_code == 404

        # Test non-existent documentation ID for delete
        response = api_client.delete(
            "/api/blueprints/00000000-0000-0000-0000-000000000000/documentation/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 404

    def test_invalid_document_type(self, api_client, test_blueprint_id):
        """Test handling of invalid document types."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["invalid_type"],
            "document_type": "invalid_type",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        assert response.status_code == 400

    def test_empty_document_content(self, api_client, test_blueprint_id):
        """Test handling of empty document content."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["empty"],
            "document_type": "changelog",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        # API should reject empty document content with 400 Bad Request
        assert response.status_code == 400

        # Verify the error message
        error_data = response.json()
        assert "error" in error_data
        assert "Document content required" in error_data["error"]

    def test_whitespace_only_document_content(self, api_client, test_blueprint_id):
        """Test handling of whitespace-only document content."""
        test_doc = {
            "document": "   \n\t  ",  # Whitespace-only content
            "document_type": "changelog",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        # API should reject whitespace-only content with 400 Bad Request
        assert response.status_code == 400

        # Verify the error message
        error_data = response.json()
        assert "error" in error_data
        assert "Document content required" in error_data["error"]

    def test_very_large_document_content(self, api_client, test_blueprint_id):
        """Test handling of very large document content."""
        large_document = TEST_DOCUMENT_TEMPLATES["large"] + "x" * 10000  # 10KB document

        test_doc = {"document": large_document, "document_type": "changelog"}

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        # Should handle large content gracefully
        assert response.status_code in [200, 201, 400, 413]  # 413 = Payload Too Large

    def test_sql_injection_attempts(self, api_client):
        """Test handling of potential SQL injection attempts."""
        # Test with SQL injection in blueprint ID
        sql_injection_id = "'; DROP TABLE blueprints; --"
        response = api_client.get(f"/api/blueprints/{sql_injection_id}/documentation")
        assert response.status_code == 400

        # Test with SQL injection in tag
        sql_injection_tag = "'; DROP TABLE tag_documentation; --"
        response = api_client.get(f"/api/tags/{sql_injection_tag}/documentation")
        assert (
            response.status_code == 400
        )  # Should be handled safely - invalid tag format

    def test_xss_attempts(self, api_client, test_blueprint_id):
        """Test handling of potential XSS attempts."""
        xss_document = "<script>alert('xss')</script>"

        test_doc = {"document": xss_document, "document_type": "changelog"}

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        # Should reject dangerous content
        assert response.status_code == 400

        # Verify it's rejected due to dangerous content
        error_data = response.json()
        assert (
            "dangerous" in error_data.get("error", "").lower()
            or "script" in error_data.get("error", "").lower()
        )

    def test_various_xss_attempts(self, api_client, test_blueprint_id):
        """Test various XSS attack vectors."""
        xss_attempts = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "<iframe src=javascript:alert('xss')>",
            "<body onload=alert('xss')>",
            "<div onclick=alert('xss')>click me</div>",
            "<a href=javascript:alert('xss')>click me</a>",
            "<form onsubmit=alert('xss')><input type=submit></form>",
            "<input onfocus=alert('xss')>",
            "<textarea onblur=alert('xss')></textarea>",
            "<select onchange=alert('xss')><option>test</option></select>",
        ]

        for xss_content in xss_attempts:
            test_doc = {"document": xss_content, "document_type": "changelog"}

            response = api_client.post(
                f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
            )

            # Should reject all XSS attempts
            assert (
                response.status_code == 400
            ), f"XSS attempt '{xss_content}' was not properly handled"

            # Verify it's rejected due to dangerous content
            error_data = response.json()
            error_msg = error_data.get("error", "").lower()
            assert any(
                keyword in error_msg
                for keyword in [
                    "dangerous",
                    "script",
                    "javascript",
                    "onload",
                    "onclick",
                    "onerror",
                    "onfocus",
                    "onblur",
                    "onchange",
                    "onsubmit",
                ]
            ), f"XSS attempt '{xss_content}' was not rejected for dangerous content"

    def test_legitimate_markdown_content(self, api_client, test_blueprint_id):
        """Test that legitimate markdown content is accepted and preserved."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["legitimate_markdown"],
            "document_type": "changelog",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        assert response.status_code == 201

        data = response.json()
        stored_content = data["documentation"]["document"]

        # Verify that legitimate markdown elements are preserved
        assert "__test__ Documentation" in stored_content
        assert "**bold text**" in stored_content
        assert "*italic text*" in stored_content
        assert "- Feature 1" in stored_content
        assert "```python" in stored_content
        assert "[Link to documentation]" in stored_content
        assert "![Image description]" in stored_content
        # Note: bleach HTML-encodes > to &gt; for safety
        assert (
            "&gt; This is a blockquote" in stored_content
            or "> This is a blockquote" in stored_content
        )
        assert "| Column 1 | Column 2 |" in stored_content
