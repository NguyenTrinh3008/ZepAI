# tests/check_neo4j.py
"""
Check entities in Neo4j directly
"""
import requests

BASE_URL = "http://localhost:8000"

print("="*70)
print("CHECKING NEO4J ENTITIES")
print("="*70)

# Custom query to check ALL entities
print("\n1. Checking ALL entities (no project filter)...")

# We need to add a debug endpoint to query without project_id filter
# For now, let's use the existing debug endpoint

print("\n2. Checking test_project_001...")
response = requests.get(f"{BASE_URL}/debug/episodes/test_project_001")
if response.status_code == 200:
    data = response.json()
    print(f"   Count: {data.get('count', 0)}")
    
    # Show first few entities
    if 'relationships' in data and len(data['relationships']) > 0:
        print(f"\n   Showing first 3 entities:")
        for rel in data['relationships'][:3]:
            print(f"   - {rel.get('source')} -> {rel.get('target')}")

print("\n3. Stats for test_project_001...")
response = requests.get(f"{BASE_URL}/stats/test_project_001")
if response.status_code == 200:
    data = response.json()
    print(f"   Active: {data.get('total_memories', 0)}")
    print(f"   Expired: {data.get('expired_memories', 0)}")

print("\n4. Trying to ingest ONE test entity...")
payload = {
    "name": "Debug Test",
    "summary": "This is a debug test to check entity creation",
    "metadata": {
        "file_path": "debug.py",
        "change_type": "added",
        "change_summary": "Debug test",
        "timestamp": "2025-10-01T10:00:00Z"
    },
    "project_id": "debug_project"
}

import json
response = requests.post(
    f"{BASE_URL}/ingest/code-context",
    json=payload
)

print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Episode ID: {data.get('episode_id')}")
    print(f"   Is UUID? {len(data.get('episode_id', '')) > 32}")
    
    # Check if it appears in stats
    import time
    print("\n   Waiting 3 seconds...")
    time.sleep(3)
    
    stats = requests.get(f"{BASE_URL}/stats/debug_project")
    if stats.status_code == 200:
        data = stats.json()
        print(f"   Stats after ingest: {data.get('total_memories', 0)} memories")

print("\n" + "="*70)
print("RECOMMENDATION:")
print("="*70)
print("""
If episode_id is NAME (not UUID), then:
1. Graphiti's add_episode() returns episode WITHOUT created_entities
2. This means _set_entity_ttl() is NOT called
3. Entities exist but have NO project_id or expires_at

SOLUTION: Need to investigate Graphiti's behavior
- Check if add_episode() is async
- May need to wait for episode processing
- Or query entities after creation and update them
""")
