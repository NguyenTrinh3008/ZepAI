# -*- coding: utf-8 -*-
"""
Upload Short Term JSON to Graphiti

Script đơn giản để upload file short_term.json lên Graphiti và tạo entities trong Neo4j
"""

import asyncio
import httpx
import os
import sys

BASE_URL = "http://localhost:8000"

async def upload_short_term_json(file_path: str, project_id: str = "uploaded_stm"):
    """Upload short_term.json file to Graphiti"""
    
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found!")
        return False
    
    print(f"Uploading {file_path} to Graphiti...")
    print(f"Project ID: {project_id}")
    print("-" * 50)
    
    timeout = httpx.Timeout(120.0, read=120.0, write=30.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, 'rb') as f:
                files = {"file": (os.path.basename(file_path), f, "application/json")}
                data = {
                    "project_id": project_id,
                    "use_llm": "false"
                }
                
                print("Sending request to API...")
                response = await client.post(
                    f"{BASE_URL}/upload/json-to-graph",
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()
                
                print("SUCCESS: File uploaded successfully!")
                print(f"   Project ID: {result.get('project_id', 'N/A')}")
                print(f"   Episodes created: {result.get('episodes_created', 0)}")
                print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
                
                details = result.get('details', {})
                if details:
                    print(f"   Details:")
                    for key, value in details.items():
                        print(f"     {key}: {value}")
                
                return True
                
    except httpx.ConnectError:
        print("ERROR: Cannot connect to API server!")
        print("   Make sure the server is running on http://localhost:8000")
        print("   Start it with: python -m uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_entities(project_id: str):
    """Check entities created in Neo4j"""
    print(f"\nChecking entities for project: {project_id}")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
            response.raise_for_status()
            stats = response.json()
            
            print("Entity Statistics:")
            total_stats = stats.get('total_stats', {})
            print(f"   Total entities: {total_stats.get('total_entities', 0)}")
            print(f"   Unique groups: {total_stats.get('unique_groups', 0)}")
            
            # Find our project
            by_group = stats.get('by_group', [])
            project_entities = 0
            for group in by_group:
                if group.get('group_id') == project_id:
                    project_entities = group.get('entity_count', 0)
                    break
            
            print(f"   Entities for '{project_id}': {project_entities}")
            
            # Show top entities
            top_entities = stats.get('top_entities', [])
            if top_entities:
                print(f"\nRecent entities:")
                for i, entity in enumerate(top_entities[:10], 1):
                    name = entity.get('name', 'Unknown')
                    summary = entity.get('summary', '')
                    group = entity.get('group_id', 'Unknown')
                    
                    if group == project_id or project_id in group:
                        print(f"   {i}. {name}")
                        if summary:
                            # Truncate summary to avoid Unicode issues
                            summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                            print(f"      Summary: {summary_clean[:80]}...")
            
            return True
            
    except Exception as e:
        print(f"WARNING: Could not get entity stats: {e}")
        return False

async def main():
    """Main function"""
    print("Short Term JSON Upload to Graphiti")
    print("=" * 50)
    
    # Get file path from command line or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "short_term.json"
    
    # Get project ID from command line or use default
    if len(sys.argv) > 2:
        project_id = sys.argv[2]
    else:
        project_id = "uploaded_stm"
    
    print(f"File: {file_path}")
    print(f"Project ID: {project_id}")
    print()
    
    # Upload file
    success = await upload_short_term_json(file_path, project_id)
    
    if success:
        # Check entities
        await check_entities(project_id)
        
        print("\n" + "=" * 50)
        print("Upload completed successfully!")
        print("\nNext steps:")
        print("   1. Check Neo4j browser to see created entities")
        print("   2. Use /search endpoint to query the knowledge graph")
        print("   3. Entities are now available for semantic search")
    else:
        print("\nUpload failed!")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
