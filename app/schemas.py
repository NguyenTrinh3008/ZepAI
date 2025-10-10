# app/schemas.py
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from typing import Optional, Any, List

class IngestText(BaseModel):
    name: str
    text: str
    reference_time: Optional[str] = None
    source_description: Optional[str] = "app"
    group_id: Optional[str] = None

class IngestMessage(BaseModel):
    name: str
    messages: List[str]
    reference_time: Optional[str] = None
    source_description: Optional[str] = "chat"
    group_id: Optional[str] = None

class IngestJSON(BaseModel):
    name: str
    data: Any = Field(alias="json")  # tránh trùng tên method .json()
    reference_time: Optional[str] = None
    source_description: Optional[str] = "json"
    group_id: Optional[str] = None

    # Pydantic v2 config: allow population by field alias ("json" -> data)
    model_config = ConfigDict(populate_by_name=True)


class SearchRequest(BaseModel):
    query: str
    focal_node_uuid: Optional[str] = None
    group_id: Optional[str] = None  # Filter by conversation group
    limit: int = 10  # Maximum number of results to return
    rerank_strategy: Optional[str] = "rrf"  # Reranking strategy: rrf, mmr, cross_encoder, node_distance, episode_mentions, none
    
    # LLM-powered classification context (optional)
    use_llm_classification: bool = False  # Enable LLM-based strategy selection
    current_file: Optional[str] = None  # Current file being edited
    conversation_type: Optional[str] = None  # debugging, learning, implementation, exploration
    recent_queries: Optional[List[str]] = None  # Recent search queries for context

# =============================================================================
# SIMPLE CODE CHANGE SCHEMA - For UI testing
# =============================================================================

class IngestCodeChange(BaseModel):
    """Simple code change schema for UI testing and importance scoring"""
    project_id: str
    name: str
    change_type: str  # "fixed", "added", "refactored", "removed", "updated"
    severity: str  # "critical", "high", "medium", "low"
    file_path: str
    summary: str

# =============================================================================
# CODE CONTEXT SCHEMAS - For coding assistant memory
# =============================================================================

class CodeReference(BaseModel):
    """Reference to code stored in external long-term system (NOT actual code!)"""
    code_id: str                    # ID from external code storage system
    code_hash: str                  # SHA256 hash for verification
    language: str                   # "python", "javascript", "typescript", etc.
    line_count: Optional[int] = None

class CodeMetadata(BaseModel):
    """Metadata about code changes WITHOUT storing actual code content"""
    # Location info
    file_path: Optional[str] = None           # "src/auth/auth_service.py"
    function_name: Optional[str] = None        # "login_user"
    line_start: Optional[int] = None          # Starting line number
    line_end: Optional[int] = None            # Ending line number
    
    # Change info
    change_type: str                          # "modified", "fixed", "added", "refactored", "deleted"
    change_summary: str                       # Human-readable summary (max 500 chars)
    severity: Optional[str] = None            # For bugs: "critical", "high", "medium", "low"
    
    # Phase 1 Schema Extensions (for CodeFile/CodeChange labels)
    entity_type: Optional[str] = None         # "code_file" or "code_change" (for Neo4j labels)
    imports: Optional[List[str]] = None       # List of imported modules/files
    language: Optional[str] = None            # "python", "javascript", "go", etc.
    
    # References to external storage (NO code content!)
    code_before_ref: Optional[CodeReference] = None
    code_after_ref: Optional[CodeReference] = None
    
    # Diff summary (lightweight)
    lines_added: Optional[int] = None
    lines_removed: Optional[int] = None
    diff_summary: Optional[str] = None        # "Added null check on line 3"
    
    # Git info
    git_commit: Optional[str] = None
    
    # Timestamp
    timestamp: str                            # ISO8601

class IngestCodeContext(BaseModel):
    """Ingest code conversation metadata (NOT actual code!)"""
    name: str                                 # Short name: "Fixed login bug"
    summary: str                              # Human-readable summary (REQUIRED for embeddings!)
    metadata: CodeMetadata                    # Code-specific metadata
    project_id: str                           # Strict project isolation
    reference_time: Optional[str] = None      # ISO8601, defaults to now

class SearchCodeRequest(BaseModel):
    """Search code memories with filters"""
    query: str                                # Search query text
    project_id: str                           # Required - strict project isolation
    file_filter: Optional[str] = None         # Filter by file name/path
    function_filter: Optional[str] = None     # Filter by function name
    change_type_filter: Optional[str] = None  # Filter by change type: "fixed", "added", etc.
    days_ago: Optional[int] = 2               # Filter by time: default last 2 days
    focal_node_uuid: Optional[str] = None     # Optional focal node for search
    
    # Phase 1+ Schema Extension Filters
    language_filter: Optional[str] = None     # Filter by language: "python", "javascript", etc.
    entity_type_filter: Optional[str] = None  # Filter by entity type: "code_change" (default), "code_file", etc.


