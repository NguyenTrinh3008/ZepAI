# app/routes/search.py
"""
Search endpoints
"""
from fastapi import APIRouter, Depends
import logging

from app.graph import get_graphiti
from app.schemas import SearchRequest
from app.services.search_service import search_knowledge_graph
from app.query_classifier import SmartSearchService

router = APIRouter(prefix="", tags=["search"])
logger = logging.getLogger(__name__)


@router.post("/search", operation_id="search")
async def search(req: SearchRequest, graphiti=Depends(get_graphiti)):
    """
    Search knowledge graph with semantic search and advanced reranking
    
    Features:
    - Auto-translation for non-English queries
    - Hybrid search with focal nodes
    - Group ID filtering
    - Result caching (30 min TTL)
    - LLM-powered strategy selection (optional)
    - Advanced reranking strategies:
      * rrf: Reciprocal Rank Fusion (default)
      * mmr: Maximal Marginal Relevance (reduces redundancy)
      * cross_encoder: Cross-Encoder (most accurate)
      * node_distance: Node Distance (requires focal_node_uuid)
      * episode_mentions: Episode Mentions (frequency-based)
      * none: No reranking
    
    Based on: https://help.getzep.com/graphiti/working-with-data/searching
    """
    
    # Option 1: LLM-powered intelligent strategy selection
    if req.use_llm_classification:
        logger.info(f"🤖 Using LLM classification for query: '{req.query[:50]}...'")
        
        smart_service = SmartSearchService()
        context = {
            "project_id": req.group_id,
            "current_file": req.current_file,
            "conversation_type": req.conversation_type,
            "recent_queries": req.recent_queries,
            "limit": req.limit
        }
        
        return await smart_service.smart_search(
            query=req.query,
            graphiti=graphiti,
            context=context,
            force_strategy=None  # Let LLM decide
        )
    
    # Option 2: Manual strategy selection (backward compatible)
    else:
        return await search_knowledge_graph(
            query=req.query,
            graphiti=graphiti,
            focal_node_uuid=req.focal_node_uuid,
            group_id=req.group_id,
            limit=req.limit,
            rerank_strategy=req.rerank_strategy or "rrf"
        )

