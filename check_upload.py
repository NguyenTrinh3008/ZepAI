# -*- coding: utf-8 -*-
"""
Check Upload Result

Kiểm tra kết quả upload một cách đơn giản
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

async def check_upload():
    """Kiểm tra kết quả upload"""
    
    print("Checking upload result...")
    print("-" * 40)
    
    try:
        async with httpx.AsyncClient() as client:
            # Get entity stats
            response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
            
            if response.status_code == 200:
                stats = response.json()
                
                print("SUCCESS: Got entity stats")
                
                total_stats = stats.get('total_stats', {})
                print(f"Total entities: {total_stats.get('total_entities', 0)}")
                print(f"Unique groups: {total_stats.get('unique_groups', 0)}")
                
                # Show all groups
                by_group = stats.get('by_group', [])
                print(f"\nAll groups ({len(by_group)}):")
                for i, group in enumerate(by_group, 1):
                    group_id = group.get('group_id', 'Unknown')
                    count = group.get('entity_count', 0)
                    print(f"  {i:2d}. {group_id}: {count} entities")
                
                # Check if our project exists
                our_project = "my_stm_data"
                found = False
                for group in by_group:
                    if group.get('group_id') == our_project:
                        found = True
                        print(f"\nFOUND: {our_project} has {group.get('entity_count', 0)} entities")
                        break
                
                if not found:
                    print(f"\nNOT FOUND: {our_project} not in groups")
                
            else:
                print(f"ERROR: {response.status_code}")
                print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

async def test_search_all():
    """Test search without group filter"""
    
    print(f"\nTesting search without group filter...")
    print("-" * 40)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/search",
                json={
                    "query": "authentication",
                    "limit": 3
                }
            )
            
            if response.status_code == 200:
                results = response.json()
                search_results = results.get('results', [])
                
                print(f"Found {len(search_results)} results for 'authentication':")
                
                for i, result in enumerate(search_results, 1):
                    name = result.get('name', 'Unknown')
                    score = result.get('score', 0)
                    group_id = result.get('group_id', 'Unknown')
                    
                    print(f"  {i}. {name} (score: {score:.3f}) - Group: {group_id}")
            else:
                print(f"ERROR: {response.status_code}")
                print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"ERROR: {e}")

async def main():
    """Main function"""
    print("Upload Check")
    print("=" * 50)
    
    await check_upload()
    await test_search_all()
    
    print("\n" + "=" * 50)
    print("Check completed!")

if __name__ == "__main__":
    asyncio.run(main())
