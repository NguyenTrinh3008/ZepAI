# app/innocody_routes.py
"""
Innocody Webhook Routes - Thin Adapter Layer

This module provides a simplified webhook endpoint for Innocody integration.
It transforms Innocody payloads and delegates to the core conversation route.

Architecture:
- Receives Innocody-specific payload format
- Transforms to IngestConversationContext (via innocody_adapter.py)
- Delegates to routes/conversation.py for actual processing
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime
import logging

from app.graph import get_graphiti
from app.innocody_adapter import (
    InnocodyResponse,
    ChatMeta
)
from app.conversation_adapter import transform_innocody_to_conversation
from app.cache import invalidate_search_cache
from app.routes.conversation import ingest_conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/innocody", tags=["innocody"])


@router.post("/webhook")
async def innocody_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    graphiti=Depends(get_graphiti)
):
    """
    Innocody Webhook Endpoint - Thin Adapter
    
    Receives Innocody-specific payload and delegates to conversation route.
    
    Expected payload format:
    ```json
    {
        "chat_meta": {
            "chat_id": "chat_123",
            "chat_mode": "AGENT",
            ...
        },
        "messages": [...],
        "context": [...],
        "tool_calls": [...],
        "code_changes": [...],
        "checkpoints": [...],
        "model_response": {...}
    }
    ```
    
    Returns:
        {
            "status": "success",
            "request_uuid": "...",
            "entity_counts": {...}
        }
    """
    try:
        logger.info("=== INNOCODY WEBHOOK RECEIVED ===")
        logger.info(f"Payload keys: {list(payload.keys())}")
        
        # Extract components from payload
        request_id = payload.get('request_id', f"innocody_{int(datetime.utcnow().timestamp())}")
        project_id = payload.get('project_id') or payload.get('meta', {}).get('project_id', 'default_project')
        chat_meta = payload.get('chat_meta', {})
        messages = payload.get('messages', [])
        context_files = payload.get('context', [])
        tool_calls = payload.get('tool_calls', [])
        code_changes = payload.get('code_changes', [])
        checkpoints = payload.get('checkpoints', [])
        model_response = payload.get('model_response')
        
        # Transform to IngestConversationContext
        conversation_payload = transform_innocody_to_conversation(
            request_id=request_id,
            project_id=project_id,
            chat_meta=chat_meta,
            messages=messages,
            context_files=context_files,
            tool_calls=tool_calls,
            code_changes=code_changes,
            checkpoints=checkpoints,
            model_response=model_response
        )
        
        logger.info(f"Converted to IngestConversationContext: {conversation_payload.request_id}")
        
        # Delegate to core conversation route
        result = await ingest_conversation(conversation_payload, graphiti)
        
        # Invalidate cache in background
        background_tasks.add_task(
            invalidate_search_cache,
            project_id=conversation_payload.project_id
        )
        
        logger.info(f"✓ Innocody webhook processed: {result['request_uuid']}")
        
        return {
            "status": "success",
            "request_uuid": result["request_uuid"],
            "entity_counts": result.get("entity_counts", {}),
            "project_id": conversation_payload.project_id
        }
        
    except Exception as e:
        logger.exception(f"Failed to process Innocody webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Innocody webhook: {str(e)}"
        )


@router.get("/health")
async def innocody_health_check():
    """Health check endpoint for Innocody integration"""
    return {
        "status": "ok",
        "service": "innocody-webhook",
        "version": "2.0.0",
        "adapter": "thin-layer"
    }
