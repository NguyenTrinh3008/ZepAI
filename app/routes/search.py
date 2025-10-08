# app/routes/search.py
"""
Search endpoints
"""
from fastapi import APIRouter, Depends

from app.graph import get_graphiti
from app.schemas import SearchRequest
from app.services.search_service import search_knowledge_graph

router = APIRouter(prefix="", tags=["search"])


@router.post("/search")
async def search(req: SearchRequest, graphiti=Depends(get_graphiti)):
    """
    Search knowledge graph with semantic search
    
    Features:
    - Auto-translation for non-English queries
    - Hybrid search with focal nodes
    - Group ID filtering
    - Result caching (30 min TTL)
    """
    return await search_knowledge_graph(
        query=req.query,
        graphiti=graphiti,
        focal_node_uuid=req.focal_node_uuid,
        group_id=req.group_id
    )

