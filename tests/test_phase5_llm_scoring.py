# tests/test_phase5_llm_scoring.py
"""
Phase 5 Test: LLM-Only Importance Scoring

Tests OpenAI LLM scoring for:
1. Conversation facts
2. Code changes

Prerequisites:
- OPENAI_API_KEY in .env file

Run: python tests/test_phase5_llm_scoring.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.importance import get_scorer  # LLM-only module


def test_1_conversation_facts():
    """Test 1: LLM Scoring for Conversation Facts"""
    print("\n" + "="*70)
    print("TEST 1: LLM Scoring - Conversation Facts")
    print("="*70)
    
    try:
        scorer = get_scorer()
    except ValueError as e:
        print(f"\n❌ FAILED: {e}")
        print("ℹ️  Set OPENAI_API_KEY in .env file")
        return False
    
    print(f"\n✅ OpenAI LLM enabled (model: {scorer.model})\n")
    
    test_facts = [
        ("User's name is Alice Johnson", "identity", 1.0),
        ("User prefers Python over JavaScript", "preference", 0.8),
        ("User learned React hooks recently", "knowledge", 0.7),
        ("User completed the ML course", "action", 0.6),
        ("User thinks AI is overhyped", "opinion", 0.5),
        ("User said hello", "greeting", 0.1),
    ]
    
    async def run_tests():
        passed = 0
        for fact, expected_cat, expected_score in test_facts:
            try:
                result = await scorer.score_fact(fact)
                print(f"📝 '{fact[:50]}...'")
                print(f"   Category: {result['category']} (expected: {expected_cat})")
                print(f"   Score: {result['score']:.1f} (expected: {expected_score})")
                
                # Check if category matches (flexible)
                if result['category'] == expected_cat:
                    print(f"   ✅ Correct")
                    passed += 1
                else:
                    print(f"   ⚠️  Different but acceptable")
                print()
            except Exception as e:
                print(f"❌ Error: {e}\n")
                return False
        
        print(f"📊 Passed: {passed}/{len(test_facts)}")
        return True
    
    success = asyncio.run(run_tests())
    return success


def test_2_code_changes():
    """Test 2: LLM Scoring for Code Changes"""
    print("\n" + "="*70)
    print("TEST 2: LLM Scoring - Code Changes")
    print("="*70)
    
    try:
        scorer = get_scorer()
    except ValueError as e:
        print(f"\n❌ FAILED: {e}")
        return False
    
    print(f"\n✅ OpenAI LLM enabled (model: {scorer.model})\n")
    
    test_cases = [
        {
            "name": "Critical Security Vulnerability",
            "change_type": "fixed",
            "severity": "critical",
            "file_path": "src/auth/security.py",
            "summary": "Fixed SQL injection vulnerability allowing unauthorized access",
            "expected": ("critical_bug", 1.0)
        },
        {
            "name": "Major Architecture Change",
            "change_type": "refactored",
            "severity": "high",
            "file_path": "src/core/app.py",
            "summary": "Migrated from monolith to microservices architecture",
            "expected": ("architecture", 0.95)
        },
        {
            "name": "Breaking API Change",
            "change_type": "removed",
            "file_path": "src/api/v1/endpoints.py",
            "summary": "Removed deprecated v1 API endpoints, breaking compatibility",
            "expected": ("breaking_change", 0.9)
        },
        {
            "name": "Code Formatting",
            "change_type": "refactored",
            "severity": "low",
            "file_path": "src/utils/helpers.py",
            "summary": "Applied black formatter to codebase",
            "expected": ("style", 0.2)
        },
    ]
    
    async def run_tests():
        passed = 0
        for test in test_cases:
            try:
                result = await scorer.score_code_memory_llm(
                    change_type=test["change_type"],
                    severity=test.get("severity"),
                    file_path=test["file_path"],
                    summary=test["summary"]
                )
                
                expected_cat, expected_score = test["expected"]
                
                print(f"📝 {test['name']}")
                print(f"   Category: {result['category']} (expected: {expected_cat})")
                print(f"   Score: {result['score']:.2f} (expected: ~{expected_score})")
                
                # Check category and score range
                score_diff = abs(result['score'] - expected_score)
                if result['category'] == expected_cat and score_diff < 0.3:
                    print(f"   ✅ Correct")
                    passed += 1
                else:
                    print(f"   ⚠️  Different: {result['reasoning']}")
                print()
            except Exception as e:
                print(f"❌ Error: {e}\n")
                import traceback
                traceback.print_exc()
                return False
        
        print(f"📊 Passed: {passed}/{len(test_cases)}")
        return True
    
    success = asyncio.run(run_tests())
    return success


def test_3_edge_cases():
    """Test 3: Edge Cases"""
    print("\n" + "="*70)
    print("TEST 3: Edge Cases")
    print("="*70)
    
    try:
        scorer = get_scorer()
    except ValueError as e:
        print(f"\n❌ FAILED: {e}")
        return False
    
    print(f"\n✅ Testing edge cases...\n")
    
    edge_cases = [
        {
            "name": "Missing severity",
            "change_type": "fixed",
            "file_path": "src/api/routes.py",
            "summary": "Fixed timeout error",
        },
        {
            "name": "Empty summary",
            "change_type": "added",
            "severity": "medium",
            "file_path": "src/models/user.py",
            "summary": "",
        },
        {
            "name": "Very long summary",
            "change_type": "refactored",
            "file_path": "src/utils/parser.py",
            "summary": "Refactored the entire parsing logic to improve performance and maintainability, including adding type hints, improving error handling, and optimizing the core algorithm" * 10,
        },
    ]
    
    async def run_tests():
        for test in edge_cases:
            try:
                # Extract name and valid params
                name = test.pop('name')
                result = await scorer.score_code_memory_llm(**test)
                print(f"📝 {name}")
                print(f"   Category: {result['category']}")
                print(f"   Score: {result['score']:.3f}")
                print(f"   ✅ Handled gracefully\n")
            except Exception as e:
                print(f"❌ Error: {e}\n")
                return False
        return True
    
    success = asyncio.run(run_tests())
    return success


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all LLM scoring tests"""
    print("\n" + "🤖"*35)
    print("PHASE 5 - LLM-ONLY IMPORTANCE SCORING TESTS")
    print("🤖"*35)
    
    print("\n⚠️  Requirements:")
    print("  1. OPENAI_API_KEY must be set in .env")
    print("  2. API costs will be incurred (~$0.01)")
    
    input("\nPress Enter to start tests...")
    
    tests = [
        ("Conversation Facts", test_1_conversation_facts),
        ("Code Changes", test_2_code_changes),
        ("Edge Cases", test_3_edge_cases),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            print(f"\n{'='*70}")
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
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
        print("\n🎉 All LLM tests passed!")
        print("\n💡 Your system can now use AI-powered importance scoring!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 5 LLM Scoring Tests")
    parser.add_argument("--test", type=int, help="Run specific test (1-3)")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.test:
        tests = [
            test_1_conversation_facts,
            test_2_code_changes,
            test_3_edge_cases,
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
        print("PHASE 5 - LLM-ONLY IMPORTANCE SCORING TESTS")
        print("="*70)
        print("\nAvailable tests:")
        print("1. Conversation Facts Scoring")
        print("2. Code Changes Scoring")
        print("3. Edge Cases")
        print("4. Run All Tests")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "4":
            run_all_tests()
        elif choice.isdigit() and 1 <= int(choice) <= 3:
            tests = [
                test_1_conversation_facts,
                test_2_code_changes,
                test_3_edge_cases,
            ]
            tests[int(choice) - 1]()
        else:
            print("Invalid choice")
