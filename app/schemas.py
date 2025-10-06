# app/schemas.py
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from typing import Optional, Any, List, Dict

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

# =============================================================================
# SHORT TERM MEMORY SCHEMAS - For chat message storage
# =============================================================================

class ShortTermMemoryMetadata(BaseModel):
    """Metadata for short term memory message"""
    conversation_id: str                      # Required: ID of the conversation
    file_path: Optional[str] = None           # File path if related to code
    function_name: Optional[str] = None       # Function name if related to code
    line_start: Optional[int] = None          # Starting line number of code range that AI modified
    line_end: Optional[int] = None            # Ending line number of code range that AI modified
    code_changes: Optional[Dict[str, Any]] = None  # Detailed code changes made by AI
    lines_added: Optional[int] = None              # Number of lines added by AI
    lines_removed: Optional[int] = None            # Number of lines removed by AI
    diff_summary: Optional[str] = None             # Summary of line changes
    intent: Optional[str] = None              # Intent of the message (question, request, etc.)
    keywords: Optional[List[str]] = None      # Extracted keywords
    embedding: List[float]                    # Required: Vector embedding for similarity search
    ttl: Optional[int] = None                 # Time to live in seconds

class ShortTermMemory(BaseModel):
    """Schema for storing chat messages in short term memory"""
    id: str                                   # Required: Unique message ID
    role: str                                 # Required: "user", "assistant", "system"
    content: str                              # Required: Message content
    timestamp: str                            # Required: ISO8601 timestamp
    project_id: str                           # Required: Project identifier
    metadata: ShortTermMemoryMetadata         # Required: Message metadata

class ShortTermMemoryRequest(BaseModel):
    """Request to save a message to short term memory"""
    role: str                                 # "user", "assistant", "system"
    content: str                              # Message content
    project_id: str                           # Project identifier
    conversation_id: str                      # Conversation identifier
    file_path: Optional[str] = None           # File path if related to code
    function_name: Optional[str] = None       # Function name if related to code
    line_start: Optional[int] = None          # Starting line number of code range that AI modified
    line_end: Optional[int] = None            # Ending line number of code range that AI modified
    code_changes: Optional[Dict[str, Any]] = None  # Detailed code changes made by AI
    lines_added: Optional[int] = None              # Number of lines added by AI
    lines_removed: Optional[int] = None            # Number of lines removed by AI
    diff_summary: Optional[str] = None             # Summary of line changes
    intent: Optional[str] = None              # Intent of the message
    keywords: Optional[List[str]] = None      # Extracted keywords
    ttl: Optional[int] = None                 # Time to live in seconds

class ShortTermMemorySearchRequest(BaseModel):
    """Request to search short term memory"""
    query: str                                # Search query
    project_id: str                           # Project identifier
    conversation_id: Optional[str] = None     # Filter by conversation
    role: Optional[str] = None                # Filter by role
    limit: Optional[int] = 10                 # Maximum results to return

# =============================================================================
# CONVERSATION STORAGE SCHEMA - For detailed conversation tracking
# =============================================================================

class ContextFile(BaseModel):
    """Context file information"""
    file_path: str
    usefulness: float
    content_hash: str
    source: str = "vecdb"
    symbols: List[str] = []

class ToolCall(BaseModel):
    """Tool call information"""
    tool_call_id: str
    tool_name: str
    arguments_hash: str
    status: str = "success"
    execution_time_ms: int = 200

class CodeChange(BaseModel):
    """Code change information"""
    name: str
    summary: str
    file_path: str
    function_name: Optional[str] = None
    change_type: str
    change_summary: str
    severity: str
    diff_summary: str
    lines_added: int = 0
    lines_removed: int = 0
    language: str = "python"
    imports: List[str] = []
    code_before_hash: str
    code_after_hash: str
    timestamp: str

class ConversationMessage(BaseModel):
    """Individual conversation message"""
    sequence: int
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str
    total_tokens: int = 0
    metadata: Dict[str, Any] = {}

class ModelResponse(BaseModel):
    """Model response information"""
    model: str
    finish_reason: str = "stop"

class ConversationPayload(BaseModel):
    """Complete conversation payload for storage"""
    request_id: str
    project_id: str
    timestamp: str
    chat_meta: Dict[str, Any]
    messages: List[ConversationMessage]
    context_files: List[ContextFile] = []
    tool_calls: List[ToolCall] = []
    checkpoints: List[Dict[str, Any]] = []
    code_changes: List[CodeChange] = []
    model_response: ModelResponse
    group_id: Optional[str] = None