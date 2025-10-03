# app/short_term_integration.py
"""
Module tích hợp Short Term Memory vào hệ thống chat

Chức năng:
1. Tự động lưu user và assistant messages
2. Tích hợp với UI chat system
3. Quản lý conversation context
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import requests
import json

from app.schemas import ShortTermMemoryRequest
from app.short_term_storage import get_storage

logger = logging.getLogger(__name__)


class ShortTermMemoryIntegration:
    """
    Tích hợp Short Term Memory vào chat system
    """
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.storage = get_storage()
        
    async def save_user_message(self, 
                               content: str, 
                               project_id: str, 
                               conversation_id: str,
                               file_path: Optional[str] = None,
                               function_name: Optional[str] = None,
                               line_start: Optional[int] = None,
                               line_end: Optional[int] = None,
                               code_changes: Optional[Dict[str, Any]] = None,
                               lines_added: Optional[int] = None,
                               lines_removed: Optional[int] = None,
                               diff_summary: Optional[str] = None) -> str:
        """
        Lưu user message vào short term memory
        
        Args:
            content: Nội dung message
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            file_path: Đường dẫn file nếu liên quan đến code
            function_name: Tên function nếu liên quan đến code
            line_start: Số dòng bắt đầu của khoảng code mà AI đã chỉnh sửa
            line_end: Số dòng kết thúc của khoảng code mà AI đã chỉnh sửa
            code_changes: Chi tiết thay đổi code nếu có
            lines_added: Số dòng code được thêm vào
            lines_removed: Số dòng code bị xóa
            diff_summary: Tóm tắt thay đổi dòng code
            
        Returns:
            ID của message đã lưu
        """
        try:
            request = ShortTermMemoryRequest(
                role="user",
                content=content,
                project_id=project_id,
                conversation_id=conversation_id,
                file_path=file_path,
                function_name=function_name,
                line_start=line_start,
                line_end=line_end,
                code_changes=code_changes,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff_summary=diff_summary
            )
            
            message_id = await self.storage.save_message(request)
            logger.info(f"Saved user message {message_id} to short term memory")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving user message: {e}")
            return None
    
    async def save_assistant_message(self, 
                                   content: str, 
                                   project_id: str, 
                                   conversation_id: str,
                                   file_path: Optional[str] = None,
                                   function_name: Optional[str] = None,
                                   line_start: Optional[int] = None,
                                   line_end: Optional[int] = None,
                                   code_changes: Optional[Dict[str, Any]] = None,
                                   lines_added: Optional[int] = None,
                                   lines_removed: Optional[int] = None,
                                   diff_summary: Optional[str] = None) -> str:
        """
        Lưu assistant message vào short term memory
        
        Args:
            content: Nội dung message
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            file_path: Đường dẫn file nếu liên quan đến code
            function_name: Tên function nếu liên quan đến code
            line_start: Số dòng bắt đầu của khoảng code mà AI đã chỉnh sửa
            line_end: Số dòng kết thúc của khoảng code mà AI đã chỉnh sửa
            code_changes: Chi tiết thay đổi code mà AI đã thực hiện
            lines_added: Số dòng code được thêm vào
            lines_removed: Số dòng code bị xóa
            diff_summary: Tóm tắt thay đổi dòng code
            
        Returns:
            ID của message đã lưu
        """
        try:
            request = ShortTermMemoryRequest(
                role="assistant",
                content=content,
                project_id=project_id,
                conversation_id=conversation_id,
                file_path=file_path,
                function_name=function_name,
                line_start=line_start,
                line_end=line_end,
                code_changes=code_changes,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff_summary=diff_summary
            )
            
            message_id = await self.storage.save_message(request)
            logger.info(f"Saved assistant message {message_id} to short term memory")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving assistant message: {e}")
            return None
    
    async def save_system_message(self, 
                                content: str, 
                                project_id: str, 
                                conversation_id: str) -> str:
        """
        Lưu system message vào short term memory
        
        Args:
            content: Nội dung message
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            
        Returns:
            ID của message đã lưu
        """
        try:
            request = ShortTermMemoryRequest(
                role="system",
                content=content,
                project_id=project_id,
                conversation_id=conversation_id
            )
            
            message_id = await self.storage.save_message(request)
            logger.info(f"Saved system message {message_id} to short term memory")
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving system message: {e}")
            return None
    
    async def search_recent_context(self, 
                                  query: str, 
                                  project_id: str, 
                                  conversation_id: Optional[str] = None,
                                  limit: int = 5) -> list:
        """
        Tìm kiếm context gần đây từ short term memory
        
        Args:
            query: Query tìm kiếm
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện (optional)
            limit: Số lượng kết quả tối đa
            
        Returns:
            Danh sách messages phù hợp
        """
        try:
            from app.schemas import ShortTermMemorySearchRequest
            
            search_request = ShortTermMemorySearchRequest(
                query=query,
                project_id=project_id,
                conversation_id=conversation_id,
                limit=limit
            )
            
            results = await self.storage.search_messages(search_request)
            logger.info(f"Found {len(results)} recent context messages")
            return results
            
        except Exception as e:
            logger.error(f"Error searching recent context: {e}")
            return []
    
    async def get_conversation_history(self, 
                                     project_id: str, 
                                     conversation_id: str,
                                     limit: int = 20) -> list:
        """
        Lấy lịch sử cuộc trò chuyện từ short term memory
        
        Args:
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            limit: Số lượng messages tối đa
            
        Returns:
            Danh sách messages trong cuộc trò chuyện
        """
        try:
            from app.schemas import ShortTermMemorySearchRequest
            
            # Tìm kiếm tất cả messages trong conversation
            search_request = ShortTermMemorySearchRequest(
                query="",  # Empty query để lấy tất cả
                project_id=project_id,
                conversation_id=conversation_id,
                limit=limit
            )
            
            results = await self.storage.search_messages(search_request)
            
            # Sắp xếp theo timestamp
            results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            logger.info(f"Retrieved {len(results)} messages from conversation {conversation_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def cleanup_expired_messages(self) -> int:
        """
        Xóa các messages đã hết hạn
        
        Returns:
            Số lượng messages đã xóa
        """
        try:
            deleted_count = await self.storage.cleanup_expired()
            logger.info(f"Cleaned up {deleted_count} expired messages")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired messages: {e}")
            return 0
    
    def extract_code_context_from_message(self, content: str) -> Dict[str, Any]:
        """
        Trích xuất thông tin code context từ message content
        
        Args:
            content: Nội dung message
            
        Returns:
            Dict chứa file_path, function_name, line_start, line_end, code_changes
            - line_start/line_end: Vị trí dòng nơi code changes được thêm vào
        """
        import re
        
        code_info = {
            "file_path": None,
            "function_name": None,
            "line_start": None,
            "line_end": None,
            "code_changes": None
        }
        
        try:
            # Tìm file path patterns
            file_patterns = [
                r'file\s+([^\s]+\.(py|js|ts|java|cpp|c|h|html|css|json|yaml|yml|xml|md|txt))',
                r'([^\s]+\.(py|js|ts|java|cpp|c|h|html|css|json|yaml|yml|xml|md|txt))',
                r'path\s+([^\s]+)',
                r'đường\s+dẫn\s+([^\s]+)'
            ]
            
            for pattern in file_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    code_info["file_path"] = match.group(1)
                    break
            
            # Tìm function name patterns
            function_patterns = [
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'hàm\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ]
            
            for pattern in function_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    code_info["function_name"] = match.group(1)
                    break
            
            # Tìm line number patterns
            line_patterns = [
                r'dòng\s+(\d+)',
                r'line\s+(\d+)',
                r'(\d+)\s*dòng',
                r'(\d+)\s*line'
            ]
            
            for pattern in line_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    line_num = int(match.group(1))
                    code_info["line_start"] = line_num
                    code_info["line_end"] = line_num
                    break
            
            # Tìm range patterns
            range_patterns = [
                r'dòng\s+(\d+)\s*-\s*(\d+)',
                r'line\s+(\d+)\s*-\s*(\d+)',
                r'(\d+)\s*-\s*(\d+)\s*dòng',
                r'(\d+)\s*-\s*(\d+)\s*line'
            ]
            
            for pattern in range_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    code_info["line_start"] = int(match.group(1))
                    code_info["line_end"] = int(match.group(2))
                    break
            
            # Phát hiện code changes (AI đã chỉnh sửa code)
            code_change_patterns = [
                r'```(\w+)?\n(.*?)\n```',  # Code blocks
                r'đã thêm\s+(.*?)(?:\n|$)',  # "đã thêm ..."
                r'đã sửa\s+(.*?)(?:\n|$)',   # "đã sửa ..."
                r'đã xóa\s+(.*?)(?:\n|$)',   # "đã xóa ..."
                r'đã refactor\s+(.*?)(?:\n|$)',  # "đã refactor ..."
                r'da them\s+(.*?)(?:\n|$)',  # "da them ..."
                r'da sua\s+(.*?)(?:\n|$)',   # "da sua ..."
                r'da xoa\s+(.*?)(?:\n|$)',   # "da xoa ..."
                r'da refactor\s+(.*?)(?:\n|$)',  # "da refactor ..."
            ]
            
            for pattern in code_change_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    # Tạo code_changes object
                    code_changes = {
                        "change_type": "modified",  # Default
                        "description": "Code changes detected",
                        "code_blocks": []
                    }
                    
                    for match in matches:
                        if isinstance(match, tuple):
                            language, code = match
                            code_changes["code_blocks"].append({
                                "language": language or "text",
                                "code": code.strip()
                            })
                        else:
                            code_changes["code_blocks"].append({
                                "language": "text",
                                "code": match.strip()
                            })
                    
                    # Xác định change_type dựa trên keywords
                    if any(word in content.lower() for word in ['thêm', 'them', 'added', 'add']):
                        code_changes["change_type"] = "added"
                    elif any(word in content.lower() for word in ['xóa', 'xoa', 'deleted', 'delete', 'remove']):
                        code_changes["change_type"] = "deleted"
                    elif any(word in content.lower() for word in ['refactor', 'refactored']):
                        code_changes["change_type"] = "refactored"
                    
                    code_info["code_changes"] = code_changes
                    break
            
            return code_info
            
        except Exception as e:
            logger.error(f"Error extracting code context: {e}")
            return code_info


# Global instance
_integration_instance = None

def get_integration() -> ShortTermMemoryIntegration:
    """Get global integration instance"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = ShortTermMemoryIntegration()
    return _integration_instance


