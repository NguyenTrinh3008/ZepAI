# app/ai_helpers.py
"""
High-Level AI Integration Helpers

Provides simple, convenient functions for AI assistants to:
1. Search code memories
2. Format context for LLM
3. Generate prompts with context
4. Store new code changes

This is the main interface AI assistants should use.
"""

import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.context_formatters import (
    format_code_context,
    format_conversation_context,
    optimize_context_for_token_limit,
    deduplicate_memories
)
from app.prompts import (
    format_code_system_prompt,
    format_code_query_expansion,
    format_code_change_summary,
    get_prompt_config
)


class MemoryLayerClient:
    """Client for interacting with the Memory Layer API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", project_id: str = "default"):
        """Initialize client
        
        Args:
            base_url: Memory Layer API base URL
            project_id: Project identifier for memory isolation
        """
        self.base_url = base_url.rstrip('/')
        self.project_id = project_id
    
    def search_code(self, 
                   query: str,
                   file_filter: Optional[str] = None,
                   function_filter: Optional[str] = None,
                   change_type_filter: Optional[str] = None,
                   limit: int = 10) -> List[Dict[str, Any]]:
        """Search code memories
        
        Args:
            query: Search query text
            file_filter: Filter by file path (optional)
            function_filter: Filter by function name (optional)
            change_type_filter: Filter by change type (optional)
            limit: Maximum results (not directly supported by API, but we can truncate)
            
        Returns:
            List of memory dicts
        """
        payload = {
            "query": query,
            "project_id": self.project_id
        }
        
        if file_filter:
            payload["file_filter"] = file_filter
        if function_filter:
            payload["function_filter"] = function_filter
        if change_type_filter:
            payload["change_type_filter"] = change_type_filter
        
        try:
            response = requests.post(
                f"{self.base_url}/search/code",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            # Truncate to limit
            return results[:limit]
        
        except requests.exceptions.RequestException as e:
            print(f"Error searching code memories: {e}")
            return []
    
    def ingest_code_context(self,
                           name: str,
                           summary: str,
                           file_path: str,
                           change_type: str,
                           change_summary: str,
                           function_name: Optional[str] = None,
                           line_start: Optional[int] = None,
                           line_end: Optional[int] = None,
                           severity: Optional[str] = None) -> Optional[str]:
        """Store code change context
        
        Args:
            name: Short name for the change
            summary: Detailed summary (for embeddings)
            file_path: Path to the file
            change_type: Type of change (fixed, added, refactored, removed)
            change_summary: Brief change description
            function_name: Function affected (optional)
            line_start: Starting line number (optional)
            line_end: Ending line number (optional)
            severity: Severity level (optional)
            
        Returns:
            Episode ID if successful, None otherwise
        """
        payload = {
            "name": name,
            "summary": summary,
            "metadata": {
                "file_path": file_path,
                "change_type": change_type,
                "change_summary": change_summary,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "project_id": self.project_id
        }
        
        # Optional fields
        if function_name:
            payload["metadata"]["function_name"] = function_name
        if line_start is not None:
            payload["metadata"]["line_start"] = line_start
        if line_end is not None:
            payload["metadata"]["line_end"] = line_end
        if severity:
            payload["metadata"]["severity"] = severity
        
        try:
            response = requests.post(
                f"{self.base_url}/ingest/code-context",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('episode_id')
        
        except requests.exceptions.RequestException as e:
            print(f"Error ingesting code context: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get project statistics
        
        Returns:
            Stats dict with memory counts
        """
        try:
            response = requests.get(
                f"{self.base_url}/stats/{self.project_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Error getting stats: {e}")
            return {}


# =============================================================================
# High-Level Helper Functions
# =============================================================================

