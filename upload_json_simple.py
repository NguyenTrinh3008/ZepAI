# -*- coding: utf-8 -*-
"""
Simple JSON Upload Script

Script đơn giản để upload short_term.json lên Graphiti
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def upload_json_file(file_path: str, project_id: str):
    """Upload JSON file với timeout dài hơn"""
    
    print(f"File: {file_path}")
    print(f"Size: {os.path.getsize(file_path)} bytes")
    print(f"Project ID: {project_id}")
    print("-" * 50)
    
    # Tăng timeout cho file lớn
    timeout = httpx.Timeout(300.0, read=300.0, write=60.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print("Starting upload...")
            
            with open(file_path, 'rb') as f:
                files = {"file": (os.path.basename(file_path), f, "application/json")}
                data = {
                    "project_id": project_id,
                    "use_llm": "false"  # Tat LLM de xu ly nhanh hon
                }
                
                print("Sending request to API...")
                response = await client.post(
                    f"{BASE_URL}/upload/json-to-graph",
                    files=files,
                    data=data
                )
                
                print(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print("SUCCESS!")
                    print(f"   Project ID: {result.get('project_id', 'N/A')}")
                    print(f"   Episodes created: {result.get('episodes_created', 0)}")
                    print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
                    
                    details = result.get('details', {})
                    if details:
                        print(f"   Details:")
                        for key, value in details.items():
                            print(f"     {key}: {value}")
                    
                    return True
                else:
                    print(f"ERROR: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"   Error details: {error_data}")
                    except:
                        print(f"   Error text: {response.text}")
                    return False
                    
    except httpx.TimeoutException:
        print("ERROR: Request timeout - file qua lon hoac xu ly lau")
        print("   Thu chia nho file hoac tang timeout")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def check_upload_result(project_id: str):
    """Kiểm tra kết quả upload"""
    
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
            
            # Tim entities cua project nay
            by_group = stats.get('by_group', [])
            project_entities = 0
            for group in by_group:
                if project_id in group.get('group_id', ''):
                    project_entities += group.get('entity_count', 0)
                    print(f"   {group.get('group_id')}: {group.get('entity_count', 0)} entities")
            
            print(f"   Total for '{project_id}': {project_entities} entities")
            
            # Hien thi top entities
            top_entities = stats.get('top_entities', [])
            if top_entities:
                print(f"\nRecent entities:")
                for i, entity in enumerate(top_entities[:5], 1):
                    name = entity.get('name', 'Unknown')
                    group = entity.get('group_id', 'Unknown')
                    
                    if project_id in group:
                        print(f"   {i}. {name}")
                        summary = entity.get('summary', '')
                        if summary:
                            # Lam sach summary de tranh loi Unicode
                            summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                            if summary_clean:
                                print(f"      Summary: {summary_clean[:60]}...")
            
            return True
            
    except Exception as e:
        print(f"WARNING: Could not get entity stats: {e}")
        return False

async def main():
    """Main function"""
    print("JSON Upload to Graphiti")
    print("=" * 50)
    
    # Lấy tham số từ command line
    file_path = sys.argv[1] if len(sys.argv) > 1 else "short_term.json"
    project_id = sys.argv[2] if len(sys.argv) > 2 else "uploaded_stm"
    
    print(f"File: {file_path}")
    print(f"Project ID: {project_id}")
    print()
    
    # Kiem tra file ton tai
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found!")
        return False
    
    # Upload file
    success = await upload_json_file(file_path, project_id)
    
    if success:
        # Kiem tra ket qua
        await check_upload_result(project_id)
        
        print("\n" + "=" * 50)
        print("Upload completed successfully!")
        print("\nNext steps:")
        print("   1. Check Neo4j browser to see created entities")
        print("   2. Use /search endpoint to query the knowledge graph")
        print("   3. Entities are now available for semantic search")
        print(f"   4. Project ID '{project_id}' contains your data")
    else:
        print("\nUpload failed!")
        print("\nTroubleshooting:")
        print("   1. Check if server is running: curl http://localhost:8000/")
        print("   2. Try with smaller file or increase timeout")
        print("   3. Check server logs for errors")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
