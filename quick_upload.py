# -*- coding: utf-8 -*-
"""
Quick Upload Script

Upload nhanh với file nhỏ để test
"""

import asyncio
import httpx
import json
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def quick_upload():
    """Upload nhanh với dữ liệu nhỏ"""
    
    print("Quick Upload Test")
    print("=" * 40)
    
    # Tạo dữ liệu test nhỏ
    test_data = {
        "name": "Quick Test",
        "text": "user: How do I implement authentication in FastAPI?\n\nassistant: I'll help you implement authentication in FastAPI. Here's a step-by-step guide:\n\n1. Install required packages\n2. Create JWT token utilities\n3. Implement password hashing\n4. Create authentication middleware\n5. Protect your routes",
        "source_description": "quick_test",
        "group_id": "quick_test"
    }
    
    timeout = httpx.Timeout(30.0, read=30.0, write=10.0, connect=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print("Uploading test data...")
            
            response = await client.post(
                f"{BASE_URL}/ingest/text",
                json=test_data
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("SUCCESS!")
                print(f"Message: {result.get('message', 'OK')}")
                
                # Đợi xử lý
                print("Waiting for processing...")
                await asyncio.sleep(5)
                
                # Kiểm tra entities
                print("Checking entities...")
                stats_response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
                
                if stats_response.status_code == 200:
                    stats = stats_response.json()
                    total_entities = stats.get('total_stats', {}).get('total_entities', 0)
                    print(f"Total entities: {total_entities}")
                    
                    if total_entities > 0:
                        print("SUCCESS: Entities created!")
                        return True
                    else:
                        print("WARNING: No entities created")
                        return False
                else:
                    print(f"ERROR getting stats: {stats_response.status_code}")
                    return False
            else:
                print(f"ERROR: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Details: {error_data}")
                except:
                    print(f"Text: {response.text}")
                return False
    
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def upload_short_term_small():
    """Upload một phần nhỏ của short_term.json"""
    
    print("\nUploading small part of short_term.json...")
    print("-" * 40)
    
    # Đọc file
    with open("short_term.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Lấy 3 messages đầu
    messages = data.get('messages', [])[:3]
    
    text_parts = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        if content.strip():
            text_parts.append(f"{role}: {content}")
    
    full_text = "\n\n".join(text_parts)
    print(f"Using {len(messages)} messages, {len(full_text)} characters")
    
    # Upload
    upload_data = {
        "name": "Short Term Memory Sample",
        "text": full_text,
        "source_description": "short_term_sample",
        "group_id": "short_term_sample"
    }
    
    timeout = httpx.Timeout(60.0, read=60.0, write=30.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{BASE_URL}/ingest/text",
                json=upload_data
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("SUCCESS!")
                print(f"Message: {result.get('message', 'OK')}")
                
                # Đợi xử lý
                print("Waiting for processing...")
                await asyncio.sleep(5)
                
                # Kiểm tra entities
                stats_response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
                
                if stats_response.status_code == 200:
                    stats = stats_response.json()
                    total_entities = stats.get('total_stats', {}).get('total_entities', 0)
                    print(f"Total entities: {total_entities}")
                    
                    if total_entities > 0:
                        print("SUCCESS: Entities created!")
                        return True
                    else:
                        print("WARNING: No entities created")
                        return False
                else:
                    print(f"ERROR getting stats: {stats_response.status_code}")
                    return False
            else:
                print(f"ERROR: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Details: {error_data}")
                except:
                    print(f"Text: {response.text}")
                return False
    
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Main function"""
    print("Quick Upload Test Suite")
    print("=" * 60)
    
    # Test 1: Upload dữ liệu nhỏ
    success1 = await quick_upload()
    
    if success1:
        print("\n" + "=" * 60)
        print("Test 1 PASSED: Basic upload working!")
        
        # Test 2: Upload phần nhỏ của short_term.json
        success2 = await upload_short_term_small()
        
        if success2:
            print("\n" + "=" * 60)
            print("Test 2 PASSED: Short term upload working!")
            print("\nYou can now upload the full file using:")
            print("python upload_json_simple.py short_term.json your_project_name")
        else:
            print("\nTest 2 FAILED: Short term upload has issues")
    else:
        print("\nTest 1 FAILED: Basic upload not working")
        print("Check Neo4j connection first!")
    
    return success1

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
