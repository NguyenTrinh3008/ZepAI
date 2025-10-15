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
from fastapi import FastAPI, Request, status, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

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


@app.get("/", operation_id="root")
def root():
    """
    Root endpoint - API documentation
    """
    return {
        "status": "ok",
        "service": "graphiti-memory-layer",
        "version": "2.0.0",
        "core_tools": {
            # 🔍 SEARCH (2 tools)
            "/search": "POST - Search knowledge graph (supports LLM classification via use_llm_classification=true)",
            "/search/code": "POST - Search code memories with filters",
            
            # 📥 INGEST (6 tools)
            "/ingest/text": "POST - Ingest plain text",
            "/ingest/message": "POST - Ingest conversation messages",
            "/ingest/json": "POST - Ingest JSON data",
            "/ingest/code": "POST - Ingest simple code change with LLM scoring",
            "/ingest/code-context": "POST - Ingest code conversation metadata (advanced)",
            "/conversation/ingest": "POST - Ingest full conversation context",
        },
        "analytics": {
            # Conversation analytics
            "/conversation/requests/{project_id}": "GET - Get conversation requests",
            "/conversation/flow/{request_id}": "GET - Get conversation flow",
            "/conversation/context-stats/{project_id}": "GET - Get context file usage stats",
            "/conversation/tool-stats": "GET - Get tool call statistics",
            
            # Stats
            "/stats/{project_id}": "GET - Get project statistics",
            "/export/{group_id}": "GET - Export conversation to JSON",
        },
        "admin": {
            # Admin
            "/admin/cleanup": "POST - Manually cleanup expired memories",
            
            # Cache
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
        },
        "integrations": {
            # Innocody integration
            "/innocody/webhook": "POST - Receive Innocody DiffChunk",
            "/innocody/webhook/batch": "POST - Receive batch of DiffChunks",
            "/innocody/test/mock": "POST - Test with mock data",
            "/innocody/health": "GET - Health check"
        }
    }


@app.get("/favicon.ico", operation_id="favicon")
def favicon():
    """Favicon endpoint"""
    return Response(status_code=204)


# Backward compatibility endpoint removed - use /conversation/ingest instead
# Previous endpoint: POST /ingest/conversation → Now use: POST /conversation/ingest


# =============================================================================
# CENTRALIZED EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions (404, 500, etc.)"""
    logger.error(f"HTTP {exc.status_code} error: {exc.detail} - Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "path": str(request.url.path),
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.error(f"Validation error: {exc.errors()} - Path: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other unhandled exceptions"""
    logger.exception(f"Unhandled exception: {str(exc)} - Path: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "path": str(request.url.path),
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
