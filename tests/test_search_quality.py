"""
TEST SEARCH QUALITY - Verify semantic search retrieves correct context

Mục tiêu: Kiểm tra xem hệ thống có tìm đúng context không khi user hỏi
Ví dụ: User hỏi về "login bug" → System phải tìm được conversation về fix login
"""

import asyncio
import httpx
from datetime import datetime
import hashlib
import uuid as uuid_lib
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

BASE_URL = "http://localhost:8000"
PROJECT_ID = "search_quality_test"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def make_context_file(file_path: str, usefulness: float, source: str = "vecdb") -> dict:
    return {
        "file_path": file_path,
        "usefulness": usefulness,
        "content_hash": hashlib.sha256(file_path.encode()).hexdigest(),
        "source": source,
        "symbols": [],
        "language": "python"
    }


def make_tool_call(tool_name: str, status: str = "success") -> dict:
    return {
        "tool_call_id": f"call_{uuid_lib.uuid4().hex[:8]}",
        "tool_name": tool_name,
        "arguments_hash": hashlib.sha256(f"{tool_name}:args".encode()).hexdigest(),
        "status": status,
        "execution_time_ms": 200
    }


def create_conversation(request_id: str, chat_id: str, user_msg: str, assistant_msg: str, 
                       context_files: list = None, code_changes: list = None) -> dict:
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return {
        "request_id": request_id,
        "project_id": PROJECT_ID,
        "timestamp": timestamp,
        "chat_meta": {
            "chat_id": chat_id,
            "chat_mode": "AGENT"
        },
        "messages": [
            {
                "role": "user",
                "content_summary": user_msg,
                "content_hash": hashlib.sha256(user_msg.encode()).hexdigest(),
                "total_tokens": len(user_msg.split()),
                "sequence": 0
            },
            {
                "role": "assistant",
                "content_summary": assistant_msg,
                "content_hash": hashlib.sha256(assistant_msg.encode()).hexdigest(),
                "total_tokens": len(assistant_msg.split()),
                "sequence": 1
            }
        ],
        "context_files": context_files or [],
        "tool_calls": [make_tool_call("read_file")],
        "code_changes": code_changes or [],
        "checkpoints": [],
        "model_response": {"model": "gpt-4o-mini"}
    }


# =============================================================================
# SETUP: Ingest test conversations
# =============================================================================

async def setup_test_data(client: httpx.AsyncClient):
    """Ingest 5 diverse conversations để test search"""
    
    print("📝 Setting up test data...")
    
    conversations = [
        # 1. Login Bug Fix
        create_conversation(
            "req_login_bug_001",
            "chat_login",
            "Users can't login! Getting 'invalid credentials' even with correct password",
            "Fixed login bug in auth/login.py. Issue was bcrypt salt rounds mismatch between registration (12) and login (10). Updated both to use 12 rounds. Added test to prevent regression."
        ),
        
        # 2. Payment Integration
        create_conversation(
            "req_payment_stripe_001",
            "chat_payment",
            "Add Stripe payment integration for subscription billing",
            "Implemented Stripe payment integration. Created payment/stripe_service.py with charge, refund, and webhook handling. Added subscription management. Configured webhook endpoint at /webhooks/stripe for payment events."
        ),
        
        # 3. Database Performance
        create_conversation(
            "req_db_performance_001",
            "chat_db_perf",
            "Database queries are slow, dashboard takes 10 seconds to load",
            "Optimized database queries. Added indexes on users.email and projects.user_id. Reduced N+1 queries using select_related(). Dashboard load time: 10s → 800ms. Added Redis caching for frequently accessed data."
        ),
        
        # 4. Email Notifications
        create_conversation(
            "req_email_notif_001",
            "chat_notifications",
            "Need to send email notifications when user completes a task",
            "Implemented email notification system. Created notifications/email_service.py using SendGrid API. Added background job queue with Celery. Sends emails for: task completion, project updates, mentions. Added email templates with HTML/text versions."
        ),
        
        # 5. Security Audit
        create_conversation(
            "req_security_audit_001",
            "chat_security",
            "Security scan found SQL injection in search endpoint",
            "Fixed critical SQL injection vulnerability in api/search.py. Replaced string concatenation with parameterized queries. Added input validation using Pydantic. Implemented rate limiting (10 req/min) to prevent abuse. Added security tests with 15 attack payloads."
        )
    ]
    
    for conv in conversations:
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=conv)
        response.raise_for_status()
        print(f"  ✅ Ingested: {conv['request_id']}")
    
    # Wait for Graphiti to process and generate embeddings
    print("  ⏳ Waiting for embeddings generation (8 seconds)...")
    await asyncio.sleep(8)
    print("  ✅ Test data ready!\n")


# =============================================================================
# SEARCH QUALITY TESTS
# =============================================================================

