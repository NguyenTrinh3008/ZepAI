# app/main.py
"""
Main FastAPI application - Refactored and modular

All business logic has been moved to:
- routes/basic.py - Basic ingest endpoints
- routes/code.py - Code context endpoints
- routes/conversation.py - Conversation context endpoints
- routes/search.py - Search endpoints
- routes/admin.py - Admin, debug, cache management
- services/search_service.py - Search business logic
"""
from fastapi import FastAPI, Depends
from fastapi.responses import Response

from app.schemas import IngestConversationContext
from app.graph import get_graphiti

# Create FastAPI app
app = FastAPI(
    title="Graphiti Memory Layer",
    description="Knowledge Graph Memory System for AI Coding Assistants",
    version="2.0.0"
)

# Import and register routers
from app.routes import basic, code, conversation, search, admin
from app.innocody_routes import router as innocody_router

# Register all routers
app.include_router(basic.router)
app.include_router(code.router)
app.include_router(conversation.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(innocody_router)


@app.get("/")
def root():
    """
    Root endpoint - API documentation
    """
    return {
        "status": "ok",
        "service": "graphiti-memory-layer",
        "version": "2.0.0",
        "endpoints": {
            # Basic ingest
            "/ingest/text": "POST - Ingest plain text",
            "/ingest/message": "POST - Ingest conversation messages",
            "/ingest/json": "POST - Ingest JSON data",
            
            # Code context
            "/ingest/code": "POST - Ingest simple code change with LLM scoring",
            "/ingest/code-context": "POST - Ingest code conversation metadata (Phase 1+)",
            "/search/code": "POST - Search code memories with filters",
            
            # Conversation context (Phase 1.5)
            "/conversation/ingest": "POST - Ingest full conversation context",
            "/conversation/requests/{project_id}": "GET - Get conversation requests",
            "/conversation/flow/{request_id}": "GET - Get conversation flow",
            "/conversation/context-stats/{project_id}": "GET - Get context file usage stats",
            "/conversation/tool-stats": "GET - Get tool call statistics",
            
            # Search
            "/search": "POST - Search knowledge graph",
            
            # Admin & Stats
            "/stats/{project_id}": "GET - Get project statistics",
            "/export/{group_id}": "GET - Export conversation to JSON",
            "/admin/cleanup": "POST - Manually cleanup expired memories",
            
            # Cache management
            "/cache/stats": "GET - Get cache statistics",
            "/cache/clear": "POST - Clear all cache",
            "/cache/clear-search": "POST - Clear search cache",
            "/cache/clear-node/{node_uuid}": "POST - Clear node cache",
            "/cache/health": "GET - Check cache health",
            
            # Config
            "/config/neo4j": "GET - Get Neo4j configuration",
            "/config/reload-neo4j": "POST - Reload Neo4j configuration",
            
            # Debug
            "/debug/all-entities": "GET - Show all entities (debug)",
            "/debug/entity/{entity_uuid}": "GET - Show entity detail (debug)",
            "/debug/episodes/{group_id}": "GET - Show episodes by group (debug)",
            
            # Innocody integration
            "/innocody/webhook": "POST - Receive Innocody DiffChunk",
            "/innocody/webhook/batch": "POST - Receive batch of DiffChunks",
            "/innocody/test/mock": "POST - Test with mock data",
            "/innocody/health": "GET - Health check"
        }
    }


@app.get("/favicon.ico")
def favicon():
    """Favicon endpoint"""
    return Response(status_code=204)


# For backward compatibility - redirect old endpoint
@app.post("/ingest/conversation")
async def ingest_conversation_compat(
    payload: IngestConversationContext,
    graphiti=Depends(get_graphiti)
):
    """
    Backward compatibility: redirect to /conversation/ingest
    This will be removed in future versions.
    
    Note: This is a simple wrapper that calls the actual endpoint from routes.
    """
    from app.routes.conversation import ingest_conversation
    
    return await ingest_conversation(payload, graphiti)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