# Helper functions for easy integration
async def save_chat_message(role: str, 
                           content: str, 
                           project_id: str, 
                           conversation_id: str,
                           **kwargs) -> Optional[str]:
    """
    Helper function để lưu chat message
    
    Args:
        role: "user", "assistant", "system"
        content: Nội dung message
        project_id: ID dự án
        conversation_id: ID cuộc trò chuyện
        **kwargs: Các tham số khác (file_path, function_name, etc.)
        
    Returns:
        ID của message đã lưu
    """
    integration = get_integration()
    
    # Extract specific parameters from kwargs
    file_path = kwargs.get('file_path')
    function_name = kwargs.get('function_name')
    line_start = kwargs.get('line_start')
    line_end = kwargs.get('line_end')
    code_changes = kwargs.get('code_changes')
    lines_added = kwargs.get('lines_added')
    lines_removed = kwargs.get('lines_removed')
    diff_summary = kwargs.get('diff_summary')
    
    if role == "user":
        return await integration.save_user_message(
            content, project_id, conversation_id,
            file_path=file_path,
            function_name=function_name,
            line_start=line_start,
            line_end=line_end,
            code_changes=code_changes,
            lines_added=lines_added,
            lines_removed=lines_removed,
            diff_summary=diff_summary
        )
    elif role == "assistant":
        return await integration.save_assistant_message(
            content, project_id, conversation_id,
            file_path=file_path,
            function_name=function_name,
            line_start=line_start,
            line_end=line_end,
            code_changes=code_changes,
            lines_added=lines_added,
            lines_removed=lines_removed,
            diff_summary=diff_summary
        )
    elif role == "system":
        return await integration.save_system_message(content, project_id, conversation_id)
    else:
        logger.warning(f"Unknown role: {role}")
        return None


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_integration():
        integration = ShortTermMemoryIntegration()
        
        # Test save messages
        project_id = "test_project"
        conversation_id = "conv_001"
        
        # Save user message
        user_id = await integration.save_user_message(
            content="Tôi muốn thêm chức năng đăng nhập vào file auth.py, function login_user ở dòng 25-30",
            project_id=project_id,
            conversation_id=conversation_id,
            file_path="auth.py",
            function_name="login_user",
            line_start=25,
            line_end=30
        )
        print(f"Saved user message: {user_id}")
        
        # Save assistant message
        assistant_id = await integration.save_assistant_message(
            content="Tôi sẽ giúp bạn thêm chức năng đăng nhập. Trước tiên, hãy xem code hiện tại của function login_user.",
            project_id=project_id,
            conversation_id=conversation_id
        )
        print(f"Saved assistant message: {assistant_id}")
        
        # Search recent context
        results = await integration.search_recent_context(
            query="đăng nhập",
            project_id=project_id,
            conversation_id=conversation_id
        )
        print(f"Found {len(results)} relevant messages")
        
        # Get conversation history
        history = await integration.get_conversation_history(
            project_id=project_id,
            conversation_id=conversation_id
        )
        print(f"Conversation history: {len(history)} messages")
    
    asyncio.run(test_integration())
