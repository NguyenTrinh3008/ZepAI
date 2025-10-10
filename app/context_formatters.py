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
        """Format a single code memory into readable text with full metadata
        
        Args:
            memory: Memory dict from search results
            include_metadata: Whether to include file/function metadata
            
        Returns:
            Formatted string representation with enhanced metadata
        """
        parts = []
        
        # Main content
        text = memory.get('text', memory.get('summary', ''))
        parts.append(text)
        
        # Enhanced metadata
        if include_metadata:
            meta_parts = []
            
            # File and function
            if memory.get('file_path'):
                file_path = memory['file_path']
                if memory.get('function_name'):
                    meta_parts.append(f"{file_path}::{memory['function_name']}()")
                else:
                    meta_parts.append(f"{file_path}")
            
            # Change type and severity
            if memory.get('change_type'):
                meta_parts.append(f"[{memory['change_type'].upper()}]")
            
            if memory.get('severity'):
                meta_parts.append(f"{memory['severity']}")
            
            # Code changes (lines)
            if memory.get('lines_added') is not None or memory.get('lines_removed') is not None:
                added = memory.get('lines_added', 0)
                removed = memory.get('lines_removed', 0)
                meta_parts.append(f"+{added}/-{removed} lines")
            
            # Language
            if memory.get('language'):
                meta_parts.append(f"{memory['language']}")
            
            # Imports
            if memory.get('imports'):
                imports = memory['imports'] if isinstance(memory['imports'], list) else [memory['imports']]
                if imports:
                    meta_parts.append(f"imports: {', '.join(imports)}")
            
            # Conversation context
            if memory.get('chat_id'):
                meta_parts.append(f"chat: {memory['chat_id']}")
            
            if memory.get('model'):
                meta_parts.append(f"model: {memory['model']}")
            
            # Timestamp
            if memory.get('created_at'):
                time_ago = ContextFormatter.format_timestamp(memory['created_at'])
                meta_parts.append(f"{time_ago}")
            
            if meta_parts:
                parts.append(f"  ({' | '.join(meta_parts)})")
        
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
            section = [f"**{file_path}**"]
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
        """Detailed format with all available metadata (enhanced for AI)
        
        Args:
            memories: List of memory dicts
            
        Returns:
            Comprehensive formatted context with full metadata
        """
        if not memories:
            return "No code context available."
        
        sections = []
        for i, mem in enumerate(memories, 1):
            section = [f"{'='*70}"]
            section.append(f"Code Memory #{i}: {mem.get('name', 'Unknown')}")
            section.append(f"{'='*70}\n")
            
            # Main content
            text = mem.get('text', mem.get('summary', 'No description'))
            section.append(f"**Description:**\n  {text}\n")
            
            # File and code location
            if mem.get('file_path'):
                section.append(f"**File:** {mem['file_path']}")
            if mem.get('function_name'):
                section.append(f"**Function:** {mem['function_name']}()")
            
            # Change details
            if mem.get('change_type'):
                section.append(f"**Change Type:** {mem['change_type'].upper()}")
            
            if mem.get('change_summary'):
                section.append(f"**Change Summary:** {mem['change_summary']}")
            
            # Severity and impact
            if mem.get('severity'):
                section.append(f"**Severity:** {mem['severity']}")
            
            # Code metrics
            if mem.get('lines_added') is not None or mem.get('lines_removed') is not None:
                added = mem.get('lines_added', 0)
                removed = mem.get('lines_removed', 0)
                delta = added - removed
                section.append(f"**Code Changes:** +{added}/-{removed} lines (net: {delta:+d})")
            
            if mem.get('language'):
                section.append(f"**Language:** {mem['language']}")
            
            # Dependencies
            if mem.get('imports'):
                imports = mem['imports'] if isinstance(mem['imports'], list) else [mem['imports']]
                if imports:
                    section.append(f"**Imports:** {', '.join(imports)}")
            
            # Conversation context
            if mem.get('chat_id'):
                section.append(f"**Chat ID:** {mem['chat_id']}")
            
            if mem.get('chat_mode'):
                section.append(f"**Chat Mode:** {mem['chat_mode']}")
            
            if mem.get('model'):
                section.append(f"**Model:** {mem['model']}")
            
            if mem.get('total_tokens'):
                section.append(f"**Tokens Used:** {mem['total_tokens']:,}")
            
            # Related information
            if mem.get('related_nodes'):
                section.append(f"\n**Related Changes:**")
                for j, related in enumerate(mem['related_nodes'][:3], 1):
                    rel_type = related.get('type', 'Unknown')
                    rel_name = related.get('name', 'N/A')
                    rel_file = related.get('file_path', '')
                    if rel_file:
                        section.append(f"  {j}. [{rel_type}] {rel_name} ({rel_file})")
                    else:
                        section.append(f"  {j}. [{rel_type}] {rel_name}")
            
            # Timestamp
            if mem.get('created_at'):
                time_ago = ContextFormatter.format_timestamp(mem['created_at'])
                section.append(f"\n**When:** {time_ago}")
            
            sections.append("\n".join(section))
        
        return "\n\n".join(sections)


