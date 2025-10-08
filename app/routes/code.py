# app/routes/code.py
"""
Code context endpoints - Phase 1+
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from graphiti_core.nodes import EpisodeType

from app.graph import (
    get_graphiti, 
    add_code_metadata, 
    _set_entity_ttl,
    apply_entity_labels,
    find_or_create_file_entity,
    create_relationship
)
from app.schemas import IngestCodeChange, IngestCodeContext, SearchCodeRequest
from app.cache import invalidate_search_cache

router = APIRouter(prefix="", tags=["code"])
logger = logging.getLogger(__name__)


@router.post("/ingest/code")
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
    from app.importance import get_scorer
    
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
        
        episode_uuid = getattr(episode_result, 'episode_uuid', None) or getattr(episode_result, 'uuid', 'unknown')
        logger.info(f"Episode created: {episode_uuid}")
        
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


@router.post("/ingest/code-context")
async def ingest_code_context(payload: IngestCodeContext, graphiti=Depends(get_graphiti)):
    """
    Ingest code conversation metadata (NOT actual code!)
    
    Stores metadata about code changes with 48-hour TTL.
    """
    # Validate payload serialization
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
        
        # Validate required fields
        if not payload.project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        
        if not payload.summary or len(payload.summary.strip()) == 0:
            raise HTTPException(status_code=400, detail="summary is required and cannot be empty")
        
        logger.info(f"Ingesting code context for project {payload.project_id}: {payload.name}")
        
        # Add episode using Graphiti
        episode = await graphiti.add_episode(
            name=payload.name,
            episode_body=payload.summary,
            source=EpisodeType.text,
            source_description="code_conversation",
            reference_time=ts,
            group_id=payload.project_id
        )
        
        logger.info(f"Episode created, waiting for entities...")
        
        # Wait for Graphiti to process and create entities
        await asyncio.sleep(2)
        
        # Query Neo4j to find created entities
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
                "reference_time": (ts - timedelta(seconds=60)).isoformat()
            })
            async for record in result:
                entity_uuids.append(record["uuid"])
        
        logger.info(f"Found {len(entity_uuids)} entities for group {payload.project_id}")
        
        # Fallback: try without time filter
        if not entity_uuids:
            logger.warning(f"No entities found with time filter, trying without...")
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
        
        entity_uuid = entity_uuids[0] if entity_uuids else None
        
        if not entity_uuids:
            logger.warning(f"No entity UUID found for group {payload.project_id}")
        
        # Set TTL and project_id for ALL found entities
        if entity_uuids:
            expires_at_dt = ts + timedelta(hours=48)
            
            for uuid in entity_uuids:
                await _set_entity_ttl(graphiti, uuid, expires_at_dt, payload.project_id)
                logger.info(f"Set TTL for entity {uuid}")
        
        # Add code-specific metadata to ALL entities
        if entity_uuids:
            logger.info("Building metadata dict...")
            metadata_dict = {}
            
            # Extract metadata from payload
            meta = payload.metadata
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
            metadata_dict["timestamp"] = str(meta.timestamp) if meta.timestamp else None
            
            if meta.severity:
                metadata_dict["severity"] = meta.severity
            
            # Phase 1 Schema Extensions
            if hasattr(meta, 'entity_type') and meta.entity_type:
                metadata_dict["entity_type"] = meta.entity_type
            if hasattr(meta, 'imports') and meta.imports:
                metadata_dict["imports"] = meta.imports
            if hasattr(meta, 'language') and meta.language:
                metadata_dict["language"] = meta.language
            
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
                    logger.info(f"Setting metadata for entity {idx}/{len(entity_uuids)} ({uuid[:16]}...)")
                    result = await add_code_metadata(graphiti, uuid, metadata_dict)
                    logger.info(f"✓ Successfully added code metadata to entity {uuid[:16]}...")
                    del result  # Don't use the result - might contain DateTime objects
                    
                    # Apply custom labels based on entity_type
                    if metadata_dict.get('entity_type'):
                        await apply_entity_labels(graphiti, uuid, metadata_dict['entity_type'])
                    
                    # Create file entity and relationships
                    if metadata_dict.get('file_path') and metadata_dict.get('entity_type') == 'code_change':
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
                            to_uuid=uuid,
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
                                try:
                                    imported_file_uuid = await find_or_create_file_entity(
                                        graphiti,
                                        file_path=imported_module if '.' in imported_module else f"{imported_module}.py",
                                        project_id=payload.project_id,
                                        language=metadata_dict.get('language')
                                    )
                                    
                                    await create_relationship(
                                        graphiti,
                                        from_uuid=file_uuid,
                                        to_uuid=imported_file_uuid,
                                        relationship_type='IMPORTS',
                                        properties={'import_name': imported_module}
                                    )
                                except Exception as import_error:
                                    logger.warning(f"Could not create import relationship for {imported_module}: {import_error}")
                    
                except Exception as meta_error:
                    logger.error(f"✗ Error adding metadata to {uuid[:16]}...: {str(meta_error)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.error(f"✗ SKIPPED metadata setting - no entities found!")
        
        invalidate_search_cache()
        
        logger.info("Preparing response...")
        
        # Calculate expiration
        expires_dt = ts + timedelta(hours=48)
        expires_at_str = expires_dt.isoformat()
        if not expires_at_str.endswith('Z'):
            expires_at_str += "Z"
        
        # Build response
        episode_id_str = str(entity_uuid) if entity_uuid else str(payload.name)
        project_id_str = str(payload.project_id)
        name_str = str(payload.name)
        
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


@router.post("/search/code")
async def search_code(req: SearchCodeRequest, graphiti=Depends(get_graphiti)):
    """
    Search code memories with strict project isolation and filters
    
    Returns only memories from the specified project that haven't expired.
    """
    try:
        # Validate project_id
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
        
        # Default: Only return CodeChange entities
        if req.entity_type_filter is None:
            filter_conditions.append("e.entity_type = 'code_change'")
        elif req.entity_type_filter:
            filter_conditions.append("e.entity_type = $entity_type")
            filter_params["entity_type"] = req.entity_type_filter
        
        # TTL filter
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
        
        # Language filter
        if req.language_filter:
            filter_conditions.append("e.language = $language")
            filter_params["language"] = req.language_filter
        
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
        
        # If no entities match filters, return empty
        if len(valid_uuids) == 0:
            logger.warning("No entities found matching project_id and filters")
            return {
                "results": [],
                "count": 0,
                "project_id": req.project_id
            }
        
        # Step 3: Return filtered entities
        filtered_results = []
        for uuid, data in entity_data.items():
            result_item = {
                "text": data.get("summary") or data.get("name", ""),
                "id": uuid,
                "project_id": req.project_id,
            }
            result_item.update(data)
            filtered_results.append(result_item)
        
        # Sort by created_at desc
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

