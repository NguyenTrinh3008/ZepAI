# app/graphiti_estimator.py
"""
Estimate Graphiti Token Usage

Since direct tracking doesn't work with Graphiti's internal LLM client,
we estimate token usage based on known patterns from research.

Based on: docs/GRAPHITI_TOKEN_ANALYSIS.md
"""

from typing import Dict
from app.graphiti_token_tracker import get_global_tracker


def estimate_tokens_for_episode(
    episode_id: str,
    episode_body: str,
    model: str = "gpt-4o-mini"
) -> Dict[str, any]:
    """
    Estimate token usage for a Graphiti episode based on content length
    
    Args:
        episode_id: Episode identifier
        episode_body: The text content of episode
        model: LLM model used (for pricing)
    
    Returns:
        Dictionary with estimated tokens and cost
    """
    tracker = get_global_tracker()
    
    # Calculate base metrics
    body_length = len(episode_body)
    word_count = len(episode_body.split())
    
    # Estimate number of entities (rough heuristic)
    # Typically 1 entity per 10-20 words
    estimated_entities = max(1, word_count // 15)
    
    # Estimate number of facts/edges
    # Typically 0.5-1 fact per entity
    estimated_facts = max(1, int(estimated_entities * 0.7))
    
    # === ESTIMATE TOKENS PER OPERATION ===
    # Based on research in docs/GRAPHITI_TOKEN_ANALYSIS.md
    
    # 1. Entity Extraction: 400-2500 tokens
    # Formula: base 200 + (body_length * 1.5)
    entity_extraction_tokens = min(2500, 200 + int(body_length * 1.5))
    
    # 2. Entity Summarization: 200-450 tokens per entity
    # Average: 300 tokens/entity
    entity_summarization_tokens = estimated_entities * 300
    
    # 3. Entity Resolution: 420-850 tokens per entity (if candidates found)
    # Assume 60% of entities need resolution
    entities_needing_resolution = int(estimated_entities * 0.6)
    entity_resolution_tokens = entities_needing_resolution * 600
    
    # 4. Reflection: 400-700 tokens
    reflection_tokens = 550
    
    # 5. Fact Extraction: 450-2800 tokens  
    # Formula: base 400 + (body_length * 1.2)
    fact_extraction_tokens = min(2800, 400 + int(body_length * 1.2))
    
    # 6. Edge Deduplication: 330-880 tokens per edge
    # Assume 40% of edges need dedup check
    edges_needing_dedup = int(estimated_facts * 0.4)
    edge_dedup_tokens = edges_needing_dedup * 550
    
    # 7. Temporal Reasoning: 360-540 tokens (if temporal info present)
    # Assume 20% of episodes have temporal conflicts
    temporal_tokens = 450 if word_count > 50 else 0
    
    # === TOTAL CALCULATION ===
    total_tokens = (
        entity_extraction_tokens +
        entity_summarization_tokens +
        entity_resolution_tokens +
        reflection_tokens +
        fact_extraction_tokens +
        edge_dedup_tokens +
        temporal_tokens
    )
    
    # Split prompt/completion (rough estimate: 65% prompt, 35% completion)
    prompt_tokens = int(total_tokens * 0.65)
    completion_tokens = int(total_tokens * 0.35)
    
    # === RECORD TO TRACKER ===
    tracker.set_episode_context(episode_id)
    
    # Record each operation
    tracker.track("entity_extraction", model, 
                  int(entity_extraction_tokens * 0.65), 
                  int(entity_extraction_tokens * 0.35),
                  episode_id=episode_id,
                  metadata={"estimated": True})
    
    tracker.track("entity_summarization", model,
                  int(entity_summarization_tokens * 0.65),
                  int(entity_summarization_tokens * 0.35),
                  episode_id=episode_id,
                  metadata={"estimated": True, "entities": estimated_entities})
    
    tracker.track("entity_resolution", model,
                  int(entity_resolution_tokens * 0.65),
                  int(entity_resolution_tokens * 0.35),
                  episode_id=episode_id,
                  metadata={"estimated": True, "resolutions": entities_needing_resolution})
    
    tracker.track("reflection", model,
                  int(reflection_tokens * 0.65),
                  int(reflection_tokens * 0.35),
                  episode_id=episode_id,
                  metadata={"estimated": True})
    
    tracker.track("fact_extraction", model,
                  int(fact_extraction_tokens * 0.65),
                  int(fact_extraction_tokens * 0.35),
                  episode_id=episode_id,
                  metadata={"estimated": True, "facts": estimated_facts})
    
    if edges_needing_dedup > 0:
        tracker.track("edge_deduplication", model,
                      int(edge_dedup_tokens * 0.65),
                      int(edge_dedup_tokens * 0.35),
                      episode_id=episode_id,
                      metadata={"estimated": True, "dedups": edges_needing_dedup})
    
    if temporal_tokens > 0:
        tracker.track("temporal_reasoning", model,
                      int(temporal_tokens * 0.65),
                      int(temporal_tokens * 0.35),
                      episode_id=episode_id,
                      metadata={"estimated": True})
    
    tracker.clear_episode_context()
    
    # === RETURN SUMMARY ===
    return {
        "episode_id": episode_id,
        "estimated": True,
        "body_length": body_length,
        "word_count": word_count,
        "estimated_entities": estimated_entities,
        "estimated_facts": estimated_facts,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "operations": {
            "entity_extraction": entity_extraction_tokens,
            "entity_summarization": entity_summarization_tokens,
            "entity_resolution": entity_resolution_tokens,
            "reflection": reflection_tokens,
            "fact_extraction": fact_extraction_tokens,
            "edge_deduplication": edge_dedup_tokens,
            "temporal_reasoning": temporal_tokens
        },
        "model": model
    }


# Convenience function
def estimate_and_track(episode_id: str, episode_body: str, model: str = "gpt-4o-mini"):
    """
    Estimate and track tokens for an episode
    
    This is a convenience function that calls estimate_tokens_for_episode
    and returns a summary.
    """
    return estimate_tokens_for_episode(episode_id, episode_body, model)

