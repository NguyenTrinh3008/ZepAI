# app/routes/conversation.py
"""
Conversation context endpoints - Phase 1.5
"""
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException

from app.graph import get_graphiti
from app.schemas import IngestConversationContext
from app.cache import invalidate_search_cache
from app.prompts import format_conversation_episode_body
from app.conversation_graph import (
    create_request_node,
    create_message_node,
    create_context_file_node,
    create_tool_call_node,
    create_checkpoint_node,
    create_code_change_node,
    search_requests,
    get_conversation_flow as get_flow,
    get_context_file_stats as get_stats,
    get_tool_statistics
)
from graphiti_core.nodes import EpisodeType

router = APIRouter(prefix="/conversation", tags=["conversation"])
logger = logging.getLogger(__name__)


@router.post("/ingest", operation_id="ingest_conversation")
async def ingest_conversation(payload: IngestConversationContext, graphiti=Depends(get_graphiti)):
    """
    Ingest full conversation context - Phase 1.5
    
    Creates entities:
    - Request node (root)
    - Message nodes (user/assistant messages)
    - ContextFile nodes (files from VecDB/AST)
    - ToolCall nodes (tool invocations)
    - Checkpoint nodes (git snapshots)
    - CodeChange nodes (reuse existing logic)
    
    With relationships linking them all together.
    """
    try:
        logger.info(f"📥 Ingesting conversation context for request: {payload.request_id}")
        
        total_tokens = payload.messages[-1].total_tokens if payload.messages and payload.messages[-1].total_tokens else 0
        model = payload.model_response.model if payload.model_response else "unknown"
        
        # Convert Pydantic models to dicts for prompts
        messages_dicts = [
            {
                "role": msg.role,
                "content_summary": msg.content_summary
            }
            for msg in payload.messages
        ]
        
        context_files_dicts = [
            {
                "file_path": cf.file_path,
                "usefulness": cf.usefulness
            }
            for cf in payload.context_files
        ] if payload.context_files else None
        
        tool_calls_dicts = [
            {
                "tool_name": tc.tool_name
            }
            for tc in payload.tool_calls
        ] if payload.tool_calls else None
        
        # Use prompt formatter for better structure
        conversation_summary = format_conversation_episode_body(
            chat_id=payload.chat_meta.chat_id,
            chat_mode=payload.chat_meta.chat_mode,
            project_id=payload.project_id,
            messages=messages_dicts,
            context_files=context_files_dicts,
            tools=tool_calls_dicts
        )
        
        # Build human-readable summary for search results
        summary_parts = []
        for msg in payload.messages[:2]:
            if msg.content_summary:
                snippet = msg.content_summary.strip().replace("\n", " ")
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                summary_parts.append(f"{msg.role.upper()}: {snippet}")
        if payload.context_files:
            file_list = ", ".join([cf.file_path for cf in payload.context_files[:3]])
            summary_parts.append(f"FILES: {file_list}")
        if payload.tool_calls:
            tool_list = ", ".join(sorted({tc.tool_name for tc in payload.tool_calls}))
            summary_parts.append(f"TOOLS: {tool_list}")
        entity_summary = " | ".join(summary_parts) if summary_parts else "Conversation context"
        entity_name = f"Conversation {payload.chat_meta.chat_id}"

        # Parse timestamp (handle 'Z' suffix for Python < 3.11 compatibility)
        time_str = payload.timestamp.replace('Z', '+00:00')
        ts = datetime.fromisoformat(time_str)
        
        episode = await graphiti.add_episode(
            name=entity_name,
            episode_body=conversation_summary,
            source=EpisodeType.text,
            source_description="conversation",
            reference_time=ts,
            group_id=payload.project_id
        )
        
        logger.info("✓ Episode created, waiting for entity and embeddings...")
        
        # Wait for entity creation and embedding generation (Graphiti needs ~5s)
        await asyncio.sleep(5)
        
        # Find created entity - try multiple times with different strategies
        query = """
        MATCH (e:Entity {group_id: $group_id})
        WHERE e.created_at >= datetime($reference_time)
        RETURN e.uuid as uuid, e.created_at as created_at, e.name as name
        ORDER BY e.created_at DESC
        LIMIT 1
        """
        
        request_uuid = None
        max_retries = 3
        
        for attempt in range(max_retries):
            async with graphiti.driver.session() as session:
                result = await session.run(query, {
                    "group_id": payload.project_id,
                    "reference_time": (ts - timedelta(seconds=30)).isoformat()  # Wider time window
                })
                record = await result.single()
                if record:
                    request_uuid = record["uuid"]
                    logger.info(f"✓ Found entity: {record['name']} (created: {record['created_at']})")
                    break
                else:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries}: Entity not found yet, waiting...")
                    await asyncio.sleep(2)
        
        if not request_uuid:
            # Last resort: get the most recent entity for this group
            logger.warning("Trying fallback: get most recent entity for group")
            fallback_query = """
            MATCH (e:Entity {group_id: $group_id})
            RETURN e.uuid as uuid, e.created_at as created_at, e.name as name
            ORDER BY e.created_at DESC
            LIMIT 1
            """
            async with graphiti.driver.session() as session:
                result = await session.run(fallback_query, {"group_id": payload.project_id})
                record = await result.single()
                if record:
                    request_uuid = record["uuid"]
                    logger.info(f"✓ Fallback found entity: {record['name']}")
        
        if not request_uuid:
            raise Exception("Failed to create conversation entity after retries")
        
        logger.info(f"✓ Entity created: {request_uuid}")
        
        # Add all metadata via Cypher
        expires_at = ts + timedelta(days=2)
        
        metadata_query = """
        MATCH (e:Entity {uuid: $uuid})
        SET e.entity_type = 'request',
            e.name = $name,
            e.project_id = $project_id,
            e.request_id = $request_id,
            e.chat_id = $chat_id,
            e.chat_mode = $chat_mode,
            e.model = $model,
            e.total_tokens = $total_tokens,
            e.message_count = $message_count,
            e.context_file_count = $context_file_count,
            e.tool_call_count = $tool_call_count,
            e.summary = $summary,
            e.expires_at = $expires_at
        SET e:Request
        RETURN e.uuid as uuid
        """
        
        async with graphiti.driver.session() as session:
            await session.run(metadata_query, {
                "uuid": request_uuid,
                "name": entity_name,
                "project_id": payload.project_id,
                "request_id": payload.request_id,
                "chat_id": payload.chat_meta.chat_id,
                "chat_mode": payload.chat_meta.chat_mode,
                "model": model,
                "total_tokens": total_tokens,
                "message_count": len(payload.messages),
                "context_file_count": len(payload.context_files),
                "tool_call_count": len(payload.tool_calls),
                "summary": entity_summary,
                "expires_at": expires_at.isoformat() + 'Z'
            })
        
        # Create detailed graph structure
        request_node_uuid = await create_request_node(
            graphiti=graphiti,
            request_id=payload.request_id,
            project_id=payload.project_id,
            chat_meta=payload.chat_meta,
            timestamp=payload.timestamp,
            model=model,
            total_tokens=total_tokens
        )
        logger.info(f"Request node created: {request_node_uuid}")
        
        # Messages
        for msg in payload.messages:
            try:
                await create_message_node(
                    graphiti=graphiti,
                    request_uuid=request_node_uuid,
                    request_id=payload.request_id,
                    message=msg,
                    timestamp=payload.timestamp,
                    project_id=payload.project_id
                )
            except Exception as message_error:
                logger.warning(f"Failed to create message node: {message_error}")
        
        # Context files
        for cf in payload.context_files or []:
            try:
                await create_context_file_node(
                    graphiti=graphiti,
                    request_uuid=request_node_uuid,
                    request_id=payload.request_id,
                    context_file=cf,
                    timestamp=payload.timestamp,
                    project_id=payload.project_id
                )
            except Exception as ctx_error:
                logger.warning(f"Failed to create context file node: {ctx_error}")
        
        # Tool calls
        for tc in payload.tool_calls or []:
            try:
                await create_tool_call_node(
                    graphiti=graphiti,
                    request_uuid=request_node_uuid,
                    request_id=payload.request_id,
                    tool_call=tc,
                    timestamp=payload.timestamp,
                    project_id=payload.project_id
                )
            except Exception as tool_error:
                logger.warning(f"Failed to create tool call node: {tool_error}")
        
        # Checkpoints
        for cp in payload.checkpoints or []:
            try:
                await create_checkpoint_node(
                    graphiti=graphiti,
                    request_uuid=request_node_uuid,
                    request_id=payload.request_id,
                    checkpoint=cp,
                    timestamp=payload.timestamp,
                    project_id=payload.project_id
                )
            except Exception as checkpoint_error:
                logger.warning(f"Failed to create checkpoint node: {checkpoint_error}")
        
        # Code changes (link to code files)
        for cc in payload.code_changes or []:
            try:
                await create_code_change_node(
                    graphiti=graphiti,
                    request_uuid=request_node_uuid,
                    request_id=payload.request_id,
                    code_change=cc,
                    timestamp=payload.timestamp,
                    project_id=payload.project_id
                )
            except Exception as code_error:
                logger.warning(f"Failed to create code change node: {code_error}")

        # Invalidate cache
        invalidate_search_cache()
        
        logger.info(f"✅ Conversation context ingested successfully!")
        
        return {
            "status": "success",
            "request_uuid": request_node_uuid,
            "request_id": payload.request_id,
            "entity_type": "request",
            "metadata": {
                "chat_id": payload.chat_meta.chat_id,
                "model": model,
                "total_tokens": total_tokens,
                "message_count": len(payload.messages),
                "context_file_count": len(payload.context_files),
                "tool_call_count": len(payload.tool_calls),
                "summary": entity_summary
            },
            "expires_at": expires_at.isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"❌ Error ingesting conversation context: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest conversation context: {str(e)}")


