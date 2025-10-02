# app/innocody_routes.py
"""
FastAPI routes để nhận webhook từ Innocody và process vào memory layer
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import logging

from app.graph import get_graphiti
from app.innocody_adapter import (
    InnocodyResponse,
    ChatMeta,
    convert_innocody_to_memory_layer,
    process_innocody_webhook
)
from app.schemas import IngestCodeContext
from app.cache import invalidate_search_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/innocody", tags=["innocody"])


@router.post("/webhook")
async def innocody_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    graphiti=Depends(get_graphiti)
):
    """
    Webhook endpoint để nhận DiffChunk từ Innocody
    
    Expected payload format:
    {
        "file_before": "<full file content before>",
        "file_after": "<full file content after>",
        "chunks": [
            {
                "file_name": "src/auth/auth_service.py",
                "file_action": "edit",
                "line1": 45,
                "line2": 52,
                "lines_remove": "<removed code>",
                "lines_add": "<added code>"
            }
        ],
        "meta": {  // Optional
            "chat_id": "...",
            "project_id": "my_project"
        }
    }
    
    Returns:
        {
            "status": "success",
            "ingested_count": 3,
            "episode_ids": ["...", "...", "..."],
            "summaries": ["...", "...", "..."]
        }
    """
    try:
        logger.info("=== INNOCODY WEBHOOK RECEIVED ===")
        logger.info(f"Payload keys: {payload.keys()}")
        
        # Extract meta if exists
        meta_data = payload.pop('meta', None)
        chat_meta = ChatMeta(**meta_data) if meta_data else None
        
        # Parse Innocody response
        innocody_resp = InnocodyResponse(**payload)
        logger.info(f"Parsed {len(innocody_resp.chunks)} chunks")
        
        # Convert to memory layer format
        memory_payloads = await convert_innocody_to_memory_layer(
            innocody_resp,
            chat_meta=chat_meta,
            use_llm_summary=True  # Use LLM để generate summary
        )
        
        logger.info(f"Converted to {len(memory_payloads)} memory payloads")
        
        # Ingest từng payload
        episode_ids = []
        summaries = []
        
        for idx, mp in enumerate(memory_payloads, 1):
            try:
                logger.info(f"Ingesting payload {idx}/{len(memory_payloads)}: {mp['name']}")
                
                # Parse to Pydantic model
                from app.schemas import IngestCodeContext
                code_context = IngestCodeContext(**mp)
                
                # Ingest via existing endpoint logic
                from app.main import ingest_code_context
                result = await ingest_code_context(code_context, graphiti)
                
                # Extract episode_id from response
                if isinstance(result, JSONResponse):
                    import json
                    body = json.loads(result.body.decode())
                    episode_id = body.get('episode_id')
                else:
                    episode_id = result.get('episode_id', 'unknown')
                
                episode_ids.append(episode_id)
                summaries.append(mp['summary'])
                
                logger.info(f"✓ Ingested: {episode_id}")
                
            except Exception as e:
                logger.error(f"Failed to ingest payload {idx}: {e}")
                # Continue with next payload
                episode_ids.append(f"error_{idx}")
                summaries.append(f"Error: {str(e)}")
        
        # Invalidate cache
        invalidate_search_cache()
        
        return {
            "status": "success",
            "ingested_count": len(episode_ids),
            "episode_ids": episode_ids,
            "summaries": summaries,
            "project_id": chat_meta.project_id if chat_meta else "default_project"
        }
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Innocody webhook: {str(e)}"
        )


@router.post("/webhook/batch")
async def innocody_webhook_batch(
    payloads: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    graphiti=Depends(get_graphiti)
):
    """
    Batch webhook endpoint để nhận nhiều DiffChunk responses cùng lúc
    
    Expected: Array of InnocodyResponse objects
    """
    try:
        logger.info(f"=== INNOCODY BATCH WEBHOOK: {len(payloads)} payloads ===")
        
        all_episode_ids = []
        all_summaries = []
        total_chunks = 0
        
        for payload in payloads:
            # Process each payload
            result = await innocody_webhook(payload, background_tasks, graphiti)
            
            if result['status'] == 'success':
                all_episode_ids.extend(result['episode_ids'])
                all_summaries.extend(result['summaries'])
                total_chunks += result['ingested_count']
        
        return {
            "status": "success",
            "total_payloads": len(payloads),
            "total_chunks": total_chunks,
            "episode_ids": all_episode_ids,
            "summaries": all_summaries
        }
        
    except Exception as e:
        logger.error(f"Batch webhook failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process batch webhook: {str(e)}"
        )


@router.post("/test/mock")
async def test_with_mock_data(graphiti=Depends(get_graphiti)):
    """
    Test endpoint với mock data
    
    Không cần Innocody, dùng để test adapter logic
    """
    try:
        from app.innocody_adapter import generate_mock_innocody_response
        
        logger.info("=== TESTING WITH MOCK DATA ===")
        
        # Generate mock response
        mock_response = generate_mock_innocody_response()
        
        # Convert
        memory_payloads = await convert_innocody_to_memory_layer(
            mock_response,
            use_llm_summary=True
        )
        
        logger.info(f"Generated {len(memory_payloads)} payloads from mock")
        
        # Ingest first payload để test
        if memory_payloads:
            mp = memory_payloads[0]
            from app.schemas import IngestCodeContext
            code_context = IngestCodeContext(**mp)
            
            from app.main import ingest_code_context
            result = await ingest_code_context(code_context, graphiti)
            
            return {
                "status": "success",
                "message": "Mock data ingested successfully",
                "payload": mp,
                "result": result if not isinstance(result, JSONResponse) else "JSONResponse"
            }
        else:
            return {
                "status": "error",
                "message": "No payloads generated"
            }
            
    except Exception as e:
        logger.error(f"Mock test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Mock test failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "innocody-adapter",
        "endpoints": {
            "/innocody/webhook": "POST - Receive single Innocody response",
            "/innocody/webhook/batch": "POST - Receive multiple responses",
            "/innocody/test/mock": "POST - Test with mock data"
        }
    }
