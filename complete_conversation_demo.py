# -*- coding: utf-8 -*-
"""
Complete Conversation Demo

Demo đầy đủ về conversation với memory, update và retrieval
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any

BASE_URL = "http://localhost:8000"

class CompleteConversationSystem:
    """Hệ thống conversation hoàn chỉnh với memory"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.conversation_history = []
        self.context_cache = {}
    
    async def start_conversation(self, user_message: str) -> str:
        """
        Bắt đầu hoặc tiếp tục conversation
        
        Args:
            user_message: Message của user
            
        Returns:
            Response của assistant
        """
        print(f"\n👤 User: {user_message}")
        
        # 1. Tìm kiếm context từ memory
        context = await self._get_context_from_memory(user_message)
        
        # 2. Tạo response dựa trên context
        response = await self._generate_response(user_message, context)
        
        # 3. Lưu conversation turn
        await self._save_conversation_turn(user_message, response)
        
        # 4. Cập nhật context cache
        self._update_context_cache(user_message, response)
        
        print(f"🤖 Assistant: {response}")
        return response
    
    async def _get_context_from_memory(self, message: str) -> str:
        """Lấy context từ memory"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/search",
                    json={
                        "query": message,
                        "group_id": self.project_id,
                        "limit": 3
                    }
                )
                
                if response.status_code == 200:
                    results = response.json().get('results', [])
                    
                    if results:
                        context_parts = ["=== RELEVANT MEMORY ==="]
                        for i, result in enumerate(results, 1):
                            name = result.get('name', 'Unknown')
                            summary = result.get('summary', '')
                            score = result.get('score', 0)
                            
                            context_parts.append(f"{i}. {name} (relevance: {score:.2f})")
                            if summary:
                                summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                                if summary_clean:
                                    context_parts.append(f"   {summary_clean[:100]}...")
                        
                        return "\n".join(context_parts)
                
                return "No relevant memory found"
        
        except Exception as e:
            print(f"Error getting context: {e}")
            return "Error retrieving context"
    
    async def _generate_response(self, user_message: str, context: str) -> str:
        """Tạo response dựa trên message và context"""
        
        # Simulate AI response generation
        # Trong thực tế, đây sẽ gọi đến LLM API
        
        if "authentication" in user_message.lower():
            if context and "JWT" in context:
                return "Based on our previous discussion about JWT authentication, I can help you implement it. We've covered JWT token generation, password hashing with bcrypt, and FastAPI middleware. What specific aspect would you like to work on?"
            else:
                return "I can help you with authentication systems. We've discussed JWT tokens, password hashing, and FastAPI implementation. Would you like me to review the implementation details?"
        
        elif "bug" in user_message.lower() or "error" in user_message.lower():
            if context and "rate limiter" in context:
                return "I remember we fixed a rate limiter bug where users were getting locked out permanently. The issue was missing TTL in Redis. We added a 15-minute expiration to fix this. Are you experiencing a similar issue?"
            else:
                return "I can help you debug issues. We've worked on various bugs including rate limiting, authentication, and database problems. What specific error are you encountering?"
        
        elif "code" in user_message.lower() or "implement" in user_message.lower():
            return "I can help you implement code solutions. Based on our previous work, I have examples of JWT authentication, rate limiting, database operations, and API development. What would you like to implement?"
        
        elif "learn" in user_message.lower() or "study" in user_message.lower():
            return "I can help you learn new concepts. We've covered authentication systems, database optimization, API development, and security best practices. What topic would you like to explore?"
        
        else:
            return "I'm here to help! Based on our previous conversations, I can assist with authentication, bug fixes, code implementation, and learning new technologies. What would you like to work on?"
    
    async def _save_conversation_turn(self, user_message: str, assistant_response: str):
        """Lưu conversation turn vào memory"""
        
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
                    print("✓ Saved to memory")
                else:
                    print(f"✗ Failed to save: {response.status_code}")
        
        except Exception as e:
            print(f"✗ Error saving: {e}")
    
    def _update_context_cache(self, user_message: str, assistant_response: str):
        """Cập nhật context cache"""
        # Extract key topics from conversation
        topics = []
        if "authentication" in user_message.lower():
            topics.append("authentication")
        if "bug" in user_message.lower():
            topics.append("bug_fix")
        if "code" in user_message.lower():
            topics.append("code_implementation")
        
        for topic in topics:
            if topic not in self.context_cache:
                self.context_cache[topic] = []
            self.context_cache[topic].append({
                "user": user_message,
                "assistant": assistant_response,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def get_conversation_summary(self) -> str:
        """Lấy tóm tắt conversation"""
        if not self.conversation_history:
            return "No conversation history"
        
        summary = f"""
=== CONVERSATION SUMMARY ===
Project: {self.project_id}
Total Turns: {len(self.conversation_history)//2}
Last Activity: {self.conversation_history[-1]['timestamp'] if self.conversation_history else 'None'}

Topics Discussed:
"""
        
        for topic, conversations in self.context_cache.items():
            summary += f"- {topic}: {len(conversations)} discussions\n"
        
        return summary
    
    async def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """Tìm kiếm trong memory"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/search",
                    json={
                        "query": query,
                        "group_id": self.project_id,
                        "limit": 5
                    }
                )
                
                if response.status_code == 200:
                    return response.json().get('results', [])
                else:
                    return []
        
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def update_knowledge(self, topic: str, new_info: str):
        """Cập nhật kiến thức"""
        update_data = {
            "name": f"Knowledge Update: {topic}",
            "text": f"Updated information about {topic}:\n{new_info}",
            "source_description": "knowledge_update",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=update_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Updated knowledge: {topic}")
                else:
                    print(f"✗ Failed to update: {response.status_code}")
        
        except Exception as e:
            print(f"✗ Error updating: {e}")

async def demo_complete_conversation():
    """Demo conversation hoàn chỉnh"""
    
    print("Complete Conversation System Demo")
    print("=" * 60)
    
    # Khởi tạo hệ thống
    system = CompleteConversationSystem("demo_complete")
    
    # Demo conversation
    conversations = [
        "I need help with authentication implementation",
        "What was the bug we fixed earlier?",
        "Can you show me the code for JWT tokens?",
        "I want to learn about database optimization",
        "There's a new error in my rate limiter",
        "Can you help me implement 2FA?",
        "What topics have we covered so far?"
    ]
    
    for i, message in enumerate(conversations, 1):
        print(f"\n--- Turn {i} ---")
        await system.start_conversation(message)
        
        # Đợi một chút để Graphiti xử lý
        await asyncio.sleep(2)
    
    # Hiển thị summary
    print("\n" + "=" * 60)
    summary = await system.get_conversation_summary()
    print(summary)
    
    # Demo search
    print("\n--- Memory Search Demo ---")
    search_results = await system.search_memory("authentication")
    print(f"Found {len(search_results)} authentication-related items")
    
    # Demo update
    print("\n--- Knowledge Update Demo ---")
    await system.update_knowledge(
        "authentication",
        "Added new information about OAuth 2.0 implementation and security best practices for token management."
    )

async def main():
    """Main function"""
    print("Complete Conversation with Memory System")
    print("=" * 70)
    
    await demo_complete_conversation()
    
    print("\n" + "=" * 70)
    print("Demo completed!")
    print("\nKey Features Demonstrated:")
    print("✓ Conversation with memory retrieval")
    print("✓ Context-aware responses")
    print("✓ Automatic memory saving")
    print("✓ Knowledge updates")
    print("✓ Memory search")
    print("✓ Conversation summarization")

if __name__ == "__main__":
    asyncio.run(main())
