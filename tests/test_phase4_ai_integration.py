# tests/test_phase4_ai_integration.py
"""
Phase 4 Test: AI Integration & Context Formatting

Simple test to verify:
1. Context formatters work correctly
2. AI helpers retrieve and format memories
3. Prompts are generated correctly

Run: python tests/test_phase4_ai_integration.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from app.ai_helpers import (
    MemoryLayerClient,
    get_code_context_for_query,
    store_code_change
)
from app.context_formatters import (
    format_code_context,
    deduplicate_memories
)
from app.prompts import (
    format_code_system_prompt,
    get_prompt_config
)


# =============================================================================
# Configuration
# =============================================================================

API_URL = "http://localhost:8000"
PROJECT_ID = "phase4_test"


# =============================================================================
# Test Functions
# =============================================================================

def test_1_store_test_data():
    """Test 1: Store some test data"""
    print("\n" + "="*70)
    print("TEST 1: Store Test Data")
    print("="*70)
    
    test_data = [
        {
            "name": "Fixed auth bug",
            "summary": "Fixed null pointer exception in login_user() by adding null check before accessing user.token",
            "file_path": "src/auth/auth_service.py",
            "change_type": "fixed",
            "change_summary": "Added null check",
            "function_name": "login_user",
            "severity": "high"
        },
        {
            "name": "Added rate limiting",
            "summary": "Implemented rate limiting middleware using Redis with 100 requests per minute limit",
            "file_path": "src/api/middleware.py",
            "change_type": "added",
            "change_summary": "Rate limiting with Redis",
            "function_name": "rate_limit_middleware"
        },
        {
            "name": "Refactored to async",
            "summary": "Converted get_user_by_id() to async/await pattern for 50% performance improvement",
            "file_path": "src/db/repository.py",
            "change_type": "refactored",
            "change_summary": "Async/await migration",
            "function_name": "get_user_by_id"
        }
    ]
    
    success_count = 0
    for data in test_data:
        result = store_code_change(
            project_id=PROJECT_ID,
            base_url=API_URL,
            **data
        )
        if result:
            success_count += 1
            print(f"✅ Stored: {data['name']}")
        else:
            print(f"❌ Failed: {data['name']}")
    
    print(f"\n📊 Result: {success_count}/{len(test_data)} stored successfully")
    return success_count == len(test_data)


def test_2_search_and_format():
    """Test 2: Search and format context"""
    print("\n" + "="*70)
    print("TEST 2: Search and Format Context")
    print("="*70)
    
    query = "authentication bugs"
    print(f"\n🔍 Query: '{query}'")
    
    # Get formatted context
    context, memories = get_code_context_for_query(
        query=query,
        project_id=PROJECT_ID,
        base_url=API_URL,
        format_style="relevance",
        max_results=5
    )
    
    print(f"\n✅ Found {len(memories)} memories")
    print("\n📝 Formatted Context:")
    print("-" * 70)
    print(context[:500] + "..." if len(context) > 500 else context)
    print("-" * 70)
    
    return len(memories) > 0


def test_3_format_styles():
    """Test 3: Test different formatting styles"""
    print("\n" + "="*70)
    print("TEST 3: Different Formatting Styles")
    print("="*70)
    
    client = MemoryLayerClient(API_URL, PROJECT_ID)
    memories = client.search_code("refactored OR added", limit=5)
    
    if not memories:
        print("❌ No memories found")
        return False
    
    print(f"\n✅ Found {len(memories)} memories\n")
    
    styles = ["relevance", "chronological", "grouped", "compact"]
    
    for style in styles:
        print(f"\n📋 Style: {style.upper()}")
        print("-" * 50)
        context = format_code_context(memories, style=style, limit=3)
        print(context[:200] + "..." if len(context) > 200 else context)
    
    return True


def test_4_system_prompt():
    """Test 4: Generate system prompt with context"""
    print("\n" + "="*70)
    print("TEST 4: Generate System Prompt")
    print("="*70)
    
    client = MemoryLayerClient(API_URL, PROJECT_ID)
    memories = client.search_code("authentication", limit=3)
    
    # Format system prompt
    system_prompt = format_code_system_prompt(memories)
    
    print(f"\n✅ Generated system prompt ({len(system_prompt)} chars)")
    print("\n📝 System Prompt Preview:")
    print("-" * 70)
    print(system_prompt[:600])
    print("\n... (truncated)")
    print("-" * 70)
    
    return "Code History" in system_prompt or "Your Capabilities" in system_prompt


def test_5_prompt_config():
    """Test 5: Verify prompt configurations"""
    print("\n" + "="*70)
    print("TEST 5: Prompt Configurations")
    print("="*70)
    
    configs = ["code_assistant", "code_review", "code_summarization"]
    
    all_valid = True
    for config_type in configs:
        config = get_prompt_config(config_type)
        print(f"\n📋 {config_type}:")
        print(f"   Temperature: {config.get('temperature')}")
        print(f"   Max tokens: {config.get('max_tokens')}")
        
        if not config.get('temperature') or not config.get('max_tokens'):
            all_valid = False
            print("   ❌ Missing configuration")
        else:
            print("   ✅ Valid")
    
    return all_valid


def test_6_deduplicate():
    """Test 6: Test deduplication"""
    print("\n" + "="*70)
    print("TEST 6: Memory Deduplication")
    print("="*70)
    
    client = MemoryLayerClient(API_URL, PROJECT_ID)
    memories = client.search_code("refactored", limit=10)
    
    original_count = len(memories)
    deduplicated = deduplicate_memories(memories)
    dedup_count = len(deduplicated)
    
    print(f"\n📊 Original memories: {original_count}")
    print(f"📊 After deduplication: {dedup_count}")
    print(f"{'✅' if dedup_count <= original_count else '❌'} Deduplication works")
    
    return dedup_count <= original_count


def test_7_client_methods():
    """Test 7: MemoryLayerClient methods"""
    print("\n" + "="*70)
    print("TEST 7: MemoryLayerClient Methods")
    print("="*70)
    
    client = MemoryLayerClient(API_URL, PROJECT_ID)
    
    # Test search
    print("\n🔍 Testing search...")
    memories = client.search_code("authentication", limit=3)
    print(f"✅ Search returned {len(memories)} results")
    
    # Test stats
    print("\n📊 Testing stats...")
    stats = client.get_stats()
    print(f"✅ Stats: {stats.get('total_memories', 0)} total memories")
    
    # Test filtered search
    print("\n🔍 Testing filtered search...")
    filtered = client.search_code(
        query="auth",
        change_type_filter="fixed",
        limit=5
    )
    print(f"✅ Filtered search returned {len(filtered)} results")
    
    return len(memories) >= 0 and 'total_memories' in stats


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all Phase 4 tests"""
    print("\n" + "🧪"*35)
    print("PHASE 4 - AI INTEGRATION TESTS")
    print("🧪"*35)
    
    print("\n⚠️  Make sure:")
    print("  1. API server is running: python -m uvicorn app.main:app --reload")
    print("  2. Neo4j database is running")
    
    input("\nPress Enter to start tests...")
    
    tests = [
        ("Store Test Data", test_1_store_test_data),
        ("Search & Format", test_2_search_and_format),
        ("Format Styles", test_3_format_styles),
        ("System Prompt", test_4_system_prompt),
        ("Prompt Config", test_5_prompt_config),
        ("Deduplication", test_6_deduplicate),
        ("Client Methods", test_7_client_methods),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results.append((name, False))
        
        if test_func != tests[-1][1]:
            input("\n⏸️  Press Enter to continue...")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n📊 Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 4 AI Integration Tests")
    parser.add_argument("--test", type=int, help="Run specific test (1-7)")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.test:
        tests = [
            test_1_store_test_data,
            test_2_search_and_format,
            test_3_format_styles,
            test_4_system_prompt,
            test_5_prompt_config,
            test_6_deduplicate,
            test_7_client_methods,
        ]
        
        if 1 <= args.test <= len(tests):
            tests[args.test - 1]()
        else:
            print(f"Invalid test number. Choose 1-{len(tests)}")
    
    elif args.all:
        run_all_tests()
    
    else:
        # Interactive menu
        print("\n" + "="*70)
        print("PHASE 4 - AI INTEGRATION TESTS")
        print("="*70)
        print("\nAvailable tests:")
        print("1. Store Test Data")
        print("2. Search & Format Context")
        print("3. Different Format Styles")
        print("4. Generate System Prompt")
        print("5. Prompt Configurations")
        print("6. Memory Deduplication")
        print("7. Client Methods")
        print("8. Run All Tests")
        
        choice = input("\nEnter choice (1-8): ").strip()
        
        if choice == "8":
            run_all_tests()
        elif choice.isdigit() and 1 <= int(choice) <= 7:
            tests = [
                test_1_store_test_data,
                test_2_search_and_format,
                test_3_format_styles,
                test_4_system_prompt,
                test_5_prompt_config,
                test_6_deduplicate,
                test_7_client_methods,
            ]
            tests[int(choice) - 1]()
        else:
            print("Invalid choice")
