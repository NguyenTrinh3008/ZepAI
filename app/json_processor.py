# -*- coding: utf-8 -*-
"""
JSON Processor for Graphiti Integration

Chuyển đổi JSON data thành Graphiti episodes để lưu vào Neo4j
Hỗ trợ nhiều format: short_term.json, conversation JSON, custom JSON
"""

import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from graphiti_core.nodes import EpisodeType

from app.graphiti_estimator import estimate_tokens_for_episode
from app.graphiti_token_tracker import get_global_tracker


async def process_json_to_graphiti(
    json_text: str,
    project_id: str,
    use_llm: bool = False,
    graphiti = None
) -> Dict[str, Any]:
    """
    Xử lý JSON data và tạo Graphiti episodes
    
    Args:
        json_text: JSON content as string
        project_id: Project identifier
        use_llm: Whether to use LLM for enhanced processing
        graphiti: Graphiti instance
    
    Returns:
        Processing results dictionary
    """
    start_time = time.time()
    tracker = get_global_tracker()
    
    try:
        # Parse JSON
        data = json.loads(json_text)
        
        # Detect JSON format and process accordingly
        if isinstance(data, dict) and "messages" in data:
            # Short Term Memory format
            return await process_stm_json(data, project_id, use_llm, graphiti, tracker)
        elif isinstance(data, list) and len(data) > 0 and "messages" in data[0]:
            # Conversation list format
            return await process_conversation_list(data, project_id, use_llm, graphiti, tracker)
        elif isinstance(data, dict) and "conversation_id" in data:
            # Single conversation format
            return await process_single_conversation(data, project_id, use_llm, graphiti, tracker)
        else:
            # Generic JSON - try to extract text content
            return await process_generic_json(data, project_id, use_llm, graphiti, tracker)
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "episodes_created": 0,
            "entities_created": 0,
            "processing_time": time.time() - start_time
        }


async def process_stm_json(
    data: Dict[str, Any],
    project_id: str,
    use_llm: bool,
    graphiti,
    tracker
) -> Dict[str, Any]:
    """Xử lý Short Term Memory JSON format"""
    start_time = time.time()
    episodes_created = 0
    entities_created = 0
    
    messages = data.get("messages", [])
    
    # Group messages by conversation for better context
    conversations = {}
    for msg in messages:
        conv_id = msg.get("metadata", {}).get("conversation_id", "default")
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(msg)
    
    # Process each conversation as an episode
    for conv_id, conv_messages in conversations.items():
        try:
            # Create episode body from messages
            episode_body = create_episode_body_from_messages(conv_messages)
            
            if not episode_body.strip():
                print(f"Warning: Empty episode body for conversation {conv_id}")
                continue
                
            print(f"Creating episode for conversation {conv_id} with {len(episode_body)} characters")
            
            # Create episode
            episode = await graphiti.add_episode(
                name=f"STM_Conversation_{conv_id}",
                episode_body=episode_body,
                source=EpisodeType.message,
                source_description="short_term_memory_upload",
                reference_time=datetime.utcnow(),
                group_id=project_id
            )
            
            episodes_created += 1
            
            # Estimate tokens and track
            estimate_tokens_for_episode(
                episode_id=episode.id if hasattr(episode, 'id') else conv_id,
                episode_body=episode_body,
                model="gpt-4o-mini"
            )
            
            # Wait for entities to be created
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error processing conversation {conv_id}: {e}")
            continue
    
    return {
        "status": "success",
        "episodes_created": episodes_created,
        "entities_created": entities_created,  # Will be updated by Graphiti
        "processing_time": time.time() - start_time,
        "details": {
            "conversations_processed": len(conversations),
            "total_messages": len(messages),
            "format": "short_term_memory"
        }
    }


async def process_conversation_list(
    data: List[Dict[str, Any]],
    project_id: str,
    use_llm: bool,
    graphiti,
    tracker
) -> Dict[str, Any]:
    """Xử lý danh sách conversations"""
    start_time = time.time()
    episodes_created = 0
    entities_created = 0
    
    for i, conv in enumerate(data):
        try:
            # Extract conversation data
            conv_id = conv.get("conversation_id", f"conv_{i}")
            messages = conv.get("messages", [])
            
            if not messages:
                continue
                
            # Create episode body
            episode_body = create_episode_body_from_conversation(conv)
            
            if not episode_body.strip():
                continue
                
            # Create episode
            episode = await graphiti.add_episode(
                name=f"Uploaded_Conversation_{conv_id}",
                episode_body=episode_body,
                source=EpisodeType.text,
                source_description="conversation_upload",
                reference_time=datetime.utcnow(),
                group_id=project_id
            )
            
            episodes_created += 1
            
            # Estimate tokens
            estimate_tokens_for_episode(
                episode_id=episode.id if hasattr(episode, 'id') else conv_id,
                episode_body=episode_body,
                model="gpt-4o-mini"
            )
            
            # Wait for processing
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error processing conversation {i}: {e}")
            continue
    
    return {
        "status": "success",
        "episodes_created": episodes_created,
        "entities_created": entities_created,
        "processing_time": time.time() - start_time,
        "details": {
            "conversations_processed": len(data),
            "format": "conversation_list"
        }
    }


