# -*- coding: utf-8 -*-
"""
Memory Update System

Hệ thống cập nhật thông tin trong knowledge graph
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_URL = "http://localhost:8000"

class MemoryUpdater:
    """Class cập nhật thông tin trong memory"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    async def add_new_knowledge(self, topic: str, content: str, source: str = "manual") -> bool:
        """
        Thêm kiến thức mới
        
        Args:
            topic: Chủ đề
            content: Nội dung
            source: Nguồn thông tin
            
        Returns:
            True nếu thành công
        """
        episode_data = {
            "name": f"New Knowledge: {topic}",
            "text": f"Topic: {topic}\nContent: {content}\nSource: {source}",
            "source_description": "new_knowledge",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=episode_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Added new knowledge: {topic}")
                    return True
                else:
                    print(f"✗ Failed to add knowledge: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error adding knowledge: {e}")
            return False
    
    async def update_existing_entity(self, entity_name: str, new_info: str) -> bool:
        """
        Cập nhật entity hiện có
        
        Args:
            entity_name: Tên entity
            new_info: Thông tin mới
            
        Returns:
            True nếu thành công
        """
        update_data = {
            "name": f"Update: {entity_name}",
            "text": f"Updated information about {entity_name}:\n{new_info}",
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
                    return True
                else:
                    print(f"✗ Failed to update entity: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error updating entity: {e}")
            return False
    
    async def add_code_solution(self, problem: str, solution: str, language: str = "python") -> bool:
        """
        Thêm code solution
        
        Args:
            problem: Vấn đề
            solution: Giải pháp code
            language: Ngôn ngữ lập trình
            
        Returns:
            True nếu thành công
        """
        code_data = {
            "name": f"Code Solution: {problem[:50]}...",
            "text": f"Problem: {problem}\n\nSolution ({language}):\n```{language}\n{solution}\n```",
            "source_description": "code_solution",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=code_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Added code solution: {problem[:30]}...")
                    return True
                else:
                    print(f"✗ Failed to add code solution: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error adding code solution: {e}")
            return False
    
    async def add_bug_fix(self, bug_description: str, fix_description: str, code_changes: str = "") -> bool:
        """
        Thêm bug fix
        
        Args:
            bug_description: Mô tả bug
            fix_description: Mô tả fix
            code_changes: Thay đổi code
            
        Returns:
            True nếu thành công
        """
        bug_data = {
            "name": f"Bug Fix: {bug_description[:50]}...",
            "text": f"Bug: {bug_description}\n\nFix: {fix_description}\n\nCode Changes:\n{code_changes}",
            "source_description": "bug_fix",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=bug_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Added bug fix: {bug_description[:30]}...")
                    return True
                else:
                    print(f"✗ Failed to add bug fix: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error adding bug fix: {e}")
            return False
    
    async def add_learning_note(self, topic: str, notes: str, difficulty: str = "intermediate") -> bool:
        """
        Thêm learning note
        
        Args:
            topic: Chủ đề học
            notes: Ghi chú
            difficulty: Độ khó
            
        Returns:
            True nếu thành công
        """
        learning_data = {
            "name": f"Learning Note: {topic}",
            "text": f"Topic: {topic}\nDifficulty: {difficulty}\n\nNotes:\n{notes}",
            "source_description": "learning_note",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=learning_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Added learning note: {topic}")
                    return True
                else:
                    print(f"✗ Failed to add learning note: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error adding learning note: {e}")
            return False
    
    async def add_conversation_summary(self, conversation_id: str, summary: str, key_points: List[str]) -> bool:
        """
        Thêm tóm tắt conversation
        
        Args:
            conversation_id: ID conversation
            summary: Tóm tắt
            key_points: Các điểm chính
            
        Returns:
            True nếu thành công
        """
        summary_data = {
            "name": f"Conversation Summary: {conversation_id}",
            "text": f"Conversation ID: {conversation_id}\n\nSummary:\n{summary}\n\nKey Points:\n" + "\n".join(f"- {point}" for point in key_points),
            "source_description": "conversation_summary",
            "group_id": self.project_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BASE_URL}/ingest/text",
                    json=summary_data
                )
                
                if response.status_code == 200:
                    print(f"✓ Added conversation summary: {conversation_id}")
                    return True
                else:
                    print(f"✗ Failed to add conversation summary: {response.status_code}")
                    return False
        
        except Exception as e:
            print(f"✗ Error adding conversation summary: {e}")
            return False
    
    async def bulk_update_from_json(self, json_file_path: str) -> Dict[str, int]:
        """
        Cập nhật hàng loạt từ JSON file
        
        Args:
            json_file_path: Đường dẫn file JSON
            
        Returns:
            Dict với kết quả cập nhật
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results = {
                "total_items": 0,
                "successful": 0,
                "failed": 0,
                "errors": []
            }
            
            # Xử lý từng item
            for item in data:
                results["total_items"] += 1
                
                try:
                    # Tạo episode data
                    episode_data = {
                        "name": item.get("name", "Bulk Update Item"),
                        "text": item.get("content", str(item)),
                        "source_description": "bulk_update",
                        "group_id": self.project_id
                    }
                    
                    # Upload
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{BASE_URL}/ingest/text",
                            json=episode_data
                        )
                        
                        if response.status_code == 200:
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"Item {results['total_items']}: {response.status_code}")
                
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Item {results['total_items']}: {str(e)}")
            
            return results
        
        except Exception as e:
            return {
                "total_items": 0,
                "successful": 0,
                "failed": 1,
                "errors": [f"File error: {str(e)}"]
            }

async def demo_memory_update():
    """Demo memory update"""
    
    print("Memory Update Demo")
    print("=" * 50)
    
    updater = MemoryUpdater("demo_update")
    
    # Demo các loại cập nhật
    print("1. Adding new knowledge...")
    await updater.add_new_knowledge(
        "Machine Learning",
        "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
        "educational"
    )
    
    print("\n2. Adding code solution...")
    await updater.add_code_solution(
        "How to implement JWT authentication in FastAPI",
        """
from fastapi import FastAPI, Depends, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
        """,
        "python"
    )
    
    print("\n3. Adding bug fix...")
    await updater.add_bug_fix(
        "Users getting locked out after failed login attempts",
        "Added TTL to Redis rate limiter to reset failed attempts after 15 minutes",
        "redis.setex(f'login_attempts:{user_id}', 900, attempts)"
    )
    
    print("\n4. Adding learning note...")
    await updater.add_learning_note(
        "Database Optimization",
        "Use indexes on frequently queried columns. Consider query optimization and connection pooling.",
        "advanced"
    )
    
    print("\n5. Adding conversation summary...")
    await updater.add_conversation_summary(
        "conv_001",
        "Discussed authentication implementation and security best practices",
        [
            "JWT tokens for stateless authentication",
            "Password hashing with bcrypt",
            "Rate limiting for security",
            "Session management strategies"
        ]
    )

async def main():
    """Main function"""
    print("Memory Update System")
    print("=" * 60)
    
    await demo_memory_update()
    
    print("\n" + "=" * 60)
    print("Demo completed!")

if __name__ == "__main__":
    asyncio.run(main())