def get_code_context_for_query(query: str,
                               project_id: str,
                               base_url: str = "http://localhost:8000",
                               format_style: str = "relevance",
                               max_results: int = 10,
                               max_tokens: int = 1000) -> Tuple[str, List[Dict]]:
    """Get formatted code context for a query
    
    This is the main function AI assistants should use to retrieve code context.
    
    Args:
        query: User's query
        project_id: Project identifier
        base_url: Memory Layer API URL
        format_style: How to format results ("relevance", "chronological", "grouped", "compact")
        max_results: Maximum memories to retrieve
        max_tokens: Maximum tokens for context (approximate)
        
    Returns:
        Tuple of (formatted_context, raw_memories)
    """
    client = MemoryLayerClient(base_url, project_id)
    
    # Search for relevant memories
    memories = client.search_code(query, limit=max_results)
    
    if not memories:
        return "No relevant code context found.", []
    
    # Deduplicate
    memories = deduplicate_memories(memories)
    
    # Optimize for token budget
    memories = optimize_context_for_token_limit(memories, max_tokens)
    
    # Format for LLM consumption
    formatted = format_code_context(memories, style=format_style, query=query)
    
    return formatted, memories


def build_code_assistant_prompt(query: str,
                                project_id: str,
                                base_url: str = "http://localhost:8000",
                                include_context: bool = True) -> str:
    """Build a complete system prompt for code assistant with context
    
    Args:
        query: User's query
        project_id: Project identifier
        base_url: Memory Layer API URL
        include_context: Whether to include retrieved context
        
    Returns:
        Complete system prompt ready for LLM
    """
    if not include_context:
        from app.prompts import CODE_SYSTEM_PROMPT_BASE
        return CODE_SYSTEM_PROMPT_BASE
    
    # Get relevant memories
    client = MemoryLayerClient(base_url, project_id)
    memories = client.search_code(query, limit=10)
    
    if not memories:
        from app.prompts import CODE_SYSTEM_PROMPT_BASE
        return CODE_SYSTEM_PROMPT_BASE
    
    # Format as system prompt
    return format_code_system_prompt(memories)


def store_code_change(name: str,
                     summary: str,
                     file_path: str,
                     change_type: str,
                     change_summary: str,
                     project_id: str,
                     base_url: str = "http://localhost:8000",
                     **kwargs) -> bool:
    """Store a code change in memory
    
    Convenience function for storing code changes.
    
    Args:
        name: Short name
        summary: Detailed summary
        file_path: File path
        change_type: Change type (fixed/added/refactored/removed)
        change_summary: Brief change description
        project_id: Project identifier
        base_url: Memory Layer API URL
        **kwargs: Additional optional fields (function_name, line_start, line_end, severity)
        
    Returns:
        True if successful, False otherwise
    """
    client = MemoryLayerClient(base_url, project_id)
    
    episode_id = client.ingest_code_context(
        name=name,
        summary=summary,
        file_path=file_path,
        change_type=change_type,
        change_summary=change_summary,
        **kwargs
    )
    
    return episode_id is not None


def search_similar_bugs(bug_description: str,
                       project_id: str,
                       base_url: str = "http://localhost:8000",
                       limit: int = 5) -> List[Dict[str, Any]]:
    """Search for similar bugs in memory
    
    Args:
        bug_description: Description of the bug
        project_id: Project identifier
        base_url: Memory Layer API URL
        limit: Maximum results
        
    Returns:
        List of similar bug memories
    """
    client = MemoryLayerClient(base_url, project_id)
    
    # Search with "fixed" change type filter
    memories = client.search_code(
        query=bug_description,
        change_type_filter="fixed",
        limit=limit
    )
    
    return memories


def search_file_history(file_path: str,
                       project_id: str,
                       base_url: str = "http://localhost:8000") -> List[Dict[str, Any]]:
    """Get change history for a specific file
    
    Args:
        file_path: Path to the file
        project_id: Project identifier
        base_url: Memory Layer API URL
        
    Returns:
        List of changes to this file
    """
    client = MemoryLayerClient(base_url, project_id)
    
    # Search with file filter
    memories = client.search_code(
        query=file_path,  # Use filename as query
        file_filter=file_path,
        limit=50
    )
    
    return memories


