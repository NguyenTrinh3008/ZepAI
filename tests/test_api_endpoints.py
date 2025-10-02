# tests/test_api_endpoints.py
"""
Manual API endpoint testing script
Run with: python tests/test_api_endpoints.py
"""
import requests
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://localhost:8000"

def print_response(response, title):
    """Pretty print response"""
    print("\n" + "="*60)
    print(f"📋 {title}")
    print("="*60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Success")
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print(response.text)
    else:
        print("❌ Failed")
        print(response.text)

def verify_neo4j_entities():
    """Verify entities in Neo4j before testing"""
    print("\n" + "🔍"*30)
    print("NEO4J ENTITY VERIFICATION")
    print("🔍"*30)
    
    # Check test_project_001
    response = requests.get(f"{BASE_URL}/debug/episodes/test_project_001")
    if response.status_code == 200:
        data = response.json()
        print(f"\n📊 Project: test_project_001")
        print(f"   Total entities: {data.get('count', 0)}")
        
        # Show relationships if any
        if data.get('relationships'):
            print(f"   Relationships: {len(data.get('relationships', []))}")
    
    # Get stats
    stats = requests.get(f"{BASE_URL}/stats/test_project_001")
    if stats.status_code == 200:
        data = stats.json()
        print(f"\n📈 Statistics:")
        print(f"   Active memories: {data.get('total_memories', 0)}")
        print(f"   Expired memories: {data.get('expired_memories', 0)}")
        print(f"   Files: {data.get('files_count', 0)}")
        print(f"   Change types: {data.get('change_types', [])}")
    
    print("\n" + "="*90)
    input("Press Enter to continue with tests...")

def test_root():
    """Test root endpoint"""
    response = requests.get(f"{BASE_URL}/")
    print_response(response, "Test 1: Root Endpoint")
    return response.status_code == 200

def test_ingest_code_context():
    """Test ingesting code context"""
    payload = {
        "name": "Fixed login null pointer bug",
        "summary": "Fixed critical null pointer exception in auth_service.py:login_user() function by adding null check before accessing user.token attribute. This prevents AttributeError when token is None.",
        "metadata": {
            "file_path": "src/auth/auth_service.py",
            "function_name": "login_user",
            "line_start": 45,
            "line_end": 52,
            "change_type": "fixed",
            "change_summary": "Added null check before accessing user.token",
            "severity": "high",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "project_id": "test_project_001"
    }
    
    response = requests.post(f"{BASE_URL}/ingest/code-context", json=payload)
    print_response(response, "Test 2: Ingest Code Context")
    
    if response.status_code == 200:
        return response.json().get("episode_id")
    return None

def test_ingest_multiple():
    """Test ingesting multiple code contexts"""
    contexts = [
        {
            "name": "Added rate limiting middleware",
            "summary": "Implemented rate limiting middleware in api/middleware.py using Redis. Configured limit of 100 requests per minute per IP address. Includes error handling and custom response messages for rate limit exceeded.",
            "metadata": {
                "file_path": "src/api/middleware.py",
                "function_name": "rate_limit_middleware",
                "line_start": 120,
                "line_end": 145,
                "change_type": "added",
                "change_summary": "Implemented rate limiting using Redis",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "project_id": "test_project_001"
        },
        {
            "name": "Refactored database connection",
            "summary": "Refactored UserRepository.get_user_by_id() from synchronous to async/await pattern for 50% performance improvement. Updated database connection handling to use async context manager.",
            "metadata": {
                "file_path": "src/db/repository.py",
                "function_name": "get_user_by_id",
                "line_start": 30,
                "line_end": 48,
                "change_type": "refactored",
                "change_summary": "Migrated to async/await pattern",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "project_id": "test_project_001"
        }
    ]
    
    episode_ids = []
    for i, context in enumerate(contexts):
        response = requests.post(f"{BASE_URL}/ingest/code-context", json=context)
        print_response(response, f"Test 3.{i+1}: Ingest - {context['name']}")
        if response.status_code == 200:
            episode_ids.append(response.json().get("episode_id"))
    
    return episode_ids

def test_search_code_basic():
    """Test basic code search"""
    # First, verify entities exist in Neo4j
    print("\n" + "="*60)
    print("🔍 Verifying entities in Neo4j...")
    print("="*60)
    
    stats_response = requests.get(f"{BASE_URL}/stats/test_project_001")
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"Total memories: {stats.get('total_memories', 0)}")
        print(f"Files: {stats.get('files_count', 0)}")
        print(f"Change types: {stats.get('change_types', [])}")
    
    debug_response = requests.get(f"{BASE_URL}/debug/episodes/test_project_001")
    if debug_response.status_code == 200:
        debug_data = debug_response.json()
        print(f"Entities in Neo4j: {debug_data.get('count', 0)}")
    
    # Wait for Graphiti to index
    print("\n⏳ Waiting 5 seconds for Graphiti indexing...")
    import time
    time.sleep(5)
    
    # Try multiple search queries
    queries = [
        "authentication bug fixes",
        "login",
        "null pointer",
        "bug",
        "fixed",
        "auth_service"
    ]
    
    for query in queries:
        payload = {
            "query": query,
            "project_id": "test_project_001"
        }
        
        response = requests.post(f"{BASE_URL}/search/code", json=payload)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if len(results) > 0:
                print(f"\n✅ Found {len(results)} results for query: '{query}'")
                print_response(response, f"Test 4: Search - '{query}'")
                return True
    
    # If no results found, print debug info
    payload = {
        "query": "authentication bug fixes",
        "project_id": "test_project_001"
    }
    response = requests.post(f"{BASE_URL}/search/code", json=payload)
    print_response(response, "Test 4: Search - Basic (no results found)")
    
    return response.status_code == 200

def test_search_with_filters():
    """Test search with filters"""
    payload = {
        "query": "null pointer fixes",
        "project_id": "test_project_001",
        "file_filter": "src/auth/auth_service.py",
        "change_type_filter": "fixed"
    }
    
    response = requests.post(f"{BASE_URL}/search/code", json=payload)
    print_response(response, "Test 5: Search - With Filters")
    return response.status_code == 200

def test_project_isolation():
    """Test project isolation"""
    # Ingest to different project
    payload_project2 = {
        "name": "Test isolation",
        "summary": "This is in project 2 and should NOT appear in project 1 searches",
        "metadata": {
            "file_path": "test.py",
            "change_type": "added",
            "change_summary": "Test",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "project_id": "test_project_002"  # Different project!
    }
    
    response1 = requests.post(f"{BASE_URL}/ingest/code-context", json=payload_project2)
    print_response(response1, "Test 6.1: Ingest to Project 2")
    
    # Search in project 1 (should NOT find project 2 data)
    search_payload = {
        "query": "isolation test",
        "project_id": "test_project_001"
    }
    
    response2 = requests.post(f"{BASE_URL}/search/code", json=search_payload)
    print_response(response2, "Test 6.2: Search Project 1 (should not find Project 2)")
    
    if response2.status_code == 200:
        results = response2.json().get("results", [])
        # Should NOT contain project 2 data
        for result in results:
            if result.get("project_id") == "test_project_002":
                print("❌ FAILED: Project isolation breach!")
                return False
        print("✅ PASSED: Project isolation working!")
        return True
    return False

def test_stats():
    """Test project statistics"""
    response = requests.get(f"{BASE_URL}/stats/test_project_001")
    print_response(response, "Test 7: Project Statistics")
    return response.status_code == 200

def test_cleanup():
    """Test manual cleanup (careful - this deletes data!)"""
    print("\n" + "="*60)
    print("⚠️  Test 8: Manual Cleanup")
    print("="*60)
    print("This will delete expired memories.")
    user_input = input("Continue? (y/n): ")
    
    if user_input.lower() == 'y':
        response = requests.post(f"{BASE_URL}/admin/cleanup")
        print_response(response, "Test 8: Manual Cleanup")
        return response.status_code == 200
    else:
        print("Skipped cleanup test")
        return True

def test_search_different_queries():
    """Test various search queries"""
    queries = [
        ("bug fix", "General bug search"),
        ("authentication", "Authentication related"),
        ("rate limiting", "Feature search"),
        ("async refactor", "Refactoring search"),
    ]
    
    for query, description in queries:
        payload = {
            "query": query,
            "project_id": "test_project_001",
            "days_ago": 7
        }
        
        response = requests.post(f"{BASE_URL}/search/code", json=payload)
        print_response(response, f"Test 9: Search - {description}")

def run_all_tests():
    """Run all tests"""
    print("\n" + "🚀"*30)
    print("CODE MEMORY LAYER - API TESTING")
    print("🚀"*30)
    
    print(f"\nTesting API at: {BASE_URL}")
    print("Make sure the server is running!")
    print()
    
    # Wait for user confirmation
    input("Press Enter to start testing...")
    
    # Verify existing entities in Neo4j
    verify_neo4j_entities()
    
    results = []
    
    # Test sequence
    print("\n" + "🧪 STARTING TESTS...")
    
    results.append(("Root Endpoint", test_root()))
    results.append(("Ingest Code Context", test_ingest_code_context() is not None))
    results.append(("Ingest Multiple", len(test_ingest_multiple()) > 0))
    results.append(("Search Basic", test_search_code_basic()))
    results.append(("Search with Filters", test_search_with_filters()))
    results.append(("Project Isolation", test_project_isolation()))
    results.append(("Project Statistics", test_stats()))
    
    # Optional tests
    test_search_different_queries()
    results.append(("Cleanup", test_cleanup()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"✅ {test_name}")
            passed += 1
        else:
            print(f"❌ {test_name}")
            failed += 1
    
    print()
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} test(s) failed")
    
    print("="*60)

if __name__ == "__main__":
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API")
        print("Make sure the server is running:")
        print("  uvicorn app.main:app --reload")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
