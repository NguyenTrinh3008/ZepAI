# -*- coding: utf-8 -*-
"""
Debug Upload Script

Debug việc upload JSON để tìm lỗi
"""

import asyncio
import httpx
import json
import os

BASE_URL = "http://localhost:8000"

async def debug_upload():
    """Debug upload process"""
    
    print("Debug Upload Process")
    print("=" * 50)
    
    # Tạo JSON data nhỏ để test
    test_data = {
        "messages": [
            {
                "id": "debug_001",
                "role": "user",
                "content": "How do I implement authentication in FastAPI?",
                "timestamp": "2025-10-06T03:30:00Z",
                "project_id": "debug_test",
                "metadata": {
                    "conversation_id": "conv_debug",
                    "intent": "code_help",
                    "keywords": ["authentication", "FastAPI", "security"]
                }
            },
            {
                "id": "debug_002", 
                "role": "assistant",
                "content": "I'll help you implement authentication in FastAPI. Here's a step-by-step guide:\n\n1. Install required packages: `pip install python-jose[cryptography] passlib[bcrypt]`\n2. Create JWT token utilities\n3. Implement password hashing\n4. Create authentication middleware\n5. Protect your routes\n\nThis will give you a secure authentication system.",
                "timestamp": "2025-10-06T03:30:30Z",
                "project_id": "debug_test",
                "metadata": {
                    "conversation_id": "conv_debug",
                    "intent": "code_help",
                    "keywords": ["authentication", "FastAPI", "JWT", "security", "middleware"]
                }
            }
        ]
    }
    
    # Lưu vào file tạm
    temp_file = "debug_test.json"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)
    
    print(f"Created test file: {temp_file}")
    print(f"File size: {os.path.getsize(temp_file)} bytes")
    
    # Upload file
    timeout = httpx.Timeout(60.0, read=60.0, write=30.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print("\nUploading test file...")
            
            with open(temp_file, 'rb') as f:
                files = {"file": ("debug_test.json", f, "application/json")}
                data = {
                    "project_id": "debug_test",
                    "use_llm": "false"
                }
                
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
                    
                    # Đợi một chút để Graphiti xử lý
                    print("\nWaiting for Graphiti to process...")
                    await asyncio.sleep(5)
                    
                    # Kiểm tra entities
                    print("\nChecking entities...")
                    stats_response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
                    
                    if stats_response.status_code == 200:
                        stats = stats_response.json()
                        total_entities = stats.get('total_stats', {}).get('total_entities', 0)
                        print(f"Total entities: {total_entities}")
                        
                        if total_entities > 0:
                            print("SUCCESS: Entities were created!")
                        else:
                            print("WARNING: No entities created - there might be an issue")
                    else:
                        print(f"ERROR getting stats: {stats_response.status_code}")
                    
                else:
                    print(f"ERROR: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"Error details: {error_data}")
                    except:
                        print(f"Error text: {response.text}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.remove(temp_file)
            print(f"\nCleaned up {temp_file}")

async def main():
    """Main function"""
    await debug_upload()
    print("\nDebug completed!")

if __name__ == "__main__":
    asyncio.run(main())
