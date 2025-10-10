#!/usr/bin/env python3
"""
Print Human-Readable Context từ Knowledge Graph
Giống như context mà AI sẽ nhận được
"""

import asyncio
import os
import sys
from pathlib import Path
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.context_formatters import (
    ConversationContextFormatter,
    AIContextFormatter,
    CodeContextFormatter,
    format_for_ai
)

load_dotenv()

# PROJECT_ID = "full_integration_test"  # Old test project
PROJECT_ID = "innocody_test_project"  # Current project with data

async def get_entity_with_context(uuid: str, driver):
    """Get entity và tất cả relationships của nó"""
    async with driver.session() as session:
        query = """
        MATCH (source:Entity {uuid: $uuid})
        OPTIONAL MATCH (source)-[r]-(connected)
        RETURN 
          source.name as entity_name,
          source.summary as entity_summary,
          source.created_at as created_at,
          collect({
            rel_type: type(r),
            rel_name: r.name,
            connected_name: connected.name,
            connected_labels: labels(connected)
          }) as relationships
        """
        result = await session.run(query, uuid=uuid)
        record = await result.single()
        return record

async def format_entity_context(entity_data):
    """Format entity + relationships thành human-readable text"""
    if not entity_data:
        return "No data found"
    
    lines = []
    
    # Main entity
    entity_name = entity_data["entity_name"]
    entity_summary = entity_data["entity_summary"] or "No summary"
    created_at = entity_data["created_at"]
    
    lines.append("=" * 80)
    lines.append(f"ENTITY: {entity_name}")
    lines.append("=" * 80)
    lines.append(f"\n{entity_summary}\n")
    
    # Relationships
    relationships = [r for r in entity_data["relationships"] if r["rel_type"]]
    
    if relationships:
        lines.append("\nRELATED INFORMATION:")
        lines.append("-" * 80)
        
        for rel in relationships:
            rel_type = rel["rel_type"]
            rel_name = rel["rel_name"]
            connected = rel["connected_name"]
            labels = rel["connected_labels"]
            
            if rel_name:
                lines.append(f"• {rel_name}")
                lines.append(f"  -> {connected} ({', '.join(labels)})")
            else:
                lines.append(f"• [{rel_type}] -> {connected}")
        
    lines.append("\n" + "=" * 80)
    
    return "\n".join(lines)