def search_function_history(function_name: str,
                           project_id: str,
                           base_url: str = "http://localhost:8000") -> List[Dict[str, Any]]:
    """Get change history for a specific function
    
    Args:
        function_name: Function name
        project_id: Project identifier
        base_url: Memory Layer API URL
        
    Returns:
        List of changes to this function
    """
    client = MemoryLayerClient(base_url, project_id)
    
    # Search with function filter
    memories = client.search_code(
        query=function_name,
        function_filter=function_name,
        limit=20
    )
    
    return memories


# =============================================================================
# Context Enhancement Functions
# =============================================================================

def enhance_context_with_related(memories: List[Dict[str, Any]],
                                project_id: str,
                                base_url: str = "http://localhost:8000",
                                max_additional: int = 3) -> List[Dict[str, Any]]:
    """Enhance context by finding related memories
    
    For each memory, find related memories from same file or function.
    
    Args:
        memories: Initial memories
        project_id: Project identifier
        base_url: Memory Layer API URL
        max_additional: Maximum additional memories per file
        
    Returns:
        Enhanced list with related memories
    """
    if not memories:
        return memories
    
    client = MemoryLayerClient(base_url, project_id)
    enhanced = list(memories)
    seen_ids = {m.get('id') for m in memories}
    
    # For each file mentioned, get a few more recent changes
    files_seen = set()
    for mem in memories:
        file_path = mem.get('file_path')
        if file_path and file_path not in files_seen:
            files_seen.add(file_path)
            
            related = client.search_code(
                query=file_path,
                file_filter=file_path,
                limit=max_additional + len(memories)
            )
            
            # Add unseen related memories
            added = 0
            for r in related:
                if r.get('id') not in seen_ids and added < max_additional:
                    enhanced.append(r)
                    seen_ids.add(r.get('id'))
                    added += 1
    
    return enhanced


def format_context_as_markdown(memories: List[Dict[str, Any]]) -> str:
    """Format memories as clean markdown for documentation
    
    Args:
        memories: List of memory dicts
        
    Returns:
        Markdown formatted string
    """
    if not memories:
        return "No code context available."
    
    lines = ["# Code Change History\n"]
    
    # Group by file
    by_file = {}
    for mem in memories:
        file_path = mem.get('file_path', 'Unknown')
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(mem)
    
    # Format each file section
    for file_path, file_mems in by_file.items():
        lines.append(f"## {file_path}\n")
        
        for mem in file_mems:
            change_type = mem.get('change_type', 'changed')
            text = mem.get('text', mem.get('summary', ''))
            function = mem.get('function_name')
            created = mem.get('created_at', '')
            
            lines.append(f"### {change_type.title()}")
            if function:
                lines.append(f"**Function:** `{function}()`")
            if created:
                lines.append(f"**When:** {created}")
            lines.append(f"\n{text}\n")
    
    return "\n".join(lines)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example: Get code context for a query
    context, memories = get_code_context_for_query(
        query="authentication bugs",
        project_id="my_project",
        format_style="relevance",
        max_results=5
    )
    
    print("=== Formatted Context ===")
    print(context)
    print("\n=== Raw Memories ===")
    print(f"Found {len(memories)} memories")
    
    # Example: Store a code change
    success = store_code_change(
        name="Fixed login timeout",
        summary="Fixed timeout issue in login_user() by increasing session timeout from 5 to 30 seconds",
        file_path="src/auth/auth_service.py",
        change_type="fixed",
        change_summary="Increased session timeout",
        function_name="login_user",
        severity="medium",
        project_id="my_project"
    )
    
    print(f"\nStore success: {success}")
    
    # Example: Search similar bugs
    similar = search_similar_bugs(
        bug_description="login timeout error",
        project_id="my_project",
        limit=3
    )
    
    print(f"\nFound {len(similar)} similar bugs")
