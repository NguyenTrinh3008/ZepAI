# app/queries/__init__.py
"""
Cypher query loader for Neo4j operations

Separates Cypher queries from Python code for better maintainability
and easier testing.
"""
from pathlib import Path
from typing import Dict

QUERIES_DIR = Path(__file__).parent

# Cache for loaded queries
_query_cache: Dict[str, str] = {}


def load_query(name: str) -> str:
    """
    Load Cypher query from file
    
    Args:
        name: Query file name (without .cypher extension)
        
    Returns:
        Query string
        
    Example:
        >>> query = load_query("metadata_enrichment")
        >>> # Use query with Neo4j session
    """
    # Check cache first
    if name in _query_cache:
        return _query_cache[name]
    
    # Load from file
    query_file = QUERIES_DIR / f"{name}.cypher"
    if not query_file.exists():
        raise FileNotFoundError(f"Query file not found: {query_file}")
    
    query = query_file.read_text(encoding='utf-8')
    
    # Cache it
    _query_cache[name] = query
    
    return query


def clear_cache():
    """Clear the query cache (useful for testing)"""
    _query_cache.clear()


# Pre-load common queries for convenience
METADATA_ENRICHMENT_QUERY = load_query("metadata_enrichment")
FETCH_GROUP_IDS_QUERY = load_query("fetch_group_ids")

