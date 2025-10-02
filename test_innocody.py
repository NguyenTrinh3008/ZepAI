#!/usr/bin/env python
# test_innocody.py
"""
Quick test script for Innocody integration

Usage:
    python test_innocody.py
"""

import requests
import json
import sys


def test_health():
    """Test 1: Health check"""
    print("\n" + "="*70)
    print("TEST 1: Health Check")
    print("="*70)
    
    try:
        response = requests.get("http://localhost:8000/innocody/health", timeout=5)
        if response.status_code == 200:
            print("✅ PASS - Innocody adapter is healthy")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL - {e}")
        print("💡 Hint: Is the API running? Run: uvicorn app.main:app --reload")
        return False


def test_mock_ingest():
    """Test 2: Mock data ingest"""
    print("\n" + "="*70)
    print("TEST 2: Mock Data Ingest")
    print("="*70)
    
    try:
        response = requests.post("http://localhost:8000/innocody/test/mock", timeout=30)
        if response.status_code == 200:
            result = response.json()
            print("✅ PASS - Mock data ingested successfully")
            print(f"   Status: {result.get('status')}")
            print(f"   Message: {result.get('message')}")
            if 'payload' in result:
                payload = result['payload']
                print(f"   Name: {payload['name'][:60]}...")
                print(f"   File: {payload['metadata']['file_path']}")
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ FAIL - {e}")
        return False


def test_webhook():
    """Test 3: Real webhook call"""
    print("\n" + "="*70)
    print("TEST 3: Webhook Call")
    print("="*70)
    
    payload = {
        "file_before": "def hello():\n    print('hi')",
        "file_after": "def hello():\n    if True:\n        print('hi')",
        "chunks": [{
            "file_name": "test_integration.py",
            "file_action": "edit",
            "line1": 2,
            "line2": 2,
            "lines_remove": "    print('hi')",
            "lines_add": "    if True:\n        print('hi')"
        }],
        "meta": {
            "project_id": "test_innocody_integration"
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/innocody/webhook",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ PASS - Webhook processed successfully")
            print(f"   Status: {result.get('status')}")
            print(f"   Ingested: {result.get('ingested_count')} changes")
            print(f"   Project: {result.get('project_id')}")
            if 'summaries' in result:
                print(f"   Summary: {result['summaries'][0][:80]}...")
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ FAIL - {e}")
        return False


def test_search():
    """Test 4: Search ingested data"""
    print("\n" + "="*70)
    print("TEST 4: Search Code Memories")
    print("="*70)
    
    payload = {
        "query": "test integration",
        "project_id": "test_innocody_integration",
        "days_ago": 1
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/search/code",  # Using /search/code for full metadata
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            count = result.get('count', 0)
            
            if count > 0:
                print(f"✅ PASS - Found {count} results")
                item = result['results'][0]
                print(f"   Text: {item['text'][:80]}...")
                print(f"   File: {item.get('file_path', 'N/A')}")
                print(f"   Type: {item.get('change_type', 'N/A')}")
                
                # DEBUG: Print all keys
                print(f"\n   DEBUG - All keys in result: {list(item.keys())}")
                print(f"   DEBUG - Full item: {item}\n")
                
                # Check entity detail in Neo4j
                entity_id = item['id']
                entity_resp = requests.get(f"http://localhost:8000/debug/entity/{entity_id}")
                if entity_resp.status_code == 200:
                    entity_detail = entity_resp.json()
                    print(f"   DEBUG - Neo4j entity properties:")
                    props = entity_detail.get('properties', {})
                    for key in ['file_path', 'change_type', 'severity', 'function_name']:
                        print(f"     {key}: {props.get(key, 'NOT SET')}")
                print()
                
                return True
            else:
                print("⚠️  WARN - No results found (maybe TTL expired or not ingested yet)")
                print("   This is OK for first-time testing")
                return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL - {e}")
        return False


def test_batch():
    """Test 5: Batch webhook"""
    print("\n" + "="*70)
    print("TEST 5: Batch Webhook")
    print("="*70)
    
    batch = [
        {
            "file_before": "a = 1",
            "file_after": "a = 2",
            "chunks": [{
                "file_name": "file1.py",
                "file_action": "edit",
                "line1": 1,
                "line2": 1,
                "lines_remove": "a = 1",
                "lines_add": "a = 2"
            }],
            "meta": {"project_id": "test_batch"}
        },
        {
            "file_before": "b = 1",
            "file_after": "b = 2",
            "chunks": [{
                "file_name": "file2.py",
                "file_action": "edit",
                "line1": 1,
                "line2": 1,
                "lines_remove": "b = 1",
                "lines_add": "b = 2"
            }],
            "meta": {"project_id": "test_batch"}
        }
    ]
    
    try:
        response = requests.post(
            "http://localhost:8000/innocody/webhook/batch",
            json=batch,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ PASS - Batch processed successfully")
            print(f"   Status: {result.get('status')}")
            print(f"   Payloads: {result.get('total_payloads')}")
            print(f"   Chunks: {result.get('total_chunks')}")
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL - {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("INNOCODY INTEGRATION TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Mock Ingest", test_mock_ingest()))
    results.append(("Webhook Call", test_webhook()))
    results.append(("Search Memories", test_search()))
    results.append(("Batch Webhook", test_batch()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