async def process_single_conversation(
    data: Dict[str, Any],
    project_id: str,
    use_llm: bool,
    graphiti,
    tracker
) -> Dict[str, Any]:
    """Xử lý single conversation"""
    start_time = time.time()
    
    try:
        # Create episode body
        episode_body = create_episode_body_from_conversation(data)
        
        if not episode_body.strip():
            return {
                "status": "error",
                "error": "No content to process",
                "episodes_created": 0,
                "entities_created": 0,
                "processing_time": time.time() - start_time
            }
            
        # Create episode
        episode = await graphiti.add_episode(
            name=f"Uploaded_Conversation_{data.get('conversation_id', 'unknown')}",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description="single_conversation_upload",
            reference_time=datetime.utcnow(),
            group_id=project_id
        )
        
        # Estimate tokens
        estimate_tokens_for_episode(
            episode_id=episode.id if hasattr(episode, 'id') else data.get('conversation_id', 'unknown'),
            episode_body=episode_body,
            model="gpt-4o-mini"
        )
        
        return {
            "status": "success",
            "episodes_created": 1,
            "entities_created": 0,  # Will be updated by Graphiti
            "processing_time": time.time() - start_time,
            "details": {
                "conversation_id": data.get('conversation_id', 'unknown'),
                "format": "single_conversation"
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "episodes_created": 0,
            "entities_created": 0,
            "processing_time": time.time() - start_time
        }


async def process_generic_json(
    data: Any,
    project_id: str,
    use_llm: bool,
    graphiti,
    tracker
) -> Dict[str, Any]:
    """Xử lý generic JSON data"""
    start_time = time.time()
    
    try:
        # Convert to text representation
        episode_body = json.dumps(data, indent=2, ensure_ascii=False)
        
        # Create episode
        episode = await graphiti.add_episode(
            name="Uploaded_JSON_Data",
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description="generic_json_upload",
            reference_time=datetime.utcnow(),
            group_id=project_id
        )
        
        # Estimate tokens
        estimate_tokens_for_episode(
            episode_id=episode.id if hasattr(episode, 'id') else "generic_json",
            episode_body=episode_body,
            model="gpt-4o-mini"
        )
        
        return {
            "status": "success",
            "episodes_created": 1,
            "entities_created": 0,
            "processing_time": time.time() - start_time,
            "details": {
                "format": "generic_json",
                "data_type": type(data).__name__
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "episodes_created": 0,
            "entities_created": 0,
            "processing_time": time.time() - start_time
        }


def create_episode_body_from_messages(messages: List[Dict[str, Any]]) -> str:
    """Tạo episode body từ STM messages"""
    body_parts = []
    
    print(f"Processing {len(messages)} messages")
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        
        print(f"  Message {i+1}: role={role}, content_length={len(content)}")
        
        if content.strip():
            body_parts.append(f"{role}: {content}")
        else:
            print(f"    Warning: Empty content for message {i+1}")
    
    result = "\n\n".join(body_parts)
    print(f"Created episode body with {len(result)} characters")
    return result


def create_episode_body_from_conversation(conv: Dict[str, Any]) -> str:
    """Tạo episode body từ conversation data"""
    body_parts = []
    
    # Add conversation metadata
    conv_id = conv.get("conversation_id", "unknown")
    project_id = conv.get("project_id", "unknown")
    timestamp = conv.get("timestamp", "")
    
    body_parts.append(f"Conversation ID: {conv_id}")
    body_parts.append(f"Project: {project_id}")
    body_parts.append(f"Timestamp: {timestamp}")
    body_parts.append("")
    
    # Add messages
    messages = conv.get("messages", [])
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        if content.strip():
            body_parts.append(f"{role}: {content}")
    
    # Add context files if available
    context_files = conv.get("context_files", [])
    if context_files:
        body_parts.append("\nContext Files:")
        for cf in context_files:
            file_path = cf.get("file_path", "unknown")
            usefulness = cf.get("usefulness", 0)
            body_parts.append(f"- {file_path} (usefulness: {usefulness})")
    
    # Add tool calls if available
    tool_calls = conv.get("tool_calls", [])
    if tool_calls:
        body_parts.append("\nTool Calls:")
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "unknown")
            status = tc.get("status", "unknown")
            body_parts.append(f"- {tool_name} ({status})")
    
    # Add code changes if available
    code_changes = conv.get("code_changes", [])
    if code_changes:
        body_parts.append("\nCode Changes:")
        for cc in code_changes:
            file_path = cc.get("file_path", "unknown")
            change_type = cc.get("change_type", "unknown")
            summary = cc.get("summary", "")
            body_parts.append(f"- {change_type} {file_path}: {summary}")
    
    return "\n".join(body_parts)


# Alias for backward compatibility
async def process_conversation_json_to_graphiti(
    json_text: str,
    project_id: str,
    graphiti = None
) -> Dict[str, Any]:
    """Alias for process_json_to_graphiti specifically for conversation JSON"""
    return await process_json_to_graphiti(
        json_text=json_text,
        project_id=project_id,
        use_llm=False,
        graphiti=graphiti
    )
