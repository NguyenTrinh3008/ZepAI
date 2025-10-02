# app/context_formatters.py
"""
Context Formatters for LLM Consumption

Converts raw memory search results into well-structured context
that AI assistants can easily understand and use.

Design Principles:
1. Clarity - Easy for LLM to parse and understand
2. Relevance - Prioritize important information
3. Conciseness - Avoid overwhelming the context window
4. Structure - Consistent formatting for reliable parsing
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class ContextFormatter:
    """Base formatter for memory context"""
    
    @staticmethod
    def format_timestamp(timestamp: str) -> str:
        """Format timestamp to human-readable relative time"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo)
            delta = now - dt
            
            if delta.days > 365:
                return f"{delta.days // 365} year(s) ago"
            elif delta.days > 30:
                return f"{delta.days // 30} month(s) ago"
            elif delta.days > 0:
                return f"{delta.days} day(s) ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hour(s) ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minute(s) ago"
            else:
                return "just now"
        except:
            return "recently"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 200) -> str:
        """Truncate text to max length with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


class CodeContextFormatter(ContextFormatter):
    """Format code memories for AI assistant context"""
    
    @staticmethod
    def format_single_memory(memory: Dict[str, Any], include_metadata: bool = True) -> str:
        """Format a single code memory into readable text
        
        Args:
            memory: Memory dict from search results
            include_metadata: Whether to include file/function metadata
            
        Returns:
            Formatted string representation
        """
        parts = []
        
        # Main content
        text = memory.get('text', memory.get('summary', ''))
        parts.append(text)
        
        # Metadata
        if include_metadata:
            meta_parts = []
            
            if memory.get('file_path'):
                file_path = memory['file_path']
                if memory.get('function_name'):
                    meta_parts.append(f"{file_path}::{memory['function_name']}()")
                else:
                    meta_parts.append(file_path)
            
            if memory.get('change_type'):
                meta_parts.append(f"[{memory['change_type']}]")
            
            if memory.get('severity'):
                meta_parts.append(f"severity: {memory['severity']}")
            
            if memory.get('created_at'):
                time_ago = ContextFormatter.format_timestamp(memory['created_at'])
                meta_parts.append(time_ago)
            
            if meta_parts:
                parts.append(f"  ({', '.join(meta_parts)})")
        
        return "\n".join(parts)
    
    @staticmethod
    def format_grouped_by_file(memories: List[Dict[str, Any]]) -> str:
        """Group memories by file for better organization
        
        Returns:
            Formatted context grouped by file path
        """
        if not memories:
            return "No code context available."
        
        # Group by file
        by_file = {}
        for mem in memories:
            file_path = mem.get('file_path', 'unknown')
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(mem)
        
        # Format each file group
        sections = []
        for file_path, file_mems in by_file.items():
            section = [f"📄 **{file_path}**"]
            for mem in file_mems:
                text = mem.get('text', mem.get('summary', ''))
                change_type = mem.get('change_type') or ''  # Handle None
                function = mem.get('function_name', '')
                
                prefix = f"  • [{change_type.upper()}]" if change_type else "  •"
                if function:
                    prefix += f" {function}():"
                
                section.append(f"{prefix} {text}")
            
            sections.append("\n".join(section))
        
        return "\n\n".join(sections)
    
    @staticmethod
    def format_chronological(memories: List[Dict[str, Any]], limit: int = 10) -> str:
        """Format memories in chronological order (most recent first)
        
        Args:
            memories: List of memory dicts
            limit: Maximum number to include
            
        Returns:
            Formatted chronological context
        """
        if not memories:
            return "No code context available."
        
        # Sort by created_at (most recent first)
        sorted_mems = sorted(
            memories,
            key=lambda m: m.get('created_at', ''),
            reverse=True
        )[:limit]
        
        lines = ["**Recent Code Changes:**\n"]
        for i, mem in enumerate(sorted_mems, 1):
            text = mem.get('text', mem.get('summary', ''))
            file_path = mem.get('file_path', 'unknown')
            change_type = mem.get('change_type') or 'changed'  # Handle None
            time_ago = ContextFormatter.format_timestamp(mem.get('created_at', ''))
            
            lines.append(f"{i}. [{change_type.upper()}] {file_path}")
            lines.append(f"   {text}")
            lines.append(f"   ({time_ago})\n")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_by_relevance(memories: List[Dict[str, Any]], 
                           query: str = "",
                           limit: int = 5) -> str:
        """Format top N most relevant memories
        
        Args:
            memories: List of memory dicts (assumed already sorted by relevance)
            query: Original search query
            limit: Maximum number to include
            
        Returns:
            Formatted context highlighting most relevant
        """
        if not memories:
            return "No relevant code context found."
        
        top_mems = memories[:limit]
        
        lines = []
        if query:
            lines.append(f"**Most Relevant to '{query}':**\n")
        else:
            lines.append("**Most Relevant Code Context:**\n")
        
        for i, mem in enumerate(top_mems, 1):
            text = mem.get('text', mem.get('summary', ''))
            file_path = mem.get('file_path', 'unknown')
            function = mem.get('function_name')
            change_type = mem.get('change_type') or ''  # Handle None
            
            location = f"{file_path}::{function}()" if function else file_path
            tag = f"[{change_type.upper()}] " if change_type else ""
            
            lines.append(f"{i}. {tag}{location}")
            lines.append(f"   {text}\n")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_compact(memories: List[Dict[str, Any]], max_items: int = 10) -> str:
        """Compact format for limited context windows
        
        Args:
            memories: List of memory dicts
            max_items: Maximum number to include
            
        Returns:
            Very concise formatted context
        """
        if not memories:
            return "No code context."
        
        lines = []
        for mem in memories[:max_items]:
            file_path = mem.get('file_path', '?')
            change_type = mem.get('change_type') or '?'  # Handle None
            summary = mem.get('change_summary') or mem.get('text') or 'No description'  # Handle None
            
            # Ultra compact: [type] file - summary
            summary = ContextFormatter.truncate_text(summary, 80)
            lines.append(f"[{change_type}] {file_path} - {summary}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_detailed(memories: List[Dict[str, Any]]) -> str:
        """Detailed format with all available metadata
        
        Args:
            memories: List of memory dicts
            
        Returns:
            Comprehensive formatted context
        """
        if not memories:
            return "No code context available."
        
        sections = []
        for i, mem in enumerate(memories, 1):
            section = [f"{'='*60}"]
            section.append(f"Memory #{i}")
            section.append(f"{'='*60}\n")
            
            # Content
            text = mem.get('text', mem.get('summary', 'No description'))
            section.append(f"**Content:** {text}\n")
            
            # Metadata
            if mem.get('file_path'):
                section.append(f"**File:** {mem['file_path']}")
            
            if mem.get('function_name'):
                section.append(f"**Function:** {mem['function_name']}()")
            
            if mem.get('change_type'):
                section.append(f"**Change Type:** {mem['change_type']}")
            
            if mem.get('change_summary'):
                section.append(f"**Change Summary:** {mem['change_summary']}")
            
            if mem.get('severity'):
                section.append(f"**Severity:** {mem['severity']}")
            
            if mem.get('created_at'):
                time_ago = ContextFormatter.format_timestamp(mem['created_at'])
                section.append(f"**When:** {time_ago}")
            
            sections.append("\n".join(section))
        
        return "\n\n".join(sections)


class ConversationContextFormatter(ContextFormatter):
    """Format general conversation memories"""
    
    @staticmethod
    def format_list(memories: List[Dict[str, Any]], limit: int = 10) -> str:
        """Simple bulleted list of facts"""
        if not memories:
            return "No conversation context available."
        
        lines = ["**Relevant Facts:**\n"]
        for mem in memories[:limit]:
            text = mem.get('text', mem.get('fact', ''))
            lines.append(f"• {text}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_categorized(memories: List[Dict[str, Any]]) -> str:
        """Group conversation memories by category/type"""
        if not memories:
            return "No conversation context available."
        
        # This would require category metadata - placeholder for now
        return ConversationContextFormatter.format_list(memories)


# =============================================================================
# Convenience Functions
# =============================================================================

def format_code_context(memories: List[Dict[str, Any]], 
                        style: str = "relevance",
                        **kwargs) -> str:
    """Format code memories with specified style
    
    Args:
        memories: List of memory dicts from search
        style: Formatting style - "relevance", "chronological", "grouped", "compact", "detailed"
        **kwargs: Additional arguments for specific formatters
        
    Returns:
        Formatted context string
    """
    formatter = CodeContextFormatter()
    
    if style == "relevance":
        return formatter.format_by_relevance(memories, **kwargs)
    elif style == "chronological":
        return formatter.format_chronological(memories, **kwargs)
    elif style == "grouped":
        return formatter.format_grouped_by_file(memories)
    elif style == "compact":
        # Map 'limit' to 'max_items' for compact style
        if 'limit' in kwargs:
            kwargs['max_items'] = kwargs.pop('limit')
        return formatter.format_compact(memories, **kwargs)
    elif style == "detailed":
        return formatter.format_detailed(memories)
    else:
        # Default to relevance
        return formatter.format_by_relevance(memories, **kwargs)


def format_conversation_context(memories: List[Dict[str, Any]], 
                                style: str = "list",
                                **kwargs) -> str:
    """Format conversation memories with specified style
    
    Args:
        memories: List of memory dicts from search
        style: Formatting style - "list", "categorized"
        **kwargs: Additional arguments
        
    Returns:
        Formatted context string
    """
    formatter = ConversationContextFormatter()
    
    if style == "categorized":
        return formatter.format_categorized(memories)
    else:
        return formatter.format_list(memories, **kwargs)


# =============================================================================
# Context Optimization
# =============================================================================

def optimize_context_for_token_limit(memories: List[Dict[str, Any]], 
                                     max_tokens: int = 1000,
                                     chars_per_token: int = 4) -> List[Dict[str, Any]]:
    """Reduce memories to fit within token budget
    
    Args:
        memories: List of memory dicts
        max_tokens: Maximum tokens allowed
        chars_per_token: Rough estimate (GPT uses ~4 chars per token)
        
    Returns:
        Truncated list that fits within budget
    """
    max_chars = max_tokens * chars_per_token
    
    result = []
    current_chars = 0
    
    for mem in memories:
        text = mem.get('text', mem.get('summary', ''))
        mem_chars = len(text) + 50  # Add overhead for metadata
        
        if current_chars + mem_chars > max_chars:
            break
        
        result.append(mem)
        current_chars += mem_chars
    
    return result


def deduplicate_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate or highly similar memories
    
    Args:
        memories: List of memory dicts
        
    Returns:
        Deduplicated list
    """
    seen_texts = set()
    result = []
    
    for mem in memories:
        text = mem.get('text', mem.get('summary', '')).lower().strip()
        
        # Simple deduplication by exact text match
        if text and text not in seen_texts:
            seen_texts.add(text)
            result.append(mem)
    
    return result
