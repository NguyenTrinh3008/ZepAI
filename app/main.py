# app/main.py
import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.responses import Response
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from app.graph import get_graphiti
from app.graph import _graphiti  # for reset endpoint
from app.schemas import (
    IngestText, IngestMessage, IngestJSON, SearchRequest,
    IngestCodeChange, IngestCodeContext, SearchCodeRequest,
    IngestConversationContext
)
from app.cache import (
    cached_with_ttl, cache_search_result, memory_cache, 
    invalidate_search_cache, invalidate_node_cache, get_cache_metrics
)

app = FastAPI(title="Graphiti Memory Layer")

# Import và register Innocody routes
from app.innocody_routes import router as innocody_router
app.include_router(innocody_router)

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
    
    # Invalidate search cache khi có dữ liệu mới
    invalidate_search_cache()
    
    return {
        "episode_id": ep.id if hasattr(ep, "id") else payload.name,
        "group_id": payload.group_id,
        "name": payload.name
    }

@app.post("/ingest/message")
async def ingest_message(payload: IngestMessage, graphiti=Depends(get_graphiti)):
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
            txt = item.get("summary") or item.get("fact") or item.get("text") or item.get("name") or str(item)
            # For edges, prefer source_node_uuid over edge uuid
            ident = (
                item.get("source_node_uuid")  # Entity UUID (for EntityEdge)
                or item.get("uuid")  # Edge/Node UUID
                or item.get("node_uuid")
                or item.get("edge_id")
                or item.get("id")
            )
            grp_id = item.get("group_id") or item.get("groupId")
            name = item.get("name")
            summary = item.get("summary") or item.get("fact") or item.get("text")
            score = item.get("score") or item.get("similarity")
        else:
            txt = (
                getattr(item, "summary", None)
                or getattr(item, "fact", None)
                or getattr(item, "text", None)
                or getattr(item, "name", None)
                or str(item)
            )
            # For EntityEdge objects, use source_node_uuid (the actual entity)
            ident = (
                getattr(item, "source_node_uuid", None)  # Entity UUID (for EntityEdge)
                or getattr(item, "uuid", None)  # Edge/Node UUID
                or getattr(item, "node_uuid", None)
                or getattr(item, "edge_id", None)
                or getattr(item, "id", None)
            )
            grp_id = getattr(item, "group_id", None) or getattr(item, "groupId", None)
            name = getattr(item, "name", None)
            summary = getattr(item, "summary", None) or getattr(item, "fact", None) or getattr(item, "text", None)
            score = getattr(item, "score", None)
        
        # Debug logging
        logger.info(f"Normalize: type={type(item).__name__}, text={txt[:50] if txt else 'N/A'}, id={ident}, group_id={grp_id}")
        
        if not grp_id:
            logger.warning(f"Search result missing group_id: {type(item)} - {txt[:50] if txt else 'N/A'}")
        if not ident:
            logger.warning(f"Search result missing ID: {type(item)} - {txt[:50] if txt else 'N/A'}, item_keys={list(item.keys()) if isinstance(item, dict) else dir(item)}")
        return {
            "text": txt,
            "summary": summary or txt,
            "name": name,
            "id": ident,
            "group_id": grp_id,
            "score": score
        }

    # Normalize then deduplicate and filter self-echoes of the query
    normalized = [normalize(r) for r in results]

    # Enrich items missing descriptive text using Neo4j metadata
    metadata_needed = [item for item in normalized if not (item.get("text") and item.get("text").strip() and item.get("text").strip().lower() not in {"unknown", "..."})]
    if metadata_needed:
        uuids = [item.get("id") for item in metadata_needed if item.get("id")]
        if uuids:
            meta_query = """
            MATCH (n)
            WHERE n.uuid IN $uuids
            RETURN n.uuid as uuid,
                   n.name as name,
                   n.summary as summary,
                   n.episode_body as episode_body,
                   labels(n) as labels
            """
            metadata_map = {}
            async with graphiti.driver.session() as session:
                result = await session.run(meta_query, {"uuids": uuids})
                async for record in result:
                    metadata_map[record["uuid"]] = {
                        "name": record["name"],
                        "summary": record["summary"],
                        "episode_body": record.get("episode_body"),
                        "labels": record.get("labels")
                    }
            for item in metadata_needed:
                meta = metadata_map.get(item.get("id"))
                if not meta:
                    continue
                summary_val = meta.get("summary")
                summary = summary_val.strip() if isinstance(summary_val, str) else (str(summary_val).strip() if summary_val is not None else "")
                name_val = meta.get("name")
                name = name_val.strip() if isinstance(name_val, str) else (str(name_val).strip() if name_val is not None else "")
                episode_val = meta.get("episode_body")
                episode = episode_val.strip() if isinstance(episode_val, str) else (str(episode_val).strip() if episode_val is not None else "")

                chosen_text = summary or episode or item.get("text") or name or ""
                # Trim overly long episode bodies
                if len(chosen_text) > 400:
                    chosen_text = chosen_text[:397] + "..."
                item["text"] = chosen_text
                item["summary"] = item.get("summary") or chosen_text
                item["name"] = item.get("name") or name or "Conversation"

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

    # Finalize: ensure name/summary present, fallback to trimmed text
    for item in filtered:
        summary_text = item.get("summary") or item.get("text") or ""
        if summary_text and len(summary_text) > 400:
            summary_text = summary_text[:397] + "..."
        item["summary"] = summary_text
        if not item.get("name"):
            item["name"] = summary_text[:80] + ("..." if len(summary_text) > 80 else "") if summary_text else "Conversation"
        if item.get("score") is None:
            item["score"] = 0.0

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
            "/admin/cleanup": "POST - Manually cleanup expired memories (Phase 3)"
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
               e.file_path as file_path,
               e.change_type as change_type,
               e.severity as severity,
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
                    "file_path": record["file_path"],
                    "change_type": record["change_type"],
                    "severity": record["severity"],
                    "expires_at": str(record["expires_at"]) if record["expires_at"] else None,
                    "created_at": str(record["created_at"]) if record["created_at"] else None
                })
        
        return {
            "total": len(entities),
            "entities": entities
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/entity/{entity_uuid}")
async def debug_entity_detail(entity_uuid: str, graphiti=Depends(get_graphiti)):
    """Debug: Show single entity detail"""
    try:
        query = """
        MATCH (e:Entity {uuid: $uuid})
        RETURN properties(e) as props
        """
        
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"uuid": entity_uuid})
            record = await result.single()
            
            if record:
                return {
                    "uuid": entity_uuid,
                    "properties": record["props"]
                }
            else:
                return {"error": "Entity not found"}
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
        # Widen the time window to 60 seconds to catch entities even with clock skew
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
                "reference_time": (ts - __import__('datetime').timedelta(seconds=60)).isoformat()
            })
            async for record in result:
                entity_uuids.append(record["uuid"])
        
        logger.info(f"Found {len(entity_uuids)} entities for group {payload.project_id}")
        
        # If still not found, try without time filter (just get latest for this group)
        if not entity_uuids:
            logger.warning(f"No entities found with time filter, trying without time filter...")
            query_no_time = """
            MATCH (e:Entity {group_id: $group_id})
            RETURN e.uuid as uuid
            ORDER BY e.created_at DESC
            LIMIT 5
            """
            async with graphiti.driver.session() as session:
                result = await session.run(query_no_time, {"group_id": payload.project_id})
                async for record in result:
                    entity_uuids.append(record["uuid"])
            logger.info(f"Found {len(entity_uuids)} entities without time filter")
        
        # Use first entity UUID for response
        entity_uuid = entity_uuids[0] if entity_uuids else None
        
        if not entity_uuids:
            logger.warning(f"No entity UUID found for group {payload.project_id}")
        
        # Set TTL and project_id for ALL found entities
        if entity_uuids:
            from app.graph import _set_entity_ttl
            from datetime import timedelta as td
            expires_at_dt = ts + td(hours=48)
            
            for uuid in entity_uuids:
                await _set_entity_ttl(graphiti, uuid, expires_at_dt, payload.project_id)
                logger.info(f"Set TTL for entity {uuid}")
        
        # Add code-specific metadata to ALL entities (not just first!)
        if entity_uuids:
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
            
            # Phase 1 Schema Extensions
            if hasattr(meta, 'entity_type') and meta.entity_type:
                metadata_dict["entity_type"] = meta.entity_type  # 'code_change' for CodeChange label
            if hasattr(meta, 'imports') and meta.imports:
                metadata_dict["imports"] = meta.imports  # List of imported modules
            if hasattr(meta, 'language') and meta.language:
                metadata_dict["language"] = meta.language  # Programming language
            
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
            
            # Add metadata to ALL entities
            for idx, uuid in enumerate(entity_uuids, 1):
                try:
                    logger.info(f"Setting metadata for entity {idx}/{len(entity_uuids)} ({uuid[:16]}...): {list(metadata_dict.keys())}")
                    result = await add_code_metadata(graphiti, uuid, metadata_dict)
                    logger.info(f"✓ Successfully added code metadata to entity {uuid[:16]}...")
                    # Don't use the result - it might contain DateTime objects
                    del result
                    
                    # Phase 1: Apply custom labels based on entity_type
                    if metadata_dict.get('entity_type'):
                        from app.graph import apply_entity_labels
                        await apply_entity_labels(graphiti, uuid, metadata_dict['entity_type'])
                    
                    # Phase 1+: Create file entity and relationships
                    if metadata_dict.get('file_path') and metadata_dict.get('entity_type') == 'code_change':
                        from app.graph import find_or_create_file_entity, create_relationship
                        
                        # Find or create CodeFile entity
                        file_uuid = await find_or_create_file_entity(
                            graphiti,
                            file_path=metadata_dict['file_path'],
                            project_id=payload.project_id,
                            language=metadata_dict.get('language'),
                            module_name=metadata_dict.get('file_path').split('/')[0] if '/' in metadata_dict.get('file_path', '') else None
                        )
                        
                        # Create MODIFIED_IN relationship: CodeFile -> CodeChange
                        await create_relationship(
                            graphiti,
                            from_uuid=file_uuid,
                            to_uuid=uuid,  # CodeChange entity
                            relationship_type='MODIFIED_IN',
                            properties={
                                'timestamp': metadata_dict.get('timestamp'),
                                'lines_changed': (metadata_dict.get('lines_added', 0) + 
                                                metadata_dict.get('lines_removed', 0))
                            }
                        )
                        
                        # Create IMPORTS relationships if imports data exists
                        if metadata_dict.get('imports'):
                            for imported_module in metadata_dict['imports']:
                                # Try to find or create imported file entity
                                # Note: This is best-effort, might not exist yet
                                try:
                                    imported_file_uuid = await find_or_create_file_entity(
                                        graphiti,
                                        file_path=imported_module if '.' in imported_module else f"{imported_module}.py",
                                        project_id=payload.project_id,
                                        language=metadata_dict.get('language')
                                    )
                                    
                                    # Create IMPORTS relationship: CodeFile -> CodeFile
                                    await create_relationship(
                                        graphiti,
                                        from_uuid=file_uuid,
                                        to_uuid=imported_file_uuid,
                                        relationship_type='IMPORTS',
                                        properties={
                                            'import_name': imported_module
                                        }
                                    )
                                except Exception as import_error:
                                    logger.warning(f"Could not create import relationship for {imported_module}: {import_error}")
                    
                except Exception as meta_error:
                    logger.error(f"✗ Error adding metadata to {uuid[:16]}...: {str(meta_error)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Continue with next entity - metadata is optional
        else:
            logger.error(f"✗ SKIPPED metadata setting - no entities found!")
        
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


# =============================================================================
# PHASE 1.5: CONVERSATION CONTEXT ENDPOINT
# =============================================================================

@app.post("/ingest/conversation")
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from datetime import timedelta
        import asyncio
        
        logger.info(f"📥 Ingesting conversation context for request: {payload.request_id}")
        
        # Use structured prompts for better episode body
        from app.prompts import format_conversation_episode_body
        from app.conversation_graph import (
            create_request_node,
            create_message_node,
            create_context_file_node,
            create_tool_call_node,
            create_checkpoint_node,
            create_code_change_node,
        )
        
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

        ts = datetime.fromisoformat(payload.timestamp.replace('Z', ''))
        
        episode = await graphiti.add_episode(
            name=entity_name,
            episode_body=conversation_summary,
            source=EpisodeType.text,
            source_description="conversation",
            reference_time=ts,
            group_id=payload.project_id
        )
        
        logger.info("✓ Episode created, waiting for entity and embeddings...")
        
        # Wait for entity creation and embedding generation (Graphiti needs ~3s)
        await asyncio.sleep(3)
        
        # Find created entity
        query = """
        MATCH (e:Entity {group_id: $group_id})
        WHERE e.created_at >= datetime($reference_time)
        RETURN e.uuid as uuid
        ORDER BY e.created_at DESC
        LIMIT 1
        """
        
        request_uuid = None
        async with graphiti.driver.session() as session:
            result = await session.run(query, {
                "group_id": payload.project_id,
                "reference_time": (ts - timedelta(seconds=10)).isoformat()
            })
            record = await result.single()
            if record:
                request_uuid = record["uuid"]
        
        if not request_uuid:
            raise Exception("Failed to create conversation entity")
        
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
        
        # DEBUG: Inspect search result structure
        if results and len(results) > 0:
            first_result = results[0]
            logger.info(f"Graphiti search returned {len(results)} results")
            logger.info(f"Search result type: {type(first_result)}")
            if isinstance(first_result, dict):
                logger.info(f"Search result keys: {list(first_result.keys())}")
                logger.info(f"Search result sample: {first_result}")
            else:
                logger.info(f"Search result attrs: {[a for a in dir(first_result) if not a.startswith('_')]}")
                # Try to get all attributes
                logger.info(f"Search result data: {vars(first_result) if hasattr(first_result, '__dict__') else str(first_result)}")
        
        # Step 2: Build Neo4j filter query
        filter_conditions = ["e.project_id = $project_id"]
        filter_params = {"project_id": req.project_id}
        
        # Default: Only return CodeChange entities (exclude Graphiti concept entities)
        # This ensures results have metadata like severity, change_type
        # User can override by setting entity_type_filter=None explicitly
        if req.entity_type_filter is None:
            filter_conditions.append("e.entity_type = 'code_change'")
        elif req.entity_type_filter:  # If explicitly set (not empty string)
            filter_conditions.append("e.entity_type = $entity_type")
            filter_params["entity_type"] = req.entity_type_filter
        
        # TTL filter (only active memories OR no TTL set)
        # Some entities might not have TTL (legacy or non-code contexts)
        filter_conditions.append("(e.expires_at IS NULL OR datetime(e.expires_at) > datetime())")
        
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
        
        # Phase 1+ Schema Extension Filters
        # Language filter
        if req.language_filter:
            filter_conditions.append("e.language = $language")
            filter_params["language"] = req.language_filter
        
        # Entity type filter already handled above (with default)
        
        # Build complete query
        where_clause = " AND ".join(filter_conditions)
        query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        RETURN e.uuid as uuid,
               e.name as name,
               e.summary as summary,
               e.file_path as file_path,
               e.function_name as function_name,
               e.change_type as change_type,
               e.change_summary as change_summary,
               e.severity as severity,
               e.code_after_id as code_after_id,
               e.code_after_hash as code_after_hash,
               e.diff_summary as diff_summary,
               e.lines_added as lines_added,
               e.lines_removed as lines_removed,
               e.created_at as created_at,
               e.language as language,
               e.entity_type as entity_type,
               e.imports as imports
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
                    "name": record.get("name"),
                    "summary": record.get("summary"),
                    "file_path": record.get("file_path"),
                    "function_name": record.get("function_name"),
                    "change_type": record.get("change_type"),
                    "change_summary": record.get("change_summary"),
                    "severity": record.get("severity"),
                    "code_after_id": record.get("code_after_id"),
                    "code_after_hash": record.get("code_after_hash"),
                    "diff_summary": record.get("diff_summary"),
                    "lines_added": record.get("lines_added"),
                    "lines_removed": record.get("lines_removed"),
                    "created_at": str(record.get("created_at")) if record.get("created_at") else None,
                    "language": record.get("language"),
                    "entity_type": record.get("entity_type"),
                    "imports": record.get("imports")
                }
        
        logger.info(f"Project filter: {len(valid_uuids)} valid entities for project {req.project_id}")
        logger.info(f"Sample valid UUIDs: {list(valid_uuids)[:3]}")
        
        # If no entities match filters, return empty
        if len(valid_uuids) == 0:
            logger.warning("No entities found matching project_id and filters")
            return {
                "results": [],
                "count": 0,
                "project_id": req.project_id
            }
        
        # Step 3: Return filtered entities directly
        # Graphiti creates multiple entities per code change (dates, format_date, etc.)
        # So we just return our filtered entities with full metadata
        filtered_results = []
        for uuid, data in entity_data.items():
            result_item = {
                "text": data.get("summary") or data.get("name", ""),
                "id": uuid,
                "project_id": req.project_id,
            }
            # Merge all metadata
            result_item.update(data)
            filtered_results.append(result_item)
        
        # Sort by created_at desc (most recent first)
        filtered_results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
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
# PHASE 1.5: CONVERSATION CONTEXT SEARCH ENDPOINTS
# =============================================================================

@app.get("/conversation/requests/{project_id}")
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.conversation_graph import search_requests
        
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


@app.get("/conversation/flow/{request_id}")
async def get_conversation_flow(
    request_id: str,
    graphiti=Depends(get_graphiti)
):
    """
    Get complete conversation flow for a specific request
    
    Returns:
        Request with all messages, context files, tool calls
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.conversation_graph import get_conversation_flow as get_flow
        
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


@app.get("/conversation/context-stats/{project_id}")
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.conversation_graph import get_context_file_stats as get_stats
        
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


@app.get("/conversation/tool-stats")
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.conversation_graph import get_tool_statistics
        
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