#!/usr/bin/env python3
"""
Debug script to check API routes and test data.
"""

import os
import sys

import requests

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .test_constants import TEST_DOCUMENT_TEMPLATES


def debug_api_routes():
    """Debug API routes and test data."""
    base_url = "http://localhost:5328"
    api_key = "1234567890"  # Fixed API key

    print("🔍 Debugging API Routes")
    print("=" * 50)

    # Test basic connectivity
    print("1. Testing basic connectivity...")
    blueprints = None  # Initialize to prevent NameError
    try:
        response = requests.get(f"{base_url}/api/blueprints", timeout=5)
        print(f"   Blueprints endpoint: {response.status_code}")
        if response.status_code == 200:
            blueprints = response.json()
            print(f"   Found {len(blueprints)} blueprints")
            if blueprints:
                print(f"   First blueprint ID: {blueprints[0]['id']}")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return

    # Test tag documentation routes
    print("\n2. Testing tag documentation routes...")

    # Test GET tag documentation
    try:
        response = requests.get(
            f"{base_url}/api/tags/texture/dungeon_stone/documentation", timeout=5
        )
        status = response.status_code
        print(f"   GET /api/tags/texture/dungeon_stone/documentation: {status}")
        if response.status_code == 200:
            data = response.json()
            print(
                f"   Found {len(data.get('documentation', []))} documentation entries"
            )
        elif response.status_code == 404:
            print("   ❌ Route not found - tag documentation routes may not be")
            print("      implemented")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test POST tag documentation (should fail without auth)
    try:
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["debug"],
            "document_type": "instructions",
        }
        response = requests.post(
            f"{base_url}/api/tags/test/debug/documentation", json=test_doc, timeout=5
        )
        status = response.status_code
        print(f"   POST /api/tags/test/debug/documentation (no auth): {status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test POST tag documentation with auth
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.post(
            f"{base_url}/api/tags/test/debug/documentation",
            json=test_doc,
            headers=headers,
            timeout=5,
        )
        status = response.status_code
        print(f"   POST /api/tags/test/debug/documentation (with auth): {status}")
        if response.status_code in [200, 201]:
            data = response.json()
            doc_id = data.get("documentation", {}).get("id")
            print(f"   Created documentation ID: {doc_id}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test blueprint documentation routes
    print("\n3. Testing blueprint documentation routes...")

    if blueprints:
        blueprint_id = blueprints[0]["id"]

        # Test GET blueprint documentation
        try:
            response = requests.get(
                f"{base_url}/api/blueprints/{blueprint_id}/documentation", timeout=5
            )
            status = response.status_code
            print(f"   GET /api/blueprints/{blueprint_id}/documentation: {status}")
            if response.status_code == 200:
                data = response.json()
                doc_count = len(data.get("documentation", []))
                print(f"   Found {doc_count} documentation entries")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test POST blueprint documentation (should fail without auth)
        try:
            test_doc = {
                "document": TEST_DOCUMENT_TEMPLATES["changelog"],
                "document_type": "changelog",
            }
            response = requests.post(
                f"{base_url}/api/blueprints/{blueprint_id}/documentation",
                json=test_doc,
                timeout=5,
            )
            status = response.status_code
            print(f"   POST /api/blueprints/{blueprint_id}/documentation ")
            print(f"        (no auth): {status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test POST blueprint documentation with auth
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.post(
                f"{base_url}/api/blueprints/{blueprint_id}/documentation",
                json=test_doc,
                headers=headers,
                timeout=5,
            )
            status = response.status_code
            print(f"   POST /api/blueprints/{blueprint_id}/documentation ")
            print(f"        (with auth): {status}")
            if response.status_code in [200, 201]:
                data = response.json()
                doc_id = data.get("documentation", {}).get("id")
                print(f"   Created documentation ID: {doc_id}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Test error cases
    print("\n4. Testing error cases...")

    # Test invalid blueprint ID
    try:
        response = requests.get(
            f"{base_url}/api/blueprints/invalid-uuid/documentation", timeout=5
        )
        print(
            f"   GET /api/blueprints/invalid-uuid/documentation: {response.status_code}"
        )
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test invalid tag format
    try:
        response = requests.get(
            f"{base_url}/api/tags/invalid-tag-format/documentation", timeout=5
        )
        status = response.status_code
        print(f"   GET /api/tags/invalid-tag-format/documentation: {status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test alternative tag documentation routes
    print("\n5. Testing alternative tag documentation routes...")

    try:
        response = requests.get(f"{base_url}/api/tag-documentation", timeout=5)
        print(f"   GET /api/tag-documentation: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            doc_count = len(data.get("documentation", []))
            print(f"   Found {doc_count} total documentation entries")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    try:
        response = requests.get(f"{base_url}/api/tag-documentation/texture", timeout=5)
        print(f"   GET /api/tag-documentation/texture: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            doc_count = len(data.get("documentation", []))
            print(f"   Found {doc_count} documentation entries for texture")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print("\n✅ Debug complete!")


if __name__ == "__main__":
    debug_api_routes()
