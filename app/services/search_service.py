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
from app.queries import METADATA_ENRICHMENT_QUERY, FETCH_GROUP_IDS_QUERY
from app.config import llm, cache, content, metadata

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _safe_get(obj: Any, *keys: str) -> Any:
    """
    Get value from dict or object attributes, trying keys in order
    
    Args:
        obj: Dict or object to extract value from
        *keys: Keys to try in order
        
    Returns:
        First non-None value found, or None
    """
    for key in keys:
        if isinstance(obj, dict):
            val = obj.get(key)
        else:
            val = getattr(obj, key, None)
        if val:
            return val
    return None


def _apply_metadata_to_item(
    item: Dict[str, Any], 
    meta: Dict[str, Any], 
    fields: List[str]
) -> None:
    """
    Apply metadata fields to item if present
    
    Args:
        item: Item dict to update (modified in-place)
        meta: Metadata dict to extract from
        fields: List of field names to copy
    """
    for field in fields:
        if meta.get(field) is not None:
            item[field] = meta[field]


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
            model=llm.get_model_name(),
            messages=[{"role": "user", "content": trans_prompt}],
            temperature=trans_config.get("temperature", llm.TRANSLATION_TEMPERATURE),
            max_tokens=trans_config.get("max_tokens", llm.TRANSLATION_MAX_TOKENS),
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
    
    Handles both dict and object formats from Graphiti using unified accessor
    """
    # Extract fields using unified accessor (works for both dict and object)
    txt = _safe_get(item, "summary", "fact", "text", "name") or str(item)
    ident = _safe_get(item, "source_node_uuid", "uuid", "node_uuid", "edge_id", "id")
    grp_id = _safe_get(item, "group_id", "groupId")
    name = _safe_get(item, "name")
    summary = _safe_get(item, "summary", "fact", "text")
    score = _safe_get(item, "score", "similarity")
    
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
    Enrich items with full metadata from Neo4j (code changes, conversation context)
    
    Modifies items in-place
    """
    # Get ALL items (not just those missing text) to enrich with metadata
    uuids = [item.get("id") for item in items if item.get("id")]
    if not uuids:
        return
    
    metadata_map = {}
    async with graphiti.driver.session() as session:
        result = await session.run(METADATA_ENRICHMENT_QUERY, {"uuids": uuids})
        async for record in result:
            # Build metadata dict with all fields
            meta = {
                "name": record["name"],
                "summary": record["summary"],
                "episode_body": record.get("episode_body"),
                "labels": record.get("labels")
            }
            
            # Add code change metadata if present
            if record.get("file_path"):
                meta["file_path"] = record["file_path"]
            if record.get("change_type"):
                meta["change_type"] = record["change_type"]
            if record.get("severity"):
                meta["severity"] = record["severity"]
            if record.get("lines_added") is not None:
                meta["lines_added"] = record["lines_added"]
            if record.get("lines_removed") is not None:
                meta["lines_removed"] = record["lines_removed"]
            if record.get("imports"):
                meta["imports"] = record["imports"]
            if record.get("function_name"):
                meta["function_name"] = record["function_name"]
            if record.get("change_summary"):
                meta["change_summary"] = record["change_summary"]
            if record.get("language"):
                meta["language"] = record["language"]
            if record.get("diff_summary"):
                meta["diff_summary"] = record["diff_summary"]
            
            # Add conversation metadata if present
            if record.get("project_id"):
                meta["project_id"] = record["project_id"]
            if record.get("request_id"):
                meta["request_id"] = record["request_id"]
            if record.get("chat_id"):
                meta["chat_id"] = record["chat_id"]
            if record.get("chat_mode"):
                meta["chat_mode"] = record["chat_mode"]
            if record.get("model"):
                meta["model"] = record["model"]
            if record.get("total_tokens") is not None:
                meta["total_tokens"] = record["total_tokens"]
            if record.get("message_count") is not None:
                meta["message_count"] = record["message_count"]
            if record.get("context_file_count") is not None:
                meta["context_file_count"] = record["context_file_count"]
            if record.get("tool_call_count") is not None:
                meta["tool_call_count"] = record["tool_call_count"]
            
            # Add related nodes (code changes, files, tools)
            related = record.get("related_nodes", [])
            if related and any(r.get("name") for r in related):
                meta["related_nodes"] = [r for r in related if r.get("name")]
            
            metadata_map[record["uuid"]] = meta
    
    # Apply metadata to ALL items (not just those missing text)
    for item in items:
        meta = metadata_map.get(item.get("id"))
        if not meta:
            continue
        
        # Update text/summary only if missing
        if not item.get("text") or item.get("text").strip().lower() in {"unknown", "..."}:
            summary_val = meta.get("summary")
            summary = summary_val.strip() if isinstance(summary_val, str) else (str(summary_val).strip() if summary_val is not None else "")
            
            name_val = meta.get("name")
            name = name_val.strip() if isinstance(name_val, str) else (str(name_val).strip() if name_val is not None else "")
            
            episode_val = meta.get("episode_body")
            episode = episode_val.strip() if isinstance(episode_val, str) else (str(episode_val).strip() if episode_val is not None else "")
            
            chosen_text = summary or episode or item.get("text") or name or ""
            
            # Trim overly long episode bodies
            if len(chosen_text) > content.get_max_text_length():
                chosen_text = chosen_text[:content.get_max_display_length()] + "..."
            
            item["text"] = chosen_text
            item["summary"] = item.get("summary") or chosen_text
            item["name"] = item.get("name") or name or "Conversation"
        
        # ✅ ADD ALL METADATA TO ITEM using helper function
        # Apply code change metadata
        _apply_metadata_to_item(item, meta, metadata.get_code_fields())
        
        # Apply conversation metadata
        _apply_metadata_to_item(item, meta, metadata.get_conversation_fields())
        
        # Apply special fields (related nodes, labels)
        if meta.get("related_nodes"):
            item["related_nodes"] = meta["related_nodes"]
        if meta.get("labels"):
            item["labels"] = meta["labels"]


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
    
    group_id_map = {}
    async with graphiti.driver.session() as session:
        result = await session.run(FETCH_GROUP_IDS_QUERY, {"uuids": uuids})
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
        if summary_text and len(summary_text) > content.get_max_text_length():
            summary_text = summary_text[:content.get_max_display_length()] + "..."
        
        item["summary"] = summary_text
        
        if not item.get("name"):
            item["name"] = (
                summary_text[:80] + ("..." if len(summary_text) > 80 else "") 
                if summary_text else "Conversation"
            )
        
        if item.get("score") is None:
            item["score"] = 0.0


