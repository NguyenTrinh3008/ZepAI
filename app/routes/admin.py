# app/routes/admin.py
"""
Admin, debug, and cache management endpoints
"""
import os
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.graph import get_graphiti, reset_graphiti_cache, cleanup_expired_memories, get_project_stats
from app.cache import (
    get_cache_metrics,
    invalidate_all_cache,
    invalidate_search_cache,
    invalidate_node_cache
)
from app.langfuse_tracer import get_health_status, flush_langfuse

router = APIRouter(prefix="", tags=["admin"])
logger = logging.getLogger(__name__)


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return get_cache_metrics()


@router.post("/cache/clear")
async def clear_cache():
    """Clear all cache"""
    invalidate_all_cache()
    return {"message": "Cache cleared successfully"}


@router.post("/cache/clear-search")
async def clear_search_cache():
    """Clear search cache only"""
    invalidate_search_cache()
    return {"message": "Search cache cleared successfully"}


@router.post("/cache/clear-node/{node_uuid}")
async def clear_node_cache(node_uuid: str):
    """Clear cache for specific node"""
    invalidate_node_cache(node_uuid)
    return {"message": f"Cache for node {node_uuid} cleared successfully"}


@router.get("/cache/health")
async def cache_health():
    """Check cache health"""
    stats = get_cache_metrics()
    return {
        "status": "healthy" if stats["active_entries"] > 0 else "empty",
        "stats": stats
    }


# =============================================================================
# LANGFUSE MONITORING
# =============================================================================

@router.get("/langfuse/health")
async def check_langfuse_health():
    """Check Langfuse tracing health status"""
    return get_health_status()


@router.post("/langfuse/flush")
async def flush_langfuse_traces():
    """Manually flush all pending traces to Langfuse"""
    try:
        flush_langfuse()
        return {
            "status": "success",
            "message": "Langfuse traces flushed successfully"
        }
    except Exception as e:
        logger.error(f"Error flushing Langfuse: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to flush Langfuse: {str(e)}")


# =============================================================================
# ADMIN OPERATIONS
# =============================================================================

@router.post("/admin/cleanup")
async def manual_cleanup(graphiti=Depends(get_graphiti)):
    """
    Manually trigger cleanup of expired memories
    
    Deletes all entities past their 48-hour TTL.
    """
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


@router.get("/stats/{project_id}")
async def get_stats(project_id: str, graphiti=Depends(get_graphiti)):
    """
    Get statistics for a specific project
    
    Returns counts of memories, files, and change types.
    """
    try:
        logger.info(f"Getting stats for project {project_id}")
        stats = await get_project_stats(graphiti, project_id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/export/{group_id}")
async def export_conversation(group_id: str, graphiti=Depends(get_graphiti)):
    """Export conversation to JSON for backup/sharing"""
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


# =============================================================================
# CONFIG MANAGEMENT
# =============================================================================

@router.get("/config/neo4j")
async def get_neo4j_config():
    """Get Neo4j configuration (non-sensitive)"""
    return {
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USER": os.getenv("NEO4J_USER"),
        "NEO4J_DATABASE": os.getenv("NEO4J_DATABASE"),
    }


@router.post("/config/reload-neo4j")
async def reload_neo4j_config():
    """Reload Neo4j configuration"""
    reset_graphiti_cache()
    return {"message": "Neo4j config reloaded. Next request will create a new connection."}


# =============================================================================
# DEBUG ENDPOINTS
# =============================================================================

@router.get("/debug/all-entities")
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


@router.get("/debug/entity/{entity_uuid}")
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


@router.get("/debug/episodes/{group_id}")
async def debug_episodes_by_group(group_id: str, graphiti=Depends(get_graphiti)):
    """Debug endpoint to check entities and relationships by group_id"""
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
        
        relationships = []
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"group_id": group_id})
            async for record in result:
                relationships.append({
                    "source": record["source"],
                    "relationship": record["rel_type"],
                    "properties": record["rel_props"],
                    "target": record["target"],
                    "source_uuid": record["source_uuid"],
                    "target_uuid": record["target_uuid"]
                })
        
        return {
            "group_id": group_id,
            "entity_count": len(records),
            "entities": records,
            "relationship_count": len(relationships),
            "relationships": relationships
        }
    except Exception as e:
        return {"error": str(e), "group_id": group_id}

