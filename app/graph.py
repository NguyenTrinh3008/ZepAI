# app/graph.py
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from graphiti_core import Graphiti
from app.cache import cached_with_ttl
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# MONKEY PATCH: Fix Graphiti's JSON serialization for Neo4j DateTime objects
# ============================================================================
def _json_serializer(obj):
    """Custom JSON serializer that handles Neo4j DateTime objects"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

# Monkey patch json.dumps to use custom serializer
_original_json_dumps = json.dumps

def _patched_json_dumps(obj, **kwargs):
    """Patched json.dumps that handles Neo4j DateTime"""
    if 'default' not in kwargs:
        kwargs['default'] = _json_serializer
    return _original_json_dumps(obj, **kwargs)

json.dumps = _patched_json_dumps
# ============================================================================

# Graphiti sẽ dùng mặc định OpenAI cho LLM/embeddings nếu có OPENAI_API_KEY
# Bạn có thể truyền client tuỳ chỉnh theo LLM Configuration doc khi cần.

# Load .env from project (memory_layer/.env)
# override=True để .env ghi đè các biến môi trường cũ (vd còn sót cấu hình Aura)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

_graphiti: Graphiti | None = None

async def get_graphiti() -> Graphiti:
    """Lấy Graphiti instance với caching"""
    global _graphiti
    if _graphiti is None:
        # Graphiti uses OpenAI embeddings by default (text-embedding-ada-002)
        # To use text-embedding-3-small, set OPENAI_EMBEDDING_MODEL env var
        # Note: Graphiti may not support custom embedding models out of the box
        # Check Graphiti docs for embedding configuration
        
        _graphiti = Graphiti(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "neo4j"),
        )
    return _graphiti

@cached_with_ttl(ttl=3600, key_prefix="graphiti_search")
async def cached_search(query: str, focal_node_uuid: str = None):
    """Cached search function"""
    graphiti = await get_graphiti()
    if focal_node_uuid:
        return await graphiti.search(query, focal_node_uuid)
    else:
        return await graphiti.search(query)

@cached_with_ttl(ttl=1800, key_prefix="graphiti_node")
async def cached_get_node(node_uuid: str):
    """Cached get node function"""
    graphiti = await get_graphiti()
    # Giả sử có method get_node, nếu không có thì bỏ qua
    try:
        return await graphiti.get_node(node_uuid)
    except AttributeError:
        # Nếu method không tồn tại, trả về None
        return None

def reset_graphiti_cache():
    """Reset Graphiti instance cache"""
    global _graphiti
    _graphiti = None

# =============================================================================
# TTL & CODE METADATA FUNCTIONS - Phase 2
# =============================================================================

async def add_episode_with_ttl(
    graphiti: Graphiti,
    episode_body: str,
    source_description: str,
    reference_time: datetime,
    group_id: str,
    **kwargs
) -> Any:
    """
    Add episode with automatic TTL (48 hours)
    
    Args:
        graphiti: Graphiti instance
        episode_body: Episode text content
        source_description: Source description
        reference_time: Reference time for the episode
        group_id: Group ID (used as project_id)
        **kwargs: Additional arguments
    
    Returns:
        Episode result from Graphiti
    """
    try:
        # Add episode using Graphiti
        from graphiti_core.nodes import EpisodeType
        
        episode = await graphiti.add_episode(
            name=kwargs.get('name', 'Code Context'),
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description=source_description,
            reference_time=reference_time,
            group_id=group_id
        )
        
        # Set TTL for created entities
        if hasattr(episode, 'created_entities') and episode.created_entities:
            expires_at = reference_time + timedelta(hours=48)
            
            for entity in episode.created_entities:
                entity_uuid = getattr(entity, 'uuid', None)
                if entity_uuid:
                    await _set_entity_ttl(graphiti, entity_uuid, expires_at, group_id)
        
        logger.info(f"Added episode with TTL for group {group_id}")
        return episode
        
    except Exception as e:
        logger.error(f"Error adding episode with TTL: {e}")
        raise

async def _set_entity_ttl(
    graphiti: Graphiti,
    entity_uuid: str,
    expires_at: datetime,
    project_id: str
):
    """
    Set TTL and project_id for an entity
    
    Args:
        graphiti: Graphiti instance
        entity_uuid: Entity UUID
        expires_at: Expiration datetime
        project_id: Project ID for isolation
    """
    query = """
    MATCH (e:Entity {uuid: $uuid})
    SET e.expires_at = datetime($expires_at),
        e.project_id = $project_id
    """
    
    params = {
        "uuid": entity_uuid,
        "expires_at": expires_at.isoformat(),
        "project_id": project_id
    }
    
    async with graphiti.driver.session() as session:
        result = await session.run(query, params)
        # Consume the result to avoid leaving it in the session
        await result.consume()

async def add_code_metadata(
    graphiti: Graphiti,
    entity_uuid: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add code-specific metadata to an entity
    
    Args:
        graphiti: Graphiti instance
        entity_uuid: Entity UUID
        metadata: Dictionary with code metadata fields:
            - file_path: str
            - function_name: str
            - line_start: int
            - line_end: int
            - change_type: str
            - change_summary: str
            - severity: str
            - code_before_id: str
            - code_after_id: str
            - code_before_hash: str
            - code_after_hash: str
            - lines_added: int
            - lines_removed: int
            - diff_summary: str
            - git_commit: str
            - language: str
    
    Returns:
        Updated entity properties
    """
    try:
        # Build SET clause dynamically based on provided metadata
        set_clauses = []
        params = {"uuid": entity_uuid}
        
        # Map metadata keys to Neo4j properties
        field_mapping = {
            "file_path": "file_path",
            "function_name": "function_name",
            "line_start": "line_start",
            "line_end": "line_end",
            "change_type": "change_type",
            "change_summary": "change_summary",
            "severity": "severity",
            "code_before_id": "code_before_id",
            "code_after_id": "code_after_id",
            "code_before_hash": "code_before_hash",
            "code_after_hash": "code_after_hash",
            "lines_added": "lines_added",
            "lines_removed": "lines_removed",
            "diff_summary": "diff_summary",
            "git_commit": "git_commit",
            "language": "language"
        }
        
        for key, prop_name in field_mapping.items():
            if key in metadata and metadata[key] is not None:
                set_clauses.append(f"e.{prop_name} = ${key}")
                params[key] = metadata[key]
        
        if not set_clauses:
            logger.warning(f"No metadata provided for entity {entity_uuid}")
            return {}
        
        query = f"""
        MATCH (e:Entity {{uuid: $uuid}})
        SET {', '.join(set_clauses)}
        RETURN e
        """
        
        async with graphiti.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            
            if record:
                logger.info(f"Added code metadata to entity {entity_uuid}")
                # Convert Neo4j types to JSON-serializable types
                entity_dict = dict(record['e'])
                # Convert DateTime objects to ISO strings
                for key, value in entity_dict.items():
                    if hasattr(value, 'isoformat'):  # DateTime object
                        entity_dict[key] = value.isoformat()
                return entity_dict
            else:
                logger.warning(f"Entity {entity_uuid} not found")
                return {}
                
    except Exception as e:
        logger.error(f"Error adding code metadata: {e}")
        raise

