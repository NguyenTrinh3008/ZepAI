"""
Conversation Context Graph Functions - Phase 1.5
Create and query conversation entities in Neo4j
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from app.graph import create_relationship, find_or_create_file_entity
from app.config import cache

from .schemas import (
    IngestConversationContext,
    ChatMetadata,
    MessagePayload,
    ContextFilePayload,
    ToolCallPayload,
    CheckpointPayload,
    CodeChangeMetadata,
)


async def _create_entity_node(graphiti: Graphiti, labels: List[str], properties: Dict[str, Any]) -> str:
    """Create an entity node with dynamic labels via Cypher."""
    props = {k: v for k, v in properties.items() if v is not None}
    if "uuid" not in props:
        props["uuid"] = str(uuid.uuid4())
    if "created_at" not in props:
        props["created_at"] = datetime.utcnow().isoformat() + "Z"

    label_suffix = ":" + ":".join(labels) if labels else ""
    query = f"""
    CREATE (e:Entity{label_suffix})
    SET e += $props
    RETURN e.uuid as uuid
    """

    async with graphiti.driver.session() as session:
        result = await session.run(query, {"props": props})
        record = await result.single()
        if not record:
            raise Exception("Failed to create entity node")
        return record["uuid"]


async def _create_entity_via_episode(
    graphiti: Graphiti,
    name: str,
    summary: str,
    project_id: str,
    timestamp: str,
    metadata: Dict[str, Any],
    labels: List[str]
) -> str:
    """
    Helper: Create entity via episode + metadata
    
    Returns:
        UUID of created entity
    """
    ts = datetime.fromisoformat(timestamp.replace('Z', ''))
    
    # Create episode
    await graphiti.add_episode(
        name=name,
        episode_body=summary,
        source=EpisodeType.text,
        source_description="conversation_context",
        reference_time=ts,
        group_id=project_id
    )
    
    # Wait for entity creation
    import asyncio
    await asyncio.sleep(0.5)
    
    # Find created entity
    query = """
    MATCH (e:Entity {group_id: $group_id})
    WHERE e.created_at >= datetime($reference_time)
    RETURN e.uuid as uuid
    ORDER BY e.created_at DESC
    LIMIT 1
    """
    
    entity_uuid = None
    async with graphiti.driver.session() as session:
        result = await session.run(query, {
            "group_id": project_id,
            "reference_time": (ts - timedelta(seconds=10)).isoformat()
        })
        record = await result.single()
        if record:
            entity_uuid = record["uuid"]
    
    if not entity_uuid:
        raise Exception(f"Failed to create entity: {name}")
    
    # Build SET clauses for metadata
    set_clauses = []
    params = {"uuid": entity_uuid}
    
    for key, value in metadata.items():
        if value is not None:
            set_clauses.append(f"e.{key} = ${key}")
            params[key] = value
    
    # Add labels
    label_str = ":".join(labels) if labels else ""
    set_label = f"SET e:{label_str}" if label_str else ""
    
    # Update entity
    update_query = f"""
    MATCH (e:Entity {{uuid: $uuid}})
    SET {', '.join(set_clauses)}
    {set_label}
    RETURN e.uuid as uuid
    """
    
    async with graphiti.driver.session() as session:
        await session.run(update_query, params)
    
    return entity_uuid


async def create_request_node(
    graphiti: Graphiti,
    request_id: str,
    project_id: str,
    chat_meta: ChatMetadata,
    timestamp: str,
    model: str,
    total_tokens: int
) -> str:
    """Ensure Request entity exists and update metadata"""
    ts = datetime.fromisoformat(timestamp.replace('Z', ''))
    expires_at = ts + timedelta(days=cache.get_conversation_ttl_days())

    # Try to find existing Request created during ingestion
    lookup_query = """
    MATCH (r:Request {request_id: $request_id, project_id: $project_id})
    RETURN r.uuid as uuid
    """

    async with graphiti.driver.session() as session:
        result = await session.run(lookup_query, {
            "request_id": request_id,
            "project_id": project_id
        })
        record = await result.single()
        if record and record["uuid"]:
            existing_uuid = record["uuid"]
        else:
            existing_uuid = None

    metadata = {
        "entity_type": "request",
        "project_id": project_id,
        "request_id": request_id,
        "chat_id": chat_meta.chat_id,
        "base_chat_id": chat_meta.base_chat_id,
        "request_attempt_id": chat_meta.request_attempt_id,
        "chat_mode": chat_meta.chat_mode,
        "model": model,
        "total_tokens": total_tokens,
        "expires_at": expires_at.isoformat() + 'Z'
    }

    if existing_uuid:
        update_query = """
        MATCH (r:Request {uuid: $uuid})
        SET r += $metadata
        RETURN r.uuid as uuid
        """
        async with graphiti.driver.session() as session:
            await session.run(update_query, {
                "uuid": existing_uuid,
                "metadata": metadata
            })
        return existing_uuid

    return await _create_entity_via_episode(
        graphiti,
        name=f"Request {chat_meta.chat_id}",
        summary=f"Conversation request in {chat_meta.chat_mode} mode with {total_tokens} tokens",
        project_id=project_id,
        timestamp=timestamp,
        metadata=metadata,
        labels=["Request"]
    )


async def create_message_node(
    graphiti: Graphiti,
    request_uuid: str,
    request_id: str,
    message: MessagePayload,
    timestamp: str,
    project_id: str
) -> str:
    """Create Message entity node."""
    expires_at = datetime.fromisoformat(timestamp.replace('Z', '')) + timedelta(days=cache.get_conversation_ttl_days())

    entity_uuid = await _create_entity_node(
        graphiti,
        ['Message'],
        {
            "name": f"Message {message.role} seq{message.sequence}",
            "summary": message.content_summary[:200] if message.content_summary else None,
            "group_id": project_id,
            "entity_type": 'message',
            "request_id": request_id,
            "role": message.role,
            "content_summary": message.content_summary,
            "content_hash": message.content_hash,
            "sequence": message.sequence,
            "prompt_tokens": message.prompt_tokens,
            "completion_tokens": message.completion_tokens,
            "total_tokens": message.total_tokens,
            "created_at": timestamp,
            "expires_at": expires_at.isoformat() + 'Z'
        }
    )

    # Link request -> message
    await create_relationship(
        graphiti,
        from_uuid=request_uuid,
        to_uuid=entity_uuid,
        relationship_type='CONTAINS_MESSAGE',
        properties={
            'sequence': message.sequence,
            'role': message.role
        }
    )

    return entity_uuid


async def create_context_file_node(
    graphiti: Graphiti,
    request_uuid: str,
    request_id: str,
    context_file: ContextFilePayload,
    timestamp: str,
    project_id: str
) -> str:
    """Create ContextFile entity node."""
    expires_at = datetime.fromisoformat(timestamp.replace('Z', '')) + timedelta(days=cache.get_conversation_ttl_days())
    symbols_str = ', '.join(context_file.symbols) if context_file.symbols else 'none'

    entity_uuid = await _create_entity_node(
        graphiti,
        ['ContextFile'],
        {
            "name": f"Context: {context_file.file_path}",
            "summary": f"Context file from {context_file.source} with usefulness {context_file.usefulness:.2f}, symbols: {symbols_str}",
            "group_id": project_id,
            "entity_type": 'context_file',
            "request_id": request_id,
            "file_path": context_file.file_path,
            "line_start": context_file.line_start,
            "line_end": context_file.line_end,
            "usefulness": context_file.usefulness,
            "source": context_file.source,
            "symbols": context_file.symbols,
            "content_hash": context_file.content_hash,
            "language": context_file.language,
            "created_at": timestamp,
            "expires_at": expires_at.isoformat() + 'Z'
        }
    )

    # Link request -> context file
    await create_relationship(
        graphiti,
        from_uuid=request_uuid,
        to_uuid=entity_uuid,
        relationship_type='USES_CONTEXT',
        properties={
            'usefulness': context_file.usefulness,
            'source': context_file.source
        }
    )

    return entity_uuid


async def create_tool_call_node(
    graphiti: Graphiti,
    request_uuid: str,
    request_id: str,
    tool_call: ToolCallPayload,
    timestamp: str,
    project_id: str
) -> str:
    """Create ToolCall entity node."""
    expires_at = datetime.fromisoformat(timestamp.replace('Z', '')) + timedelta(days=cache.get_conversation_ttl_days())

    entity_uuid = await _create_entity_node(
        graphiti,
        ['ToolCall'],
        {
            "name": f"Tool: {tool_call.tool_name}",
            "summary": f"Tool {tool_call.tool_name} executed with status {tool_call.status} in {tool_call.execution_time_ms}ms",
            "group_id": project_id,
            "entity_type": 'tool_call',
            "request_id": request_id,
            "tool_call_id": tool_call.tool_call_id,
            "tool_name": tool_call.tool_name,
            "arguments_hash": tool_call.arguments_hash,
            "status": tool_call.status,
            "execution_time_ms": tool_call.execution_time_ms,
            "diff_chunk_id": tool_call.diff_chunk_id,
            "created_at": timestamp,
            "expires_at": expires_at.isoformat() + 'Z'
        }
    )

    await create_relationship(
        graphiti,
        from_uuid=request_uuid,
        to_uuid=entity_uuid,
        relationship_type='INVOKES_TOOL',
        properties={
            'status': tool_call.status,
            'execution_time_ms': tool_call.execution_time_ms
        }
    )

    return entity_uuid


async def create_checkpoint_node(
    graphiti: Graphiti,
    request_uuid: str,
    request_id: str,
    checkpoint: CheckpointPayload,
    timestamp: str,
    project_id: str
) -> str:
    """Create Checkpoint entity node."""
    expires_at = datetime.fromisoformat(timestamp.replace('Z', '')) + timedelta(days=cache.get_conversation_ttl_days())

    entity_uuid = await _create_entity_node(
        graphiti,
        ['Checkpoint'],
        {
            "name": f"Checkpoint {checkpoint.checkpoint_id}",
            "summary": f"Git checkpoint {checkpoint.checkpoint_id} parent: {checkpoint.parent_checkpoint}",
            "group_id": project_id,
            "entity_type": 'checkpoint',
            "request_id": request_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "parent_checkpoint": checkpoint.parent_checkpoint,
            "workspace_dir": checkpoint.workspace_dir,
            "git_hash": checkpoint.git_hash,
            "created_at": timestamp,
            "expires_at": expires_at.isoformat() + 'Z'
        }
    )

    await create_relationship(
        graphiti,
        from_uuid=request_uuid,
        to_uuid=entity_uuid,
        relationship_type='HAS_CHECKPOINT',
        properties={
            'parent_checkpoint': checkpoint.parent_checkpoint
        }
    )

    return entity_uuid


async def create_code_change_node(
    graphiti: Graphiti,
    request_uuid: str,
    request_id: str,
    code_change: CodeChangeMetadata,
    timestamp: str,
    project_id: str
) -> str:
    """Create a CodeChange entity and connect it to the related CodeFile."""
    expires_at = datetime.fromisoformat(timestamp.replace('Z', '')) + timedelta(days=cache.get_conversation_ttl_days())
    metadata = code_change.model_dump()

    entity_uuid = await _create_entity_node(
        graphiti,
        ['CodeChange'],
        {
            "name": metadata.get("name") or f"CodeChange {metadata.get('file_path', 'unknown')}",
            "summary": metadata.get("change_summary") or metadata.get("summary") or metadata.get("description") or metadata.get("name") or "Code change",
            "group_id": project_id,
            "entity_type": 'code_change',
            "request_id": request_id,
            "file_path": metadata.get('file_path'),
            "change_type": metadata.get('change_type'),
            "change_summary": metadata.get('change_summary') or metadata.get('summary'),
            "severity": metadata.get('severity'),
            "code_before_hash": metadata.get('code_before_hash'),
            "code_after_hash": metadata.get('code_after_hash'),
            "lines_added": metadata.get('lines_added'),
            "lines_removed": metadata.get('lines_removed'),
            "diff_summary": metadata.get('diff_summary') or metadata.get('change_summary'),
            "language": metadata.get('language'),
            "imports": metadata.get('imports'),
            "created_at": timestamp,
            "expires_at": expires_at.isoformat() + 'Z'
        }
    )

    await create_relationship(
        graphiti,
        from_uuid=request_uuid,
        to_uuid=entity_uuid,
        relationship_type='APPLIED_CODE_CHANGE',
        properties={
            'change_type': metadata.get('change_type'),
            'severity': metadata.get('severity')
        }
    )

    file_path = metadata.get('file_path')
    if file_path:
        file_uuid = await find_or_create_file_entity(
            graphiti,
            file_path=file_path,
            project_id=project_id,
            language=metadata.get('language'),
            module_name=file_path.split('/')[0] if '/' in file_path else None
        )

        await create_relationship(
            graphiti,
            from_uuid=file_uuid,
            to_uuid=entity_uuid,
            relationship_type='MODIFIED_IN',
            properties={
                'timestamp': metadata.get('timestamp'),
                'lines_changed': (metadata.get('lines_added') or 0) + (metadata.get('lines_removed') or 0)
            }
        )

    # Link code change back to originating tool call when possible
    tool_call_id = metadata.get('tool_call_id') or metadata.get('diff_chunk_id')
    if tool_call_id:
        link_query = """
        MATCH (tc:ToolCall {tool_call_id: $tool_call_id})
        MATCH (cc:CodeChange {uuid: $code_change_uuid})
        MERGE (tc)-[rel:GENERATED_DIFF]->(cc)
        SET rel.timestamp = $timestamp
        RETURN rel
        """
        async with graphiti.driver.session() as session:
            await session.run(link_query, {
                "tool_call_id": tool_call_id,
                "code_change_uuid": entity_uuid,
                "timestamp": metadata.get('timestamp')
            })

    return entity_uuid


async def search_requests(
    graphiti: Graphiti,
    project_id: str,
    chat_id: Optional[str] = None,
    days_ago: int = 7
) -> List[Dict[str, Any]]:
    """
    Search conversation requests
    
    Args:
        project_id: Project ID filter
        chat_id: Optional chat ID filter
        days_ago: Time window in days
    
    Returns:
        List of request entities with metadata
    """
    cutoff = datetime.utcnow() - timedelta(days=days_ago)
    
    # Build query
    filter_conditions = [
        "e.project_id = $project_id",
        "e.entity_type = 'conversation'",
        "e.created_at >= datetime($cutoff)",
        "(e.expires_at IS NULL OR datetime(e.expires_at) > datetime())"
    ]
    
    filter_params = {
        "project_id": project_id,
        "cutoff": cutoff.isoformat()
    }
    
    if chat_id:
        filter_conditions.append("e.chat_id = $chat_id")
        filter_params["chat_id"] = chat_id
    
    where_clause = " AND ".join(filter_conditions)
    query = f"""
    MATCH (e:Entity)
    WHERE {where_clause}
    RETURN e.uuid as uuid,
           e.request_id as request_id,
           e.chat_id as chat_id,
           e.chat_mode as chat_mode,
           e.model as model,
           e.total_tokens as total_tokens,
           e.created_at as created_at
    ORDER BY e.created_at DESC
    """
    
    results = []
    async with graphiti.driver.session() as session:
        result = await session.run(query, filter_params)
        async for record in result:
            results.append({
                "uuid": record["uuid"],
                "request_id": record["request_id"],
                "chat_id": record["chat_id"],
                "chat_mode": record["chat_mode"],
                "model": record["model"],
                "total_tokens": record["total_tokens"],
                "created_at": str(record["created_at"])
            })
    
    return results


async def get_conversation_flow(
    graphiti: Graphiti,
    request_id: str
) -> Dict[str, Any]:
    """
    Get conversation entity by request_id
    
    Args:
        request_id: Request ID
    
    Returns:
        Dict with conversation entity data
    """
    query = """
    MATCH (e:Entity {request_id: $request_id, entity_type: 'conversation'})
    RETURN e
    """
    
    async with graphiti.driver.session() as session:
        result = await session.run(query, {"request_id": request_id})
        record = await result.single()
        
        if not record or not record["e"]:
            return None
        
        entity = dict(record["e"])
        
        return {
            "request_id": entity.get("request_id"),
            "chat_id": entity.get("chat_id"),
            "chat_mode": entity.get("chat_mode"),
            "model": entity.get("model"),
            "total_tokens": entity.get("total_tokens"),
            "message_count": entity.get("message_count"),
            "context_file_count": entity.get("context_file_count"),
            "tool_call_count": entity.get("tool_call_count"),
            "created_at": str(entity.get("created_at")),
            "expires_at": entity.get("expires_at"),
            "summary": entity.get("summary")
        }


async def get_context_file_stats(
    graphiti: Graphiti,
    project_id: str,
    days_ago: int = 7
) -> List[Dict[str, Any]]:
    """
    Get context file usage statistics
    
    Returns:
        List of files with usage count and average usefulness
    """
    cutoff = datetime.utcnow() - timedelta(days=days_ago)
    
    query = """
    MATCH (cf:Entity {project_id: $project_id, entity_type: 'context_file'})
    WHERE cf.created_at >= datetime($cutoff)
      AND (cf.expires_at IS NULL OR datetime(cf.expires_at) > datetime())
    WITH cf.file_path as file_path,
         cf.source as source,
         count(*) as usage_count,
         avg(cf.usefulness) as avg_usefulness,
         collect(cf.symbols) as all_symbols
    RETURN file_path, source, usage_count, avg_usefulness, all_symbols
    ORDER BY usage_count DESC, avg_usefulness DESC
    LIMIT 20
    """
    
    results = []
    async with graphiti.driver.session() as session:
        result = await session.run(query, {
            "project_id": project_id,
            "cutoff": cutoff.isoformat()
        })
        async for record in result:
            results.append({
                "file_path": record["file_path"],
                "source": record["source"],
                "usage_count": record["usage_count"],
                "avg_usefulness": record["avg_usefulness"],
                "symbols": record["all_symbols"]
            })
    
    return results


async def get_tool_statistics(
    graphiti: Graphiti,
    days_ago: int = 7
) -> List[Dict[str, Any]]:
    """
    Get tool call statistics
    
    Returns:
        List of tools with success rates and performance metrics
    """
    cutoff = datetime.utcnow() - timedelta(days=days_ago)
    
    query = """
    MATCH (tc:Entity {entity_type: 'tool_call'})
    WHERE tc.created_at >= datetime($cutoff)
      AND (tc.expires_at IS NULL OR datetime(tc.expires_at) > datetime())
    WITH tc.tool_name as tool_name,
         count(*) as total_calls,
         sum(CASE WHEN tc.status = 'success' THEN 1 ELSE 0 END) as successful_calls,
         avg(tc.execution_time_ms) as avg_execution_time
    RETURN tool_name,
           total_calls,
           successful_calls,
           (successful_calls * 100.0 / total_calls) as success_rate,
           avg_execution_time
    ORDER BY total_calls DESC
    """
    
    results = []
    async with graphiti.driver.session() as session:
        result = await session.run(query, {"cutoff": cutoff.isoformat()})
        async for record in result:
            results.append({
                "tool_name": record["tool_name"],
                "total_calls": record["total_calls"],
                "successful_calls": record["successful_calls"],
                "success_rate": record["success_rate"],
                "avg_execution_time": record["avg_execution_time"]
            })
    
    return results
