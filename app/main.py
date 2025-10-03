# app/main.py
import asyncio
import os
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from app.graph import get_graphiti
from app.graph import _graphiti  # for reset endpoint
from app.schemas import (
    IngestText, IngestMessage, IngestJSON, SearchRequest,
    IngestCodeChange, IngestCodeContext, SearchCodeRequest,
    ShortTermMemoryRequest, ShortTermMemorySearchRequest
)
from app.cache import (
    cached_with_ttl, cache_search_result, memory_cache, 
    invalidate_search_cache, invalidate_node_cache, get_cache_metrics
)

from app.graphiti_integration import enable_global_openai_tracking
from app.graphiti_token_tracker import get_global_tracker
from app.graphiti_estimator import estimate_and_track
from app.short_term_storage import get_storage
from app.file_upload_handler import get_file_upload_handler
from app.stm_to_neo4j import import_stm_json_content
from app.stm_to_neo4j import import_stm_json_content

enable_global_openai_tracking()
app = FastAPI(title="Graphiti Memory Layer")

@app.post("/ingest/text")
async def ingest_text(payload: IngestText, graphiti=Depends(get_graphiti)):
    ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Ingesting text with group_id: {payload.group_id}")
    
    ep = await graphiti.add_episode(
        name=payload.name,
        episode_body=payload.text,
        source=EpisodeType.text,
        source_description=payload.source_description,
        reference_time=ts,
        group_id=payload.group_id,
    )
    
    # ESTIMATE token usage for this episode
    token_estimate = estimate_and_track(
        episode_id=payload.name,
        episode_body=payload.text,
        model="gpt-4o-mini"
    )
    
    # Invalidate search cache khi có dữ liệu mới
    invalidate_search_cache()
    
    return {
        "episode_id": ep.id if hasattr(ep, "id") else payload.name,
        "group_id": payload.group_id,
        "name": payload.name,
        "token_estimate": token_estimate
    }

@app.post("/ingest/message")
async def ingest_message(payload: IngestMessage, graphiti=Depends(get_graphiti)):
    tracker = get_global_tracker()
    tracker.set_episode_context(payload.name)
    
    try:
        ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
        body = "\n".join(payload.messages)  # yêu cầu dạng "speaker: message" theo doc
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Ingesting message with group_id: {payload.group_id}, name: {payload.name}")
        
        ep = await graphiti.add_episode(
            name=payload.name,
            episode_body=body,
            source=EpisodeType.message,
            source_description=payload.source_description,
            reference_time=ts,
            group_id=payload.group_id,
        )
        
        # Invalidate search cache khi có dữ liệu mới
        invalidate_search_cache()
        
        return {
            "episode_id": ep.id if hasattr(ep, "id") else payload.name,
            "group_id": payload.group_id,
            "name": payload.name
        }
    finally:
        tracker.clear_episode_context()

# removed duplicate old JSON ingest using payload.json

