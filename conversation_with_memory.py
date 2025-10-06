# -*- coding: utf-8 -*-
"""
Conversation with Memory System

Hệ thống trò chuyện với memory từ knowledge graph
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_URL = "http://localhost:8000"

class ConversationMemory:
    """Class quản lý conversation với memory"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.conversation_history = []
        self.context_cache = {}
    
    async def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Tìm kiếm thông tin liên quan trong knowledge graph
        
        Args:
            query: Câu hỏi hoặc từ khóa tìm kiếm
            limit: Số lượng kết quả tối đa
            
        Returns:
            List các kết quả tìm kiếm
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/search",
                    json={
                        "query": query,
                        "group_id": self.project_id,
                        "limit": limit
                    }
                )
                
                if response.status_code == 200:
                    results = response.json()
                    return results.get('results', [])
                else:
                    print(f"Search error: {response.status_code}")
                    return []
        
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def get_conversation_context(self, current_message: str) -> str:
        """
        Lấy context từ memory dựa trên message hiện tại
        
        Args:
            current_message: Message hiện tại của user
            
        Returns:
            Context string để feed vào AI
        """
        # Tìm kiếm thông tin liên quan
        search_results = await self.search_memory(current_message, limit=3)
        
        context_parts = []
        
        if search_results:
            context_parts.append("=== RELEVANT MEMORY ===")
            for i, result in enumerate(search_results, 1):
                name = result.get('name', 'Unknown')
                summary = result.get('summary', '')
                score = result.get('score', 0)
                
                context_parts.append(f"{i}. {name} (relevance: {score:.2f})")
                if summary:
                    # Clean summary để tránh lỗi Unicode
                    summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                    if summary_clean:
                        context_parts.append(f"   {summary_clean}")
            context_parts.append("")
        
        # Thêm conversation history gần đây
        if self.conversation_history:
            context_parts.append("=== RECENT CONVERSATION ===")
            for msg in self.conversation_history[-3:]:  # 3 messages gần nhất
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                context_parts.append(f"{role}: {content}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    async def save_conversation_turn(self, user_message: str, assistant_response: str):
        """
        Lưu một lượt conversation vào memory
        
        Args:
            user_message: Message của user
            assistant_response: Response của assistant
        """
        # Thêm vào conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        self.conversation_history.append({
            "role": "assistant", 
            "content": assistant_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Tạo episode từ conversation turn
        episode_data = {
            "name": f"Conversation Turn {len(self.conversation_history)//2}",
            "text": f"user: {user_message}\n\nassistant: {assistant_response}",
            "source_description": "conversation_memory",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=episode_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ Saved conversation turn: {result.get('message', 'OK')}")
                else:
                    print(f"✗ Failed to save conversation: {response.status_code}")
        
        except Exception as e:
            print(f"✗ Error saving conversation: {e}")
    
    async def get_entity_info(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin chi tiết về một entity
        
        Args:
            entity_name: Tên entity cần tìm
            
        Returns:
            Thông tin entity hoặc None
        """
        # Tìm kiếm entity cụ thể
        search_results = await self.search_memory(entity_name, limit=1)
        
        if search_results:
            return search_results[0]
        return None
    
    async def update_entity_info(self, entity_name: str, new_info: str):
        """
        Cập nhật thông tin cho entity
        
        Args:
            entity_name: Tên entity
            new_info: Thông tin mới
        """
        # Tạo episode với thông tin cập nhật
        update_data = {
            "name": f"Update: {entity_name}",
            "text": f"Updated information about {entity_name}: {new_info}",
            "source_description": "entity_update",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=update_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Updated entity: {entity_name}")
                else:
                    print(f"✗ Failed to update entity: {response.status_code}")
        
        except Exception as e:
            print(f"✗ Error updating entity: {e}")
    
    async def get_conversation_summary(self) -> str:
        """
        Lấy tóm tắt conversation hiện tại
        
        Returns:
            Summary string
        """
        if not self.conversation_history:
            return "No conversation history"
        
        # Tìm kiếm summary trong memory
        summary_results = await self.search_memory("conversation summary", limit=3)
        
        summary_parts = []
        summary_parts.append("=== CONVERSATION SUMMARY ===")
        summary_parts.append(f"Total turns: {len(self.conversation_history)//2}")
        summary_parts.append(f"Project: {self.project_id}")
        summary_parts.append("")
        
        if summary_results:
            summary_parts.append("Key topics discussed:")
            for result in summary_results:
                name = result.get('name', 'Unknown')
                summary_parts.append(f"- {name}")
        
        return "\n".join(summary_parts)

async def demo_conversation_with_memory():
    """Demo conversation với memory"""
    
    print("Conversation with Memory Demo")
    print("=" * 50)
    
    # Khởi tạo conversation memory
    memory = ConversationMemory("demo_conversation")
    
    # Demo conversation
    conversations = [
        {
            "user": "What do you know about authentication systems?",
            "assistant": "Based on our previous discussions, I know about JWT authentication, password hashing with bcrypt, and FastAPI middleware implementation. Would you like me to elaborate on any specific aspect?"
        },
        {
            "user": "Can you help me implement rate limiting?",
            "assistant": "I can help you implement rate limiting! From our memory, I see we've discussed Redis-based sliding window rate limiting for FastAPI. Let me provide you with the implementation details."
        },
        {
            "user": "What was the bug we fixed earlier?",
            "assistant": "I remember we fixed a critical login bug where users were getting locked out permanently after 5 failed attempts. The issue was that the rate limiter used Redis with no TTL, so failed attempts never expired. We added a 15-minute TTL to fix this."
        }
    ]
    
    for i, conv in enumerate(conversations, 1):
        print(f"\n--- Conversation Turn {i} ---")
        
        user_msg = conv["user"]
        assistant_msg = conv["assistant"]
        
        print(f"User: {user_msg}")
        
        # Lấy context từ memory
        context = await memory.get_conversation_context(user_msg)
        if context:
            print(f"\nContext from memory:")
            print(context)
        
        print(f"\nAssistant: {assistant_msg}")
        
        # Lưu conversation turn
        await memory.save_conversation_turn(user_msg, assistant_msg)
        
        # Đợi một chút để Graphiti xử lý
        await asyncio.sleep(2)
    
    # Hiển thị summary
    print("\n" + "=" * 50)
    summary = await memory.get_conversation_summary()
    print(summary)

async def demo_entity_operations():
    """Demo các thao tác với entities"""
    
    print("\nEntity Operations Demo")
    print("=" * 50)
    
    memory = ConversationMemory("demo_entities")
    
    # Tìm kiếm entity
    print("Searching for 'authentication'...")
    results = await memory.search_memory("authentication", limit=3)
    
    if results:
        print("Found entities:")
        for i, result in enumerate(results, 1):
            name = result.get('name', 'Unknown')
            score = result.get('score', 0)
            print(f"  {i}. {name} (score: {score:.2f})")
    
    # Lấy thông tin entity cụ thể
    print("\nGetting info about 'JWT'...")
    jwt_info = await memory.get_entity_info("JWT")
    if jwt_info:
        print(f"JWT info: {jwt_info.get('summary', 'No summary')[:100]}...")
    
    # Cập nhật thông tin
    print("\nUpdating entity info...")
    await memory.update_entity_info("authentication", "Added new security features including 2FA support and session management improvements")

async def main():
    """Main function"""
    print("Conversation with Memory System")
    print("=" * 60)
    
    # Demo conversation
    await demo_conversation_with_memory()
    
    # Demo entity operations
    await demo_entity_operations()
    
    print("\n" + "=" * 60)
    print("Demo completed!")

if __name__ == "__main__":
    asyncio.run(main())
