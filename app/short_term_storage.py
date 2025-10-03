# app/short_term_storage.py
"""
Module lưu trữ và quản lý Short Term Memory

Chức năng:
1. Lưu trữ messages vào JSON file
2. Tìm kiếm messages theo similarity
3. Quản lý TTL (Time To Live)
4. Cleanup expired messages
"""

import json
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.schemas import ShortTermMemory, ShortTermMemoryRequest, ShortTermMemorySearchRequest
from app.short_term_extractor import get_extractor

logger = logging.getLogger(__name__)


class ShortTermMemoryStorage:
    """
    Quản lý lưu trữ Short Term Memory
    """
    
    def __init__(self, storage_file: str = "short_term.json"):
        self.storage_file = Path(storage_file)
        self.extractor = get_extractor()
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Cache để tăng tốc độ tìm kiếm
        self._memory_cache: Dict[str, ShortTermMemory] = {}
        self._cache_loaded = False
        
        # Load existing data if file exists
        self._load_json_data()
        
    async def save_message(self, request: ShortTermMemoryRequest) -> str:
        """
        Lưu message vào short term memory
        
        Args:
            request: Thông tin message cần lưu
            
        Returns:
            ID của message đã lưu
        """
        try:
            # Tạo unique ID
            message_id = str(uuid.uuid4())
            
            # Trích xuất thông tin bằng LLM
            extracted_info = await self.extractor.extract_message_info(
                content=request.content,
                role=request.role,
                project_id=request.project_id,
                conversation_id=request.conversation_id
            )
            
            # Merge với thông tin từ request
            metadata = {
                "conversation_id": request.conversation_id,
                "file_path": request.file_path or extracted_info.get("file_path"),
                "function_name": request.function_name or extracted_info.get("function_name"),
                "line_start": request.line_start or extracted_info.get("line_start"),
                "line_end": request.line_end or extracted_info.get("line_end"),
                "code_changes": request.code_changes or extracted_info.get("code_changes"),
                "lines_added": request.lines_added or extracted_info.get("lines_added"),
                "lines_removed": request.lines_removed or extracted_info.get("lines_removed"),
                "diff_summary": request.diff_summary or extracted_info.get("diff_summary"),
                "intent": request.intent or extracted_info.get("intent"),
                "keywords": request.keywords or extracted_info.get("keywords", []),
                "embedding": extracted_info.get("embedding", []),
                "ttl": request.ttl or extracted_info.get("ttl", 3600)
            }
            
            # Tạo ShortTermMemory object
            memory = ShortTermMemory(
                id=message_id,
                role=request.role,
                content=request.content,
                timestamp=datetime.utcnow().isoformat(),
                project_id=request.project_id,
                metadata=metadata
            )
            
            # Lưu vào file JSON
            await self._save_to_json_file(memory)
            
            # Update cache
            self._memory_cache[message_id] = memory
            
            logger.info(f"Saved message {message_id} to short term memory")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
    
    async def search_messages(self, search_request: ShortTermMemorySearchRequest) -> List[Dict[str, Any]]:
        """
        Tìm kiếm messages trong short term memory
        
        Args:
            search_request: Thông tin tìm kiếm
            
        Returns:
            Danh sách messages phù hợp
        """
        try:
            # Load cache nếu chưa load
            if not self._cache_loaded:
                await self._load_cache()
            
            # Filter messages theo project_id
            project_messages = [
                memory for memory in self._memory_cache.values()
                if memory.project_id == search_request.project_id
            ]
            
            # Filter theo conversation_id nếu có
            if search_request.conversation_id:
                project_messages = [
                    memory for memory in project_messages
                    if memory.metadata.conversation_id == search_request.conversation_id
                ]
            
            # Filter theo role nếu có
            if search_request.role:
                project_messages = [
                    memory for memory in project_messages
                    if memory.role == search_request.role
                ]
            
            # Tạo embedding cho query
            query_embedding = await self.extractor._create_embedding(search_request.query)
            
            # Tính similarity với tất cả messages
            similarities = []
            for memory in project_messages:
                if memory.metadata.embedding:
                    similarity = self.extractor.calculate_similarity(
                        query_embedding, 
                        memory.metadata.embedding
                    )
                    similarities.append((memory, similarity))
            
            # Sắp xếp theo similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Trả về kết quả
            results = []
            limit = search_request.limit or 10
            
            for memory, similarity in similarities[:limit]:
                results.append({
                    "id": memory.id,
                    "role": memory.role,
                    "content": memory.content,
                    "timestamp": memory.timestamp,
                    "project_id": memory.project_id,
                    "similarity": similarity,
                    "metadata": {
                        "conversation_id": memory.metadata.conversation_id,
                        "file_path": memory.metadata.file_path,
                        "function_name": memory.metadata.function_name,
                        "line_start": memory.metadata.line_start,
                        "line_end": memory.metadata.line_end,
                        "intent": memory.metadata.intent,
                        "keywords": memory.metadata.keywords,
                        "ttl": memory.metadata.ttl
                    }
                })
            
            logger.info(f"Found {len(results)} messages for query: {search_request.query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []
    
    async def get_message(self, message_id: str) -> Optional[ShortTermMemory]:
        """Lấy message theo ID"""
        try:
            # Load cache nếu chưa load
            if not self._cache_loaded:
                await self._load_cache()
            
            return self._memory_cache.get(message_id)
            
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    async def delete_message(self, message_id: str) -> bool:
        """Xóa message theo ID"""
        try:
            # Xóa khỏi cache
            if message_id in self._memory_cache:
                del self._memory_cache[message_id]
            
            # Xóa khỏi file JSON
            success = await self._remove_from_json_file(message_id)
            if success:
                logger.info(f"Deleted message {message_id}")
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
            return False
    
    async def cleanup_expired(self) -> int:
        """Xóa các messages đã hết hạn"""
        try:
            if not self._cache_loaded:
                await self._load_cache()
            
            current_time = datetime.utcnow()
            expired_ids = []
            
            for memory in self._memory_cache.values():
                # Tính thời gian hết hạn
                created_time = datetime.fromisoformat(memory.timestamp)
                ttl_seconds = memory.metadata.ttl or 3600
                expires_at = created_time + timedelta(seconds=ttl_seconds)
                
                if current_time > expires_at:
                    expired_ids.append(memory.id)
            
            # Xóa expired messages
            deleted_count = 0
            for message_id in expired_ids:
                if await self.delete_message(message_id):
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} expired messages")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired messages: {e}")
            return 0
    
    async def get_stats(self, project_id: str) -> Dict[str, Any]:
        """Lấy thống kê cho project"""
        try:
            if not self._cache_loaded:
                await self._load_cache()
            
            project_messages = [
                memory for memory in self._memory_cache.values()
                if memory.project_id == project_id
            ]
            
            # Thống kê theo role
            role_stats = {}
            for memory in project_messages:
                role = memory.role
                role_stats[role] = role_stats.get(role, 0) + 1
            
            # Thống kê theo intent
            intent_stats = {}
            for memory in project_messages:
                intent = memory.metadata.intent or "unknown"
                intent_stats[intent] = intent_stats.get(intent, 0) + 1
            
            # Thống kê theo conversation
            conversation_stats = {}
            for memory in project_messages:
                conv_id = memory.metadata.conversation_id
                conversation_stats[conv_id] = conversation_stats.get(conv_id, 0) + 1
            
            return {
                "total_messages": len(project_messages),
                "by_role": role_stats,
                "by_intent": intent_stats,
                "by_conversation": conversation_stats,
                "cache_loaded": self._cache_loaded
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def _save_to_json_file(self, memory: ShortTermMemory):
        """Lưu memory vào file JSON"""
        try:
            # Load existing data
            data = self._load_json_data()
            
            # Add new message
            memory_dict = memory.dict()
            data['messages'].append(memory_dict)
            
            # Save to file
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving to JSON file: {e}")
            raise
    
    def _load_json_data(self) -> dict:
        """Load data từ file JSON"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure data has messages array
                    if 'messages' not in data:
                        data['messages'] = []
                    return data
            except Exception as e:
                logger.warning(f"Error loading JSON file: {e}")
        
        # Return empty structure if file doesn't exist or error
        return {
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0"
        }
    
    async def _remove_from_json_file(self, message_id: str) -> bool:
        """Xóa message khỏi file JSON"""
        try:
            # Load existing data
            data = self._load_json_data()
            
            # Remove message
            original_count = len(data['messages'])
            data['messages'] = [msg for msg in data['messages'] if msg.get('id') != message_id]
            
            # Check if message was found and removed
            if len(data['messages']) < original_count:
                # Save updated data
                with open(self.storage_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error removing from JSON file: {e}")
            return False
    
    async def _load_cache(self):
        """Load tất cả messages vào cache"""
        try:
            if self._cache_loaded:
                return
            
            self._memory_cache.clear()
            
            # Load từ file JSON
            data = self._load_json_data()
            messages_data = data.get('messages', [])
            
            for message_data in messages_data:
                try:
                    # Convert to ShortTermMemory object
                    memory = ShortTermMemory(**message_data)
                    self._memory_cache[memory.id] = memory
                except Exception as e:
                    logger.warning(f"Error loading message: {e}")
                    continue
            
            self._cache_loaded = True
            logger.info(f"Loaded {len(self._memory_cache)} messages into cache")
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            self._cache_loaded = False
    


# Global instance
_storage_instance = None

def get_storage() -> ShortTermMemoryStorage:
    """Get global storage instance"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ShortTermMemoryStorage(storage_file="short_term.json")
    return _storage_instance


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_storage():
        storage = ShortTermMemoryStorage()
        
        # Test save message
        request = ShortTermMemoryRequest(
            role="user",
            content="Tôi muốn thêm chức năng đăng nhập vào file auth.py",
            project_id="test_project",
            conversation_id="conv_001",
            file_path="auth.py",
            function_name="login_user"
        )
        
        message_id = await storage.save_message(request)
        print(f"Saved message: {message_id}")
        
        # Test search
        search_request = ShortTermMemorySearchRequest(
            query="đăng nhập",
            project_id="test_project"
        )
        
        results = await storage.search_messages(search_request)
        print(f"Found {len(results)} results")
        for result in results:
            print(f"- {result['role']}: {result['content'][:50]}...")
        
        # Test stats
        stats = await storage.get_stats("test_project")
        print(f"Stats: {stats}")
    
    asyncio.run(test_storage())