@app.post("/search")
async def search(req: SearchRequest, graphiti=Depends(get_graphiti)):
    import logging
    from openai import OpenAI
    from app.prompts import format_query_translation_prompt, PROMPT_CONFIG
    
    logger = logging.getLogger(__name__)
    
    # Kiểm tra cache trước
    cache_key = cache_search_result(req.query, req.focal_node_uuid, req.group_id)
    cached_result = memory_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Auto-translate non-English queries to English for better semantic search
    search_query = req.query
    try:
        # Detect if query is non-English (simple heuristic: contains non-ASCII)
        if any(ord(char) > 127 for char in req.query):
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                client = OpenAI(api_key=openai_key)
                trans_prompt = format_query_translation_prompt(req.query)
                trans_config = PROMPT_CONFIG.get("translation", {})
                
                translation = client.chat.completions.create(
                    model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": trans_prompt}],
                    temperature=trans_config.get("temperature", 0.2),
                    max_tokens=trans_config.get("max_tokens", 100),
                )
                search_query = translation.choices[0].message.content.strip()
                logger.info(f"Translated query: '{req.query}' → '{search_query}'")
    except Exception as e:
        logger.warning(f"Translation failed, using original query: {e}")
        search_query = req.query

    # Hybrid search; nếu có focal_node_uuid sẽ ưu tiên kết quả gần node đó
    if req.focal_node_uuid:
        results = await graphiti.search(search_query, req.focal_node_uuid)
    else:
        results = await graphiti.search(search_query)

    # Chuẩn hoá đầu ra (ví dụ edges → fact/plaintext)
    def normalize(item):
        import logging
        logger = logging.getLogger(__name__)
        
        # item có thể là edge/node hoặc dict; ưu tiên các trường id phổ biến
        if isinstance(item, dict):
            txt = item.get("fact") or item.get("text") or item.get("name") or str(item)
            # For edges, prefer source_node_uuid over edge uuid
            ident = (
                item.get("source_node_uuid")  # Entity UUID (for EntityEdge)
                or item.get("uuid")  # Edge/Node UUID
                or item.get("node_uuid")
                or item.get("edge_id")
                or item.get("id")
            )
            grp_id = item.get("group_id") or item.get("groupId")
        else:
            txt = getattr(item, "fact", None) or getattr(item, "text", None) or getattr(item, "name", None) or str(item)
            # For EntityEdge objects, use source_node_uuid (the actual entity)
            ident = (
                getattr(item, "source_node_uuid", None)  # Entity UUID (for EntityEdge)
                or getattr(item, "uuid", None)  # Edge/Node UUID
                or getattr(item, "node_uuid", None)
                or getattr(item, "edge_id", None)
                or getattr(item, "id", None)
            )
            grp_id = getattr(item, "group_id", None) or getattr(item, "groupId", None)
        
        # Debug logging
        logger.info(f"Normalize: type={type(item).__name__}, text={txt[:50] if txt else 'N/A'}, id={ident}, group_id={grp_id}")
        
        if not grp_id:
            logger.warning(f"Search result missing group_id: {type(item)} - {txt[:50] if txt else 'N/A'}")
        if not ident:
            logger.warning(f"Search result missing ID: {type(item)} - {txt[:50] if txt else 'N/A'}, item_keys={list(item.keys()) if isinstance(item, dict) else dir(item)}")
        
        return {"text": txt, "id": ident, "group_id": grp_id}

    # Normalize then deduplicate and filter self-echoes of the query
    normalized = [normalize(r) for r in results]

    # If group_id filtering is requested but results don't have group_id, query Neo4j directly
    if req.group_id:
        missing_group_ids = [item for item in normalized if not item.get("group_id")]
        
        if missing_group_ids:
            # Fetch group_ids from Neo4j for items missing them
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Fetching group_ids from Neo4j for {len(missing_group_ids)} items")
            
            # Create a map of uuid -> group_id from Neo4j
            uuids = [item["id"] for item in missing_group_ids if item.get("id")]
            if uuids:
                query = """
                MATCH (n)
                WHERE n.uuid IN $uuids
                RETURN n.uuid as uuid, n.group_id as group_id
                """
                group_id_map = {}
                async with graphiti.driver.session() as session:
                    result = await session.run(query, {"uuids": uuids})
                    async for record in result:
                        if record["group_id"]:
                            group_id_map[record["uuid"]] = record["group_id"]
                
                # Update normalized items with fetched group_ids
                for item in normalized:
                    if not item.get("group_id") and item.get("id") in group_id_map:
                        item["group_id"] = group_id_map[item["id"]]
        
        # Now filter by group_id
        normalized = [item for item in normalized if item.get("group_id") == req.group_id]

    seen = set()
    deduped = []
    for item in normalized:
        key = item.get("id") or item.get("text")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    # Filter out items that are just the query echoed back
    q = (req.query or "").strip()
    q_variants = {q, f"user: {q}", f"assistant: {q}"}
    filtered = [it for it in deduped if (it.get("text") or "").strip() not in q_variants]

    # Cache kết quả với TTL 30 phút
    result = {"results": filtered}
    memory_cache.set(cache_key, result, ttl=1800)
    
    return result
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "graphiti-memory-layer",
        "endpoints": {
            "/ingest/text": "POST - Ingest plain text",
            "/ingest/message": "POST - Ingest conversation messages",
            "/ingest/code-context": "POST - Ingest code conversation metadata (Phase 3)",
            "/search": "POST - Search knowledge graph",
            "/search/code": "POST - Search code memories with filters (Phase 3)",
            "/export/{group_id}": "GET - Export conversation to JSON",
            "/stats/{project_id}": "GET - Get project statistics (Phase 3)",
            "/admin/cleanup": "POST - Manually cleanup expired memories (Phase 3)",
            "/short-term/save": "POST - Save message to short term memory",
            "/short-term/search": "POST - Search short term memory",
            "/short-term/message/{message_id}": "GET - Get short term message by ID",
            "/short-term/message/{message_id}": "DELETE - Delete short term message",
                    "/short-term/stats/{project_id}": "GET - Get short term memory stats",
                    "/short-term/cleanup": "POST - Cleanup expired short term messages",
                    "/short-term/health": "GET - Check short term memory health",
                    "/upload/file": "POST - Upload file code and extract changes",
                    "/upload/code-changes": "POST - Upload code changes payload from IDE",
                    "/upload/text-content": "POST - Upload file content as text"
        }
    }

