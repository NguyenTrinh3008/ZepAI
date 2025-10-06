# -*- coding: utf-8 -*-
"""
Memory Retrieval System

Hệ thống truy xuất thông tin từ knowledge graph
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

class MemoryRetriever:
    """Class truy xuất thông tin từ memory"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    async def search_by_topic(self, topic: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Tìm kiếm theo chủ đề
        
        Args:
            topic: Chủ đề cần tìm
            limit: Số lượng kết quả
            
        Returns:
            List kết quả tìm kiếm
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/search",
                    json={
                        "query": topic,
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
    
    async def get_recent_conversations(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Lấy conversations gần đây
        
        Args:
            days: Số ngày gần đây
            
        Returns:
            List conversations
        """
        # Tìm kiếm conversations gần đây
        query = f"conversation recent {days} days"
        return await self.search_by_topic(query, limit=10)
    
    async def get_code_examples(self, language: str = "python") -> List[Dict[str, Any]]:
        """
        Lấy code examples
        
        Args:
            language: Ngôn ngữ lập trình
            
        Returns:
            List code examples
        """
        query = f"code example {language} implementation"
        return await self.search_by_topic(query, limit=5)
    
    async def get_bug_fixes(self) -> List[Dict[str, Any]]:
        """
        Lấy thông tin về bug fixes
        
        Returns:
            List bug fixes
        """
        query = "bug fix error solution"
        return await self.search_by_topic(query, limit=5)
    
    async def get_learning_progress(self) -> Dict[str, Any]:
        """
        Lấy tiến độ học tập
        
        Returns:
            Dict chứa thông tin tiến độ
        """
        # Tìm kiếm các chủ đề đã học
        topics = ["authentication", "database", "API", "security", "testing"]
        progress = {}
        
        for topic in topics:
            results = await self.search_by_topic(topic, limit=3)
            progress[topic] = {
                "count": len(results),
                "last_mentioned": results[0].get('created_at', 'Unknown') if results else None,
                "confidence": results[0].get('score', 0) if results else 0
            }
        
        return progress
    
    async def get_related_entities(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        Lấy các entities liên quan
        
        Args:
            entity_name: Tên entity
            
        Returns:
            List entities liên quan
        """
        # Tìm kiếm entities liên quan
        query = f"related to {entity_name}"
        return await self.search_by_topic(query, limit=5)
    
    async def get_conversation_timeline(self) -> List[Dict[str, Any]]:
        """
        Lấy timeline của conversations
        
        Returns:
            List conversations theo thời gian
        """
        # Tìm kiếm conversations theo thời gian
        query = "conversation timeline chronological"
        return await self.search_by_topic(query, limit=20)
    
    async def search_by_intent(self, intent: str) -> List[Dict[str, Any]]:
        """
        Tìm kiếm theo intent
        
        Args:
            intent: Intent cần tìm (code_help, bug_fix, learning, etc.)
            
        Returns:
            List kết quả theo intent
        """
        query = f"intent {intent}"
        return await self.search_by_topic(query, limit=5)
    
    async def get_knowledge_summary(self) -> str:
        """
        Lấy tóm tắt kiến thức
        
        Returns:
            String tóm tắt
        """
        # Lấy thống kê entities
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
                
                if response.status_code == 200:
                    stats = response.json()
                    total_entities = stats.get('total_stats', {}).get('total_entities', 0)
                    unique_groups = stats.get('total_stats', {}).get('unique_groups', 0)
                    
                    summary = f"""
=== KNOWLEDGE SUMMARY ===
Project: {self.project_id}
Total Entities: {total_entities}
Unique Groups: {unique_groups}

Recent Learning Areas:
"""
                    
                    # Lấy các chủ đề gần đây
                    recent_topics = await self.get_recent_conversations(3)
                    for topic in recent_topics[:5]:
                        name = topic.get('name', 'Unknown')
                        summary += f"- {name}\n"
                    
                    return summary
                else:
                    return "Unable to get knowledge summary"
        
        except Exception as e:
            return f"Error getting summary: {e}"

async def demo_memory_retrieval():
    """Demo memory retrieval"""
    
    print("Memory Retrieval Demo")
    print("=" * 50)
    
    retriever = MemoryRetriever("demo_retrieval")
    
    # Demo các loại tìm kiếm
    print("1. Searching by topic...")
    auth_results = await retriever.search_by_topic("authentication", limit=3)
    print(f"Found {len(auth_results)} authentication-related items")
    
    print("\n2. Getting code examples...")
    code_results = await retriever.get_code_examples("python")
    print(f"Found {len(code_results)} Python code examples")
    
    print("\n3. Getting bug fixes...")
    bug_results = await retriever.get_bug_fixes()
    print(f"Found {len(bug_results)} bug fixes")
    
    print("\n4. Getting learning progress...")
    progress = await retriever.get_learning_progress()
    print("Learning Progress:")
    for topic, info in progress.items():
        print(f"  {topic}: {info['count']} items, confidence: {info['confidence']:.2f}")
    
    print("\n5. Getting knowledge summary...")
    summary = await retriever.get_knowledge_summary()
    print(summary)

async def main():
    """Main function"""
    print("Memory Retrieval System")
    print("=" * 60)
    
    await demo_memory_retrieval()
    
    print("\n" + "=" * 60)
    print("Demo completed!")

if __name__ == "__main__":
    asyncio.run(main())
