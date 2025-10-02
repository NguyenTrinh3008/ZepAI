# ui/token_tracker.py
"""
Token Usage Tracker for OpenAI API calls

Tracks all token usage including:
- Chat messages (user + assistant)
- Hidden operations (decision, summarization, translation, importance)
- Cost estimation based on OpenAI pricing
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json


# OpenAI Pricing (as of 2024)
# Update these if prices change
PRICING = {
    "gpt-4o": {
        "input": 0.005 / 1000,   # $5 per 1M tokens
        "output": 0.015 / 1000,  # $15 per 1M tokens
    },
    "gpt-4o-mini": {
        "input": 0.00015 / 1000,   # $0.15 per 1M tokens
        "output": 0.0006 / 1000,   # $0.60 per 1M tokens
    },
    "gpt-4": {
        "input": 0.03 / 1000,
        "output": 0.06 / 1000,
    },
    "gpt-4-turbo": {
        "input": 0.01 / 1000,
        "output": 0.03 / 1000,
    },
    "gpt-3.5-turbo": {
        "input": 0.0005 / 1000,
        "output": 0.0015 / 1000,
    },
}


@dataclass
class TokenUsage:
    """Single token usage record"""
    timestamp: str
    operation: str  # "chat", "decision", "summarization", "translation", "importance"
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    group_id: Optional[str] = None  # Conversation group_id
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "operation": self.operation,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "group_id": self.group_id,
            "metadata": self.metadata
        }


class TokenTracker:
    """Track all token usage across session"""
    
    def __init__(self):
        self.usage_history: List[TokenUsage] = []
        self.session_start = datetime.now().isoformat()
    
    def track(self, 
              operation: str,
              model: str,
              prompt_tokens: int,
              completion_tokens: int,
              group_id: Optional[str] = None,
              metadata: Optional[Dict] = None) -> TokenUsage:
        """
        Track a single API call
        
        Args:
            operation: Type of operation (chat, decision, summarization, etc.)
            model: Model name (gpt-4o-mini, gpt-4, etc.)
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            group_id: Conversation group_id (to track per conversation)
            metadata: Additional context (e.g., message_id, turn_number)
        
        Returns:
            TokenUsage object
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        usage = TokenUsage(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            group_id=group_id,
            metadata=metadata or {}
        )
        
        self.usage_history.append(usage)
        return usage
    
    def track_from_response(self,
                           operation: str,
                           response: Any,
                           group_id: Optional[str] = None,
                           metadata: Optional[Dict] = None) -> Optional[TokenUsage]:
        """
        Track from OpenAI response object
        
        Args:
            operation: Type of operation
            response: OpenAI ChatCompletion response
            group_id: Conversation group_id
            metadata: Additional context
        
        Returns:
            TokenUsage object or None if response doesn't have usage
        """
        try:
            if hasattr(response, 'usage') and response.usage:
                return self.track(
                    operation=operation,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    group_id=group_id,
                    metadata=metadata
                )
        except Exception as e:
            print(f"Error tracking tokens from response: {e}")
        
        return None
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model pricing"""
        # Try exact match first
        if model in PRICING:
            pricing = PRICING[model]
        else:
            # Try partial match (e.g., "gpt-4o-mini-2024-07-18" -> "gpt-4o-mini")
            for key in PRICING:
                if key in model:
                    pricing = PRICING[key]
                    break
            else:
                # Default to gpt-4o-mini if unknown
                pricing = PRICING["gpt-4o-mini"]
        
        input_cost = prompt_tokens * pricing["input"]
        output_cost = completion_tokens * pricing["output"]
        return input_cost + output_cost
    
    def get_total_tokens(self) -> Dict[str, int]:
        """Get total tokens by type"""
        total_prompt = sum(u.prompt_tokens for u in self.usage_history)
        total_completion = sum(u.completion_tokens for u in self.usage_history)
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion
        }
    
    def get_total_cost(self) -> float:
        """Get total cost across all operations"""
        return sum(u.cost for u in self.usage_history)
    
    def get_by_operation(self, group_id: Optional[str] = None) -> Dict[str, Dict]:
        """Get tokens and cost breakdown by operation type
        
        Args:
            group_id: Filter by conversation group_id (None = all conversations)
        """
        breakdown = {}
        
        # Filter by group_id if provided
        history = self.usage_history
        if group_id:
            history = [u for u in self.usage_history if u.group_id == group_id]
        
        for usage in history:
            op = usage.operation
            if op not in breakdown:
                breakdown[op] = {
                    "count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0
                }
            
            breakdown[op]["count"] += 1
            breakdown[op]["prompt_tokens"] += usage.prompt_tokens
            breakdown[op]["completion_tokens"] += usage.completion_tokens
            breakdown[op]["total_tokens"] += usage.total_tokens
            breakdown[op]["cost"] += usage.cost
        
        return breakdown
    
    def get_by_group_id(self) -> Dict[str, Dict]:
        """Get tokens and cost breakdown by conversation (group_id)"""
        breakdown = {}
        
        for usage in self.usage_history:
            gid = usage.group_id or "unknown"
            if gid not in breakdown:
                breakdown[gid] = {
                    "count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "operations": {}
                }
            
            breakdown[gid]["count"] += 1
            breakdown[gid]["prompt_tokens"] += usage.prompt_tokens
            breakdown[gid]["completion_tokens"] += usage.completion_tokens
            breakdown[gid]["total_tokens"] += usage.total_tokens
            breakdown[gid]["cost"] += usage.cost
            
            # Track operations within this group
            op = usage.operation
            if op not in breakdown[gid]["operations"]:
                breakdown[gid]["operations"][op] = 0
            breakdown[gid]["operations"][op] += 1
        
        return breakdown
    
    def get_all_group_ids(self) -> List[str]:
        """Get list of all unique group_ids"""
        group_ids = set()
        for usage in self.usage_history:
            if usage.group_id:
                group_ids.add(usage.group_id)
        return sorted(list(group_ids))
    
    def get_total_tokens(self, group_id: Optional[str] = None) -> Dict[str, int]:
        """Get total tokens by type
        
        Args:
            group_id: Filter by conversation group_id (None = all conversations)
        """
        history = self.usage_history
        if group_id:
            history = [u for u in self.usage_history if u.group_id == group_id]
        
        total_prompt = sum(u.prompt_tokens for u in history)
        total_completion = sum(u.completion_tokens for u in history)
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion
        }
    
    def get_total_cost(self, group_id: Optional[str] = None) -> float:
        """Get total cost across all operations
        
        Args:
            group_id: Filter by conversation group_id (None = all conversations)
        """
        history = self.usage_history
        if group_id:
            history = [u for u in self.usage_history if u.group_id == group_id]
        
        return sum(u.cost for u in history)
    
    def get_recent(self, n: int = 10) -> List[TokenUsage]:
        """Get N most recent usage records"""
        return self.usage_history[-n:]
    
    def clear(self):
        """Clear all tracking history"""
        self.usage_history = []
        self.session_start = datetime.now().isoformat()
    
    def export_to_dict(self) -> Dict:
        """Export all data for serialization"""
        return {
            "session_start": self.session_start,
            "total_calls": len(self.usage_history),
            "total_tokens": self.get_total_tokens(),
            "total_cost": self.get_total_cost(),
            "breakdown_by_operation": self.get_by_operation(),
            "history": [u.to_dict() for u in self.usage_history]
        }
    
    def export_to_json(self, filepath: str):
        """Export to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.export_to_dict(), f, indent=2)
    
    def get_stats_summary(self) -> str:
        """Get human-readable summary"""
        total = self.get_total_tokens()
        cost = self.get_total_cost()
        breakdown = self.get_by_operation()
        
        lines = [
            f"📊 Token Usage Summary",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Total API Calls: {len(self.usage_history)}",
            f"Total Tokens: {total['total_tokens']:,}",
            f"  - Prompt: {total['prompt_tokens']:,}",
            f"  - Completion: {total['completion_tokens']:,}",
            f"Total Cost: ${cost:.4f}",
            f"",
            f"Breakdown by Operation:",
        ]
        
        for op, stats in breakdown.items():
            lines.append(f"  {op.capitalize()}:")
            lines.append(f"    - Calls: {stats['count']}")
            lines.append(f"    - Tokens: {stats['total_tokens']:,}")
            lines.append(f"    - Cost: ${stats['cost']:.4f}")
        
        return "\n".join(lines)


