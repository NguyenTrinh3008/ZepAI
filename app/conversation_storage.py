# -*- coding: utf-8 -*-
"""
Conversation Storage Service

Lưu trữ chi tiết conversation data từ AI chat vào JSON files
Bao gồm: messages, context files, tool calls, code changes, metadata
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
import uuid

from app.schemas import ConversationPayload, ConversationMessage, ContextFile, ToolCall, CodeChange, ModelResponse


class ConversationStorage:
    """Service để lưu trữ conversation data chi tiết"""
    
    def __init__(self, storage_dir: str = "data/conversations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Tạo subdirectories
        (self.storage_dir / "by_project").mkdir(exist_ok=True)
        (self.storage_dir / "by_date").mkdir(exist_ok=True)
        (self.storage_dir / "by_chat").mkdir(exist_ok=True)
    
    def _generate_conversation_id(self, request_id: str, chat_id: str) -> str:
        """Generate unique conversation ID"""
        return f"{chat_id}_{request_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _get_storage_paths(self, conversation_id: str, project_id: str) -> Dict[str, Path]:
        """Get storage paths for different organization methods"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        return {
            "main": self.storage_dir / f"{conversation_id}.json",
            "by_project": self.storage_dir / "by_project" / f"{project_id}" / f"{conversation_id}.json",
            "by_date": self.storage_dir / "by_date" / f"{date_str}" / f"{conversation_id}.json",
            "by_chat": self.storage_dir / "by_chat" / f"{conversation_id.split('_')[0]}" / f"{conversation_id}.json"
        }
    
    async def save_conversation(self, payload: ConversationPayload) -> Dict[str, Any]:
        """
        Lưu conversation data vào JSON files
        
        Args:
            payload: ConversationPayload object
            
        Returns:
            Dict với thông tin lưu trữ
        """
        try:
            # Generate conversation ID
            conversation_id = self._generate_conversation_id(
                payload.request_id, 
                payload.chat_meta.get("chat_id", "unknown")
            )
            
            # Get storage paths
            paths = self._get_storage_paths(conversation_id, payload.project_id)
            
            # Create directories
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for storage
            storage_data = {
                "conversation_id": conversation_id,
                "request_id": payload.request_id,
                "project_id": payload.project_id,
                "timestamp": payload.timestamp,
                "chat_meta": payload.chat_meta,
                "messages": [msg.dict() for msg in payload.messages],
                "context_files": [cf.dict() for cf in payload.context_files],
                "tool_calls": [tc.dict() for tc in payload.tool_calls],
                "checkpoints": payload.checkpoints,
                "code_changes": [cc.dict() for cc in payload.code_changes],
                "model_response": payload.model_response.dict(),
                "group_id": payload.group_id,
                "storage_metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "file_size": 0,  # Will be updated after saving
                    "message_count": len(payload.messages),
                    "context_file_count": len(payload.context_files),
                    "tool_call_count": len(payload.tool_calls),
                    "code_change_count": len(payload.code_changes)
                }
            }
            
            # Save to all paths
            saved_paths = []
            for path_type, path in paths.items():
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(storage_data, f, indent=2, ensure_ascii=False)
                saved_paths.append(str(path))
            
            # Update file size
            storage_data["storage_metadata"]["file_size"] = os.path.getsize(paths["main"])
            
            # Update main file with file size
            with open(paths["main"], 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, indent=2, ensure_ascii=False)
            
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "saved_paths": saved_paths,
                "metadata": storage_data["storage_metadata"]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "conversation_id": None
            }
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Lấy conversation data từ storage"""
        try:
            # Try main storage first
            main_path = self.storage_dir / f"{conversation_id}.json"
            if main_path.exists():
                with open(main_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Search in subdirectories
            for subdir in ["by_project", "by_date", "by_chat"]:
                search_path = self.storage_dir / subdir
                for root, dirs, files in os.walk(search_path):
                    if f"{conversation_id}.json" in files:
                        file_path = Path(root) / f"{conversation_id}.json"
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
            
            return None
            
        except Exception as e:
            print(f"Error loading conversation {conversation_id}: {e}")
            return None
    
    async def list_conversations(self, project_id: Optional[str] = None, 
                               date: Optional[str] = None) -> List[Dict[str, Any]]:
        """List conversations with optional filters"""
        try:
            conversations = []
            
            if project_id:
                # Search in project directory
                project_dir = self.storage_dir / "by_project" / project_id
                if project_dir.exists():
                    for file_path in project_dir.glob("*.json"):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            conversations.append({
                                "conversation_id": data["conversation_id"],
                                "request_id": data["request_id"],
                                "project_id": data["project_id"],
                                "timestamp": data["timestamp"],
                                "message_count": data["storage_metadata"]["message_count"],
                                "file_size": data["storage_metadata"]["file_size"]
                            })
            elif date:
                # Search in date directory
                date_dir = self.storage_dir / "by_date" / date
                if date_dir.exists():
                    for file_path in date_dir.glob("*.json"):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            conversations.append({
                                "conversation_id": data["conversation_id"],
                                "request_id": data["request_id"],
                                "project_id": data["project_id"],
                                "timestamp": data["timestamp"],
                                "message_count": data["storage_metadata"]["message_count"],
                                "file_size": data["storage_metadata"]["file_size"]
                            })
            else:
                # Search in main directory
                for file_path in self.storage_dir.glob("*.json"):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        conversations.append({
                            "conversation_id": data["conversation_id"],
                            "request_id": data["request_id"],
                            "project_id": data["project_id"],
                            "timestamp": data["timestamp"],
                            "message_count": data["storage_metadata"]["message_count"],
                            "file_size": data["storage_metadata"]["file_size"]
                        })
            
            # Sort by timestamp (newest first)
            conversations.sort(key=lambda x: x["timestamp"], reverse=True)
            return conversations
            
        except Exception as e:
            print(f"Error listing conversations: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                "total_conversations": 0,
                "total_size_bytes": 0,
                "by_project": {},
                "by_date": {},
                "recent_conversations": []
            }
            
            # Count all conversations
            for file_path in self.storage_dir.rglob("*.json"):
                if file_path.name != "index.json":  # Skip index files
                    stats["total_conversations"] += 1
                    stats["total_size_bytes"] += file_path.stat().st_size
                    
                    # Load and categorize
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # By project
                            project = data.get("project_id", "unknown")
                            if project not in stats["by_project"]:
                                stats["by_project"][project] = 0
                            stats["by_project"][project] += 1
                            
                            # By date
                            date = data.get("timestamp", "")[:10]  # YYYY-MM-DD
                            if date:
                                if date not in stats["by_date"]:
                                    stats["by_date"][date] = 0
                                stats["by_date"][date] += 1
                            
                            # Recent conversations
                            stats["recent_conversations"].append({
                                "conversation_id": data["conversation_id"],
                                "project_id": data["project_id"],
                                "timestamp": data["timestamp"],
                                "message_count": data["storage_metadata"]["message_count"]
                            })
                    except:
                        continue
            
            # Sort recent conversations
            stats["recent_conversations"].sort(key=lambda x: x["timestamp"], reverse=True)
            stats["recent_conversations"] = stats["recent_conversations"][:10]  # Top 10
            
            return stats
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {"error": str(e)}


# Singleton instance
_conversation_storage = None

def get_conversation_storage() -> ConversationStorage:
    """Get singleton ConversationStorage instance"""
    global _conversation_storage
    if _conversation_storage is None:
        _conversation_storage = ConversationStorage()
    return _conversation_storage
