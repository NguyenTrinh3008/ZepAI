# app/config.py
"""
Centralized configuration for the memory layer

All configuration values, environment variables, and constants
are defined here for easy management and modification.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


# =============================================================================
# NEO4J CONFIGURATION
# =============================================================================

class Neo4jConfig:
    """Neo4j database configuration"""
    
    URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER: str = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j")
    
    @classmethod
    def get_uri(cls) -> str:
        return cls.URI
    
    @classmethod
    def get_user(cls) -> str:
        return cls.USER
    
    @classmethod
    def get_password(cls) -> str:
        return cls.PASSWORD


# =============================================================================
# OPENAI / LLM CONFIGURATION
# =============================================================================

class LLMConfig:
    """LLM and embedding configuration"""
    
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
    
    # Translation settings
    TRANSLATION_TEMPERATURE: float = 0.2
    TRANSLATION_MAX_TOKENS: int = 100
    
    # Summarization settings
    USE_LLM_SUMMARIZATION: bool = os.getenv("USE_LLM_SUMMARIZATION", "true").lower() == "true"
    SUMMARY_MAX_LENGTH: int = int(os.getenv("SUMMARY_MAX_LENGTH", "200"))
    SUMMARY_TEMPERATURE: float = 0.2  # Low temp for consistent summaries
    SUMMARY_MAX_TOKENS: int = 250
    
    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return cls.OPENAI_API_KEY
    
    @classmethod
    def get_model_name(cls) -> str:
        return cls.MODEL_NAME


# =============================================================================
# LANGFUSE CONFIGURATION
# =============================================================================

class LangfuseConfig:
    """Langfuse tracing and observability configuration"""
    
    # Langfuse Cloud credentials
    PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    # Service identification
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "graphiti-memory-layer")
    SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "1.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Feature flags
    ENABLED: bool = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
    DEBUG: bool = os.getenv("LANGFUSE_DEBUG", "false").lower() == "true"
    
    # Sampling and batching
    SAMPLE_RATE: float = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))  # 1.0 = trace everything
    FLUSH_INTERVAL: int = int(os.getenv("LANGFUSE_FLUSH_INTERVAL", "5"))  # seconds
    
    # Tracing configuration
    TRACE_SEARCH_QUERIES: bool = True
    TRACE_INGEST_OPERATIONS: bool = True
    TRACE_LLM_CALLS: bool = True
    TRACE_DATABASE_QUERIES: bool = False  # Can be verbose
    
    # Enhanced metadata
    INCLUDE_REQUEST_ID: bool = True
    INCLUDE_TIMESTAMP: bool = True
    INCLUDE_USER_AGENT: bool = True
    INCLUDE_SOURCE_INFO: bool = True
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if Langfuse is enabled and configured"""
        return cls.ENABLED and cls.PUBLIC_KEY and cls.SECRET_KEY
    
    @classmethod
    def get_credentials(cls) -> dict:
        """Get Langfuse credentials"""
        return {
            "public_key": cls.PUBLIC_KEY,
            "secret_key": cls.SECRET_KEY,
            "host": cls.HOST
        }


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

class CacheConfig:
    """Cache TTL and configuration"""
    
    # Search cache (30 minutes)
    SEARCH_CACHE_TTL_SECONDS: int = 30 * 60
    
    # Node cache (15 minutes)
    NODE_CACHE_TTL_SECONDS: int = 15 * 60
    
    # Graphiti search cache (1 hour)
    GRAPHITI_SEARCH_TTL_SECONDS: int = 60 * 60
    
    # Default in-memory cache (1 hour)
    DEFAULT_CACHE_TTL_SECONDS: int = 60 * 60
    
    # Conversation/entity TTL (2 days / 48 hours)
    CONVERSATION_TTL_DAYS: int = 2
    CONVERSATION_TTL_SECONDS: int = 2 * 24 * 60 * 60  # 48 hours
    
    @classmethod
    def get_search_ttl(cls) -> int:
        return cls.SEARCH_CACHE_TTL_SECONDS
    
    @classmethod
    def get_node_ttl(cls) -> int:
        return cls.NODE_CACHE_TTL_SECONDS
    
    @classmethod
    def get_conversation_ttl_days(cls) -> int:
        return cls.CONVERSATION_TTL_DAYS


# =============================================================================
# TEXT AND CONTENT LIMITS
# =============================================================================

class ContentConfig:
    """Content length and formatting limits"""
    
    # Maximum text length before truncation
    MAX_TEXT_LENGTH: int = 400
    MAX_TEXT_DISPLAY_LENGTH: int = 397  # MAX_TEXT_LENGTH - 3 (for "...")
    
    # Name length limits
    MAX_NAME_LENGTH: int = 80
    
    # Summary limits
    MAX_SUMMARY_LENGTH: int = 400
    
    # Related nodes limits
    MAX_RELATED_NODES_DISPLAY: int = 2
    
    @classmethod
    def get_max_text_length(cls) -> int:
        return cls.MAX_TEXT_LENGTH
    
    @classmethod
    def get_max_display_length(cls) -> int:
        return cls.MAX_TEXT_DISPLAY_LENGTH