async def simulate_search_context(use_graphiti: bool = False, use_llm_strategy: bool = False):
    """Simulate search results và format như AI sẽ nhận
    
    Args:
        use_graphiti: If True, use real Graphiti search. If False, use Cypher approximation.
        use_llm_strategy: If True, use LLM-powered strategy selection. If False, use default RRF.
    """
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    try:
        print("\n" + "="*80)
        print("HUMAN-READABLE CONTEXT FROM KNOWLEDGE GRAPH")
        print("="*80)
        
        user_query = "async await refactoring database"
        print(f"\nQuery: '{user_query}'")
        
        # Initialize variables
        selected_strategy = "rrf"
        
        if use_graphiti:
            if use_llm_strategy:
                print("Search Method: LLM-POWERED INTELLIGENT STRATEGY SELECTION (NEW!)")
                print("-" * 80)
                
                # Import LLM-powered search
                from app.graph import get_graphiti
                from app.query_classifier import SmartSearchService
                
                # Get Graphiti instance
                graphiti = await get_graphiti()
                smart_service = SmartSearchService()
                
                # Context for LLM classification
                context = {
                    "project_id": PROJECT_ID,
                    "conversation_type": "general",
                    "limit": 10
                }
                
                # Perform LLM-powered intelligent search
                search_response = await smart_service.smart_search(
                    query=user_query,
                    graphiti=graphiti,
                    context=context
                )
                
                # Extract classification info
                classification = search_response.get("classification", {})
                selected_strategy = classification.get("strategy", "unknown")
                confidence = classification.get("confidence", 0)
                reasoning = classification.get("reasoning", "No reasoning")
                
                print(f"LLM Selected Strategy: {selected_strategy} (confidence: {confidence:.2f})")
                print(f"Reasoning: {reasoning[:100]}...")
                
            else:
                print("Search Method: GRAPHITI SEMANTIC SEARCH (Production - RRF)")
                print("-" * 80)
                
                # Import Graphiti
                from app.graph import get_graphiti
                from app.services.search_service import search_knowledge_graph
                
                # Get Graphiti instance
                graphiti = await get_graphiti()
                
                # Perform real Graphiti search with RRF
                search_response = await search_knowledge_graph(
                    query=user_query,
                    graphiti=graphiti,
                    group_id=PROJECT_ID,
                    limit=10,  # Request top 10 results
                    rerank_strategy="rrf"
                )
            
            # Convert to our format
            search_results = []
            for result in search_response.get("results", []):  # Use all results (up to limit=10)
                search_results.append({
                    "uuid": result.get("id"),
                    "name": result.get("name"),
                    "summary": result.get("summary") or result.get("text"),
                    "created_at": None  # Not always available
                })
            
            strategy_name = selected_strategy if use_llm_strategy else "RRF"
            print(f"Graphiti returned {len(search_results)} results using {strategy_name} strategy\n")
            
        else:
            print("Search Method: CYPHER KEYWORD MATCHING (Demo/Approximation)")
            print("-" * 80)
            
            # Simulate search - get top 5 relevant entities using Cypher
            async with driver.session() as session:
                search_query = """
                MATCH (e:Entity {group_id: $project_id})
                WHERE e.name =~ '(?i).*(async|await|database|refactor|performance).*'
                   OR e.summary =~ '(?i).*(async|await|database|refactor|performance).*'
                RETURN 
                  e.uuid as uuid,
                  e.name as name,
                  e.summary as summary,
                  e.created_at as created_at
                ORDER BY e.created_at DESC
                LIMIT 5
                """
                result = await session.run(search_query, project_id=PROJECT_ID)
                search_results = await result.data()
            
            print(f"Cypher returned {len(search_results)} results using regex matching\n")
        
        if not search_results:
            print("No results found in KG")
            return
        
        print(f"Found {len(search_results)} relevant memories\n")
        print("="*80)
        print("FORMATTED CONTEXT FOR AI")
        print("="*80)
        
        # Convert search results to rich memory format with metadata
        formatted_memories = []
        if use_graphiti:
            # Use actual search response with all metadata
            formatted_memories = search_response.get("results", [])  # Use all results (up to limit=10)
        else:
            # Cypher results - convert to memory format
            for result in search_results:
                formatted_memories.append({
                    "text": result["summary"] or result["name"],
                    "name": result["name"],
                    "summary": result["summary"],
                    "created_at": result["created_at"]
                })
        
        # Format 1: AI-OPTIMIZED (NEW! 🎉)
        print("\n--- FORMAT 1: AI-OPTIMIZED (RECOMMENDED) ---\n")
        
        ai_context = format_for_ai(
            memories=formatted_memories,
            query=user_query,
            max_items=10,
            include_related=True
        )
        print(ai_context)
        
        # Format 2: Simple List (legacy)
        print("\n\n--- FORMAT 2: SIMPLE LIST (LEGACY) ---\n")
        
        context_list = ConversationContextFormatter.format_list(formatted_memories)
        print(context_list)
        
        # Format 3: Categorized by severity
        print("\n\n--- FORMAT 3: CATEGORIZED BY PRIORITY ---\n")
        
        context_categorized = ConversationContextFormatter.format_categorized(
            formatted_memories[:5]
        )
        print(context_categorized)
        
        # Format 4: Detailed with full metadata
        print("\n\n--- FORMAT 4: DETAILED (COMPREHENSIVE) ---\n")
        
        if formatted_memories:
            detailed_context = CodeContextFormatter.format_detailed(formatted_memories[:2])
            print(detailed_context)
        
        # Format 5: Full context cho 1 entity (with relationships)
        print("\n\n--- FORMAT 5: FULL CONTEXT (WITH RELATIONSHIPS) ---\n")
        
        # Get first entity with all relationships
        first_uuid = search_results[0]["uuid"]
        entity_data = await get_entity_with_context(first_uuid, driver)
        
        if entity_data:
            full_context = await format_entity_context(entity_data)
            print(full_context)
        
        # Show how this would be used in AI prompt
        print("\n\n" + "="*80)
        print("HOW AI RECEIVES THIS CONTEXT (PRODUCTION)")
        print("="*80)
        
        ai_prompt = f"""
SYSTEM MESSAGE:
You are a coding assistant with access to project memory.

CONTEXT FROM KNOWLEDGE GRAPH:
{ai_context}

Use this context to answer user questions accurately.

USER QUERY:
{user_query}

YOUR RESPONSE:
[AI would use the rich context above to generate accurate, file-specific responses]
"""
        print(ai_prompt)
        
        # Comparison
        print("\n\n" + "="*80)
        print("FORMAT COMPARISON")
        print("="*80)
        print(f"\nAI-Optimized: ~{len(ai_context)//4:,} tokens (BEST for production)")
        print(f"Simple List:  ~{len(context_list)//4:,} tokens (minimal metadata)")
        print(f"Detailed:     ~{len(detailed_context)//4 if formatted_memories else 0:,} tokens (comprehensive)")
        print("\nAI-Optimized provides:")
        print("   • File paths -> AI can reference specific code")
        print("   • Severity -> AI can prioritize important changes")
        print("   • Code metrics -> AI understands scope")
        print("   • Imports -> AI provides tech-specific advice")
        print("   • Related nodes -> AI has broader context")
        
    finally:
        await driver.close()