# Singleton instance for Streamlit session
def get_tracker() -> TokenTracker:
    """Get or create TokenTracker singleton"""
    import streamlit as st
    
    if "token_tracker" not in st.session_state:
        st.session_state.token_tracker = TokenTracker()
    
    return st.session_state.token_tracker


def display_token_metrics(tracker: TokenTracker, compact: bool = False, group_id: Optional[str] = None):
    """
    Display token metrics in Streamlit UI
    
    Args:
        tracker: TokenTracker instance
        compact: If True, show compact version
        group_id: Filter by conversation group_id (None = all conversations)
    """
    import streamlit as st
    
    if not tracker.usage_history:
        st.info("ℹ️ No token usage tracked yet")
        return
    
    # Filter display label
    display_label = f" (Conversation: {group_id[:8]}...)" if group_id else " (All Conversations)"
    
    total = tracker.get_total_tokens(group_id)
    cost = tracker.get_total_cost(group_id)
    breakdown = tracker.get_by_operation(group_id)
    
    if compact:
        # Compact inline metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tokens", f"{total['total_tokens']:,}")
        with col2:
            filtered_count = len([u for u in tracker.usage_history if not group_id or u.group_id == group_id])
            st.metric("API Calls", filtered_count)
        with col3:
            st.metric("Cost", f"${cost:.4f}")
    else:
        # Full detailed view
        st.markdown(f"### 📊 Token Usage{display_label}")
        
        # Overall metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tokens", f"{total['total_tokens']:,}")
        with col2:
            st.metric("Prompt", f"{total['prompt_tokens']:,}")
        with col3:
            st.metric("Completion", f"{total['completion_tokens']:,}")
        with col4:
            st.metric("Cost", f"${cost:.4f}")
        
        # Breakdown by operation
        st.markdown("#### Breakdown by Operation")
        
        breakdown_data = []
        total_tokens = total['total_tokens']
        for op, stats in breakdown.items():
            breakdown_data.append({
                "Operation": op.capitalize(),
                "Calls": stats['count'],
                "Tokens": f"{stats['total_tokens']:,}",
                "Cost": f"${stats['cost']:.4f}",
                "% of Total": f"{(stats['total_tokens'] / total_tokens * 100):.1f}%" if total_tokens > 0 else "0%"
            })
        
        if breakdown_data:
            st.dataframe(breakdown_data, use_container_width=True)
        else:
            st.info("No data for this filter")
        
        # Recent history
        with st.expander("📜 Recent API Calls", expanded=False):
            recent = tracker.get_recent(20)
            # Filter by group_id if provided
            if group_id:
                recent = [u for u in recent if u.group_id == group_id]
            
            recent_data = []
            for u in reversed(recent):  # Most recent first
                recent_data.append({
                    "Time": u.timestamp.split("T")[1][:8],  # HH:MM:SS
                    "Operation": u.operation,
                    "Group": (u.group_id[:8] + "...") if u.group_id else "N/A",
                    "Model": u.model.split("-")[-1] if "-" in u.model else u.model,
                    "Tokens": u.total_tokens,
                    "Cost": f"${u.cost:.4f}"
                })
            
            if recent_data:
                st.dataframe(recent_data, use_container_width=True)
            else:
                st.info("No recent calls for this filter")


