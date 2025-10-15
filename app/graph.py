# app/graph.py
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from graphiti_core import Graphiti
from app.cache import cached_with_ttl
from app.config import neo4j, cache
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
# MONKEY PATCH: Fix Graphiti's parse_db_date function for Neo4j DateTime with Z suffix
# ============================================================================
def _patched_parse_db_date(input_date):
    """Fixed parse_db_date that handles Neo4j DateTime with Z suffix"""
    if isinstance(input_date, str):
        # Handle Neo4j DateTime format with Z suffix: '2025-10-10T10:15:27.803310Z'
        if input_date.endswith('Z'):
            # Replace Z with +00:00 for proper ISO format
            input_date = input_date[:-1] + '+00:00'
        return datetime.fromisoformat(input_date)
    return input_date

# Monkey patch parse_db_date in graphiti_core.helpers
try:
    import graphiti_core.helpers
    graphiti_core.helpers.parse_db_date = _patched_parse_db_date
    logger.info("✓ Patched parse_db_date function to handle Neo4j Z suffix")
except Exception as e:
    logger.warning(f"Could not patch parse_db_date: {e}")

# ============================================================================
# MONKEY PATCH: Fix EntityNode creation with None summary field
# ============================================================================
# Save the original function before patching
import graphiti_core.nodes
_original_get_entity_node_from_record = graphiti_core.nodes.get_entity_node_from_record

def _convert_neo4j_datetime(neo4j_datetime):
    """Convert Neo4j DateTime to Python datetime"""
    if neo4j_datetime is None:
        return datetime.now()
    
    # Handle Neo4j DateTime objects
    if hasattr(neo4j_datetime, 'to_native'):
        return neo4j_datetime.to_native()
    elif hasattr(neo4j_datetime, 'isoformat'):
        return datetime.fromisoformat(neo4j_datetime.isoformat())
    elif isinstance(neo4j_datetime, str):
        return _patched_parse_db_date(neo4j_datetime)
    else:
        return datetime.now()

def _patched_get_entity_node_from_record(record, provider):
    """Fixed get_entity_node_from_record that handles None summary field"""
    from graphiti_core.nodes import EntityNode
    from graphiti_core.helpers import parse_db_date
    
    # Extract data from record - mimic original behavior
    entity_data = {
        'uuid': record.get('uuid'),
        'group_id': record.get('group_id'),
        'name': record.get('name'),
        'name_embedding': record.get('name_embedding'),
        'labels': record.get('labels', []),
        'created_at': _convert_neo4j_datetime(record.get('created_at')) if record.get('created_at') else datetime.now(),
        'summary': record.get('summary') or "",  # Fix: Replace None with empty string
    }
    
    # Create EntityNode with fixed data
    return EntityNode(**entity_data)

# Monkey patch get_entity_node_from_record in multiple places
try:
    import graphiti_core.nodes
    import graphiti_core.search.search_utils
    
    graphiti_core.nodes.get_entity_node_from_record = _patched_get_entity_node_from_record
    graphiti_core.search.search_utils.get_entity_node_from_record = _patched_get_entity_node_from_record
    logger.info("✓ Patched get_entity_node_from_record function to handle None summary")
except Exception as e:
    logger.warning(f"Could not patch get_entity_node_from_record: {e}")

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
            uri=neo4j.get_uri(),
            user=neo4j.get_user(),
            password=neo4j.get_password(),
        )
    return _graphiti

@cached_with_ttl(ttl=cache.GRAPHITI_SEARCH_TTL_SECONDS, key_prefix="graphiti_search")
async def cached_search(query: str, focal_node_uuid: str = None):
    """Cached search function"""
    graphiti = await get_graphiti()
    if focal_node_uuid:
        return await graphiti.search(query, focal_node_uuid)
    else:
        return await graphiti.search(query)

@cached_with_ttl(ttl=cache.NODE_CACHE_TTL_SECONDS, key_prefix="graphiti_node")
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

