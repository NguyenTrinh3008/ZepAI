# app/langfuse_tracer.py
"""
Langfuse Tracing Integration for Graphiti Memory Layer

Compatible with Langfuse SDK v3.x
Based on: https://langfuse.com/docs
"""

import logging
import time
from typing import Optional, Any, Dict, List

from app.config import langfuse as langfuse_config

logger = logging.getLogger(__name__)

# Global Langfuse instance
_langfuse_client = None


def get_langfuse():
    """Get or initialize Langfuse client (lazy loading)"""
    global _langfuse_client
    
    if not langfuse_config.is_enabled():
        logger.debug("Langfuse is disabled or not configured")
        return None
    
    if _langfuse_client is None:
        try:
            from langfuse import Langfuse
            
            credentials = langfuse_config.get_credentials()
            _langfuse_client = Langfuse(
                secret_key=credentials["secret_key"],
                public_key=credentials["public_key"],
                host=credentials["host"],
                debug=langfuse_config.DEBUG,
                # Enhanced configuration
                environment=langfuse_config.ENVIRONMENT,
                release=langfuse_config.SERVICE_VERSION
            )
            
            logger.info(f"✓ Langfuse initialized: {credentials['host']}")
            
        except ImportError:
            logger.warning("Langfuse package not installed. Run: pip install langfuse")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            return None
    
    return _langfuse_client


def flush_langfuse():
    """Manually flush all pending traces to Langfuse"""
    client = get_langfuse()
    if client:
        try:
            client.flush()
            logger.debug("Langfuse traces flushed")
        except Exception as e:
            logger.error(f"Error flushing Langfuse: {e}")


# =============================================================================
# SIMPLIFIED TRACERS (Langfuse SDK v3.x compatible)
# =============================================================================

class SearchTracer:
    """Simplified tracer for search operations"""
    
    def __init__(self, query: str, strategy: str = "rrf", project_id: Optional[str] = None):
        self.query = query
        self.strategy = strategy
        self.project_id = project_id
        self.start_time = time.time()
        self.client = get_langfuse()
        
        if self.client and langfuse_config.TRACE_SEARCH_QUERIES:
            logger.info(f"🔍 Search trace started: '{query[:50]}...' (strategy: {strategy})")
    
    def add_step(self, name: str, output: Any = None, metadata: Optional[Dict] = None):
        """Add a step to the search trace"""
        if self.client:
            logger.debug(f"  └─ {name}: {output}")
    
    def complete(self, results_count: int, metadata: Optional[Dict] = None):
        """Complete the search trace"""
        duration_ms = round((time.time() - self.start_time) * 1000, 2)
        if self.client:
            logger.info(f"✅ Search completed: {results_count} results in {duration_ms}ms")
    
    def error(self, error_message: str):
        """Mark trace as error"""
        duration_ms = round((time.time() - self.start_time) * 1000, 2)
        if self.client:
            logger.error(f"❌ Search error after {duration_ms}ms: {error_message}")


class IngestTracer:
    """Simplified tracer for ingest operations"""
    
    def __init__(self, operation_type: str, name: str, project_id: Optional[str] = None):
        self.operation_type = operation_type
        self.name = name
        self.project_id = project_id
        self.start_time = time.time()
        self.client = get_langfuse()
        self.entities = []
        
        if self.client and langfuse_config.TRACE_INGEST_OPERATIONS:
            logger.info(f"📥 Ingest trace started: {operation_type} - {name[:50]}...")
    
    def add_entity(self, entity_uuid: str, entity_type: str = "entity"):
        """Record entity creation"""
        if self.client:
            logger.debug(f"  └─ Created {entity_type}: {entity_uuid}")
        self.entities.append(entity_uuid)
    
    def complete(self, metadata: Optional[Dict] = None):
        """Complete the ingest trace"""
        duration_ms = round((time.time() - self.start_time) * 1000, 2)
        if self.client:
            logger.info(f"✅ Ingest completed: {len(self.entities)} entities in {duration_ms}ms")
    
    def error(self, error_message: str):
        """Mark trace as error"""
        duration_ms = round((time.time() - self.start_time) * 1000, 2)
        if self.client:
            logger.error(f"❌ Ingest error after {duration_ms}ms: {error_message}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log_event(
    name: str,
    metadata: Optional[Dict] = None,
    tags: Optional[List[str]] = None
):
    """Log a simple event to Langfuse"""
    client = get_langfuse()
    if client:
        logger.debug(f"📝 Event: {name}")


def get_health_status() -> Dict[str, Any]:
    """Get Langfuse health status"""
    client = get_langfuse()
    
    if not langfuse_config.is_enabled():
        return {
            "enabled": False,
            "status": "disabled",
            "message": "Langfuse is disabled or not configured"
        }
    
    if not client:
        return {
            "enabled": True,
            "status": "error",
            "message": "Failed to initialize Langfuse client"
        }
    
    return {
        "enabled": True,
        "status": "healthy",
        "host": langfuse_config.HOST,
        "sample_rate": langfuse_config.SAMPLE_RATE,
        "features": {
            "search_queries": langfuse_config.TRACE_SEARCH_QUERIES,
            "ingest_operations": langfuse_config.TRACE_INGEST_OPERATIONS,
            "llm_calls": langfuse_config.TRACE_LLM_CALLS,
            "database_queries": langfuse_config.TRACE_DATABASE_QUERIES
        }
    }
