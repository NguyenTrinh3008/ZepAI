# app/services/search_service.py
"""
Search service - Business logic for semantic search
"""
import os
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.prompts import format_query_translation_prompt, PROMPT_CONFIG
from app.cache import memory_cache, cache_search_result

logger = logging.getLogger(__name__)


async def translate_query_if_needed(query: str) -> str:
    """
    Auto-translate non-English queries to English for better semantic search
    
    Args:
        query: Original query (any language)
    
    Returns:
        Translated query (English) or original if translation fails
    """
    # Detect if query is non-English (simple heuristic: contains non-ASCII)
    if not any(ord(char) > 127 for char in query):
        return query
    
    try:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.warning("No OpenAI API key, skipping translation")
            return query
        
        client = OpenAI(api_key=openai_key)
        trans_prompt = format_query_translation_prompt(query)
        trans_config = PROMPT_CONFIG.get("translation", {})
        
        translation = client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            messages=[{"role": "user", "content": trans_prompt}],
            temperature=trans_config.get("temperature", 0.2),
            max_tokens=trans_config.get("max_tokens", 100),
        )
        
        translated = translation.choices[0].message.content.strip()
        logger.info(f"Translated query: '{query}' → '{translated}'")
        return translated
        
    except Exception as e:
        logger.warning(f"Translation failed, using original query: {e}")
        return query


def normalize_search_result(item: Any) -> Dict[str, Any]:
    """
    Normalize search result to standard format
    
    Handles both dict and object formats from Graphiti
    """
    # Extract fields from dict or object
    if isinstance(item, dict):
        txt = item.get("summary") or item.get("fact") or item.get("text") or item.get("name") or str(item)
        ident = (
            item.get("source_node_uuid")
            or item.get("uuid")
            or item.get("node_uuid")
            or item.get("edge_id")
            or item.get("id")
        )
        grp_id = item.get("group_id") or item.get("groupId")
        name = item.get("name")
        summary = item.get("summary") or item.get("fact") or item.get("text")
        score = item.get("score") or item.get("similarity")
    else:
        txt = (
            getattr(item, "summary", None)
            or getattr(item, "fact", None)
            or getattr(item, "text", None)
            or getattr(item, "name", None)
            or str(item)
        )
        ident = (
            getattr(item, "source_node_uuid", None)
            or getattr(item, "uuid", None)
            or getattr(item, "node_uuid", None)
            or getattr(item, "edge_id", None)
            or getattr(item, "id", None)
        )
        grp_id = getattr(item, "group_id", None) or getattr(item, "groupId", None)
        name = getattr(item, "name", None)
        summary = getattr(item, "summary", None) or getattr(item, "fact", None) or getattr(item, "text", None)
        score = getattr(item, "score", None)
    
    # Debug logging
    logger.debug(f"Normalize: type={type(item).__name__}, text={txt[:50] if txt else 'N/A'}, id={ident}")
    
    if not grp_id:
        logger.warning(f"Search result missing group_id: {type(item)} - {txt[:50] if txt else 'N/A'}")
    if not ident:
        logger.warning(f"Search result missing ID: {type(item)}")
    
    return {
        "text": txt,
        "summary": summary or txt,
        "name": name,
        "id": ident,
        "group_id": grp_id,
        "score": score
    }


async def enrich_metadata(items: List[Dict[str, Any]], graphiti) -> None:
    """
    Enrich items missing descriptive text using Neo4j metadata
    
    Modifies items in-place
    """
    metadata_needed = [
        item for item in items 
        if not (item.get("text") and item.get("text").strip() 
                and item.get("text").strip().lower() not in {"unknown", "..."})
    ]
    
    if not metadata_needed:
        return
    
    uuids = [item.get("id") for item in metadata_needed if item.get("id")]
    if not uuids:
        return
    
    meta_query = """
    MATCH (n)
    WHERE n.uuid IN $uuids
    RETURN n.uuid as uuid,
           n.name as name,
           n.summary as summary,
           n.episode_body as episode_body,
           labels(n) as labels
    """
    
    metadata_map = {}
    async with graphiti.driver.session() as session:
        result = await session.run(meta_query, {"uuids": uuids})
        async for record in result:
            metadata_map[record["uuid"]] = {
                "name": record["name"],
                "summary": record["summary"],
                "episode_body": record.get("episode_body"),
                "labels": record.get("labels")
            }
    
    for item in metadata_needed:
        meta = metadata_map.get(item.get("id"))
        if not meta:
            continue
        
        summary_val = meta.get("summary")
        summary = summary_val.strip() if isinstance(summary_val, str) else (str(summary_val).strip() if summary_val is not None else "")
        
        name_val = meta.get("name")
        name = name_val.strip() if isinstance(name_val, str) else (str(name_val).strip() if name_val is not None else "")
        
        episode_val = meta.get("episode_body")
        episode = episode_val.strip() if isinstance(episode_val, str) else (str(episode_val).strip() if episode_val is not None else "")
        
        chosen_text = summary or episode or item.get("text") or name or ""
        
        # Trim overly long episode bodies
        if len(chosen_text) > 400:
            chosen_text = chosen_text[:397] + "..."
        
        item["text"] = chosen_text
        item["summary"] = item.get("summary") or chosen_text
        item["name"] = item.get("name") or name or "Conversation"


