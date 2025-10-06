# -*- coding: utf-8 -*-
"""
View Entities Script

Xem chi tiết các entities đã được tạo
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

async def view_entities(project_id: str):
    """Xem entities của project"""
    
    print(f"Viewing entities for project: {project_id}")
    print("-" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            # Get entity stats
            response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
            
            if response.status_code == 200:
                stats = response.json()
                
                # Find our project
                by_group = stats.get('by_group', [])
                project_entities = 0
                for group in by_group:
                    if group.get('group_id') == project_id:
                        project_entities = group.get('entity_count', 0)
                        break
                
                print(f"Project '{project_id}' has {project_entities} entities")
                
                # Get top entities
                top_entities = stats.get('top_entities', [])
                if top_entities:
                    print(f"\nRecent entities:")
                    count = 0
                    for entity in top_entities:
                        group = entity.get('group_id', '')
                        if project_id in group:
                            count += 1
                            name = entity.get('name', 'Unknown')
                            summary = entity.get('summary', '')
                            created_at = entity.get('created_at', 'Unknown')
                            
                            print(f"\n{count}. {name}")
                            print(f"   Group: {group}")
                            print(f"   Created: {created_at}")
                            
                            if summary:
                                # Clean summary
                                summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                                if summary_clean:
                                    print(f"   Summary: {summary_clean}")
                                else:
                                    print(f"   Summary: [Contains non-ASCII characters]")
                            
                            if count >= 10:  # Limit to 10 entities
                                break
                
                if count == 0:
                    print("No entities found for this project")
                
            else:
                print(f"ERROR: {response.status_code}")
                print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"ERROR: {e}")

async def search_with_project(query: str, project_id: str):
    """Search với project ID cụ thể"""
    
    print(f"\nSearching '{query}' in project '{project_id}'...")
    print("-" * 40)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/search",
                json={
                    "query": query,
                    "group_id": project_id,
                    "limit": 5
                }
            )
            
            if response.status_code == 200:
                results = response.json()
                search_results = results.get('results', [])
                
                print(f"Found {len(search_results)} results:")
                
                for i, result in enumerate(search_results, 1):
                    name = result.get('name', 'Unknown')
                    summary = result.get('summary', '')
                    score = result.get('score', 0)
                    fact = result.get('fact', '')
                    
                    print(f"\n{i}. {name} (score: {score:.3f})")
                    
                    if summary:
                        summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                        if summary_clean:
                            print(f"   Summary: {summary_clean[:100]}...")
                    
                    if fact:
                        fact_clean = fact.encode('ascii', 'ignore').decode('ascii')
                        if fact_clean:
                            print(f"   Fact: {fact_clean[:100]}...")
            else:
                print(f"ERROR: {response.status_code}")
                print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"ERROR: {e}")

async def main():
    """Main function"""
    print("Entity Viewer")
    print("=" * 60)
    
    project_id = "my_stm_data"
    
    # View entities
    await view_entities(project_id)
    
    # Test some searches
    search_queries = [
        "code",
        "function", 
        "import",
        "python",
        "file"
    ]
    
    for query in search_queries:
        await search_with_project(query, project_id)
    
    print("\n" + "=" * 60)
    print("View completed!")

if __name__ == "__main__":
    asyncio.run(main())