async def print_specific_uuid_context():
    """Print context cho specific UUID từ search results"""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    # UUIDs from search_results.json
    uuids = [
        ("72a98f51-1147-44fe-9dbe-2f9d66f23471", "Async Refactoring"),
        ("3c05a96b-6fc7-468e-92de-2c817de4cc1b", "Database Index"),
        ("90c780bc-5023-4c03-95bf-0cfec68b7c05", "Performance Improvement"),
    ]
    
    try:
        for uuid, label in uuids:
            print(f"\n{'='*80}")
            print(f"CONTEXT FOR: {label}")
            print(f"UUID: {uuid}")
            print(f"{'='*80}\n")
            
            entity_data = await get_entity_with_context(uuid, driver)
            if entity_data:
                context = await format_entity_context(entity_data)
                print(context)
            else:
                print(f"No data found for UUID: {uuid}")
            
            print("\n")
    
    finally:
        await driver.close()

def main():
    print("""
================================================================================
           KNOWLEDGE GRAPH -> AI-OPTIMIZED CONTEXT (UPDATED!)
              Now with LLM-POWERED STRATEGY SELECTION + FULL METADATA
================================================================================
""")
    
    print("\n**NEW**: LLM-Powered Intelligent Strategy Selection!")
    print("   • AI automatically selects best search strategy (RRF, MMR, Cross-Encoder, etc.)")
    print("   • Based on query intent, complexity, and context")
    print("   • Higher accuracy and relevance for different query types")
    print("\n**ENHANCED**: AI-Optimized formatter with full metadata!")
    print("   • File paths & functions")
    print("   • Code metrics (+/-lines)")
    print("   • Severity & priority")
    print("   • Language & imports")
    print("   • Conversation context")
    print("   • Related changes")
    
    print("\nChoose option:")
    print("1. Simulate Search (Cypher - Fast, shows all formats)")
    print("2. Real Graphiti Search (Semantic - Production RRF, with FULL METADATA)")
    print("3. LLM-Powered Search (NEW! Intelligent Strategy Selection)")
    print("4. Print Specific UUIDs from search_results.json")
    print()
    
    choice = input("Enter choice (1, 2, 3, or 4): ").strip()
    
    if choice == "1":
        print("\nUsing Cypher keyword matching (shows 5 different formats)...")
        asyncio.run(simulate_search_context(use_graphiti=False))
    elif choice == "2":
        print("\nUsing REAL Graphiti semantic search with RRF strategy...")
        print("   This is the PRODUCTION method with FULL METADATA!")
        asyncio.run(simulate_search_context(use_graphiti=True, use_llm_strategy=False))
    elif choice == "3":
        print("\nUsing LLM-POWERED intelligent strategy selection...")
        print("   AI automatically selects the best search strategy!")
        asyncio.run(simulate_search_context(use_graphiti=True, use_llm_strategy=True))
    elif choice == "4":
        asyncio.run(print_specific_uuid_context())
    else:
        print("Invalid choice. Running default (option 3 - LLM-Powered)...")
        asyncio.run(simulate_search_context(use_graphiti=True, use_llm_strategy=True))

if __name__ == "__main__":
    main()

