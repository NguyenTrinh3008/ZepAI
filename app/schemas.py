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
