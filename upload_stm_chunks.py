# -*- coding: utf-8 -*-
"""
Upload Short Term JSON in chunks

Chia nhỏ file short_term.json và upload từng phần để tránh timeout
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

def split_stm_json(file_path: str, chunk_size: int = 50):
    """Chia file short_term.json thành các chunk nhỏ"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = data.get('messages', [])
    total_messages = len(messages)
    
    print(f"Total messages: {total_messages}")
    print(f"Chunk size: {chunk_size}")
    print(f"Number of chunks: {(total_messages + chunk_size - 1) // chunk_size}")
    
    chunks = []
    for i in range(0, total_messages, chunk_size):
        chunk_messages = messages[i:i + chunk_size]
        chunk_data = {
            "messages": chunk_messages
        }
        chunks.append(chunk_data)
    
    return chunks

async def upload_chunk(chunk_data: dict, project_id: str, chunk_index: int):
    """Upload một chunk"""
    
    print(f"Uploading chunk {chunk_index + 1}...")
    
    timeout = httpx.Timeout(60.0, read=60.0, write=30.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Convert to JSON string
            json_text = json.dumps(chunk_data, ensure_ascii=False)
            
            # Create temporary file
            temp_file = f"temp_chunk_{chunk_index}.json"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(json_text)
            
            try:
                with open(temp_file, 'rb') as f:
                    files = {"file": (f"chunk_{chunk_index}.json", f, "application/json")}
                    data = {
                        "project_id": f"{project_id}_chunk_{chunk_index}",
                        "use_llm": "false"
                    }
                    
                    response = await client.post(
                        f"{BASE_URL}/upload/json-to-graph",
                        files=files,
                        data=data
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    print(f"  SUCCESS: Chunk {chunk_index + 1} uploaded!")
                    print(f"    Episodes created: {result.get('episodes_created', 0)}")
                    print(f"    Processing time: {result.get('processing_time', 0):.2f}s")
                    
                    return True
                    
            finally:
                # Clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
    except Exception as e:
        print(f"  ERROR: Chunk {chunk_index + 1} failed: {e}")
        return False

async def upload_stm_in_chunks(file_path: str, project_id: str, chunk_size: int = 50):
    """Upload short_term.json in chunks"""
    
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found!")
        return False
    
    print(f"Uploading {file_path} in chunks...")
    print(f"Project ID: {project_id}")
    print(f"Chunk size: {chunk_size}")
    print("-" * 50)
    
    # Split into chunks
    chunks = split_stm_json(file_path, chunk_size)
    
    # Upload each chunk
    success_count = 0
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        success = await upload_chunk(chunk, project_id, i)
        if success:
            success_count += 1
        
        # Small delay between chunks
        await asyncio.sleep(2)
    
    print("\n" + "=" * 50)
    print(f"Upload completed: {success_count}/{total_chunks} chunks successful")
    
    return success_count > 0

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
            
            # Find our project chunks
            by_group = stats.get('by_group', [])
            project_entities = 0
            for group in by_group:
                if group.get('group_id', '').startswith(project_id):
                    project_entities += group.get('entity_count', 0)
                    print(f"   {group.get('group_id')}: {group.get('entity_count', 0)} entities")
            
            print(f"   Total entities for '{project_id}': {project_entities}")
            
            return True
            
    except Exception as e:
        print(f"WARNING: Could not get entity stats: {e}")
        return False

async def main():
    """Main function"""
    print("Short Term JSON Chunked Upload to Graphiti")
    print("=" * 60)
    
    # Get parameters
    file_path = sys.argv[1] if len(sys.argv) > 1 else "short_term.json"
    project_id = sys.argv[2] if len(sys.argv) > 2 else "uploaded_stm_chunks"
    chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    
    print(f"File: {file_path}")
    print(f"Project ID: {project_id}")
    print(f"Chunk size: {chunk_size}")
    print()
    
    # Upload in chunks
    success = await upload_stm_in_chunks(file_path, project_id, chunk_size)
    
    if success:
        # Check entities
        await check_entities(project_id)
        
        print("\n" + "=" * 60)
        print("Chunked upload completed successfully!")
        print("\nNext steps:")
        print("   1. Check Neo4j browser to see created entities")
        print("   2. Use /search endpoint to query the knowledge graph")
        print("   3. All chunks are now available for semantic search")
    else:
        print("\nUpload failed!")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