def format_token_badge(tokens: int, cost: float, 
                       prompt_tokens: int = None, 
                       completion_tokens: int = None,
                       show_breakdown: bool = False) -> str:
    """Format token usage as a badge string
    
    Args:
        tokens: Total tokens
        cost: Total cost
        prompt_tokens: Input tokens (optional, for breakdown)
        completion_tokens: Output tokens (optional, for breakdown)
        show_breakdown: If True, show detailed In/Out breakdown
    
    Returns:
        Formatted badge string
    """
    base = f"🎫 {tokens:,} tokens • ${cost:.4f}"
    
    if show_breakdown and prompt_tokens is not None and completion_tokens is not None:
        # Add breakdown with visual indicators
        breakdown = f"\n   ↗️ In: {prompt_tokens:,} | ↘️ Out: {completion_tokens:,}"
        return base + breakdown
    
    return base


if __name__ == "__main__":
    # Test the tracker
    tracker = TokenTracker()
    
    # Simulate some API calls
    tracker.track("chat", "gpt-4o-mini", 150, 50, {"turn": 1})
    tracker.track("decision", "gpt-4o-mini", 30, 5, {"turn": 1})
    tracker.track("chat", "gpt-4o-mini", 200, 80, {"turn": 2})
    tracker.track("summarization", "gpt-4o-mini", 100, 40, {"turn": 2})
    
    print(tracker.get_stats_summary())
    print("\nExport:")
    print(json.dumps(tracker.export_to_dict(), indent=2))