async def _perform_search_with_reranking(
    graphiti,
    query: str,
    focal_node_uuid: Optional[str] = None,
    limit: int = 10,
    rerank_strategy: str = "rrf"
) -> list:
    """
    Perform search with specified reranking strategy
    
    Based on Graphiti documentation: https://help.getzep.com/graphiti/working-with-data/searching
    
    IMPORTANT: Graphiti's built-in search() method only supports 2 strategies:
    - rrf: Reciprocal Rank Fusion (default) - graphiti.search(query)
    - node_distance: Node Distance - graphiti.search(query, focal_node_uuid)
    
    Advanced strategies (MMR, Cross-Encoder, Episode Mentions) require graphiti._search()
    with SearchConfig recipes, which may not be available in all versions.
    
    Args:
        graphiti: Graphiti instance
        query: Search query string
        focal_node_uuid: Optional focal node for node_distance reranking
        limit: Maximum number of results
        rerank_strategy: Reranking strategy to use
    
    Returns:
        List of search results
    """
    from app.config import search as search_config
    
    # Validate rerank strategy
    if not search_config.is_valid_strategy(rerank_strategy):
        logger.warning(f"Invalid rerank strategy '{rerank_strategy}', falling back to 'rrf'")
        rerank_strategy = "rrf"
    
    logger.info(f"🔍 Using rerank strategy: {rerank_strategy}")
    
    # =========================================================================
    # BUILT-IN STRATEGIES (Always Available)
    # =========================================================================
    
    # Strategy 1: RRF (Default) - Hybrid Search with Reciprocal Rank Fusion
    if rerank_strategy == "rrf":
        logger.info("✓ Executing RRF (Reciprocal Rank Fusion) search")
        logger.info(f"  Query: '{query}'")
        logger.info(f"  Limit: {limit}")
        
        try:
            results = await graphiti.search(query)
            logger.info(f"✓ RRF returned {len(results)} results")
            
            # Debug: Log result types
            if len(results) > 0:
                logger.info(f"  First result type: {type(results[0])}")
                if hasattr(results[0], '__dict__'):
                    logger.info(f"  First result attrs: {list(results[0].__dict__.keys())}")
            else:
                logger.warning("⚠️ Graphiti search returned EMPTY results!")
                logger.warning("  Possible causes:")
                logger.warning("  1. No entities with embeddings in database")
                logger.warning("  2. Query embedding generation failed")
                logger.warning("  3. Vector similarity threshold too high")
                logger.warning("  4. Vector index not properly configured")
                
            return results[:limit]
        except Exception as e:
            logger.error(f"❌ Graphiti search raised exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    # Strategy 2: Node Distance - Prioritizes results near focal node
    elif rerank_strategy == "node_distance":
        if not focal_node_uuid:
            logger.warning("⚠️ node_distance requires focal_node_uuid, falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        
        logger.info(f"✓ Executing Node Distance search with focal node: {focal_node_uuid[:8]}...")
        results = await graphiti.search(query, focal_node_uuid)
        logger.info(f"✓ Node Distance returned {len(results)} results")
        return results[:limit]
    
    # Strategy 3: None - Raw results without reranking
    elif rerank_strategy == "none":
        logger.info("✓ Executing raw search (no reranking)")
        results = await graphiti.search(query)
        logger.info(f"✓ Raw search returned {len(results)} results")
        return results[:limit]
    
    # =========================================================================
    # ADVANCED STRATEGIES (Require graphiti._search() + SearchConfig recipes)
    # =========================================================================
    
    # Strategy 4: MMR - Maximal Marginal Relevance (reduces redundancy)
    elif rerank_strategy == "mmr":
        logger.info("Attempting MMR (Maximal Marginal Relevance) search")
        try:
            # Try to use Graphiti's advanced _search with MMR config
            from graphiti_core.search import search_config_recipes
            EDGE_HYBRID_SEARCH_MMR = search_config_recipes.EDGE_HYBRID_SEARCH_MMR
            logger.info("Imported EDGE_HYBRID_SEARCH_MMR successfully")
            
            search_results = await graphiti._search(
                query=query,
                config=EDGE_HYBRID_SEARCH_MMR
            )
            logger.info(f"MMR _search returned: {type(search_results)}")
            
            # Extract edges from SearchResults
            if hasattr(search_results, 'edges'):
                results = search_results.edges[:limit]
                logger.info(f"MMR returned {len(results)} edge results")
            else:
                logger.warning("SearchResults has no 'edges' attribute, using raw results")
                results = []
            
            if results:
                return results
            else:
                raise ValueError("No results from MMR search")
                
        except ImportError as e:
            logger.warning(f"⚠️ MMR search_config_recipes not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except AttributeError as e:
            logger.warning(f"⚠️ graphiti._search() not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except Exception as e:
            logger.warning(f"⚠️ MMR search failed: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
    
    # Strategy 5: Cross-Encoder - Most accurate reranking
    elif rerank_strategy == "cross_encoder":
        logger.info("Attempting Cross-Encoder search")
        try:
            from graphiti_core.search import search_config_recipes
            EDGE_HYBRID_SEARCH_CROSS_ENCODER = search_config_recipes.EDGE_HYBRID_SEARCH_CROSS_ENCODER
            logger.info("Imported EDGE_HYBRID_SEARCH_CROSS_ENCODER successfully")
            
            search_results = await graphiti._search(
                query=query,
                config=EDGE_HYBRID_SEARCH_CROSS_ENCODER
            )
            logger.info(f"Cross-Encoder _search returned: {type(search_results)}")
            
            if hasattr(search_results, 'edges'):
                results = search_results.edges[:limit]
                logger.info(f"✓ Cross-Encoder returned {len(results)} edge results")
            else:
                logger.warning("SearchResults has no 'edges' attribute")
                results = []
            
            if results:
                return results
            else:
                raise ValueError("No results from Cross-Encoder search")
                
        except ImportError as e:
            logger.warning(f"⚠️ Cross-Encoder search_config_recipes not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except AttributeError as e:
            logger.warning(f"⚠️ graphiti._search() not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except Exception as e:
            logger.warning(f"⚠️ Cross-Encoder search failed: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
    
    # Strategy 6: Episode Mentions - Based on episode frequency
    elif rerank_strategy == "episode_mentions":
        logger.info("Attempting Episode Mentions search")
        try:
            from graphiti_core.search import search_config_recipes
            EDGE_HYBRID_SEARCH_EPISODE_MENTIONS = search_config_recipes.EDGE_HYBRID_SEARCH_EPISODE_MENTIONS
            logger.info("Imported EDGE_HYBRID_SEARCH_EPISODE_MENTIONS successfully")
            
            search_results = await graphiti._search(
                query=query,
                config=EDGE_HYBRID_SEARCH_EPISODE_MENTIONS
            )
            logger.info(f"Episode Mentions _search returned: {type(search_results)}")
            
            if hasattr(search_results, 'edges'):
                results = search_results.edges[:limit]
                logger.info(f"✓ Episode Mentions returned {len(results)} edge results")
            else:
                logger.warning("SearchResults has no 'edges' attribute")
                results = []
            
            if results:
                return results
            else:
                raise ValueError("No results from Episode Mentions search")
                
        except ImportError as e:
            logger.warning(f"⚠️ Episode Mentions search_config_recipes not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except AttributeError as e:
            logger.warning(f"⚠️ graphiti._search() not available: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
        except Exception as e:
            logger.warning(f"⚠️ Episode Mentions search failed: {e}")
            logger.info("→ Falling back to RRF")
            results = await graphiti.search(query)
            return results[:limit]
    
    # Fallback: RRF for any unknown strategies
    else:
        logger.warning(f"Unknown strategy '{rerank_strategy}', using RRF")
        results = await graphiti.search(query)
        return results[:limit]


async def search_knowledge_graph(
    query: str,
    graphiti,
    focal_node_uuid: Optional[str] = None,
    group_id: Optional[str] = None,
    limit: int = 10,
    rerank_strategy: str = "rrf"
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
    # Import tracer
    from app.langfuse_tracer import SearchTracer
    
    # Initialize Langfuse tracer
    tracer = SearchTracer(
        query=query,
        strategy=rerank_strategy,
        project_id=group_id
    )
    
    try:
        # Check cache first
        cache_key = cache_search_result(query, focal_node_uuid, group_id)
        cached_result = memory_cache.get(cache_key)
        if cached_result is not None:
            logger.info("Cache hit for search query")
            tracer.add_step("cache_hit", output="Retrieved from cache")
            tracer.complete(
                results_count=len(cached_result.get("results", [])),
                metadata={"cache": "hit"}
            )
            return cached_result
        
        tracer.add_step("cache_miss", output="Cache miss, performing search")
        
        # Translate query if needed
        search_query = await translate_query_if_needed(query)
        if search_query != query:
            tracer.add_step("query_translation", output=search_query, metadata={
                "original": query,
                "translated": search_query
            })
        
        # Perform semantic search with reranking strategy
        tracer.add_step("semantic_search", metadata={"strategy": rerank_strategy})
        results = await _perform_search_with_reranking(
            graphiti=graphiti,
            query=search_query,
            focal_node_uuid=focal_node_uuid,
            limit=limit,
            rerank_strategy=rerank_strategy
        )
        
        logger.info(f"📊 Raw search results: {len(results)} items")
        
        # If empty, log detailed debug info
        if len(results) == 0:
            logger.error("❌ GRAPHITI RETURNED 0 RESULTS!")
            logger.error(f"   Query: {search_query}")
            logger.error(f"   Group ID filter: {group_id}")
            logger.error(f"   Strategy: {rerank_strategy}")
            logger.error("   Possible causes:")
            logger.error("   1. Graphiti searches RELATES_TO edges, but data has isolated Entity nodes")
            logger.error("   2. Graphiti expects fact_embedding on edges, but data has name_embedding on nodes")
            logger.error("   3. Data structure mismatch between Graphiti expectations and actual Neo4j schema")
        
        # Normalize results
        normalized = [normalize_search_result(r) for r in results]
        logger.info(f"📊 After normalization: {len(normalized)} items")
        
        # Debug: Log first few results
        for idx, item in enumerate(normalized[:3]):
            logger.debug(f"  Result {idx}: group_id={item.get('group_id')}, text={item.get('text', '')[:50]}")
        
        tracer.add_step("normalization", output=f"Normalized {len(normalized)} results")
        
        # Enrich metadata
        await enrich_metadata(normalized, graphiti)
        tracer.add_step("metadata_enrichment", output=f"Enriched {len(normalized)} results")
        
        # Filter by group_id if requested
        if group_id:
            await fetch_group_ids(normalized, graphiti)
            before_count = len(normalized)
            
            # Filter by group_id, but keep items without group_id if they match
            filtered = []
            for item in normalized:
                item_group = item.get("group_id")
                # Keep if: exact match OR no group_id (could be global/shared)
                if item_group == group_id or item_group is None:
                    filtered.append(item)
            
            normalized = filtered
            
            logger.info(f"Group filter: {before_count} → {len(normalized)} results (group_id={group_id})")
            tracer.add_step("group_filter", metadata={
                "group_id": group_id,
                "before": before_count,
                "after": len(normalized)
            })
        
        # Deduplicate
        deduped = deduplicate_results(normalized)
        tracer.add_step("deduplication", output=f"{len(normalized)} -> {len(deduped)} results")
        
        # Filter query echoes
        filtered = filter_query_echoes(deduped, query)
        
        # Finalize
        finalize_results(filtered)
        
        # Cache result
        result = {"results": filtered}
        memory_cache.set(cache_key, result, ttl=cache.get_search_ttl())
        
        logger.info(f"Search completed: {len(filtered)} results")
        
        # Complete trace
        tracer.complete(
            results_count=len(filtered),
            metadata={
                "cache": "miss",
                "strategy": rerank_strategy,
                "translated": search_query != query
            }
        )
        
        return result
        
    except Exception as e:
        tracer.error(str(e))
        raise

