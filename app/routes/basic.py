# app/routes/basic.py
"""
Basic ingest endpoints: text, message, json
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from graphiti_core.nodes import EpisodeType

from app.graph import get_graphiti
from app.schemas import IngestText, IngestMessage, IngestJSON
from app.cache import invalidate_search_cache

router = APIRouter(prefix="", tags=["basic-ingest"])


@router.post("/ingest/text")
async def ingest_text(payload: IngestText, graphiti=Depends(get_graphiti)):
    """Ingest plain text into knowledge graph"""
    import logging
    logger = logging.getLogger(__name__)
    
    ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
    logger.info(f"Ingesting text with group_id: {payload.group_id}")
    
    ep = await graphiti.add_episode(
        name=payload.name,
        episode_body=payload.text,
        source=EpisodeType.text,
        source_description=payload.source_description,
        reference_time=ts,
        group_id=payload.group_id,
    )
    
    invalidate_search_cache()
    
    return {
        "episode_id": ep.id if hasattr(ep, "id") else payload.name,
        "group_id": payload.group_id,
        "name": payload.name
    }


@router.post("/ingest/message")
async def ingest_message(payload: IngestMessage, graphiti=Depends(get_graphiti)):
    """Ingest conversation messages into knowledge graph"""
    import logging
    logger = logging.getLogger(__name__)
    
    ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
    body = "\n".join(payload.messages)
    
    logger.info(f"Ingesting message with group_id: {payload.group_id}, name: {payload.name}")
    
    ep = await graphiti.add_episode(
        name=payload.name,
        episode_body=body,
        source=EpisodeType.message,
        source_description=payload.source_description,
        reference_time=ts,
        group_id=payload.group_id,
    )
    
    invalidate_search_cache()
    
    return {
        "episode_id": ep.id if hasattr(ep, "id") else payload.name,
        "group_id": payload.group_id,
        "name": payload.name
    }


@router.post("/ingest/json")
async def ingest_json(payload: IngestJSON, graphiti=Depends(get_graphiti)):
    """Ingest JSON data into knowledge graph"""
    ts = datetime.fromisoformat(payload.reference_time) if payload.reference_time else datetime.utcnow()
    
    ep = await graphiti.add_episode(
        name=payload.name,
        episode_body=payload.data,
        source=EpisodeType.json,
        source_description=payload.source_description,
        reference_time=ts,
        group_id=payload.group_id,
    )
    
    invalidate_search_cache()
    
    return {"episode_id": getattr(ep, "id", payload.name)}

