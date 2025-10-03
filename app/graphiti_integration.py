# app/graphiti_integration.py
"""
Tích hợp Graphiti Token Tracking vào hệ thống hiện tại

Module này cung cấp:
1. Graphiti instance với token tracking enabled
2. Helper functions để track token usage cho add_episode
3. Integration với UI token tracker
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from graphiti_core import Graphiti
from openai import OpenAI, AsyncOpenAI

from app.graphiti_token_tracker import GraphitiTokenTracker, get_global_tracker

logger = logging.getLogger(__name__)


class TrackedGraphiti:
    """
    Wrapper around Graphiti với token tracking
    
    Sử dụng:
        graphiti = await get_tracked_graphiti()
        
        # Track episode
        with graphiti.track_episode("episode_123"):
            result = await graphiti.add_episode(...)
        
        # Get stats
        stats = graphiti.get_episode_stats("episode_123")
    """
    
    def __init__(self, graphiti: Graphiti, tracker: GraphitiTokenTracker):
        self.graphiti = graphiti
        self.tracker = tracker
        self._episode_context = None
    
    def __getattr__(self, name):
        """Proxy all other attributes to underlying Graphiti instance"""
        return getattr(self.graphiti, name)
    
    class EpisodeContext:
        """Context manager for tracking episode"""
        def __init__(self, tracker: GraphitiTokenTracker, episode_id: str):
            self.tracker = tracker
            self.episode_id = episode_id
            self.start_time = None
            self.start_call_count = 0
        
        def __enter__(self):
            self.tracker.set_episode_context(self.episode_id)
            self.start_time = datetime.now()
            self.start_call_count = len(self.tracker.usage_history)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.tracker.clear_episode_context()
            
            # Log summary
            duration = (datetime.now() - self.start_time).total_seconds()
            new_calls = len(self.tracker.usage_history) - self.start_call_count
            
            summary = self.tracker.get_episode_summary(self.episode_id)
            logger.info(
                f"Episode {self.episode_id} completed: "
                f"{new_calls} LLM calls, "
                f"{summary['total_tokens']} tokens, "
                f"${summary['total_cost']:.4f}, "
                f"{duration:.2f}s"
            )
    
    def track_episode(self, episode_id: str):
        """Context manager to track token usage for an episode"""
        return self.EpisodeContext(self.tracker, episode_id)
    
    def get_episode_stats(self, episode_id: str) -> Dict[str, Any]:
        """Get token statistics for an episode"""
        return self.tracker.get_episode_summary(episode_id)
    
    def get_operation_breakdown(self) -> Dict[str, Dict]:
        """Get breakdown by Graphiti operation"""
        return self.tracker.get_operation_breakdown()
    
    def get_total_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        return self.tracker.get_total_stats()
    
    def print_summary(self):
        """Print human-readable summary"""
        print(self.tracker.get_summary_text())


async def create_tracked_graphiti(
    uri: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    tracker: Optional[GraphitiTokenTracker] = None
) -> TrackedGraphiti:
    """
    Create Graphiti instance with token tracking
    
    Args:
        uri: Neo4j URI (default from env)
        user: Neo4j user (default from env)
        password: Neo4j password (default from env)
        tracker: Custom tracker (default: global tracker)
    
    Returns:
        TrackedGraphiti instance
    """
    if tracker is None:
        tracker = get_global_tracker()
    
    # Create base Graphiti instance
    graphiti = Graphiti(
        uri=uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=user or os.getenv("NEO4J_USER", "neo4j"),
        password=password or os.getenv("NEO4J_PASSWORD", "neo4j"),
    )
    
    # Note: Graphiti may not support custom LLM client injection
    # This is a placeholder - you may need to:
    # 1. Monkey-patch OpenAI globally
    # 2. Use environment variables to configure tracking
    # 3. Parse Graphiti logs
    
    # Wrap in tracked version
    tracked = TrackedGraphiti(graphiti, tracker)
    
    logger.info("Created tracked Graphiti instance")
    return tracked


# Monkey-patch OpenAI globally to track all calls
def enable_global_openai_tracking(tracker: Optional[GraphitiTokenTracker] = None):
    """
    Monkey-patch OpenAI client globally to track all LLM calls
    
    WARNING: This affects ALL OpenAI calls in the application.
    Use with caution.
    
    Args:
        tracker: Custom tracker (default: global tracker)
    """
    if tracker is None:
        tracker = get_global_tracker()
    
    # Patch synchronous client
    from openai import OpenAI as OriginalOpenAI
    
    original_init = OriginalOpenAI.__init__
    
    def tracked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # Wrap chat.completions.create
        original_create = self.chat.completions.create
        
        def tracked_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            
            if hasattr(response, 'usage') and response.usage:
                # Infer operation from messages
                operation = _infer_operation(kwargs.get('messages', []))
                
                tracker.track(
                    operation=operation,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            
            return response
        
        self.chat.completions.create = tracked_create
    
    OriginalOpenAI.__init__ = tracked_init
    
    logger.info("Global OpenAI tracking enabled")


def _infer_operation(messages: list) -> str:
    """
    Infer Graphiti operation from LLM messages
    
    This is a heuristic approach - may not be 100% accurate.
    """
    if not messages:
        return "unknown"
    
    # Check system message and first user message
    text = ""
    for msg in messages[:2]:
        content = msg.get('content', '') if isinstance(msg, dict) else ''
        text += content.lower()
    
    # Keyword matching (can be improved)
    if 'extract' in text and 'entit' in text:
        return "entity_extraction"
    elif 'summar' in text and 'entit' in text:
        return "entity_summarization"
    elif 'resolve' in text or 'same entity' in text or 'duplicate' in text:
        return "entity_resolution"
    elif 'reflect' in text or 'review' in text or 'validate' in text:
        return "reflection"
    elif 'relationship' in text or 'fact' in text or 'edge' in text:
        return "fact_extraction"
    elif 'deduplicate' in text or 'duplicate edge' in text:
        return "edge_deduplication"
    elif 'temporal' in text or 'time' in text or 'conflict' in text:
        return "temporal_reasoning"
    elif 'communit' in text:
        return "community_naming"
    else:
        return "graphiti_other"


# Integration with existing token_tracker.py
def sync_to_ui_tracker(graphiti_tracker: GraphitiTokenTracker, ui_tracker):
    """
    Sync Graphiti token usage to UI TokenTracker
    
    Args:
        graphiti_tracker: GraphitiTokenTracker instance
        ui_tracker: TokenTracker instance from ui/token_tracker.py
    """
    from ui.token_tracker import TokenTracker
    
    for usage in graphiti_tracker.usage_history:
        # Check if already synced (by timestamp)
        if not any(u.timestamp == usage.timestamp for u in ui_tracker.usage_history):
            ui_tracker.track(
                operation=f"graphiti_{usage.operation}",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                group_id=usage.episode_id,
                metadata=usage.metadata
            )


# Example usage
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    
    async def test():
        # Create tracked Graphiti
        graphiti = await create_tracked_graphiti()
        
        # Add episode with tracking
        episode_id = "test_episode_001"
        
        with graphiti.track_episode(episode_id):
            result = await graphiti.add_episode(
                name="Test Episode",
                episode_body="User likes Python programming. User works as a software engineer.",
                source="text",
                source_description="test",
                reference_time=datetime.utcnow(),
                group_id="test_group"
            )
        
        # Get stats
        print("\n" + "="*60)
        graphiti.print_summary()
        
        print("\n" + "="*60)
        print("\nEpisode Stats:")
        stats = graphiti.get_episode_stats(episode_id)
        print(f"Total Tokens: {stats['total_tokens']}")
        print(f"Total Cost: ${stats['total_cost']:.4f}")
        print(f"\nOperations:")
        for op, data in stats['operations'].items():
            print(f"  {op}: {data['total_tokens']} tokens ({data['count']} calls)")
    
    asyncio.run(test())

