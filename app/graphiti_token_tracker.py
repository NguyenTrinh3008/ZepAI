# app/graphiti_token_tracker.py
"""
Token Tracker cho Graphiti LLM Calls

Module này wrap OpenAI client để track token usage trong Graphiti pipeline.
Graphiti sử dụng LLM ở nhiều bước:
1. Entity extraction
2. Entity summarization
3. Reflection
4. Entity resolution
5. Fact extraction
6. Edge deduplication
7. Temporal reasoning

Cách sử dụng:
    tracker = GraphitiTokenTracker()
    graphiti = Graphiti(..., llm_client=tracker.create_tracked_client())
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)


# Token pricing (same as ui/token_tracker.py)
PRICING = {
    "gpt-4o": {
        "input": 0.005 / 1000,
        "output": 0.015 / 1000,
    },
    "gpt-4o-mini": {
        "input": 0.00015 / 1000,
        "output": 0.0006 / 1000,
    },
    "gpt-4": {
        "input": 0.03 / 1000,
        "output": 0.06 / 1000,
    },
    "gpt-4-turbo": {
        "input": 0.01 / 1000,
        "output": 0.03 / 1000,
    },
}


@dataclass
class GraphitiTokenUsage:
    """Token usage for a single Graphiti LLM call"""
    timestamp: str
    operation: str  # "entity_extraction", "entity_resolution", "fact_extraction", etc.
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    episode_id: Optional[str] = None  # Track which episode this belongs to
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
            "episode_id": self.episode_id,
            "metadata": self.metadata
        }


class GraphitiTokenTracker:
    """Track token usage for Graphiti operations"""
    
    def __init__(self):
        self.usage_history: List[GraphitiTokenUsage] = []
        self.session_start = datetime.now().isoformat()
        self.current_episode_id: Optional[str] = None
        
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on model pricing"""
        # Try exact match first
        if model in PRICING:
            pricing = PRICING[model]
        else:
            # Try partial match
            for key in PRICING:
                if key in model:
                    pricing = PRICING[key]
                    break
            else:
                # Default to gpt-4o-mini
                pricing = PRICING["gpt-4o-mini"]
        
        input_cost = prompt_tokens * pricing["input"]
        output_cost = completion_tokens * pricing["output"]
        return input_cost + output_cost
    
    def track(self,
              operation: str,
              model: str,
              prompt_tokens: int,
              completion_tokens: int,
              episode_id: Optional[str] = None,
              metadata: Optional[Dict] = None) -> GraphitiTokenUsage:
        """Track a single LLM call"""
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        usage = GraphitiTokenUsage(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            episode_id=episode_id or self.current_episode_id,
            metadata=metadata or {}
        )
        
        self.usage_history.append(usage)
        logger.info(f"Graphiti LLM call: {operation} - {total_tokens} tokens (${cost:.6f})")
        return usage
    
    def set_episode_context(self, episode_id: str):
        """Set current episode ID for subsequent tracking"""
        self.current_episode_id = episode_id
    
    def clear_episode_context(self):
        """Clear current episode ID"""
        self.current_episode_id = None
    
    def get_episode_summary(self, episode_id: str) -> Dict[str, Any]:
        """Get token usage summary for a specific episode"""
        episode_usage = [u for u in self.usage_history if u.episode_id == episode_id]
        
        if not episode_usage:
            return {
                "episode_id": episode_id,
                "total_tokens": 0,
                "total_cost": 0,
                "operations": {}
            }
        
        # Calculate totals
        total_prompt = sum(u.prompt_tokens for u in episode_usage)
        total_completion = sum(u.completion_tokens for u in episode_usage)
        total_cost = sum(u.cost for u in episode_usage)
        
        # Breakdown by operation
        operations = {}
        for usage in episode_usage:
            op = usage.operation
            if op not in operations:
                operations[op] = {
                    "count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0
                }
            
            operations[op]["count"] += 1
            operations[op]["prompt_tokens"] += usage.prompt_tokens
            operations[op]["completion_tokens"] += usage.completion_tokens
            operations[op]["total_tokens"] += usage.total_tokens
            operations[op]["cost"] += usage.cost
        
        return {
            "episode_id": episode_id,
            "total_tokens": total_prompt + total_completion,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_cost": total_cost,
            "operations": operations,
            "call_count": len(episode_usage)
        }
    
    def get_operation_breakdown(self) -> Dict[str, Dict]:
        """Get breakdown by Graphiti operation type"""
        breakdown = {}
        
        for usage in self.usage_history:
            op = usage.operation
            if op not in breakdown:
                breakdown[op] = {
                    "count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0,
                    "avg_tokens_per_call": 0
                }
            
            breakdown[op]["count"] += 1
            breakdown[op]["prompt_tokens"] += usage.prompt_tokens
            breakdown[op]["completion_tokens"] += usage.completion_tokens
            breakdown[op]["total_tokens"] += usage.total_tokens
            breakdown[op]["cost"] += usage.cost
        
        # Calculate averages
        for op in breakdown:
            if breakdown[op]["count"] > 0:
                breakdown[op]["avg_tokens_per_call"] = breakdown[op]["total_tokens"] / breakdown[op]["count"]
        
        return breakdown
    
    def get_total_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        if not self.usage_history:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost": 0,
                "unique_episodes": 0
            }
        
        total_tokens = sum(u.total_tokens for u in self.usage_history)
        total_cost = sum(u.cost for u in self.usage_history)
        unique_episodes = len(set(u.episode_id for u in self.usage_history if u.episode_id))
        
        return {
            "total_calls": len(self.usage_history),
            "total_tokens": total_tokens,
            "prompt_tokens": sum(u.prompt_tokens for u in self.usage_history),
            "completion_tokens": sum(u.completion_tokens for u in self.usage_history),
            "total_cost": total_cost,
            "unique_episodes": unique_episodes,
            "avg_tokens_per_call": total_tokens / len(self.usage_history),
            "avg_tokens_per_episode": total_tokens / unique_episodes if unique_episodes > 0 else 0
        }
    
    def export_to_dict(self) -> Dict:
        """Export all data"""
        return {
            "session_start": self.session_start,
            "total_stats": self.get_total_stats(),
            "operation_breakdown": self.get_operation_breakdown(),
            "history": [u.to_dict() for u in self.usage_history]
        }
    
    def export_to_json(self, filepath: str):
        """Export to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.export_to_dict(), f, indent=2)
    
    def get_summary_text(self) -> str:
        """Get human-readable summary"""
        stats = self.get_total_stats()
        breakdown = self.get_operation_breakdown()
        
        lines = [
            f"🔬 Graphiti Token Usage Summary",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Total LLM Calls: {stats['total_calls']}",
            f"Total Tokens: {stats['total_tokens']:,}",
            f"  - Prompt: {stats['prompt_tokens']:,}",
            f"  - Completion: {stats['completion_tokens']:,}",
            f"Total Cost: ${stats['total_cost']:.4f}",
            f"",
            f"Unique Episodes: {stats['unique_episodes']}",
            f"Avg Tokens/Episode: {stats['avg_tokens_per_episode']:.1f}",
            f"",
            f"Breakdown by Graphiti Operation:",
        ]
        
        # Sort by total tokens (descending)
        sorted_ops = sorted(breakdown.items(), key=lambda x: x[1]['total_tokens'], reverse=True)
        
        for op, data in sorted_ops:
            pct = (data['total_tokens'] / stats['total_tokens'] * 100) if stats['total_tokens'] > 0 else 0
            lines.append(f"  {op}:")
            lines.append(f"    - Calls: {data['count']}")
            lines.append(f"    - Tokens: {data['total_tokens']:,} ({pct:.1f}%)")
            lines.append(f"    - Avg/call: {data['avg_tokens_per_call']:.0f}")
            lines.append(f"    - Cost: ${data['cost']:.4f}")
        
        return "\n".join(lines)
    
    def create_tracked_client(self, base_client: Optional[OpenAI] = None) -> OpenAI:
        """
        Create a tracked OpenAI client wrapper
        
        IMPORTANT: Graphiti may not support custom clients directly.
        This is a reference implementation. You may need to:
        1. Monkey-patch OpenAI client
        2. Use Graphiti's callback system (if available)
        3. Parse Graphiti logs
        """
        if base_client is None:
            base_client = OpenAI()
        
        # Wrap the chat.completions.create method
        original_create = base_client.chat.completions.create
        tracker = self
        
        def tracked_create(*args, **kwargs):
            # Call original method
            response = original_create(*args, **kwargs)
            
            # Track usage
            if hasattr(response, 'usage') and response.usage:
                # Try to infer operation from messages or metadata
                operation = "graphiti_llm_call"  # Default
                
                # You can enhance this by inspecting messages
                messages = kwargs.get('messages', [])
                if messages:
                    first_msg = str(messages[0])
                    if 'entity' in first_msg.lower() and 'extract' in first_msg.lower():
                        operation = "entity_extraction"
                    elif 'relationship' in first_msg.lower() or 'fact' in first_msg.lower():
                        operation = "fact_extraction"
                    elif 'resolve' in first_msg.lower() or 'same' in first_msg.lower():
                        operation = "entity_resolution"
                    elif 'reflect' in first_msg.lower():
                        operation = "reflection"
                    elif 'temporal' in first_msg.lower() or 'time' in first_msg.lower():
                        operation = "temporal_reasoning"
                
                tracker.track(
                    operation=operation,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            
            return response
        
        # Replace method
        base_client.chat.completions.create = tracked_create
        
        return base_client


# Singleton for global tracking
_global_tracker: Optional[GraphitiTokenTracker] = None


def get_global_tracker() -> GraphitiTokenTracker:
    """Get or create global Graphiti token tracker"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = GraphitiTokenTracker()
    return _global_tracker


