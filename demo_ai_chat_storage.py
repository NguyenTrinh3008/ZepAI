# -*- coding: utf-8 -*-
"""
Demo: AI Chat với Short Term Memory Storage

Mô phỏng việc chat với AI và tự động lưu vào short_term.json
"""

import asyncio
import httpx
import json
from datetime import datetime
import hashlib
import uuid

BASE_URL = "http://localhost:8000"
PROJECT_ID = "demo_ai_chat"

def create_chat_payload(user_message: str, assistant_message: str, conversation_id: str):
    """Tạo payload cho AI chat conversation"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return {
        "request_id": f"chat_{conversation_id}",
        "project_id": PROJECT_ID,
        "timestamp": timestamp,
        "chat_meta": {
            "chat_id": f"chat_{conversation_id}",
            "base_chat_id": f"chat_{conversation_id}",
            "request_attempt_id": "attempt_001",
            "chat_mode": "AGENT"
        },
        "messages": [
            {
                "sequence": 0,
                "role": "user",
                "content": user_message,
                "timestamp": timestamp,
                "total_tokens": len(user_message.split()),
                "metadata": {}
            },
            {
                "sequence": 1,
                "role": "assistant",
                "content": assistant_message,
                "timestamp": timestamp,
                "total_tokens": len(assistant_message.split()) * 2,
                "metadata": {}
            }
        ],
        "context_files": [],
        "tool_calls": [],
        "checkpoints": [],
        "code_changes": [],
        "model_response": {
            "model": "gpt-4-turbo",
            "finish_reason": "stop"
        },
        "group_id": PROJECT_ID
    }

async def simulate_ai_chat():
    """Mô phỏng cuộc trò chuyện với AI"""
    print("AI Chat Demo - Short Term Memory Storage")
    print("=" * 60)
    print("Mo phong cuoc tro chuyen voi AI va luu vao short_term.json")
    print()
    
    # Danh sách các cuộc trò chuyện mẫu
    conversations = [
        {
            "id": "001",
            "user": "Xin chao! Ban co the giup toi tao mot API REST voi FastAPI khong?",
            "assistant": "Chao ban! Toi se giup ban tao API REST voi FastAPI. Day la framework Python rat manh me de xay dung API. Toi se huong dan ban tung buoc."
        },
        {
            "id": "002", 
            "user": "Toi muon tao endpoint de quan ly users, co the them, sua, xoa user khong?",
            "assistant": "Duoc roi! Toi se giup ban tao CRUD endpoints cho user management. Chung ta se can: GET /users, POST /users, PUT /users/{id}, DELETE /users/{id}. Toi se tao model User va cac endpoint tuong ung."
        },
        {
            "id": "003",
            "user": "Lam sao de them authentication va authorization cho API nay?",
            "assistant": "Tuyet voi! De bao mat API, chung ta se su dung JWT tokens. Toi se tao middleware authentication, login endpoint, va protect cac routes can thiet. Cung se co role-based access control."
        },
        {
            "id": "004",
            "user": "Toi can them database PostgreSQL va ORM SQLAlchemy, ban co the giup khong?",
            "assistant": "Chac chan! Toi se tich hop PostgreSQL voi SQLAlchemy ORM. Se tao database models, connection pool, migrations, va cap nhat tat ca endpoints de su dung database thay vi in-memory storage."
        },
        {
            "id": "005",
            "user": "Co the them testing voi pytest va documentation voi Swagger khong?",
            "assistant": "Tuyet voi! Toi se them comprehensive testing suite voi pytest, bao gom unit tests, integration tests, va API tests. Cung se cau hinh Swagger/OpenAPI documentation tu dong cho tat ca endpoints."
        }
    ]
    
    timeout = httpx.Timeout(30.0, read=30.0, write=10.0, connect=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print("Bat dau mo phong cuoc tro chuyen...")
            print()
            
            for i, conv in enumerate(conversations, 1):
                print(f"Cuoc tro chuyen {i}:")
                print(f"   User: {conv['user']}")
                print(f"   AI: {conv['assistant']}")
                
                # Tạo payload
                payload = create_chat_payload(
                    conv['user'], 
                    conv['assistant'], 
                    conv['id']
                )
                
                # Gửi đến API
                try:
                    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    print(f"   SUCCESS: Da luu vao he thong!")
                    print(f"      - Conversation ID: {result.get('conversation_id', 'N/A')}")
                    print(f"      - Messages: {result.get('metadata', {}).get('message_count', 0)}")
                    
                    # Kiem tra Short Term Memory
                    stm_info = result.get('short_term_memory', {})
                    print(f"      - STM Messages: {stm_info.get('messages_saved', 0)}")
                    for stm_result in stm_info.get('results', []):
                        if stm_result.get('stm_id'):
                            print(f"        * {stm_result['role']}: {stm_result['stm_id'][:8]}...")
                    
                    print()
                    
                except Exception as e:
                    print(f"   ERROR: Loi: {e}")
                    print()
            
            # Test search trong Short Term Memory
            print("Test tim kiem trong Short Term Memory...")
            
            search_queries = [
                "FastAPI REST API",
                "authentication JWT",
                "PostgreSQL database",
                "testing pytest"
            ]
            
            for query in search_queries:
                try:
                    response = await client.post(f"{BASE_URL}/short-term/search", json={
                        "query": query,
                        "project_id": PROJECT_ID,
                        "limit": 3
                    })
                    response.raise_for_status()
                    search_result = response.json()
                    
                    print(f"   Query: '{query}'")
                    print(f"      Ket qua: {len(search_result.get('results', []))} messages")
                    
                    for j, result in enumerate(search_result.get('results', [])[:2], 1):
                        print(f"        {j}. {result.get('role', 'Unknown')}: {result.get('content', '')[:50]}...")
                    
                    print()
                    
                except Exception as e:
                    print(f"   ERROR: Loi search '{query}': {e}")
                    print()
            
            # Kiem tra thong ke
            print("Thong ke Short Term Memory...")
            
            try:
                response = await client.get(f"{BASE_URL}/short-term/stats/{PROJECT_ID}")
                response.raise_for_status()
                stats = response.json()
                
                print(f"   Total messages: {stats.get('total_messages', 0)}")
                print(f"   By role: {stats.get('by_role', {})}")
                print(f"   Recent: {len(stats.get('recent_messages', []))} messages")
                print()
                
            except Exception as e:
                print(f"   ERROR: Loi stats: {e}")
                print()
            
            print("Demo hoan thanh!")
            print("Kiem tra file short_term.json de xem du lieu da luu")
            print("Co the search lai bang API /short-term/search")
            
            return True
            
    except httpx.ConnectError:
        print("ERROR: Khong the ket noi den API server!")
        print("   Hay chay: python -m uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"ERROR: Loi: {e}")
        return False

async def main():
    """Main function"""
    success = await simulate_ai_chat()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