# =============================================================================
# PHASE 1.5: FULL CONVERSATION CONTEXT SCHEMAS
# =============================================================================

class ChatMetadata(BaseModel):
    """Chat metadata từ Innocody ChatMeta"""
    chat_id: str
    base_chat_id: Optional[str] = None
    request_attempt_id: Optional[str] = None
    chat_mode: Optional[str] = "AGENT"  # AGENT, NO_TOOLS, etc.
    force_initial_state: bool = False
    chat_remote: Optional[str] = None


class MessagePayload(BaseModel):
    """Single chat message (user or assistant)"""
    role: str  # "user" | "assistant" | "system"
    content_summary: str  # Summary of content (không lưu full content)
    content_hash: Optional[str] = None  # SHA256 hash của full content
    
    # Token usage
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    
    # Tool calls (if assistant message)
    tool_calls: List[dict] = []  # [{id, tool, args_hash}]
    
    # Sequence
    sequence: int = 0  # Message order in conversation


class ContextFilePayload(BaseModel):
    """File context fed to model"""
    file_path: str
    line_start: int = 1
    line_end: Optional[int] = None
    
    # Metadata
    usefulness: Optional[float] = None  # 0.0-1.0 score from Innocody
    source: str = "unknown"  # "vecdb" | "ast" | "manual"
    symbols: List[str] = []  # Extracted symbols/functions
    content_hash: str  # SHA256 (không lưu content)
    
    language: Optional[str] = None


class ToolCallPayload(BaseModel):
    """Tool invocation"""
    tool_call_id: str
    tool_name: str
    arguments_hash: str  # SHA256 of arguments (không lưu full args)
    
    # Result
    status: str = "success"  # "success" | "failed"
    execution_time_ms: Optional[int] = None
    
    # Link to changes
    diff_chunk_id: Optional[str] = None


class CheckpointPayload(BaseModel):
    """Git checkpoint/snapshot"""
    checkpoint_id: str
    parent_checkpoint: Optional[str] = None
    workspace_dir: Optional[str] = None
    git_hash: Optional[str] = None


class ModelResponseMetadata(BaseModel):
    """Model response metadata"""
    model: str
    finish_reason: Optional[str] = None
    created: Optional[float] = None  # Unix timestamp
    cached: bool = False
    compression_strength: Optional[float] = None


class CodeChangeMetadata(BaseModel):
    """Detailed code change metadata for conversation context."""
    # Identity
    name: Optional[str] = None                    # Human-friendly name
    summary: Optional[str] = None                # Optional summary
    description: Optional[str] = None            # Optional long description

    # Location info
    file_path: str                                # Required path
    function_name: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    # Change info
    change_type: Optional[str] = None             # added/modified/removed...
    change_summary: Optional[str] = None
    severity: Optional[str] = None
    diff_summary: Optional[str] = None

    # Metrics
    lines_added: Optional[int] = None
    lines_removed: Optional[int] = None

    # Hashes / references
    code_before_hash: Optional[str] = None
    code_after_hash: Optional[str] = None
    code_before_id: Optional[str] = None
    code_after_id: Optional[str] = None

    # Language/context
    language: Optional[str] = None
    imports: Optional[List[str]] = None

    # Git / timestamps
    tool_call_id: Optional[str] = None
    diff_chunk_id: Optional[str] = None
    git_commit: Optional[str] = None
    timestamp: Optional[str] = None


class IngestConversationContext(BaseModel):
    """
    Full conversation context ingest - Phase 1.5
    Lưu TOÀN BỘ ngữ cảnh của 1 conversation turn
    """
    # Request info
    request_id: str
    project_id: str
    timestamp: str  # ISO8601
    
    # Chat metadata
    chat_meta: ChatMetadata
    
    # Messages in this turn
    messages: List[MessagePayload]
    
    # Context files used
    context_files: List[ContextFilePayload] = []
    
    # Tool calls
    tool_calls: List[ToolCallPayload] = []
    
    # Code changes (reuse existing schema)
    code_changes: List[CodeChangeMetadata] = []  # Detailed code change metadata
    
    # Checkpoints
    checkpoints: List[CheckpointPayload] = []
    
    # Model response
    model_response: Optional[ModelResponseMetadata] = None
    
    # Related artifacts
    related_artifacts: List[dict] = []  # Links to logs/notes
