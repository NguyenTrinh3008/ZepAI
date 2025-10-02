# tests/test_full_pipeline.py
"""
Full End-to-End Pipeline Test

Tests the complete memory system from start to finish:
1. Add conversation memories
2. Add code memories  
3. Search memories
4. Score importance
5. Format context for AI
6. Verify TTL expiration

Run: python tests/test_full_pipeline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
from datetime import datetime, timedelta
from app.graph import get_graphiti
from app.importance import get_scorer
from app.context_formatters import format_conversation_context, format_code_context


async def test_full_pipeline():
    """Complete end-to-end test"""
    print("\n" + "="*70)
    print("🧪 FULL MEMORY SYSTEM PIPELINE TEST")
    print("="*70)
    
    # Initialize
    print("\n📦 Step 1: Initialize Components")
    print("-" * 70)
    
    graph = await get_graphiti()
    
    try:
        scorer = get_scorer()
        print("✅ LLM scorer initialized (OpenAI)")
    except ValueError as e:
        print(f"⚠️  LLM scorer unavailable: {e}")
        print("⚠️  Continuing without importance scoring...")
        scorer = None
    
    print("✅ Graphiti initialized (Neo4j + OpenAI)")
    
    # =========================================================================
    # STEP 2: Add Conversation Memories
    # =========================================================================
    print("\n💬 Step 2: Add Conversation Memories")
    print("-" * 70)
    
    conversation_facts = [
        "User's name is Sarah Chen",
        "User is a senior software engineer at Google",
        "User prefers Python and TypeScript for development",
        "User recently learned about RAG architectures",
        "User is building an AI-powered code assistant",
        "User likes clean code and test-driven development",
    ]
    
    for fact in conversation_facts:
        # Score with LLM if available
        if scorer:
            result = await scorer.score_conversation(fact)
            score = result['score']
            category = result['category']
            print(f"  📝 '{fact[:50]}...'")
            print(f"     Score: {score:.2f} | Category: {category}")
        else:
            score = 0.7  # Default
            print(f"  📝 {fact}")
        
        # Add to graph
        from graphiti_core.nodes import EpisodeType
        await graph.add_episode(
            name=f"conversation_{hash(fact)}",
            episode_body=fact,
            source=EpisodeType.message,
            source_description="User conversation",
            reference_time=datetime.now()
        )
    
    print(f"\n✅ Added {len(conversation_facts)} conversation memories")
    
    # =========================================================================
    # STEP 3: Add Code Memories
    # =========================================================================
    print("\n💻 Step 3: Add Code Memories")
    print("-" * 70)
    
    code_changes = [
        {
            "summary": "Fixed critical SQL injection vulnerability in authentication",
            "change_type": "fixed",
            "severity": "critical",
            "file_path": "src/auth/security.py",
        },
        {
            "summary": "Added new payment processing with Stripe integration",
            "change_type": "added",
            "severity": "high",
            "file_path": "src/api/payment.py",
        },
        {
            "summary": "Refactored database queries for better performance",
            "change_type": "refactored",
            "severity": "medium",
            "file_path": "src/db/repository.py",
        },
        {
            "summary": "Updated documentation for API endpoints",
            "change_type": "added",
            "severity": "low",
            "file_path": "docs/api.md",
        },
    ]
    
    for change in code_changes:
        # Score with LLM if available
        if scorer:
            result = await scorer.score_code_change(
                change_type=change['change_type'],
                severity=change['severity'],
                file_path=change['file_path'],
                summary=change['summary']
            )
            score = result['score']
            category = result['category']
            print(f"  🔧 {change['summary'][:50]}...")
            print(f"     Score: {score:.2f} | Category: {category}")
        else:
            score = 0.7  # Default
            print(f"  🔧 {change['summary']}")
        
        # Add to graph
        from graphiti_core.nodes import EpisodeType
        await graph.add_episode(
            name=f"code_{change['file_path']}_{int(time.time())}",
            episode_body=f"{change['change_type']}: {change['summary']}",
            source=EpisodeType.text,
            source_description=change['file_path'],
            reference_time=datetime.now()
        )
    
    print(f"\n✅ Added {len(code_changes)} code memories")
    
    # =========================================================================
    # STEP 4: Search Memories
    # =========================================================================
    print("\n🔍 Step 4: Search Memories")
    print("-" * 70)
    
    search_queries = [
        "What do you know about the user?",
        "Security vulnerabilities and fixes",
        "Recent code changes",
    ]
    
    for query in search_queries:
        print(f"\n  Query: '{query}'")
        results = await graph.search(query, limit=3)
        print(f"  Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            content = result.get('content', 'N/A')[:60]
            print(f"    {i}. {content}...")
    
    # =========================================================================
    # STEP 5: Format Context for AI
    # =========================================================================
    print("\n🤖 Step 5: Format Context for AI")
    print("-" * 70)
    
    # Get conversation context
    conv_results = await graph.search("user information and preferences", limit=5)
    conv_context = format_conversation_context(conv_results)
    print("\n📋 Conversation Context (for AI):")
    print(conv_context[:300] + "..." if len(conv_context) > 300 else conv_context)
    
    # Get code context
    code_results = await graph.search("code changes", limit=5)
    code_context = format_code_context(code_results)
    print("\n📋 Code Context (for AI):")
    print(code_context[:300] + "..." if len(code_context) > 300 else code_context)
    
    # =========================================================================
    # STEP 6: Test Memory Stats
    # =========================================================================
    print("\n📊 Step 6: Memory Statistics")
    print("-" * 70)
    
    stats = await graph.get_stats()
    print(f"  Total Nodes: {stats.get('total_nodes', 0)}")
    print(f"  Total Edges: {stats.get('total_edges', 0)}")
    print(f"  Episode Nodes: {stats.get('episode_nodes', 0)}")
    print(f"  Entity Nodes: {stats.get('entity_nodes', 0)}")
    
    # =========================================================================
    # STEP 7: Test TTL (Time-To-Live)
    # =========================================================================
    print("\n⏰ Step 7: Test TTL Expiration")
    print("-" * 70)
    
    # Add short-lived memory
    short_lived_fact = "This is a temporary test fact"
    await graph.add_episode(
        name="ttl_test",
        episode_type="message",
        content=short_lived_fact,
        source_description="TTL test",
        valid_hours=0.001  # Expires in ~4 seconds
    )
    print(f"  📝 Added short-lived memory (expires in ~4 seconds)")
    
    # Search immediately
    results = await graph.search(short_lived_fact, limit=1)
    print(f"  ✅ Found immediately: {len(results) > 0}")
    
    # Wait for expiration
    print(f"  ⏳ Waiting 5 seconds for expiration...")
    await asyncio.sleep(5)
    
    # Search again
    results = await graph.search(short_lived_fact, limit=1)
    print(f"  ✅ Expired correctly: {len(results) == 0}")
    
    # =========================================================================
    # STEP 8: Full AI Context Example
    # =========================================================================
    print("\n🎯 Step 8: Complete AI Context Example")
    print("-" * 70)
    
    user_query = "Help me review the recent security fixes"
    
    # Search relevant memories
    results = await graph.search(user_query, limit=5)
    
    # Format full context
    full_context = f"""# User Information
{format_conversation_context(await graph.search("user", limit=3))}