def reset_global_tracker():
    """Reset global tracker"""
    global _global_tracker
    _global_tracker = None


# Example usage
if __name__ == "__main__":
    tracker = GraphitiTokenTracker()
    
    # Simulate some Graphiti operations
    tracker.set_episode_context("episode_001")
    
    tracker.track("entity_extraction", "gpt-4o-mini", 250, 80)
    tracker.track("entity_summarization", "gpt-4o-mini", 180, 60)
    tracker.track("entity_summarization", "gpt-4o-mini", 190, 65)
    tracker.track("entity_resolution", "gpt-4o-mini", 320, 45)
    tracker.track("reflection", "gpt-4o-mini", 280, 70)
    tracker.track("fact_extraction", "gpt-4o-mini", 400, 120)
    tracker.track("edge_deduplication", "gpt-4o-mini", 220, 40)
    
    tracker.clear_episode_context()
    
    # Print summary
    print(tracker.get_summary_text())
    print("\n" + "="*50 + "\n")
    
    # Episode summary
    ep_summary = tracker.get_episode_summary("episode_001")
    print("Episode 001 Summary:")
    print(f"  Total Tokens: {ep_summary['total_tokens']:,}")
    print(f"  Total Cost: ${ep_summary['total_cost']:.4f}")
    print(f"  Operations: {ep_summary['call_count']} calls")
    
    for op, data in ep_summary['operations'].items():
        print(f"    - {op}: {data['total_tokens']} tokens, {data['count']} calls")