class ConversationContextFormatter(ContextFormatter):
    """Format general conversation memories with enhanced metadata"""
    
    @staticmethod
    def format_list(memories: List[Dict[str, Any]], limit: int = 10) -> str:
        """Simple bulleted list of facts with metadata"""
        if not memories:
            return "No conversation context available."
        
        lines = ["**Relevant Facts:**\n"]
        for mem in memories[:limit]:
            text = mem.get('text', mem.get('fact', ''))
            meta = []
            
            # Add compact metadata
            if mem.get('file_path'):
                meta.append(f"{mem['file_path']}")
            if mem.get('severity'):
                meta.append(f"{mem['severity']}")
            if mem.get('chat_id'):
                meta.append(f"chat: {mem['chat_id']}")
            
            if meta:
                lines.append(f"• {text} ({' '.join(meta)})")
            else:
                lines.append(f"• {text}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_categorized(memories: List[Dict[str, Any]]) -> str:
        """Group conversation memories by type/severity"""
        if not memories:
            return "No conversation context available."
        
        # Group by severity
        by_severity = {'high': [], 'medium': [], 'low': [], 'other': []}
        for mem in memories:
            severity = mem.get('severity', 'other')
            by_severity[severity].append(mem)
        
        sections = []
        
        # High priority first
        if by_severity['high']:
            sections.append("**High Priority Changes:**")
            for mem in by_severity['high']:
                text = mem.get('text', mem.get('summary', ''))
                file = mem.get('file_path', '')
                if file:
                    sections.append(f"  • {text} ({file})")
                else:
                    sections.append(f"  • {text}")
        
        # Medium priority
        if by_severity['medium']:
            sections.append("\n**Medium Priority Changes:**")
            for mem in by_severity['medium']:
                text = mem.get('text', mem.get('summary', ''))
                file = mem.get('file_path', '')
                if file:
                    sections.append(f"  • {text} ({file})")
                else:
                    sections.append(f"  • {text}")
        
        # Low priority
        if by_severity['low']:
            sections.append("\n**Low Priority Changes:**")
            for mem in by_severity['low'][:5]:  # Limit low priority
                text = mem.get('text', mem.get('summary', ''))
                sections.append(f"  • {text}")
        
        # Other
        if by_severity['other']:
            sections.append("\n**Other Context:**")
            for mem in by_severity['other'][:3]:
                text = mem.get('text', mem.get('summary', ''))
                sections.append(f"  • {text}")
        
        return "\n".join(sections) if sections else "No conversation context available."


# =============================================================================
# AI-Optimized Formatter
# =============================================================================

class AIContextFormatter(ContextFormatter):
    """Optimized formatter for AI/LLM consumption"""
    
    @staticmethod
    def _format_header(query: str) -> str:
        """Format context header with optional query"""
        if query:
            return f"**Context for: '{query}'**\n"
        return "**Relevant Context from Knowledge Graph:**\n"
    
    @staticmethod
    def _format_location(mem: Dict[str, Any]) -> Optional[str]:
        """Format file location and function line"""
        if not mem.get('file_path'):
            return None
        
        file_line = f"   Location: `{mem['file_path']}`"
        if mem.get('function_name'):
            file_line += f" → `{mem['function_name']}()`"
        return file_line
    
    @staticmethod
    def _format_change_info(mem: Dict[str, Any]) -> Optional[str]:
        """Format change type and severity line"""
        change_info = []
        if mem.get('change_type'):
            change_info.append(f"Type: {mem['change_type']}")
        if mem.get('severity'):
            change_info.append(f"Priority: {mem['severity']}")
        return f"   {' | '.join(change_info)}" if change_info else None
    
    @staticmethod
    def _format_code_metrics(mem: Dict[str, Any]) -> Optional[str]:
        """Format code change metrics (lines added/removed)"""
        if mem.get('lines_added') is not None or mem.get('lines_removed') is not None:
            added = mem.get('lines_added', 0)
            removed = mem.get('lines_removed', 0)
            return f"   Impact: +{added}/-{removed} lines"
        return None
    
    @staticmethod
    def _format_tech_info(mem: Dict[str, Any]) -> Optional[str]:
        """Format language and imports line"""
        tech_info = []
        if mem.get('language'):
            tech_info.append(f"Language: {mem['language']}")
        if mem.get('imports'):
            imports = mem['imports'] if isinstance(mem['imports'], list) else [mem['imports']]
            if imports:
                tech_info.append(f"Uses: {', '.join(imports)}")
        return f"   {' | '.join(tech_info)}" if tech_info else None
    
    @staticmethod
    def _format_conversation_context(mem: Dict[str, Any]) -> Optional[str]:
        """Format conversation metadata (chat, model, mode)"""
        if not (mem.get('chat_id') or mem.get('model')):
            return None
        
        conv_info = []
        if mem.get('chat_id'):
            conv_info.append(f"Chat: {mem['chat_id']}")
        if mem.get('model'):
            conv_info.append(f"Model: {mem['model']}")
        if mem.get('chat_mode'):
            conv_info.append(f"Mode: {mem['chat_mode']}")
        return f"   Context: {' | '.join(conv_info)}" if conv_info else None
    
    @staticmethod
    def _format_related_nodes(mem: Dict[str, Any], include_related: bool) -> List[str]:
        """Format related nodes section"""
        if not include_related or not mem.get('related_nodes'):
            return []
        
        related = mem['related_nodes'][:2]  # Limit to 2 most relevant
        if not related:
            return []
        
        lines = ["   Related:"]
        for rel in related:
            rel_type = rel.get('type', 'Unknown')
            rel_name = rel.get('name', 'N/A')
            rel_file = rel.get('file_path')
            if rel_file:
                lines.append(f"      - [{rel_type}] {rel_name} ({rel_file})")
            else:
                lines.append(f"      - [{rel_type}] {rel_name}")
        return lines
    
    @staticmethod
    def _format_timestamp(mem: Dict[str, Any]) -> Optional[str]:
        """Format timestamp line"""
        if mem.get('created_at'):
            time_ago = ContextFormatter.format_timestamp(mem['created_at'])
            return f"   When: {time_ago}"
        return None
    
    @staticmethod
    def _format_single_memory(mem: Dict[str, Any], index: int, include_related: bool) -> List[str]:
        """Format a single memory with all its metadata"""
        lines = []
        
        # Main description
        text = mem.get('text', mem.get('summary', 'No description'))
        lines.append(f"{index}. {text}")
        
        # Add metadata lines (each helper returns None or a formatted string)
        metadata_lines = [
            AIContextFormatter._format_location(mem),
            AIContextFormatter._format_change_info(mem),
            AIContextFormatter._format_code_metrics(mem),
            AIContextFormatter._format_tech_info(mem),
            AIContextFormatter._format_conversation_context(mem),
            AIContextFormatter._format_timestamp(mem),
        ]
        
        # Add non-None metadata lines
        lines.extend([line for line in metadata_lines if line])
        
        # Add related nodes (returns list of lines)
        lines.extend(AIContextFormatter._format_related_nodes(mem, include_related))
        
        return lines
    
    @staticmethod
    def _format_footer(total: int, max_items: int) -> str:
        """Format summary footer"""
        if total > max_items:
            return f"\nShowing top {max_items} of {total} relevant memories."
        return ""
    
    @staticmethod
    def format_for_ai(memories: List[Dict[str, Any]], 
                      query: str = "",
                      max_items: int = 5,
                      include_related: bool = True) -> str:
        """Format memories optimally for AI understanding and response generation
        
        This format prioritizes:
        - Clarity: Clear structure that LLMs parse easily
        - Relevance: Most important information first
        - Conciseness: Avoids context window bloat
        - Actionability: Includes metadata AI needs to provide specific answers
        
        Args:
            memories: Search results from knowledge graph
            query: Original user query (for context)
            max_items: Maximum memories to include
            include_related: Whether to include related nodes info
            
        Returns:
            AI-optimized formatted context string
        """
        if not memories:
            return "No relevant context found in knowledge graph."
        
        lines = [AIContextFormatter._format_header(query)]
        
        # Format each memory
        for i, mem in enumerate(memories[:max_items], 1):
            memory_lines = AIContextFormatter._format_single_memory(mem, i, include_related)
            lines.extend(memory_lines)
            
            # Separator between memories
            if i < min(len(memories), max_items):
                lines.append("")  # Blank line
        
        # Summary footer
        footer = AIContextFormatter._format_footer(len(memories), max_items)
        if footer:
            lines.append(footer)
        
        return "\n".join(lines)


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


def format_for_ai(memories: List[Dict[str, Any]], 
                  query: str = "",
                  max_items: int = 5,
                  include_related: bool = True) -> str:
    """Format memories optimally for AI/LLM consumption
    
    Convenience function for AIContextFormatter.format_for_ai()
    
    This is the RECOMMENDED format for injecting knowledge graph context
    into AI assistant prompts. It provides:
    - Clear, parseable structure
    - Rich metadata (file paths, severity, code metrics)
    - Related context for deeper understanding
    - Optimal balance of detail vs conciseness
    
    Args:
        memories: Search results from knowledge graph
        query: Original user query (for context header)
        max_items: Maximum memories to include (default: 5)
        include_related: Whether to include related nodes (default: True)
        
    Returns:
        AI-optimized formatted context string
        
    Example:
        >>> results = await search_knowledge_graph(query="async refactoring")
        >>> context = format_for_ai(results['results'], query="async refactoring")
        >>> # Inject context into AI prompt:
        >>> prompt = f"Context: {context}\\n\\nUser: {user_question}"
    """
    return AIContextFormatter.format_for_ai(
        memories=memories,
        query=query,
        max_items=max_items,
        include_related=include_related
    )


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