@router.get("/requests/{project_id}", operation_id="get_conversation_requests")
async def get_conversation_requests(
    project_id: str,
    chat_id: str = None,
    days_ago: int = 7,
    graphiti=Depends(get_graphiti)
):
    """
    Get all conversation requests for a project
    
    Args:
        project_id: Project ID filter
        chat_id: Optional chat ID filter
        days_ago: Time window (default 7 days)
    
    Returns:
        List of requests with metadata
    """
    try:
        logger.info(f"Searching requests for project {project_id}, chat_id={chat_id}, days_ago={days_ago}")
        
        results = await search_requests(
            graphiti=graphiti,
            project_id=project_id,
            chat_id=chat_id,
            days_ago=days_ago
        )
        
        return {
            "project_id": project_id,
            "count": len(results),
            "requests": results
        }
        
    except Exception as e:
        logger.error(f"Error searching requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search requests: {str(e)}")


@router.get("/flow/{request_id}", operation_id="get_conversation_flow")
async def get_conversation_flow(
    request_id: str,
    graphiti=Depends(get_graphiti)
):
    """
    Get complete conversation flow for a specific request
    
    Returns:
        Request with all messages, context files, tool calls
    """
    try:
        logger.info(f"Getting conversation flow for request {request_id}")
        
        result = await get_flow(graphiti=graphiti, request_id=request_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation flow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation flow: {str(e)}")


@router.get("/context-stats/{project_id}", operation_id="get_context_stats")
async def get_context_file_stats(
    project_id: str,
    days_ago: int = 7,
    graphiti=Depends(get_graphiti)
):
    """
    Get context file usage statistics
    
    Shows which files are most frequently used as context
    and their average usefulness scores
    
    Args:
        project_id: Project ID filter
        days_ago: Time window (default 7 days)
    
    Returns:
        List of files with usage counts and usefulness metrics
    """
    try:
        logger.info(f"Getting context file stats for project {project_id}")
        
        results = await get_stats(
            graphiti=graphiti,
            project_id=project_id,
            days_ago=days_ago
        )
        
        return {
            "project_id": project_id,
            "days_ago": days_ago,
            "count": len(results),
            "files": results
        }
        
    except Exception as e:
        logger.error(f"Error getting context stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get context stats: {str(e)}")


@router.get("/tool-stats", operation_id="get_tool_stats")
async def get_tool_stats(
    days_ago: int = 7,
    graphiti=Depends(get_graphiti)
):
    """
    Get tool call statistics
    
    Shows success rates and performance metrics for each tool
    
    Args:
        days_ago: Time window (default 7 days)
    
    Returns:
        List of tools with success rates and execution times
    """
    try:
        logger.info(f"Getting tool statistics for last {days_ago} days")
        
        results = await get_tool_statistics(
            graphiti=graphiti,
            days_ago=days_ago
        )
        
        return {
            "days_ago": days_ago,
            "count": len(results),
            "tools": results
        }
        
    except Exception as e:
        logger.error(f"Error getting tool stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tool stats: {str(e)}")

