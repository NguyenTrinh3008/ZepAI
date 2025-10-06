# -*- coding: utf-8 -*-
"""
Simple Upload Script

Upload JSON sử dụng endpoint đơn giản nhất
"""

import asyncio
import httpx
import json
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def upload_simple_text(text: str, project_id: str):
    """Upload text đơn giản"""
    
    print(f"Uploading text to project: {project_id}")
    print(f"Text length: {len(text)} characters")
    print("-" * 50)
    
    # Chia text thành các phần nhỏ
    max_length = 1000
    text_parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    print(f"Split into {len(text_parts)} parts")
    
    timeout = httpx.Timeout(30.0, read=30.0, write=10.0, connect=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for i, part in enumerate(text_parts):
                print(f"Uploading part {i+1}/{len(text_parts)}...")
                
                episode_data = {
                    "name": f"Text Part {i+1}",
                    "text": part,
                    "source_description": f"simple_upload_part_{i+1}",
                    "reference_time": datetime.utcnow().isoformat() + "Z",
                    "group_id": project_id
                }
                
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=episode_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  SUCCESS: {result.get('message', 'OK')}")
                else:
                    print(f"  ERROR: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"  Details: {error_data}")
                    except:
                        print(f"  Text: {response.text}")
                
                # Đợi một chút giữa các requests
                await asyncio.sleep(1)
            
            # Kiểm tra kết quả
            print("\nChecking results...")
            await asyncio.sleep(3)
            
            stats_response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                total_entities = stats.get('total_stats', {}).get('total_entities', 0)
                print(f"Total entities: {total_entities}")
                
                if total_entities > 0:
                    print("SUCCESS: Entities were created!")
                    return True
                else:
                    print("WARNING: No entities created")
                    return False
            else:
                print(f"ERROR getting stats: {stats_response.status_code}")
                return False
    
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Main function"""
    print("Simple Upload Test")
    print("=" * 50)
    
    # Đọc file short_term.json
    file_path = "short_term.json"
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found!")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Tạo text từ messages
    messages = data.get('messages', [])
    text_parts = []
    
    for msg in messages[:10]:  # Chỉ lấy 10 messages đầu
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        if content.strip():
            text_parts.append(f"{role}: {content}")
    
    full_text = "\n\n".join(text_parts)
    print(f"Extracted text from {len(messages)} messages")
    print(f"Using first 10 messages, {len(full_text)} characters")
    
    # Upload
    success = await upload_simple_text(full_text, "simple_upload_test")
    
    if success:
        print("\n" + "=" * 50)
        print("Upload completed successfully!")
        print("Check Neo4j browser to see entities")
    else:
        print("\nUpload failed!")

if __name__ == "__main__":
    asyncio.run(main())