async def fetch_group_ids(items: List[Dict[str, Any]], graphiti) -> None:
    """
    Fetch group_ids from Neo4j for items missing them
    
    Modifies items in-place
    """
    missing_group_ids = [item for item in items if not item.get("group_id")]
    if not missing_group_ids:
        return
    
    logger.info(f"Fetching group_ids from Neo4j for {len(missing_group_ids)} items")
    
    uuids = [item["id"] for item in missing_group_ids if item.get("id")]
    if not uuids:
        return
    
    query = """
    MATCH (n)
    WHERE n.uuid IN $uuids
    RETURN n.uuid as uuid, n.group_id as group_id
    """
    
    group_id_map = {}
    async with graphiti.driver.session() as session:
        result = await session.run(query, {"uuids": uuids})
        async for record in result:
            if record["group_id"]:
                group_id_map[record["uuid"]] = record["group_id"]
    
    # Update items with fetched group_ids
    for item in items:
        if not item.get("group_id") and item.get("id") in group_id_map:
            item["group_id"] = group_id_map[item["id"]]


def deduplicate_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate results based on ID or text"""
    seen = set()
    deduped = []
    
    for item in items:
        key = item.get("id") or item.get("text")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    
    return deduped


def filter_query_echoes(items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Filter out items that are just the query echoed back"""
    q = (query or "").strip()
    q_variants = {q, f"user: {q}", f"assistant: {q}"}
    return [it for it in items if (it.get("text") or "").strip() not in q_variants]


def finalize_results(items: List[Dict[str, Any]]) -> None:
    """
    Finalize results: ensure name/summary present, fallback to trimmed text
    
    Modifies items in-place
    """
    for item in items:
        summary_text = item.get("summary") or item.get("text") or ""
        if summary_text and len(summary_text) > 400:
            summary_text = summary_text[:397] + "..."
        
        item["summary"] = summary_text
        
        if not item.get("name"):
            item["name"] = (
                summary_text[:80] + ("..." if len(summary_text) > 80 else "") 
                if summary_text else "Conversation"
            )
        
        if item.get("score") is None:
            item["score"] = 0.0


async def search_knowledge_graph(
    query: str,
    graphiti,
    focal_node_uuid: Optional[str] = None,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main search function with caching, translation, and normalization
    
    Args:
        query: Search query
        graphiti: Graphiti instance
        focal_node_uuid: Optional focal node for hybrid search
        group_id: Optional group ID filter
    
    Returns:
        Dict with "results" key containing list of search results
    """
    # Check cache first
    cache_key = cache_search_result(query, focal_node_uuid, group_id)
    cached_result = memory_cache.get(cache_key)
    if cached_result is not None:
        logger.info("Cache hit for search query")
        return cached_result
    
    # Translate query if needed
    search_query = await translate_query_if_needed(query)
    
    # Perform semantic search
    if focal_node_uuid:
        results = await graphiti.search(search_query, focal_node_uuid)
    else:
        results = await graphiti.search(search_query)
    
    # Normalize results
    normalized = [normalize_search_result(r) for r in results]
    
    # Enrich metadata
    await enrich_metadata(normalized, graphiti)
    
    # Filter by group_id if requested
    if group_id:
        await fetch_group_ids(normalized, graphiti)
        normalized = [item for item in normalized if item.get("group_id") == group_id]
    
    # Deduplicate
    deduped = deduplicate_results(normalized)
    
    # Filter query echoes
    filtered = filter_query_echoes(deduped, query)
    
    # Finalize
    finalize_results(filtered)
    
    # Cache result with 30 min TTL
    result = {"results": filtered}
    memory_cache.set(cache_key, result, ttl=1800)
    
    logger.info(f"Search completed: {len(filtered)} results")
    return result