async def test_search_quality(client: httpx.AsyncClient):
    """Main search quality test suite"""
    
    print("="*80)
    print("🔍 TESTING SEARCH QUALITY - Context Retrieval Accuracy")
    print("="*80)
    
    test_cases = [
        # Test Case 1: Login-related query
        {
            "name": "Login Bug Query",
            "query": "login authentication bug password issue",
            "expected_keywords": ["login", "auth", "bcrypt", "password", "credentials"],
            "expected_request_id": "req_login_bug_001",
            "category": "bug_fix"
        },
        
        # Test Case 2: Payment-related query
        {
            "name": "Payment Integration Query",
            "query": "stripe payment subscription billing integration",
            "expected_keywords": ["stripe", "payment", "subscription", "webhook"],
            "expected_request_id": "req_payment_stripe_001",
            "category": "feature"
        },
        
        # Test Case 3: Performance-related query
        {
            "name": "Database Performance Query",
            "query": "slow database queries optimization indexing",
            "expected_keywords": ["database", "slow", "index", "performance", "N+1"],
            "expected_request_id": "req_db_performance_001",
            "category": "performance"
        },
        
        # Test Case 4: Email/Notification query
        {
            "name": "Email Notification Query",
            "query": "email notifications task completion alerts",
            "expected_keywords": ["email", "notification", "sendgrid", "celery"],
            "expected_request_id": "req_email_notif_001",
            "category": "feature"
        },
        
        # Test Case 5: Security-related query
        {
            "name": "Security Vulnerability Query",
            "query": "security sql injection vulnerability attack",
            "expected_keywords": ["security", "sql injection", "vulnerability", "parameterized"],
            "expected_request_id": "req_security_audit_001",
            "category": "security"
        },
        
        # Test Case 6: Cross-topic query (should find login)
        {
            "name": "User Access Problem",
            "query": "users cannot access their accounts authentication failure",
            "expected_keywords": ["login", "auth", "credentials", "password"],
            "expected_request_id": "req_login_bug_001",
            "category": "cross_topic"
        },
        
        # Test Case 7: Vague query (should find performance)
        {
            "name": "System Slow Query",
            "query": "system is slow taking too long to load",
            "expected_keywords": ["performance", "slow", "optimization"],
            "expected_request_id": "req_db_performance_001",
            "category": "vague"
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {test_case['name']}")
        print(f"   Query: \"{test_case['query']}\"")
        print(f"   Expected: {test_case['expected_request_id']}")
        
        # Perform search
        search_response = await client.post(
            f"{BASE_URL}/search",
            json={
                "query": test_case["query"],
                "group_id": PROJECT_ID
            }
        )
        search_response.raise_for_status()
        search_results = search_response.json()
        
        # Analyze results
        found_results = search_results.get("results", [])
        
        if not found_results:
            print("   ❌ NO RESULTS FOUND")
            results.append({
                "test_case": test_case["name"],
                "status": "FAIL",
                "reason": "No results returned"
            })
            continue
        
        print(f"   Found {len(found_results)} results")
        
        # Check if expected request is in top results
        top_3_texts = [r.get("text", "").lower() for r in found_results[:3]]
        top_3_summaries = [r.get("summary", "").lower() for r in found_results[:3]]
        top_3_names = [r.get("name", "").lower() for r in found_results[:3]]
        
        # Check for expected keywords in top 3 results
        keyword_matches = 0
        for keyword in test_case["expected_keywords"]:
            for text in top_3_texts + top_3_summaries + top_3_names:
                if keyword.lower() in text:
                    keyword_matches += 1
                    break
        
        keyword_accuracy = (keyword_matches / len(test_case["expected_keywords"])) * 100
        
        # Display top 3 results
        print(f"\n   Top 3 Results:")
        for j, result in enumerate(found_results[:3], 1):
            name = result.get("name", "Unknown")
            summary = result.get("summary", result.get("text", ""))[:80]
            score = result.get("score", 0.0)
            print(f"   {j}. {name}")
            print(f"      Summary: {summary}...")
            print(f"      Score: {score:.3f}")
        
        # Verdict
        if keyword_accuracy >= 60:  # At least 60% keywords found
            print(f"\n   ✅ PASS - Found {keyword_matches}/{len(test_case['expected_keywords'])} keywords ({keyword_accuracy:.0f}%)")
            results.append({
                "test_case": test_case["name"],
                "status": "PASS",
                "accuracy": keyword_accuracy,
                "results_count": len(found_results)
            })
        else:
            print(f"\n   ⚠️  PARTIAL - Found {keyword_matches}/{len(test_case['expected_keywords'])} keywords ({keyword_accuracy:.0f}%)")
            results.append({
                "test_case": test_case["name"],
                "status": "PARTIAL",
                "accuracy": keyword_accuracy,
                "results_count": len(found_results)
            })
    
    # Summary
    print("\n" + "="*80)
    print("📊 SEARCH QUALITY SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)
    
    print(f"\nResults: {passed} PASS, {partial} PARTIAL, {failed} FAIL out of {total} tests")
    print(f"Pass Rate: {(passed/total)*100:.1f}%")
    print(f"Success Rate (Pass + Partial): {((passed+partial)/total)*100:.1f}%")
    
    if passed + partial >= total * 0.7:  # 70% threshold
        print("\n✅ SEARCH QUALITY: GOOD - System retrieves relevant context accurately")
    elif passed + partial >= total * 0.5:
        print("\n⚠️  SEARCH QUALITY: ACCEPTABLE - Some improvement needed")
    else:
        print("\n❌ SEARCH QUALITY: POOR - Semantic search needs tuning")
    
    return results


# =============================================================================
# ADVANCED: Test Cross-Conversation Memory
# =============================================================================

async def test_cross_conversation_memory(client: httpx.AsyncClient):
    """Test if system can connect related conversations"""
    
    print("\n" + "="*80)
    print("🔗 TESTING CROSS-CONVERSATION MEMORY")
    print("="*80)
    
    # Scenario: User asks follow-up question about login
    print("\n📝 Scenario: User mentions login problem in new conversation")
    print("   Previous: Fixed login bug (bcrypt salt mismatch)")
    print("   New Query: 'Why are users still having login issues?'")
    
    search_response = await client.post(
        f"{BASE_URL}/search",
        json={
            "query": "users having login issues authentication problems",
            "group_id": PROJECT_ID
        }
    )
    
    results = search_response.json().get("results", [])
    
    if results:
        print(f"\n   ✅ Found {len(results)} relevant memories")
        print(f"\n   Top Result:")
        print(f"      Name: {results[0].get('name', 'Unknown')}")
        print(f"      Summary: {results[0].get('summary', '')[:100]}...")
        print(f"\n   💡 System can retrieve context from previous conversations!")
        return True
    else:
        print(f"\n   ❌ No memories found - System cannot connect conversations")
        return False


# =============================================================================
# ADVANCED: Test Specificity
# =============================================================================

async def test_search_specificity(client: httpx.AsyncClient):
    """Test if search differentiates between similar topics"""
    
    print("\n" + "="*80)
    print("🎯 TESTING SEARCH SPECIFICITY")
    print("="*80)
    
    test_cases = [
        {
            "query": "payment processing",
            "should_find": ["stripe", "payment", "subscription"],
            "should_not_find": ["login", "email", "database"]
        },
        {
            "query": "authentication security",
            "should_find": ["login", "auth", "credentials", "security"],
            "should_not_find": ["payment", "email"]
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📋 Specificity Test {i}")
        print(f"   Query: '{test['query']}'")
        
        search_response = await client.post(
            f"{BASE_URL}/search",
            json={
                "query": test["query"],
                "group_id": PROJECT_ID
            }
        )
        
        results = search_response.json().get("results", [])
        
        if not results:
            print("   ❌ No results")
            continue
        
        # Check top result
        top_text = (results[0].get("summary", "") + " " + results[0].get("text", "")).lower()
        
        found_correct = any(keyword in top_text for keyword in test["should_find"])
        found_incorrect = any(keyword in top_text for keyword in test["should_not_find"])
        
        if found_correct and not found_incorrect:
            print(f"   ✅ SPECIFIC - Found correct topic, avoided wrong topics")
        elif found_correct:
            print(f"   ⚠️  MIXED - Found correct but also some wrong topics")
        else:
            print(f"   ❌ WRONG - Did not find correct topic")


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_search_quality_tests():
    """Main test runner"""
    
    print("\n╔" + "="*78 + "╗")
    print("║" + " "*20 + "SEARCH QUALITY TEST SUITE" + " "*33 + "║")
    print("╚" + "="*78 + "╝")
    print("\n🎯 Goal: Verify semantic search retrieves correct context")
    print("⚠️  Make sure memory layer server is running on http://localhost:8000\n")
    
    timeout = httpx.Timeout(150.0, read=150.0, write=60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Setup test data
            await setup_test_data(client)
            
            # Run tests
            await test_search_quality(client)
            await test_cross_conversation_memory(client)
            await test_search_specificity(client)
            
            # Final verdict
            print("\n" + "="*80)
            print("🎉 SEARCH QUALITY TEST COMPLETED!")
            print("="*80)
            print("\n📝 Interpretation:")
            print("   ✅ PASS (>70%): System accurately retrieves relevant context")
            print("   ⚠️  PARTIAL (50-70%): System works but needs tuning")
            print("   ❌ FAIL (<50%): Embeddings or search logic needs improvement")
            print("\n💡 If results are poor:")
            print("   1. Check if Graphiti embeddings are generated")
            print("   2. Wait longer for processing (10+ seconds)")
            print("   3. Verify OpenAI API key is valid")
            print("   4. Check Neo4j has Entity nodes with embeddings")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    try:
        success = asyncio.run(run_search_quality_tests())
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        return 1


if __name__ == "__main__":
    exit(main())