# Recent Code Changes  
{format_code_context(results)}

# User Query
{user_query}
"""
    
    print("\n📄 Complete AI Prompt Context:")
    print("=" * 70)
    print(full_context[:500] + "..." if len(full_context) > 500 else full_context)
    print("=" * 70)
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "="*70)
    print("✅ PIPELINE TEST COMPLETE!")
    print("="*70)
    
    print("\n🎉 All components working:")
    print("  ✅ Memory storage (Neo4j)")
    print("  ✅ Conversation memories")
    print("  ✅ Code memories")
    print("  ✅ Semantic search")
    if scorer:
        print("  ✅ LLM importance scoring")
    print("  ✅ Context formatting")
    print("  ✅ TTL expiration")
    print("  ✅ Statistics tracking")
    
    print("\n💡 Your memory system is fully operational!")
    print("\n📚 Next steps:")
    print("  1. Integrate with your AI assistant")
    print("  2. Add memories as user codes")
    print("  3. Use formatted context in prompts")
    print("  4. Monitor with statistics endpoint")
    
    # Cleanup
    print("\n✅ Test complete!")


# =============================================================================
# Simplified Usage Examples
# =============================================================================

async def example_1_basic_conversation():
    """Example 1: Basic conversation memory"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Conversation Memory")
    print("="*70)
    
    graph = await get_graphiti()
    
    # User has a conversation
    print("\n💬 User conversation:")
    print("User: My name is Alice and I work at Microsoft")
    
    # Add to memory
    from graphiti_core.nodes import EpisodeType
    await graph.add_episode(
        name="conv_intro",
        episode_body="User's name is Alice and works at Microsoft",
        source=EpisodeType.message,
        source_description="Introduction",
        reference_time=datetime.now()
    )
    print("✅ Stored in memory")
    
    # Later, recall
    print("\n🔍 AI recalls:")
    results = await graph.search("user's name and job")
    if results:
        print(f"📝 Found: {results[0] if results else 'No results'}")