@app.get("/export/{group_id}")
async def export_conversation(group_id: str, graphiti=Depends(get_graphiti)):
    """Export conversation to JSON for backup/sharing"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Query all entities for this group
        query_entities = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id
        RETURN e.uuid AS uuid,
               e.name AS name,
               e.summary AS summary,
               e.created_at AS created_at
        ORDER BY e.created_at ASC
        """
        
        entities = []
        
        async with graphiti.driver.session() as session:
            result = await session.run(query_entities, {"group_id": group_id})
            async for record in result:
                entities.append({
                    "uuid": record["uuid"],
                    "name": record["name"],
                    "summary": record["summary"],
                    "created_at": str(record["created_at"]) if record["created_at"] else None,
                })
        
        export_data = {
            "group_id": group_id,
            "exported_at": datetime.utcnow().isoformat(),
            "entity_count": len(entities),
            "entities": entities,
            "version": "1.0"
        }
        
        logger.info(f"Exported {group_id}: {len(entities)} entities")
        
        # Return with proper UTF-8 encoding (no Unicode escaping)
        import json
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        # Encode to UTF-8 bytes to preserve Vietnamese characters
        return Response(
            content=json_str.encode('utf-8'),
            media_type="application/json; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/config/neo4j")
async def get_neo4j_config():
    return {
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USER": os.getenv("NEO4J_USER"),
        "NEO4J_DATABASE": os.getenv("NEO4J_DATABASE"),
    }

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

@app.post("/ingest/json")
async def ingest_json(payload: IngestJSON, graphiti=Depends(get_graphiti)):
    tracker = get_global_tracker()
    tracker.set_episode_context(payload.name)
    
    try:
        ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
        ep = await graphiti.add_episode(
            name=payload.name,
            episode_body=payload.data,   # <<< đổi từ payload.json -> payload.data
            source=EpisodeType.json,
            source_description=payload.source_description,
            reference_time=ts,
            group_id=payload.group_id,
        )
        
        # Invalidate search cache khi có dữ liệu mới
        invalidate_search_cache()
        
        return {"episode_id": getattr(ep, "id", payload.name)}
    finally:
        tracker.clear_episode_context()

# Cache management endpoints
@app.get("/cache/stats")
async def get_cache_stats():
    """Lấy thống kê cache"""
    return get_cache_metrics()

@app.post("/cache/clear")
async def clear_cache():
    """Xóa toàn bộ cache"""
    from app.cache import invalidate_all_cache
    invalidate_all_cache()
    return {"message": "Cache cleared successfully"}

@app.post("/cache/clear-search")
async def clear_search_cache():
    """Xóa chỉ search cache"""
    invalidate_search_cache()
    return {"message": "Search cache cleared successfully"}

@app.post("/cache/clear-node/{node_uuid}")
async def clear_node_cache(node_uuid: str):
    """Xóa cache của node cụ thể"""
    invalidate_node_cache(node_uuid)
    return {"message": f"Cache for node {node_uuid} cleared successfully"}

@app.get("/cache/health")
async def cache_health():
    """Kiểm tra sức khỏe cache"""
    stats = get_cache_metrics()
    return {
        "status": "healthy" if stats["active_entries"] > 0 else "empty",
        "stats": stats
    }

@app.post("/config/reload-neo4j")
async def reload_neo4j_config():
    # Đặt lại singleton để lần gọi tiếp theo tạo kết nối mới theo .env
    from app.graph import reset_graphiti_cache
    reset_graphiti_cache()
    return {"message": "Neo4j config reloaded. Restart next request will create a new connection."}

