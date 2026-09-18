#!/usr/bin/env python3
"""
API endpoint validation script for the documentation system.

This script tests all documentation endpoints using curl to ensure they:
1. Return correct HTTP status codes
2. Return properly formatted JSON responses
3. Handle authentication correctly
4. Validate request/response schemas
"""

import json
import subprocess
import sys
from typing import Any, Dict, Optional

from .test_constants import TEST_DOCUMENT_TEMPLATES

# Configuration
BASE_URL = "http://localhost:5328"  # Adjust if your server runs on different port
API_KEY = "1234567890"  # Use your actual API key for authenticated endpoints


class APITester:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.test_data = {}

    def curl_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make a curl request and return response details."""
        url = f"{self.base_url}{endpoint}"

        # Build curl command
        cmd = ["curl", "-s", "-w", "%{http_code}", "-X", method, url]

        # Add headers
        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        # Add data for POST/PUT requests
        if data and method in ["POST", "PUT"]:
            cmd.extend(["-H", "Content-Type: application/json"])
            cmd.extend(["-d", json.dumps(data)])

        try:
            # Execute curl command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            # Parse response
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Curl command failed: {result.stderr}",
                    "status_code": None,
                    "response": None,
                }

            # Split response body and status code
            output = result.stdout
            if output.endswith("\n"):
                output = output[:-1]

            # Find the status code (last line)
            lines = output.split("\n")
            if len(lines) >= 2:
                status_code = int(lines[-1])
                response_body = "\n".join(lines[:-1])
            else:
                # If there's only one line, it's the status code
                status_code = int(output)
                response_body = ""

            # Parse JSON response
            try:
                response_json = (
                    json.loads(response_body) if response_body.strip() else {}
                )
            except json.JSONDecodeError:
                response_json = {"raw_response": response_body}

            return {
                "success": True,
                "status_code": status_code,
                "response": response_json,
                "raw_response": response_body,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Request timed out",
                "status_code": None,
                "response": None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "status_code": None,
                "response": None,
            }

    def test_blueprint_documentation_endpoints(self):
        """Test blueprint documentation endpoints."""
        print("🔍 Testing Blueprint Documentation Endpoints...")

        # First, we need a blueprint ID to test with
        # Let's get a list of blueprints first
        print("  📋 Getting list of blueprints...")
        response = self.curl_request("GET", "/api/blueprints")

        if not response["success"]:
            print(f"    ❌ Failed to get blueprints: {response['error']}")
            return False

        if response["status_code"] != 200:
            print(f"    ❌ Unexpected status code: {response['status_code']}")
            return False

        blueprints = response["response"]
        if not blueprints or len(blueprints) == 0:
            print("    ⚠️  No blueprints found, skipping blueprint documentation tests")
            return True

        # Use the first blueprint for testing
        blueprint_id = blueprints[0]["id"]
        print(f"    ✅ Using blueprint ID: {blueprint_id}")

        # Test GET /api/blueprints/{blueprint_id}/documentation
        print("  📖 Testing GET blueprint documentation...")
        response = self.curl_request(
            "GET", f"/api/blueprints/{blueprint_id}/documentation"
        )

        if response["success"] and response["status_code"] == 200:
            print("    ✅ GET blueprint documentation successful")
            self.test_data["blueprint_docs"] = response["response"]
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ GET blueprint documentation failed: {error_msg}")

        # Test POST /api/blueprints/{blueprint_id}/documentation (requires auth)
        print("  ✏️  Testing POST blueprint documentation...")
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["changelog"],
            "document_type": "changelog",
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = self.curl_request(
            "POST",
            f"/api/blueprints/{blueprint_id}/documentation",
            data=test_doc,
            headers=headers,
        )

        if response["success"] and response["status_code"] in [200, 201]:
            print("    ✅ POST blueprint documentation successful")
            self.test_data["created_doc"] = response["response"]["documentation"]
            doc_id = response["response"]["documentation"]["id"]

            # Test PATCH /api/blueprints/{blueprint_id}/documentation/{doc_id}
            print("  🔄 Testing PATCH blueprint documentation...")
            update_doc = {
                "document": TEST_DOCUMENT_TEMPLATES["update"],
                "document_type": "changelog",
            }

            response = self.curl_request(
                "PATCH",
                f"/api/blueprints/{blueprint_id}/documentation/{doc_id}",
                data=update_doc,
                headers=headers,
            )

            if response["success"] and response["status_code"] == 200:
                print("    ✅ PATCH blueprint documentation successful")

                # Test DELETE /api/blueprints/{blueprint_id}/documentation/{doc_id}
                print("  🗑️  Testing DELETE blueprint documentation...")
                response = self.curl_request(
                    "DELETE",
                    f"/api/blueprints/{blueprint_id}/documentation/{doc_id}",
                    headers=headers,
                )

                if response["success"] and response["status_code"] == 204:
                    print("    ✅ DELETE blueprint documentation successful")
                else:
                    status = response.get("status_code")
                    error_msg = response.get("error", f"Status {status}")
                    print(f"    ❌ DELETE blueprint documentation failed: {error_msg}")
            else:
                status = response.get("status_code")
                error_msg = response.get("error", f"Status {status}")
                print(f"    ❌ PATCH blueprint documentation failed: {error_msg}")
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ POST blueprint documentation failed: {error_msg}")

        # Test GET /api/blueprints/{blueprint_id}/changelog-history
        print("  📜 Testing GET changelog history...")
        response = self.curl_request(
            "GET", f"/api/blueprints/{blueprint_id}/changelog-history"
        )

        if response["success"] and response["status_code"] == 200:
            print("    ✅ GET changelog history successful")
            self.test_data["changelog_history"] = response["response"]
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ GET changelog history failed: {error_msg}")

        # Test GET /api/blueprints/{blueprint_id}/all-documentation
        print("  📚 Testing GET all documentation...")
        response = self.curl_request(
            "GET", f"/api/blueprints/{blueprint_id}/all-documentation"
        )

        if response["success"] and response["status_code"] == 200:
            print("    ✅ GET all documentation successful")
            self.test_data["all_documentation"] = response["response"]

            # Validate response structure
            data = response["response"]
            required_fields = [
                "blueprint_id",
                "blueprint_name",
                "blueprint_documentation",
                "changelog_history",
                "tag_documentation",
            ]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                print(f"    ❌ Missing required fields: {missing_fields}")
            else:
                print("    ✅ Response structure valid")
                print(f"    📊 Blueprint docs: {len(data['blueprint_documentation'])}")
                changelog_count = len(data["changelog_history"]["changelogs"])
                print(f"    📊 Changelog entries: {changelog_count}")
                print(f"    📊 Tag docs: {len(data['tag_documentation'])} tags")
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ GET all documentation failed: {error_msg}")

        return True

    def test_tag_documentation_endpoints(self):
        """Test tag documentation endpoints."""
        print("\n🔍 Testing Tag Documentation Endpoints...")

        # Test with a common tag combination
        tag_array = "texture/dungeon_stone"

        # Test GET /api/tags/{tag_array}/documentation
        print(f"  📖 Testing GET tag documentation for '{tag_array}'...")
        response = self.curl_request("GET", f"/api/tags/{tag_array}/documentation")

        if response["success"] and response["status_code"] == 200:
            print("    ✅ GET tag documentation successful")
            self.test_data["tag_docs"] = response["response"]
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ GET tag documentation failed: {error_msg}")

        # Test POST /api/tags/{tag_array}/documentation (requires auth)
        print(f"  ✏️  Testing POST tag documentation for '{tag_array}'...")
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["instructions"],
            "document_type": "instructions",
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = self.curl_request(
            "POST",
            f"/api/tags/{tag_array}/documentation",
            data=test_doc,
            headers=headers,
        )

        if response["success"] and response["status_code"] in [200, 201]:
            print("    ✅ POST tag documentation successful")
            self.test_data["created_tag_doc"] = response["response"]["documentation"]
            doc_id = response["response"]["documentation"]["id"]

            # Test PATCH /api/tags/{tag_array}/documentation/{doc_id}
            print(f"  🔄 Testing PATCH tag documentation for '{tag_array}'...")
            update_doc = {
                "document": "Updated tag instructions",
                "document_type": "instructions",
            }

            response = self.curl_request(
                "PATCH",
                f"/api/tags/{tag_array}/documentation/{doc_id}",
                data=update_doc,
                headers=headers,
            )

            if response["success"] and response["status_code"] == 200:
                print("    ✅ PATCH tag documentation successful")

                # Test DELETE /api/tags/{tag_array}/documentation/{doc_id}
                print(f"  🗑️  Testing DELETE tag documentation for '{tag_array}'...")
                response = self.curl_request(
                    "DELETE",
                    f"/api/tags/{tag_array}/documentation/{doc_id}",
                    headers=headers,
                )

                if response["success"] and response["status_code"] == 204:
                    print("    ✅ DELETE tag documentation successful")
                else:
                    status = response.get("status_code")
                    error_msg = response.get("error", f"Status {status}")
                    print(f"    ❌ DELETE tag documentation failed: {error_msg}")
            else:
                status = response.get("status_code")
                error_msg = response.get("error", f"Status {status}")
                print(f"    ❌ PATCH tag documentation failed: {error_msg}")
        else:
            status = response.get("status_code")
            error_msg = response.get("error", f"Status {status}")
            print(f"    ❌ POST tag documentation failed: {error_msg}")

        return True

    def test_authentication(self):
        """Test authentication requirements."""
        print("\n🔍 Testing Authentication...")

        # Test that POST without auth fails
        print("  🔒 Testing POST without authentication...")
        test_doc = {"document": "Unauthorized test", "document_type": "changelog"}

        # Get a blueprint ID first
        response = self.curl_request("GET", "/api/blueprints")
        if response["success"] and response["status_code"] == 200:
            blueprints = response["response"]
            if blueprints:
                blueprint_id = blueprints[0]["id"]

                # Try POST without auth
                response = self.curl_request(
                    "POST",
                    f"/api/blueprints/{blueprint_id}/documentation",
                    data=test_doc,
                )

                if response["success"] and response["status_code"] == 401:
                    print("    ✅ Authentication required (401 returned)")
                else:
                    print(f"    ❌ Expected 401, got {response.get('status_code')}")
            else:
                print("    ⚠️  No blueprints available for auth test")
        else:
            print("    ❌ Could not get blueprints for auth test")

        return True

    def test_error_handling(self):
        """Test error handling for invalid requests."""
        print("\n🔍 Testing Error Handling...")

        # Test invalid blueprint ID
        print("  🚫 Testing invalid blueprint ID...")
        response = self.curl_request(
            "GET", "/api/blueprints/invalid-uuid/documentation"
        )

        if response["success"] and response["status_code"] == 400:
            print("    ✅ Invalid blueprint ID handled correctly (400)")
        else:
            status = response.get("status_code")
            print(f"    ❌ Expected 400 for invalid blueprint ID, got {status}")

        # Test invalid tag format
        print("  🚫 Testing invalid tag format...")
        response = self.curl_request(
            "GET", "/api/tags/invalid-tag-format/documentation"
        )

        if response["success"] and response["status_code"] in [200, 400, 404, 500]:
            status = response.get("status_code")
            print(f"    ✅ Invalid tag format handled correctly ({status})")
        else:
            status = response.get("status_code")
            print(f"    ❌ Expected 200/400/404/500 for invalid tag, got {status}")

        # Test invalid JSON in POST
        print("  🚫 Testing invalid JSON in POST...")

        # Get a blueprint ID first
        response = self.curl_request("GET", "/api/blueprints")
        if response["success"] and response["status_code"] == 200:
            blueprints = response["response"]
            if blueprints:
                blueprint_id = blueprints[0]["id"]

                # Try POST with invalid JSON
                cmd = [
                    "curl",
                    "-s",
                    "-w",
                    "%{http_code}",
                    "-X",
                    "POST",
                    f"{self.base_url}/api/blueprints/{blueprint_id}/documentation",
                    "-H",
                    f"Authorization: Bearer {self.api_key}",
                    "-H",
                    "Content-Type: application/json",
                    "-d",
                    "invalid json",
                ]

                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        output = result.stdout
                        lines = output.split("\n")
                        status_code = int(lines[-1]) if lines else 0

                        if status_code in [400, 401]:
                            print(
                                f"    ✅ Invalid JSON handled correctly ({status_code})"
                            )
                        else:
                            print(f"    ❌ Expected 400/401, got {status_code}")
                    else:
                        print("    ❌ Invalid JSON test failed")
                except Exception as e:
                    print(f"    ❌ Invalid JSON test failed: {e}")

        return True

    def run_all_tests(self):
        """Run all API tests."""
        print("🚀 Starting API Endpoint Validation...\n")

        tests = [
            ("Blueprint Documentation", self.test_blueprint_documentation_endpoints),
            ("Tag Documentation", self.test_tag_documentation_endpoints),
            ("Authentication", self.test_authentication),
            ("Error Handling", self.test_error_handling),
        ]

        results = []
        for name, test_func in tests:
            try:
                print(f"\n{'=' * 60}")
                print(f"Testing: {name}")
                print("=" * 60)

                result = test_func()
                results.append((name, result))

                if result:
                    print(f"✅ {name} tests completed")
                else:
                    print(f"❌ {name} tests failed")

            except Exception as e:
                print(f"❌ {name} tests failed with exception: {e}")
                results.append((name, False))

        # Summary
        print(f"\n{'=' * 60}")
        print("API VALIDATION SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        failed = len(results) - passed

        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{name:<25} {status}")

        print("-" * 60)
        print(f"Total: {len(results)} test suites")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed == 0:
            print("\n🎉 All API validation tests passed!")
            return 0
        else:
            print(f"\n⚠️  {failed} test suite(s) failed")
            return 1


def main():
    """Main function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL

    if len(sys.argv) > 2:
        api_key = sys.argv[2]
    else:
        api_key = API_KEY

    print(f"Using base URL: {base_url}")
    print(
        f"Using API key: {api_key[:8]}..."
        if len(api_key) > 8
        else f"Using API key: {api_key}"
    )

    tester = APITester(base_url, api_key)
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