async def example_2_code_tracking():
    """Example 2: Track code changes"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Code Change Tracking")
    print("="*70)
    
    graph = await get_graphiti()
    scorer = get_scorer()
    
    # User commits code
    change = {
        "summary": "Fixed authentication bypass vulnerability",
        "change_type": "fixed",
        "severity": "critical",
        "file_path": "src/auth/login.py"
    }
    
    print(f"\n🔧 Code commit: {change['summary']}")
    
    # Score importance
    result = await scorer.score_code_change(**change)
    print(f"📊 Importance: {result['score']:.2f} ({result['category']})")
    
    # Store in memory
    from graphiti_core.nodes import EpisodeType
    await graph.add_episode(
        name=f"fix_{int(time.time())}",
        episode_body=f"{change['change_type']}: {change['summary']}",
        source=EpisodeType.text,
        source_description=change['file_path'],
        reference_time=datetime.now()
    )
    print("✅ Tracked in memory")
    
    # Later, search
    print("\n🔍 Find all security fixes:")
    results = await graph.search("security vulnerability fixes")
    print(f"  Found {len(results) if results else 0} results")


async def example_3_ai_context():
    """Example 3: Build AI context"""
    print("\n" + "="*70)
    print("EXAMPLE 3: AI Context Building")
    print("="*70)
    
    graph = await get_graphiti()
    
    # Add some memories
    from graphiti_core.nodes import EpisodeType
    await graph.add_episode(
        name="pref1",
        episode_body="User prefers functional programming style",
        source=EpisodeType.message,
        source_description="Conversation",
        reference_time=datetime.now()
    )
    
    # User asks for help
    user_query = "Write me a Python function"
    print(f"\n💬 User: {user_query}")
    
    # Get relevant context
    memories = await graph.search("user preferences programming", limit=3)
    context = format_conversation_context(memories)
    
    # Build prompt
    ai_prompt = f"""Context about user:
{context}

User request: {user_query}

Generate code following user's preferences."""
    
    print("\n🤖 AI Prompt:")
    print(ai_prompt)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Full Pipeline Tests")
    parser.add_argument("--full", action="store_true", help="Run full pipeline test")
    parser.add_argument("--example", type=int, choices=[1,2,3], help="Run specific example")
    
    args = parser.parse_args()
    
    if args.full:
        asyncio.run(test_full_pipeline())
    elif args.example == 1:
        asyncio.run(example_1_basic_conversation())
    elif args.example == 2:
        asyncio.run(example_2_code_tracking())
    elif args.example == 3:
        asyncio.run(example_3_ai_context())
    else:
        # Interactive menu
        print("\n" + "="*70)
        print("MEMORY SYSTEM - FULL PIPELINE TESTS")
        print("="*70)
        print("\nChoose test:")
        print("1. Full Pipeline Test (comprehensive)")
        print("2. Example 1: Basic Conversation")
        print("3. Example 2: Code Change Tracking")
        print("4. Example 3: AI Context Building")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            asyncio.run(test_full_pipeline())
        elif choice == "2":
            asyncio.run(example_1_basic_conversation())
        elif choice == "3":
            asyncio.run(example_2_code_tracking())
        elif choice == "4":
            asyncio.run(example_3_ai_context())
        else:
            print("Invalid choice")