async def cleanup_expired_memories(graphiti: Graphiti) -> int:
    """
    Delete memories that have expired (past TTL of 48 hours)
    
    Args:
        graphiti: Graphiti instance
    
    Returns:
        Number of deleted entities
    """
    try:
        query = """
        MATCH (e:Entity)
        WHERE e.expires_at IS NOT NULL 
          AND datetime(e.expires_at) < datetime()
        DETACH DELETE e
        RETURN count(e) as deleted_count
        """
        
        async with graphiti.driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            
            if record:
                deleted_count = record["deleted_count"]
                logger.info(f"Cleanup: Deleted {deleted_count} expired memories")
                return deleted_count
            return 0
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise

async def create_indexes(graphiti: Graphiti):
    """
    Create Neo4j indexes for performance optimization
    
    Indexes created:
    - project_id: For strict project isolation queries
    - expires_at: For TTL cleanup queries
    - file_path: For file-based filtering
    - change_type: For change type filtering
    """
    indexes = [
        ("entity_project_id", "Entity", "project_id"),
        ("entity_expires_at", "Entity", "expires_at"),
        ("entity_file_path", "Entity", "file_path"),
        ("entity_change_type", "Entity", "change_type"),
    ]
    
    async with graphiti.driver.session() as session:
        for index_name, label, property_name in indexes:
            try:
                query = f"""
                CREATE INDEX {index_name} IF NOT EXISTS
                FOR (n:{label}) ON (n.{property_name})
                """
                await session.run(query)
                logger.info(f"Created index: {index_name}")
            except Exception as e:
                logger.warning(f"Index {index_name} may already exist: {e}")

async def get_project_stats(graphiti: Graphiti, project_id: str) -> Dict[str, Any]:
    """
    Get statistics for a specific project
    
    Args:
        graphiti: Graphiti instance
        project_id: Project ID
    
    Returns:
        Dictionary with statistics:
        - total_memories: Total count of active memories
        - files_count: Number of unique files
        - change_types: List of change types
        - expired_count: Number of expired memories
    """
    try:
        query = """
        MATCH (e:Entity {project_id: $project_id})
        WITH e,
             CASE 
                WHEN e.expires_at IS NOT NULL AND datetime(e.expires_at) > datetime() 
                THEN 'active' 
                ELSE 'expired' 
             END as status
        RETURN 
            count(CASE WHEN status = 'active' THEN 1 END) as active_count,
            count(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
            count(DISTINCT e.file_path) as files_count,
            collect(DISTINCT e.change_type) as change_types
        """
        
        async with graphiti.driver.session() as session:
            result = await session.run(query, {"project_id": project_id})
            record = await result.single()
            
            if record:
                return {
                    "project_id": project_id,
                    "total_memories": record["active_count"],
                    "expired_memories": record["expired_count"],
                    "files_count": record["files_count"],
                    "change_types": [ct for ct in record["change_types"] if ct is not None]
                }
            return {
                "project_id": project_id,
                "total_memories": 0,
                "expired_memories": 0,
                "files_count": 0,
                "change_types": []
            }
            
    except Exception as e:
        logger.error(f"Error getting project stats: {e}")
        raise