# =============================================================================
# SEARCH CONFIGURATION
# =============================================================================

class SearchConfig:
    """Search behavior and limits"""
    
    # Default search result limit
    DEFAULT_LIMIT: int = 10
    
    # Maximum search results
    MAX_LIMIT: int = 50
    
    # Minimum search results
    MIN_LIMIT: int = 1
    
    # Reranking strategies
    DEFAULT_RERANK_STRATEGY: str = "rrf"  # Reciprocal Rank Fusion (default)
    
    # Built-in strategies (always available via graphiti.search())
    BUILTIN_STRATEGIES = {
        "rrf": "Reciprocal Rank Fusion - Combines BM25 and semantic search (DEFAULT)",
        "node_distance": "Node Distance - Prioritizes results near focal node (requires focal_node_uuid)",
        "none": "No reranking - Raw search results"
    }
    
    # Advanced strategies (require graphiti._search() + SearchConfig recipes)
    # May not be available in all graphiti-core versions
    ADVANCED_STRATEGIES = {
        "mmr": "Maximal Marginal Relevance - Reduces redundancy, increases diversity",
        "cross_encoder": "Cross-Encoder - Most accurate, uses LLM classification",
        "episode_mentions": "Episode Mentions - Based on episode frequency"
    }
    
    # All available reranking strategies (based on Graphiti documentation)
    RERANK_STRATEGIES = {**BUILTIN_STRATEGIES, **ADVANCED_STRATEGIES}
    
    # Cross-encoder configuration
    CROSS_ENCODER_PROVIDER: str = os.getenv("CROSS_ENCODER_PROVIDER", "openai")  # openai, gemini, bge
    
    # MMR diversity parameter (0=relevance only, 1=diversity only)
    MMR_LAMBDA: float = 0.5
    
    @classmethod
    def get_default_limit(cls) -> int:
        return cls.DEFAULT_LIMIT
    
    @classmethod
    def get_default_rerank_strategy(cls) -> str:
        return cls.DEFAULT_RERANK_STRATEGY
    
    @classmethod
    def get_available_strategies(cls) -> dict:
        return cls.RERANK_STRATEGIES
    
    @classmethod
    def is_valid_strategy(cls, strategy: str) -> bool:
        return strategy in cls.RERANK_STRATEGIES
    
    @classmethod
    def is_builtin_strategy(cls, strategy: str) -> bool:
        """Check if strategy is built-in (always available)"""
        return strategy in cls.BUILTIN_STRATEGIES
    
    @classmethod
    def is_advanced_strategy(cls, strategy: str) -> bool:
        """Check if strategy requires advanced _search() method"""
        return strategy in cls.ADVANCED_STRATEGIES
    
    @classmethod
    def get_mmr_lambda(cls) -> float:
        return cls.MMR_LAMBDA
    
    @classmethod
    def get_cross_encoder_provider(cls) -> str:
        return cls.CROSS_ENCODER_PROVIDER
    
    @classmethod
    def validate_limit(cls, limit: int) -> int:
        """Ensure limit is within valid range"""
        return max(cls.MIN_LIMIT, min(limit, cls.MAX_LIMIT))


# =============================================================================
# METADATA FIELDS CONFIGURATION
# =============================================================================

class MetadataFields:
    """Metadata field definitions for enrichment"""
    
    CODE_METADATA_FIELDS = [
        "file_path", "change_type", "severity", "lines_added", 
        "lines_removed", "imports", "function_name", "change_summary",
        "language", "diff_summary"
    ]
    
    CONVERSATION_METADATA_FIELDS = [
        "project_id", "request_id", "chat_id", "chat_mode", 
        "model", "total_tokens", "message_count", 
        "context_file_count", "tool_call_count"
    ]
    
    @classmethod
    def get_code_fields(cls) -> list:
        return cls.CODE_METADATA_FIELDS.copy()
    
    @classmethod
    def get_conversation_fields(cls) -> list:
        return cls.CONVERSATION_METADATA_FIELDS.copy()


# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

class AppConfig:
    """General application configuration"""
    
    APP_NAME: str = "Graphiti Memory Layer"
    APP_DESCRIPTION: str = "Knowledge Graph Memory System for AI Coding Assistants"
    VERSION: str = "2.0.0"
    
    # Feature flags
    ENABLE_CACHING: bool = True
    ENABLE_TRANSLATION: bool = True
    ENABLE_METADATA_ENRICHMENT: bool = True
    
    @classmethod
    def get_app_name(cls) -> str:
        return cls.APP_NAME


# =============================================================================
# CONVENIENCE ACCESS
# =============================================================================

# Export commonly used configs for easy access
neo4j = Neo4jConfig
llm = LLMConfig
langfuse = LangfuseConfig
cache = CacheConfig
content = ContentConfig
search = SearchConfig
metadata = MetadataFields
app = AppConfig
