#!/usr/bin/env python
"""
Fresh test - Clean and test metadata
"""

import requests
import time

def cleanup_project():
    """Step 1: Delete all test project entities"""
    print("="*70)
    print("STEP 1: Cleanup old test data")
    print("="*70)
    
    # This would require a cleanup endpoint
    # For now, skip
    print("⚠️  Skipping cleanup (would need cleanup endpoint)")
    print()


def ingest_fresh_data():
    """Step 2: Ingest fresh data with full metadata"""
    print("="*70)
    print("STEP 2: Ingest fresh data")
    print("="*70)
    
    payload = {
        "file_before": "def test():\n    print('old')",
        "file_after": "def test():\n    if True:\n        print('new')",
        "chunks": [{
            "file_name": "src/test_fresh.py",
            "file_action": "edit",
            "line1": 2,
            "line2": 2,
            "lines_remove": "    print('old')",
            "lines_add": "    if True:\n        print('new')"
        }],
        "meta": {
            "project_id": "fresh_test_project"
        }
    }
    
    response = requests.post(
        "http://localhost:8000/innocody/webhook",
        json=payload,
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Ingested successfully")
        print(f"   Episode IDs: {result['episode_ids']}")
        print(f"   Summary: {result['summaries'][0][:80]}...")
        print()
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False


def wait_for_processing():
    """Step 3: Wait for Graphiti to process"""
    print("="*70)
    print("STEP 3: Wait for processing")
    print("="*70)
    print("Waiting 3 seconds for Graphiti to create entities...")
    time.sleep(3)
    print("✓ Done\n")


def search_and_verify():
    """Step 4: Search and verify metadata"""
    print("="*70)
    print("STEP 4: Search and verify metadata")
    print("="*70)
    
    response = requests.post(
        "http://localhost:8000/search/code",
        json={
            "query": "test fresh",
            "project_id": "fresh_test_project",
            "days_ago": 1
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        count = result.get('count', 0)
        
        print(f"Found {count} results\n")
        
        if count > 0:
            for idx, item in enumerate(result['results'][:3], 1):
                print(f"Result {idx}:")
                print(f"  Text: {item['text'][:60]}...")
                print(f"  ID: {item['id'][:16]}...")
                print(f"  File: {item.get('file_path', 'NONE')}")
                print(f"  Type: {item.get('change_type', 'NONE')}")
                print(f"  Severity: {item.get('severity', 'NONE')}")
                print(f"  Function: {item.get('function_name', 'NONE')}")
                
                # Query entity detail
                entity_id = item['id']
                entity_resp = requests.get(f"http://localhost:8000/debug/entity/{entity_id}")
                if entity_resp.status_code == 200:
                    entity_detail = entity_resp.json()
                    props = entity_detail.get('properties', {})
                    
                    print(f"\n  Neo4j properties:")
                    print(f"    file_path: {props.get('file_path', 'NOT SET')}")
                    print(f"    change_type: {props.get('change_type', 'NOT SET')}")
                    print(f"    severity: {props.get('severity', 'NOT SET')}")
                    print(f"    lines_added: {props.get('lines_added', 'NOT SET')}")
                    print(f"    lines_removed: {props.get('lines_removed', 'NOT SET')}")
                
                # Check if metadata is set
                has_metadata = item.get('file_path') is not None
                if has_metadata:
                    print(f"\n  ✅ METADATA IS SET!")
                else:
                    print(f"\n  ❌ METADATA IS MISSING!")
                
                print()
            
            return True
        else:
            print("❌ No results found")
            return False
    else:
        print(f"❌ Search failed: {response.status_code}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("FRESH METADATA TEST")
    print("="*70 + "\n")
    
    # Run test
    cleanup_project()
    
    if ingest_fresh_data():
        wait_for_processing()
        search_and_verify()
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