async def apply_entity_labels(graphiti, entity_uuid: str, entity_type: str):
    """
    Apply custom labels to entity based on entity_type
    
    Args:
        graphiti: Graphiti instance
        entity_uuid: Entity UUID
        entity_type: 'code_file', 'code_change', 'module', 'function', 'class', etc.
    """
    label_mapping = {
        'code_file': 'CodeFile',
        'code_change': 'CodeChange',
        'module': 'Module',
        'function': 'Function',
        'class': 'Class',
        'test': 'Test',
        'bug_fix': 'BugFix',
        'feature': 'Feature',
        'refactoring': 'Refactoring',
    }
    
    label = label_mapping.get(entity_type)
    if not label:
        logger.warning(f"Unknown entity_type: {entity_type}, skipping label")
        return  # No custom label needed
    
    # Add label to entity (keep Entity label, add specific label)
    query = f"""
    MATCH (e:Entity {{uuid: $uuid}})
    SET e:{label}
    RETURN e.uuid as uuid, labels(e) as labels
    """
    
    async with graphiti.driver.session() as session:
        result = await session.run(query, {"uuid": entity_uuid})
        record = await result.single()
        if record:
            logger.info(f"✓ Applied label {label} to entity {entity_uuid[:16]}... (labels: {record['labels']})")


async def create_relationship(
    graphiti,
    from_uuid: str,
    to_uuid: str,
    relationship_type: str,
    properties: Optional[Dict] = None
):
    """
    Create a relationship between two entities
    
    Args:
        graphiti: Graphiti instance
        from_uuid: Source entity UUID
        to_uuid: Target entity UUID
        relationship_type: MODIFIED_IN, IMPORTS, BELONGS_TO, etc.
        properties: Optional relationship properties
    """
    props_str = ""
    params = {
        "from_uuid": from_uuid,
        "to_uuid": to_uuid
    }
    
    if properties:
        # Build properties string
        prop_items = []
        for key, value in properties.items():
            param_key = f"prop_{key}"
            prop_items.append(f"{key}: ${param_key}")
            params[param_key] = value
        props_str = "{" + ", ".join(prop_items) + "}"
    
    query = f"""
    MATCH (from:Entity {{uuid: $from_uuid}})
    MATCH (to:Entity {{uuid: $to_uuid}})
    MERGE (from)-[r:{relationship_type} {props_str}]->(to)
    RETURN r
    """
    
    try:
        async with graphiti.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record:
                logger.info(f"✓ Created relationship {relationship_type}: {from_uuid[:8]}...→{to_uuid[:8]}...")
            return record
    except Exception as e:
        logger.error(f"Error creating relationship {relationship_type}: {e}")
        raise


async def find_or_create_file_entity(
    graphiti,
    file_path: str,
    project_id: str,
    language: str = None,
    module_name: str = None
) -> str:
    """
    Find existing CodeFile entity or create new one
    
    Returns:
        Entity UUID
    """
    # Try to find existing
    query = """
    MATCH (f:CodeFile {file_path: $file_path, project_id: $project_id})
    RETURN f.uuid as uuid
    LIMIT 1
    """
    
    async with graphiti.driver.session() as session:
        result = await session.run(query, {
            "file_path": file_path,
            "project_id": project_id
        })
        record = await result.single()
        
        if record:
            logger.info(f"Found existing CodeFile: {file_path}")
            return record["uuid"]
    
    # Create new file entity
    import uuid
    file_uuid = str(uuid.uuid4())
    
    create_query = """
    CREATE (f:Entity:CodeFile {
        uuid: $uuid,
        file_path: $file_path,
        project_id: $project_id,
        language: $language,
        module: $module_name,
        created_at: datetime(),
        entity_type: 'code_file'
    })
    RETURN f.uuid as uuid
    """
    
    async with graphiti.driver.session() as session:
        result = await session.run(create_query, {
            "uuid": file_uuid,
            "file_path": file_path,
            "project_id": project_id,
            "language": language,
            "module_name": module_name
        })
        record = await result.single()
        
        if record:
            logger.info(f"✓ Created CodeFile entity: {file_path} ({file_uuid[:8]}...)")
            return file_uuid
    
    return file_uuid


async def add_code_metadata(graphiti, entity_uuid: str, metadata: dict) -> dict:
    """
    Add code metadata to existing entity
    
    Args:
        graphiti: Graphiti instance
        entity_uuid: Entity UUID
        metadata: Dictionary with code metadata fields
    
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
            "language": "language",
            "entity_type": "entity_type",
            "imports": "imports"
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