@app.get("/debug/all-entities")
async def debug_all_entities(limit: int = 50, graphiti=Depends(get_graphiti)):
    """Debug: Show ALL entities regardless of project_id"""
    try:
        query = """
        MATCH (e:Entity)
        RETURN e.uuid as uuid, 
               e.name as name, 
               e.project_id as project_id,
               e.group_id as group_id,
               e.expires_at as expires_at,
               e.created_at as created_at
        ORDER BY e.created_at DESC
        LIMIT $limit
        """
        
        entities = []
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"limit": limit})
            async for record in result:
                entities.append({
                    "uuid": record["uuid"],
                    "name": record["name"],
                    "project_id": record["project_id"],
                    "group_id": record["group_id"],
                    "expires_at": str(record["expires_at"]) if record["expires_at"] else None,
                    "created_at": str(record["created_at"]) if record["created_at"] else None
                })
        
        return {
            "total": len(entities),
            "entities": entities
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/episodes/{group_id}")
async def debug_episodes_by_group(group_id: str, graphiti=Depends(get_graphiti)):
    """Debug endpoint to check entities in Neo4j by group_id (group_id is stored in Entity nodes, not EpisodeNode)"""
    try:
        # Query Neo4j directly for Entity nodes with this group_id
        query = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id
        RETURN e.uuid as uuid, e.name as name, e.group_id as group_id, 
               e.summary as summary, e.created_at as created_at
        ORDER BY e.created_at DESC
        LIMIT 50
        """
        
        records = []
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"group_id": group_id})
            async for record in result:
                records.append({
                    "uuid": record["uuid"],
                    "name": record["name"],
                    "group_id": record["group_id"],
                    "summary": record["summary"][:200] if record["summary"] else None,
                    "created_at": str(record["created_at"]).split("T")[0]
                })
        # Query Neo4j for relationships between entities with this group_id
        query = """
        MATCH (e1:Entity)-[r]-(e2:Entity)
        WHERE e1.group_id = $group_id
        RETURN e1.name as source, type(r) as rel_type, 
               properties(r) as rel_props, e2.name as target,
               e1.uuid as source_uuid, e2.uuid as target_uuid
        LIMIT 50
        """
        
        records = []
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"group_id": group_id})
            async for record in result:
                records.append({
                    "source": record["source"],
                    "relationship": record["rel_type"],
                    "properties": record["rel_props"],
                    "target": record["target"],
                    "source_uuid": record["source_uuid"],
                    "target_uuid": record["target_uuid"]
                })
        
        return {
            "group_id": group_id,
            "count": len(records),
            "relationships": records
        }
    except Exception as e:
        return {"error": str(e), "group_id": group_id}

# =============================================================================
# CODE CHANGE ENDPOINTS - Simple API for UI
# =============================================================================

@app.post("/ingest/code")
async def ingest_code_change(payload: IngestCodeChange, graphiti=Depends(get_graphiti)):
    """
    Ingest simple code change with LLM importance scoring
    
    Returns:
        {
            "status": "success",
            "episode_uuid": "...",
            "importance_score": 0.85,
            "category": "bug_fix"
        }
    """
    import logging
    from graphiti_core.nodes import EpisodeType
    from app.importance import get_scorer
    
    logger = logging.getLogger(__name__)
    tracker = get_global_tracker()
    tracker.set_episode_context(payload.name)
    
    try:
        # Score importance with LLM
        scorer = get_scorer()
        score_result = await scorer.score_code_change(
            change_type=payload.change_type,
            summary=payload.summary,
            severity=payload.severity,
            file_path=payload.file_path
        )
        
        importance_score = score_result.get("score", 0.5)
        category = score_result.get("category", "unknown")
        
        logger.info(f"Code change scored: {importance_score} ({category})")
        
        # Add to Graphiti
        ts = datetime.utcnow()
        
        episode_result = await graphiti.add_episode(
            name=payload.name,
            episode_body=f"{payload.change_type}: {payload.summary}",
            source=EpisodeType.text,
            source_description=f"code_change_{payload.change_type}",
            reference_time=ts,
            group_id=payload.project_id
        )
        
        # AddEpisodeResults has episode_uuid attribute (not uuid)
        episode_uuid = getattr(episode_result, 'episode_uuid', None) or getattr(episode_result, 'uuid', 'unknown')
        logger.info(f"Episode created: {episode_uuid}")
        
        # Invalidate search cache (sync function)
        from app.cache import invalidate_search_cache
        invalidate_search_cache()
        
        return {
            "status": "success",
            "episode_uuid": str(episode_uuid),
            "importance_score": importance_score,
            "category": category,
            "reasoning": score_result.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"Failed to ingest code change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest code change: {str(e)}")
    finally:
        tracker.clear_episode_context()


# =============================================================================
# CODE CONTEXT ENDPOINTS - Phase 3
# =============================================================================

@app.post("/ingest/code-context")
async def ingest_code_context(payload: IngestCodeContext, graphiti=Depends(get_graphiti)):
    """
    Ingest code conversation metadata (NOT actual code!)
    
    Stores metadata about code changes with 48-hour TTL.
    """
    import logging
    import json
    from app.graph import add_episode_with_ttl, add_code_metadata
    
    logger = logging.getLogger(__name__)
    tracker = get_global_tracker()
    tracker.set_episode_context(payload.name)
    
    # DEBUG: Check if payload contains DateTime objects
    try:
        _ = json.dumps(payload.dict())
        logger.info("✓ Payload serialization OK")
    except TypeError as te:
        logger.error(f"✗ Payload has DateTime: {te}")
        raise HTTPException(status_code=400, detail=f"Invalid datetime in payload: {str(te)}")
    
    try:
        logger.info("=== START INGEST ===")
        
        # Parse reference time
        ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
        logger.info(f"Parsed reference_time: {type(ts)} = {ts}")
        
        # Validate project_id
        if not payload.project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        
        # Validate summary (required for embeddings!)
        if not payload.summary or len(payload.summary.strip()) == 0:
            raise HTTPException(status_code=400, detail="summary is required and cannot be empty")
        
        logger.info(f"Ingesting code context for project {payload.project_id}: {payload.name}")
        
        # Add episode using Graphiti directly (not via add_episode_with_ttl)
        from graphiti_core.nodes import EpisodeType
        
        episode = await graphiti.add_episode(
            name=payload.name,
            episode_body=payload.summary,
            source=EpisodeType.text,
            source_description="code_conversation",
            reference_time=ts,
            group_id=payload.project_id
        )
        
        logger.info(f"Episode created, waiting for entities to be created...")
        
        # Wait for Graphiti to process and create entities
        import asyncio
        await asyncio.sleep(2)  # Give Graphiti time to create entities
        
        # Query Neo4j to find entities created for this group
        query = """
        MATCH (e:Entity {group_id: $group_id})
        WHERE e.created_at >= datetime($reference_time)
        RETURN e.uuid as uuid
        ORDER BY e.created_at DESC
        LIMIT 10
        """
        
        entity_uuids = []
        async with graphiti.driver.session() as session:
            result = await session.run(query, {
                "group_id": payload.project_id,
                "reference_time": (ts - __import__('datetime').timedelta(seconds=10)).isoformat()
            })
            async for record in result:
                entity_uuids.append(record["uuid"])
        
        logger.info(f"Found {len(entity_uuids)} entities for group {payload.project_id}")
        
        # Use first entity UUID
        entity_uuid = entity_uuids[0] if entity_uuids else None
        
        if not entity_uuid:
            logger.warning(f"No entity UUID found for group {payload.project_id}")
        
        # Set TTL and project_id for ALL found entities
        if entity_uuids:
            from app.graph import _set_entity_ttl
            from datetime import timedelta as td
            expires_at_dt = ts + td(hours=48)
            
            for uuid in entity_uuids:
                await _set_entity_ttl(graphiti, uuid, expires_at_dt, payload.project_id)
                logger.info(f"Set TTL for entity {uuid}")
        
        # Add code-specific metadata to first entity
        if entity_uuid:
            logger.info("Building metadata dict...")
            metadata_dict = {}
            
            # Extract metadata from payload
            meta = payload.metadata
            logger.info(f"Meta timestamp type: {type(meta.timestamp)}")
            if meta.file_path:
                metadata_dict["file_path"] = meta.file_path
            if meta.function_name:
                metadata_dict["function_name"] = meta.function_name
            if meta.line_start is not None:
                metadata_dict["line_start"] = meta.line_start
            if meta.line_end is not None:
                metadata_dict["line_end"] = meta.line_end
            
            metadata_dict["change_type"] = meta.change_type
            metadata_dict["change_summary"] = meta.change_summary
            # Ensure timestamp is string (it should already be from schema, but ensure it)
            metadata_dict["timestamp"] = str(meta.timestamp) if meta.timestamp else None
            
            if meta.severity:
                metadata_dict["severity"] = meta.severity
            
            # Code references
            if meta.code_before_ref:
                metadata_dict["code_before_id"] = meta.code_before_ref.code_id
                metadata_dict["code_before_hash"] = meta.code_before_ref.code_hash
                metadata_dict["language"] = meta.code_before_ref.language
            
            if meta.code_after_ref:
                metadata_dict["code_after_id"] = meta.code_after_ref.code_id
                metadata_dict["code_after_hash"] = meta.code_after_ref.code_hash
                if not metadata_dict.get("language"):
                    metadata_dict["language"] = meta.code_after_ref.language
            
            # Diff info
            if meta.lines_added is not None:
                metadata_dict["lines_added"] = meta.lines_added
            if meta.lines_removed is not None:
                metadata_dict["lines_removed"] = meta.lines_removed
            if meta.diff_summary:
                metadata_dict["diff_summary"] = meta.diff_summary
            
            # Git info
            if meta.git_commit:
                metadata_dict["git_commit"] = meta.git_commit
            
            # Add to entity
            try:
                result = await add_code_metadata(graphiti, entity_uuid, metadata_dict)
                logger.info(f"Added code metadata to entity {entity_uuid}")
                # Don't use the result - it might contain DateTime objects
                del result
            except Exception as meta_error:
                logger.error(f"Error adding metadata: {str(meta_error)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Continue anyway - metadata is optional
        
        # Invalidate cache
        invalidate_search_cache()
        
        logger.info("Preparing response...")
        
        # Calculate expiration and convert to string immediately
        from datetime import timedelta
        expires_dt = ts + timedelta(hours=48)
        expires_at_str = expires_dt.isoformat()
        if not expires_at_str.endswith('Z'):
            expires_at_str += "Z"
        
        # Build response with explicit type conversions
        episode_id_str = str(entity_uuid) if entity_uuid else str(payload.name)
        project_id_str = str(payload.project_id)
        name_str = str(payload.name)
        
        logger.info(f"Returning response...")
        
        # Return JSONResponse explicitly to avoid any serialization issues
        from fastapi.responses import JSONResponse
        return JSONResponse(content={
            "episode_id": episode_id_str,
            "project_id": project_id_str,
            "expires_at": expires_at_str,
            "name": name_str
        })
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        # If error message contains non-serializable objects, just use the exception type
        try:
            _ = json.dumps({"error": error_msg})
        except (TypeError, ValueError):
            error_msg = f"{type(e).__name__}: Serialization error"
            logger.error(f"Error ingesting code context (non-serializable): {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.error(f"Error ingesting code context: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest code context: {error_msg}")
    finally:
        tracker.clear_episode_context()

@app.post("/search/code")
async def search_code(req: SearchCodeRequest, graphiti=Depends(get_graphiti)):
    """
    Search code memories with strict project isolation and filters
    
    Returns only memories from the specified project that haven't expired.
    """
    import logging
    from datetime import timedelta
    
    logger = logging.getLogger(__name__)
    
    try:
        # Validate project_id (REQUIRED for isolation)
        if not req.project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        
        logger.info(f"Searching code in project {req.project_id}: {req.query}")
        
        # Step 1: Semantic search (no project filter yet)
        if req.focal_node_uuid:
            results = await graphiti.search(req.query, req.focal_node_uuid)
        else:
            results = await graphiti.search(req.query)
        
        # Step 2: Build Neo4j filter query
        filter_conditions = ["e.project_id = $project_id"]
        filter_params = {"project_id": req.project_id}
        
        # TTL filter (only active memories)
        filter_conditions.append("e.expires_at IS NOT NULL")
        filter_conditions.append("datetime(e.expires_at) > datetime()")
        
        # Time window filter
        if req.days_ago:
            cutoff = datetime.utcnow() - timedelta(days=req.days_ago)
            filter_conditions.append("e.created_at >= datetime($cutoff)")
            filter_params["cutoff"] = cutoff.isoformat()
        
        # File filter
        if req.file_filter:
            filter_conditions.append("e.file_path = $file_path")
            filter_params["file_path"] = req.file_filter
        
        # Function filter
        if req.function_filter:
            filter_conditions.append("e.function_name = $function_name")
            filter_params["function_name"] = req.function_filter
        
        # Change type filter
        if req.change_type_filter:
            filter_conditions.append("e.change_type = $change_type")
            filter_params["change_type"] = req.change_type_filter
        
        # Build complete query
        where_clause = " AND ".join(filter_conditions)
        query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        RETURN e.uuid as uuid,
               e.summary as summary,
               e.file_path as file_path,
               e.function_name as function_name,
               e.change_type as change_type,
               e.change_summary as change_summary,
               e.severity as severity,
               e.code_after_id as code_after_id,
               e.code_after_hash as code_after_hash,
               e.diff_summary as diff_summary,
               e.created_at as created_at
        """
        
        # Execute filter query
        valid_uuids = set()
        entity_data = {}
        
        async with graphiti.driver.session() as session:
            result = await session.run(query, filter_params)
            async for record in result:
                uuid = record["uuid"]
                valid_uuids.add(uuid)
                entity_data[uuid] = {
                    "file_path": record.get("file_path"),
                    "function_name": record.get("function_name"),
                    "change_type": record.get("change_type"),
                    "change_summary": record.get("change_summary"),
                    "severity": record.get("severity"),
                    "code_after_id": record.get("code_after_id"),
                    "code_after_hash": record.get("code_after_hash"),
                    "diff_summary": record.get("diff_summary"),
                    "created_at": str(record.get("created_at")) if record.get("created_at") else None
                }
        
        logger.info(f"Project filter: {len(valid_uuids)} valid entities for project {req.project_id}")
        
        # Step 3: Filter search results to only valid UUIDs
        filtered_results = []
        for item in results:
            # Extract UUID from search result
            if isinstance(item, dict):
                item_uuid = item.get("source_node_uuid") or item.get("uuid") or item.get("node_uuid")
            else:
                item_uuid = getattr(item, "source_node_uuid", None) or getattr(item, "uuid", None)
            
            if item_uuid in valid_uuids:
                # Get text from search result
                if isinstance(item, dict):
                    text = item.get("fact") or item.get("text") or item.get("summary") or str(item)
                else:
                    text = getattr(item, "fact", None) or getattr(item, "text", None) or getattr(item, "summary", None) or str(item)
                
                # Build result with metadata
                result_item = {
                    "text": text,
                    "id": item_uuid,
                    "project_id": req.project_id,
                }
                
                # Add entity data if available
                if item_uuid in entity_data:
                    result_item.update(entity_data[item_uuid])
                
                filtered_results.append(result_item)
        
        logger.info(f"Filtered to {len(filtered_results)} results matching all criteria")
        
        return {
            "results": filtered_results,
            "count": len(filtered_results),
            "project_id": req.project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching code: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/admin/cleanup")
async def manual_cleanup(graphiti=Depends(get_graphiti)):
    """
    Manually trigger cleanup of expired memories
    
    Deletes all entities past their 48-hour TTL.
    """
    import logging
    from app.graph import cleanup_expired_memories
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Manual cleanup triggered")
        deleted_count = await cleanup_expired_memories(graphiti)
        
        return {
            "deleted_count": deleted_count,
            "message": f"Successfully cleaned up {deleted_count} expired memories"
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/stats/{project_id}")
async def get_stats(project_id: str, graphiti=Depends(get_graphiti)):
    """
    Get statistics for a specific project
    
    Returns counts of memories, files, and change types.
    """
    import logging
    from app.graph import get_project_stats
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Getting stats for project {project_id}")
        stats = await get_project_stats(graphiti, project_id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# =============================================================================
# GRAPHITI TOKEN TRACKING ENDPOINTS
# =============================================================================

@app.get("/graphiti/tokens/stats")
async def get_graphiti_token_stats():
    """Get overall Graphiti token usage statistics"""
    tracker = get_global_tracker()
    return tracker.get_total_stats()

@app.get("/graphiti/tokens/operations")
async def get_graphiti_operations():
    """Get breakdown by Graphiti operation type"""
    tracker = get_global_tracker()
    return tracker.get_operation_breakdown()

@app.get("/graphiti/tokens/episode/{episode_id}")
async def get_graphiti_episode_stats(episode_id: str):
    """Get token statistics for a specific episode"""
    tracker = get_global_tracker()
    return tracker.get_episode_summary(episode_id)

@app.get("/graphiti/tokens/export")
async def export_graphiti_tokens():
    """Export complete Graphiti token tracking data"""
    tracker = get_global_tracker()
    return tracker.export_to_dict()

@app.get("/graphiti/tokens/summary")
async def get_graphiti_summary():
    """Get human-readable summary of Graphiti token usage"""
    tracker = get_global_tracker()
    return {"summary": tracker.get_summary_text()}

@app.get("/graphiti/entities/stats")
async def get_entity_stats(graphiti=Depends(get_graphiti)):
    """Get statistics about entities created by Graphiti"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Query for overall entity stats
        query_total = """
        MATCH (e:Entity)
        RETURN count(e) as total_entities,
               count(DISTINCT e.group_id) as unique_groups,
               count(DISTINCT e.name) as unique_entity_names
        """
        
        # Query for entities by group
        query_by_group = """
        MATCH (e:Entity)
        WHERE e.group_id IS NOT NULL
        RETURN e.group_id as group_id,
               count(e) as entity_count
        ORDER BY entity_count DESC
        LIMIT 10
        """
        
        # Query for top entities
        query_top_entities = """
        MATCH (e:Entity)
        RETURN e.name as name,
               e.summary as summary,
               e.group_id as group_id,
               e.created_at as created_at
        ORDER BY e.created_at DESC
        LIMIT 20
        """
        
        # Query for entities with relationships
        query_relationships = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]-()
        RETURN e.name as entity,
               count(r) as relationship_count
        ORDER BY relationship_count DESC
        LIMIT 10
        """
        
        total_stats = {}
        by_group = []
        top_entities = []
        top_connected = []
        
        async with graphiti.driver.session() as session:
            # Get total stats
            result = await session.run(query_total)
            record = await result.single()
            if record:
                total_stats = {
                    "total_entities": record["total_entities"],
                    "unique_groups": record["unique_groups"],
                    "unique_entity_names": record["unique_entity_names"]
                }
            
            # Get by group
            result = await session.run(query_by_group)
            async for record in result:
                by_group.append({
                    "group_id": record["group_id"],
                    "entity_count": record["entity_count"]
                })
            
            # Get top entities
            result = await session.run(query_top_entities)
            async for record in result:
                top_entities.append({
                    "name": record["name"],
                    "summary": record["summary"][:100] if record["summary"] else None,
                    "group_id": record["group_id"],
                    "created_at": str(record["created_at"]) if record["created_at"] else None
                })
            
            # Get most connected entities
            result = await session.run(query_relationships)
            async for record in result:
                if record["relationship_count"] > 0:
                    top_connected.append({
                        "entity": record["entity"],
                        "relationships": record["relationship_count"]
                    })
        
        return {
            "total_stats": total_stats,
            "by_group": by_group,
            "top_entities": top_entities,
            "most_connected": top_connected
        }
        
    except Exception as e:
        logger.error(f"Error getting entity stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get entity stats: {str(e)}")

# =============================================================================
# SHORT TERM MEMORY ENDPOINTS
# =============================================================================

@app.post("/short-term/save")
async def save_short_term_message(request: ShortTermMemoryRequest):
    """
    Lưu message vào short term memory
    
    Sử dụng LLM để trích xuất và phân loại thông tin tự động
    """
    try:
        storage = get_storage()
        message_id = await storage.save_message(request)
        
        return {
            "status": "success",
            "message_id": message_id,
            "message": "Message saved to short term memory"
        }
        
    except Exception as e:
        logger.error(f"Error saving short term message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")

@app.post("/short-term/search")
async def search_short_term_messages(request: ShortTermMemorySearchRequest):
    """
    Tìm kiếm messages trong short term memory
    
    Sử dụng semantic search với embedding similarity
    """
    try:
        storage = get_storage()
        results = await storage.search_messages(request)
        
        return {
            "status": "success",
            "results": results,
            "count": len(results),
            "query": request.query,
            "project_id": request.project_id
        }
        
    except Exception as e:
        logger.error(f"Error searching short term messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search messages: {str(e)}")

@app.get("/short-term/message/{message_id}")
async def get_short_term_message(message_id: str):
    """
    Lấy message theo ID
    """
    try:
        storage = get_storage()
        message = await storage.get_message(message_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "status": "success",
            "message": message.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting short term message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get message: {str(e)}")

@app.delete("/short-term/message/{message_id}")
async def delete_short_term_message(message_id: str):
    """
    Xóa message theo ID
    """
    try:
        storage = get_storage()
        success = await storage.delete_message(message_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "status": "success",
            "message": "Message deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting short term message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")

@app.get("/short-term/stats/{project_id}")
async def get_short_term_stats(project_id: str):
    """
    Lấy thống kê short term memory cho project
    """
    try:
        storage = get_storage()
        stats = await storage.get_stats(project_id)
        
        return {
            "status": "success",
            "project_id": project_id,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting short term stats for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/short-term/cleanup")
async def cleanup_short_term_memory():
    """
    Xóa các messages đã hết hạn
    """
    try:
        storage = get_storage()
        deleted_count = await storage.cleanup_expired()
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} expired messages"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up short term memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup: {str(e)}")

@app.get("/short-term/health")
async def short_term_health():
    """
    Kiểm tra sức khỏe short term memory system
    """
    try:
        storage = get_storage()
        stats = await storage.get_stats("health_check")
        
        return {
            "status": "healthy",
            "storage_dir": str(storage.storage_dir),
            "cache_loaded": stats.get("cache_loaded", False),
            "total_messages": stats.get("total_messages", 0)
        }
        
    except Exception as e:
        logger.error(f"Error checking short term health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# =============================================================================
# FILE UPLOAD ENDPOINTS
# =============================================================================

@app.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    conversation_id: str = Form(...),
    role: str = Form("assistant"),
    content: str = Form(""),
    change_type: str = Form("modified"),
    description: str = Form("")
):
    """
    Upload file code và trích xuất thông tin code changes
    
    Args:
        file: File code được upload
        project_id: ID dự án
        conversation_id: ID cuộc trò chuyện
        role: Role của message
        content: Nội dung message mô tả
        change_type: Loại thay đổi (added, modified, deleted, refactored)
        description: Mô tả thay đổi
        
    Returns:
        Thông tin code changes được trích xuất
    """
    try:
        # Đọc nội dung file
        file_content = await file.read()
        file_content_str = file_content.decode('utf-8')
        
        # Xử lý file upload
        handler = get_file_upload_handler()
        result = await handler.process_file_upload(
            file_content=file_content_str,
            file_name=file.filename,
            project_id=project_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            change_type=change_type,
            description=description
        )
        
        return {
            "status": "success",
            "message": "File uploaded and analyzed successfully",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.post("/upload/code-changes")
async def upload_code_changes(
    payload: Dict[str, Any],
    project_id: str = Form(...),
    conversation_id: str = Form(""),
    role: str = Form("assistant")
):
    """
    Upload payload code changes từ IDE/editor
    
    Args:
        payload: Payload chứa file_before, file_after, chunks
        project_id: ID dự án
        conversation_id: ID cuộc trò chuyện
        role: Role của message
        
    Returns:
        Thông tin code changes được xử lý
    """
    try:
        # Xử lý code changes payload
        handler = get_file_upload_handler()
        result = await handler.process_code_changes_payload(
            payload=payload,
            project_id=project_id,
            conversation_id=conversation_id or f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            role=role
        )
        
        return {
            "status": "success",
            "message": "Code changes processed successfully",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error processing code changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process code changes: {str(e)}")

@app.post("/upload/text-content")
async def upload_text_content(
    file_content: str = Form(...),
    file_name: str = Form(...),
    project_id: str = Form(...),
    conversation_id: str = Form(...),
    role: str = Form("assistant"),
    content: str = Form(""),
    change_type: str = Form("modified"),
    description: str = Form("")
):
    """
    Upload nội dung file dưới dạng text
    
    Args:
        file_content: Nội dung file code
        file_name: Tên file
        project_id: ID dự án
        conversation_id: ID cuộc trò chuyện
        role: Role của message
        content: Nội dung message mô tả
        change_type: Loại thay đổi
        description: Mô tả thay đổi
        
    Returns:
        Thông tin code changes được trích xuất
    """
    try:
        # Xử lý text content
        handler = get_file_upload_handler()
        result = await handler.process_file_upload(
            file_content=file_content,
            file_name=file_name,
            project_id=project_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            change_type=change_type,
            description=description
        )
        
        return {
            "status": "success",
            "message": "Text content uploaded and analyzed successfully",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error uploading text content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload text content: {str(e)}")


@app.post("/graph/import-stm-json")
async def import_stm_json(file: UploadFile = File(...), use_llm: bool = Form(False)):
    """Upload a Short Term Memory JSON file and import it into Neo4j."""
    try:
        text = (await file.read()).decode("utf-8")
        summary = await import_stm_json_content(text, use_llm=use_llm)
        return {"status": "success", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))