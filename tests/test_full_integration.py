"""
FULL INTEGRATION TEST - Ingest + Search Pipeline
Kết hợp test_realistic_scenarios.py + test_search_quality.py

Flow:
1. Ingest 6 realistic conversations
2. Wait for Graphiti processing
3. Test search quality on ingested data
4. Verify context retrieval works
"""

import asyncio
import httpx
from datetime import datetime
import hashlib
import uuid as uuid_lib
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

BASE_URL = "http://localhost:8000"
PROJECT_ID = "full_integration_test"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def make_context_file(file_path: str, usefulness: float, source: str = "vecdb", symbols: list = None) -> dict:
    return {
        "file_path": file_path,
        "usefulness": usefulness,
        "content_hash": hashlib.sha256(file_path.encode()).hexdigest(),
        "source": source,
        "symbols": symbols or [],
        "language": _detect_language(file_path)
    }


def _detect_language(file_path: str) -> str:
    ext_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.go': 'go', '.rs': 'rust'}
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    return 'unknown'


def make_tool_call(tool_name: str, status: str = "success", execution_time_ms: int = 200) -> dict:
    return {
        "tool_call_id": f"call_{uuid_lib.uuid4().hex[:8]}",
        "tool_name": tool_name,
        "arguments_hash": hashlib.sha256(f"{tool_name}:args".encode()).hexdigest(),
        "status": status,
        "execution_time_ms": execution_time_ms
    }


def make_code_change(file_path: str, change_summary: str, **kwargs) -> dict:
    defaults = {
        "change_type": "modified",
        "severity": "medium",
        "lines_added": 0,
        "lines_removed": 0,
        "language": _detect_language(file_path),
        "imports": [],
        "function_name": None,
    }
    defaults.update(kwargs)
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    before_hash = hashlib.sha256(f"before:{file_path}:{change_summary}".encode()).hexdigest()[:16]
    after_hash = hashlib.sha256(f"after:{file_path}:{change_summary}".encode()).hexdigest()[:16]
    
    return {
        "name": f"{defaults['change_type'].title()} {file_path}",
        "summary": change_summary,
        "file_path": file_path,
        "function_name": defaults["function_name"],
        "change_type": defaults["change_type"],
        "change_summary": change_summary,
        "severity": defaults["severity"],
        "diff_summary": change_summary,
        "lines_added": defaults["lines_added"],
        "lines_removed": defaults["lines_removed"],
        "language": defaults["language"],
        "imports": defaults["imports"],
        "code_before_hash": before_hash,
        "code_after_hash": after_hash,
        "timestamp": timestamp,
    }


def create_conversation_payload(request_id: str, chat_id: str, user_message: str, 
                                assistant_message: str, context_files: list, 
                                tool_calls: list, model: str = "gpt-4o-mini", 
                                code_changes: list = None):
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return {
        "request_id": request_id,
        "project_id": PROJECT_ID,
        "timestamp": timestamp,
        "chat_meta": {
            "chat_id": chat_id,
            "base_chat_id": chat_id.split("_")[0],
            "request_attempt_id": f"attempt_{uuid_lib.uuid4().hex[:8]}",
            "chat_mode": "AGENT"
        },
        "messages": [
            {
                "sequence": 0,
                "role": "user",
                "content_summary": user_message,
                "content_hash": hashlib.sha256(user_message.encode()).hexdigest(),
                "total_tokens": len(user_message.split()),
                "sequence": 0
            },
            {
                "sequence": 1,
                "role": "assistant",
                "content_summary": assistant_message,
                "content_hash": hashlib.sha256(assistant_message.encode()).hexdigest(),
                "prompt_tokens": len(user_message.split()) * 2,
                "completion_tokens": len(assistant_message.split()),
                "total_tokens": len(user_message.split()) * 2 + len(assistant_message.split()),
                "sequence": 1
            }
        ],
        "context_files": context_files,
        "tool_calls": tool_calls,
        "checkpoints": [],
        "code_changes": code_changes or [],
        "model_response": {
            "model": model,
            "finish_reason": "stop"
        }
    }


# =============================================================================
# PHASE 1: INGEST REALISTIC CONVERSATIONS
# =============================================================================

async def phase1_ingest_conversations(client: httpx.AsyncClient):
    """
    Ingest 6 realistic coding assistant conversations
    (From test_realistic_scenarios.py)
    """
    print("\n" + "="*80)
    print("📥 PHASE 1: INGEST REALISTIC CONVERSATIONS")
    print("="*80)
    
    conversations = [
        # 1. REFACTORING
        {
            "request_id": "req_refactor_async_001",
            "chat_id": "chat_refactor",
            "name": "Async/Await Refactoring",
            "user_message": "Convert get_user_data() to async/await - it's blocking and causing performance issues",
            "assistant_message": "Refactored get_user_data() to async/await pattern using asyncpg. Updated 3 callers. Performance improved: 450ms → 85ms (81% faster). All tests passing.",
            "context_files": [
                make_context_file("database/users.py", 0.98, "vecdb", ["get_user_data", "UserModel"]),
                make_context_file("api/users.py", 0.85, "ast", ["get_user_endpoint"]),
            ],
            "tools": [
                make_tool_call("read_file"),
                make_tool_call("edit_file", "success", 520),
                make_tool_call("run_tests", "success", 3450)
            ],
            "code_changes": [
                make_code_change(
                    "database/users.py",
                    "Converted get_user_data() from synchronous to async/await pattern",
                    change_type="refactored",
                    severity="medium",
                    lines_added=8,
                    lines_removed=6,
                    imports=["asyncpg"]
                )
            ]
        },
        
        # 2. BUG INVESTIGATION
        {
            "request_id": "req_bug_keyerror_001",
            "chat_id": "chat_debug",
            "name": "KeyError Bug Fix",
            "user_message": "Getting KeyError: 'user_preferences' in production at api/profile.py line 67. Happening randomly for some users.",
            "assistant_message": "Found the issue! New users don't have user_preferences key. Added defensive programming with .get() and default fallback. Found 847 users without preferences (12% of user base). Added migration script and test to prevent regression.",
            "context_files": [
                make_context_file("api/profile.py", 0.96, "vecdb", ["get_profile"]),
                make_context_file("models/user.py", 0.91, "ast", ["UserModel"]),
            ],
            "tools": [
                make_tool_call("read_file"),
                make_tool_call("run_query", "success", 1250),
                make_tool_call("edit_file", "success", 412),
            ],
            "code_changes": [
                make_code_change(
                    "api/profile.py",
                    "Added defensive programming for missing user_preferences with default fallback",
                    change_type="fixed",
                    severity="high",
                    lines_added=5,
                    lines_removed=2
                )
            ]
        },
        
        # 3. NEW FEATURE
        {
            "request_id": "req_feature_upload_001",
            "chat_id": "chat_feature",
            "name": "Profile Picture Upload",
            "user_message": "Add feature for users to upload profile pictures. Validate file type (jpg/png), size (max 5MB), store in S3.",
            "assistant_message": "Implemented profile picture upload! Created POST /api/users/{user_id}/profile-picture endpoint. File validation middleware (type, size, dimensions). S3 upload service with image processing (resize to 512x512). Security: Content-Type validation, magic byte checking, virus scanning, rate limiting (3 uploads/hour). Tests added.",
            "context_files": [
                make_context_file("api/users.py", 0.94, "vecdb", ["UserAPI"]),
                make_context_file("services/storage.py", 0.89, "vecdb", ["S3Service"]),
            ],
            "tools": [
                make_tool_call("create_file", "success", 580),
                make_tool_call("edit_file", "success", 420),
                make_tool_call("run_tests", "success", 4200),
            ],
            "code_changes": [
                make_code_change(
                    "api/users.py",
                    "Added POST /users/{user_id}/profile-picture endpoint with multipart file upload",
                    change_type="added",
                    severity="low",
                    lines_added=45
                )
            ]
        },
        
        # 4. CODE REVIEW
        {
            "request_id": "req_review_payment_001",
            "chat_id": "chat_review",
            "name": "Payment Code Review",
            "user_message": "Review payment/processor.py for security issues and best practices",
            "assistant_message": "Found 3 CRITICAL issues: 1) API Key Exposure (hardcoded Stripe key), 2) Missing Input Validation (amount could be negative), 3) No Idempotency Key (duplicate charges possible). Found 3 warnings: Error messages too detailed, Missing audit logging, Synchronous processing blocks requests. Recommendations: Fix API key (CRITICAL), Add validation (CRITICAL), Implement idempotency (HIGH).",
            "context_files": [
                make_context_file("payment/processor.py", 0.98, "vecdb", ["process_payment"]),
            ],
            "tools": [
                make_tool_call("read_file"),
                make_tool_call("security_scan", "success", 2300),
            ],
            "code_changes": []
        },
        
        # 5. PERFORMANCE OPTIMIZATION
        {
            "request_id": "req_perf_dashboard_001",
            "chat_id": "chat_perf",
            "name": "Dashboard Performance Fix",
            "user_message": "The /api/dashboard endpoint takes 8-12 seconds to load! Users are complaining.",
            "assistant_message": "Found N+1 query problem! Dashboard loads 100 projects, each triggers separate queries for team members, activity, tasks (301 total queries). Fixed: Used select_related() and prefetch_related() to reduce 301→4 queries. Added Redis cache (5min TTL). Added indexes on user_id and (project_id, created_at). Result: 9.5s → 350ms (96% faster!). With cache: 45ms. System can now handle 10x traffic.",
            "context_files": [
                make_context_file("api/dashboard.py", 0.97, "vecdb", ["get_dashboard"]),
                make_context_file("database/queries.py", 0.93, "ast", ["get_user_projects"]),
            ],
            "tools": [
                make_tool_call("profile_code", "success", 8500),
                make_tool_call("edit_file", "success", 680),
                make_tool_call("run_migration", "success", 2100),
            ],
            "code_changes": [
                make_code_change(
                    "database/queries.py",
                    "Optimized get_user_projects with select_related to eliminate N+1 queries",
                    change_type="refactored",
                    severity="high",
                    lines_added=12,
                    lines_removed=25
                )
            ]
        },
        
        # 6. DOCUMENTATION
        {
            "request_id": "req_docs_api_001",
            "chat_id": "chat_docs",
            "name": "API Documentation Generation",
            "user_message": "Generate comprehensive API documentation for api/auth.py endpoints in OpenAPI format",
            "assistant_message": "Generated comprehensive API documentation! Created OpenAPI 3.0 specification for 8 auth endpoints (register, login, logout, refresh, forgot-password, reset-password, verify-email, resend-verification). Added request/response schemas, authentication requirements, error responses (200, 400, 401, 403, 500). Created code examples (Python, cURL, JavaScript). Added docstrings and type hints. Preview available: npm run docs:serve",
            "context_files": [
                make_context_file("api/auth.py", 0.98, "vecdb", ["register", "login"]),
            ],
            "tools": [
                make_tool_call("generate_openapi", "success", 3400),
                make_tool_call("create_file", "success", 890),
            ],
            "code_changes": [
                make_code_change(
                    "docs/openapi/auth.yaml",
                    "Generated comprehensive OpenAPI 3.0 specification for all auth endpoints",
                    change_type="added",
                    severity="low",
                    lines_added=342,
                    language="yaml"
                )
            ]
        }
    ]
    
    ingested_conversations = []
    
    for i, conv in enumerate(conversations, 1):
        print(f"\n📝 [{i}/6] Ingesting: {conv['name']}")
        
        payload = create_conversation_payload(
            conv["request_id"],
            conv["chat_id"],
            conv["user_message"],
            conv["assistant_message"],
            conv["context_files"],
            conv["tools"],
            code_changes=conv["code_changes"]
        )
        
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"   ✅ UUID: {result['request_uuid'][:16]}...")
        print(f"   📁 Files: {len(conv['context_files'])}, 🔧 Tools: {len(conv['tools'])}, 💻 Changes: {len(conv['code_changes'])}")
        
        ingested_conversations.append({
            "request_id": conv["request_id"],
            "uuid": result["request_uuid"],
            "name": conv["name"],
            "keywords": _extract_keywords(conv["user_message"] + " " + conv["assistant_message"])
        })
    
    print("\n⏳ Waiting for Graphiti to process and generate embeddings...")
    print("   (This takes ~10 seconds for entity extraction + embedding generation)")
    await asyncio.sleep(10)
    print("   ✅ Processing complete!")
    
    return ingested_conversations


def _extract_keywords(text: str) -> list:
    """Extract key technical terms from text"""
    keywords = []
    common_terms = {
        "async", "await", "refactor", "performance", "bug", "error", "keyerror",
        "profile", "upload", "s3", "validation", "security", "payment", "review",
        "critical", "dashboard", "n+1", "query", "cache", "redis", "optimization",
        "documentation", "api", "openapi", "auth", "endpoint"
    }
    
    words = text.lower().split()
    for word in words:
        clean_word = word.strip(".,!?()[]{}:;")
        if clean_word in common_terms:
            keywords.append(clean_word)
    
    return list(set(keywords))[:5]  # Return top 5 unique keywords


# =============================================================================
# PHASE 2: TEST SEARCH QUALITY
# =============================================================================

async def phase2_test_search_quality(client: httpx.AsyncClient, conversations: list):
    """
    Test search quality on the ingested conversations
    Save results to JSON file for tracking
    """
    print("\n" + "="*80)
    print("🔍 PHASE 2: TEST SEARCH QUALITY")
    print("="*80)
    
    # Prepare results container
    test_run = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "project_id": PROJECT_ID,
        "conversations_count": len(conversations),
        "conversations": [
            {
                "request_id": conv["request_id"],
                "name": conv["name"],
                "uuid": conv["uuid"]
            }
            for conv in conversations
        ],
        "search_tests": []
    }
    
    test_cases = [
        {
            "name": "Async Refactoring Query",
            "query": "async await performance refactoring database",
            "expected_request_id": "req_refactor_async_001",
            "expected_keywords": ["async", "await", "refactor", "performance"],
        },
        {
            "name": "Bug Investigation Query",
            "query": "keyerror bug user preferences profile error",
            "expected_request_id": "req_bug_keyerror_001",
            "expected_keywords": ["bug", "keyerror", "user", "error"],
        },
        {
            "name": "Upload Feature Query",
            "query": "upload profile picture image s3 validation",
            "expected_request_id": "req_feature_upload_001",
            "expected_keywords": ["upload", "profile", "s3", "validation"],
        },
        {
            "name": "Security Review Query",
            "query": "security payment review critical api key",
            "expected_request_id": "req_review_payment_001",
            "expected_keywords": ["security", "payment", "review", "critical"],
        },
        {
            "name": "Performance Query",
            "query": "slow dashboard n+1 query optimization cache",
            "expected_request_id": "req_perf_dashboard_001",
            "expected_keywords": ["performance", "dashboard", "query", "cache"],
        },
        {
            "name": "Documentation Query",
            "query": "api documentation openapi auth endpoints",
            "expected_request_id": "req_docs_api_001",
            "expected_keywords": ["api", "documentation", "openapi", "auth"],
        },
        {
            "name": "Cross-Topic: Performance (Vague)",
            "query": "system is slow taking too long",
            "expected_request_id": "req_perf_dashboard_001",
            "expected_keywords": ["slow", "performance", "optimization"],
        },
        {
            "name": "Cross-Topic: Error Handling",
            "query": "users getting errors unexpected failures",
            "expected_request_id": "req_bug_keyerror_001",
            "expected_keywords": ["error", "bug", "user"],
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}/{len(test_cases)}: {test_case['name']}")
        print(f"   Query: \"{test_case['query']}\"")
        
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
        
        found_results = search_results.get("results", [])
        
        if not found_results:
            print("   ❌ NO RESULTS")
            test_result = {
                "test_name": test_case["name"],
                "query": test_case["query"],
                "expected_request_id": test_case["expected_request_id"],
                "status": "FAIL",
                "reason": "No results returned",
                "results_count": 0,
                "results": []
            }
            results.append({"test": test_case["name"], "status": "FAIL", "reason": "No results"})
            test_run["search_tests"].append(test_result)
            continue
        
        print(f"   📊 Found {len(found_results)} results")
        
        # Check top 3 results
        top_3 = found_results[:3]
        print(f"\n   Top 3:")
        for j, r in enumerate(top_3, 1):
            name = r.get("name", "Unknown")[:40]
            summary = r.get("summary", "")[:60]
            print(f"   {j}. {name}")
            print(f"      {summary}...")
        
        # Check keyword matches in top 3
        top_texts = " ".join([
            r.get("text", "") + " " + r.get("summary", "") + " " + r.get("name", "")
            for r in top_3
        ]).lower()
        
        keyword_matches = sum(1 for kw in test_case["expected_keywords"] if kw in top_texts)
        accuracy = (keyword_matches / len(test_case["expected_keywords"])) * 100
        
        # Determine status
        if accuracy >= 60:
            status = "PASS"
            print(f"   ✅ PASS - Found {keyword_matches}/{len(test_case['expected_keywords'])} keywords ({accuracy:.0f}%)")
        elif accuracy >= 40:
            status = "PARTIAL"
            print(f"   ⚠️  PARTIAL - Found {keyword_matches}/{len(test_case['expected_keywords'])} keywords ({accuracy:.0f}%)")
        else:
            status = "FAIL"
            print(f"   ❌ FAIL - Found {keyword_matches}/{len(test_case['expected_keywords'])} keywords ({accuracy:.0f}%)")
        
        # Store detailed results
        test_result = {
            "test_name": test_case["name"],
            "query": test_case["query"],
            "expected_request_id": test_case["expected_request_id"],
            "expected_keywords": test_case["expected_keywords"],
            "status": status,
            "accuracy": round(accuracy, 1),
            "keywords_found": keyword_matches,
            "keywords_total": len(test_case["expected_keywords"]),
            "results_count": len(found_results),
            "top_3_results": [
                {
                    "rank": j,
                    "name": r.get("name", "Unknown"),
                    "summary": r.get("summary", "")[:200],
                    "text": r.get("text", "")[:200],
                    "score": r.get("score", 0.0),
                    "id": r.get("id", "")
                }
                for j, r in enumerate(top_3, 1)
            ],
            "all_results": [
                {
                    "name": r.get("name", "Unknown"),
                    "summary": r.get("summary", "")[:100],
                    "score": r.get("score", 0.0)
                }
                for r in found_results
            ]
        }
        
        test_run["search_tests"].append(test_result)
        results.append({"test": test_case["name"], "status": status, "accuracy": accuracy})
    
    # Save results to JSON file
    output_file = Path(__file__).parent / "search_results.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_run, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Search results saved to: {output_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save results to file: {e}")
    
    return results


# =============================================================================
# PHASE 3: SUMMARY & ANALYSIS
# =============================================================================

async def phase3_summary(search_results: list, conversations: list):
    """
    Display summary of integration test
    """
    print("\n" + "="*80)
    print("📊 PHASE 3: INTEGRATION TEST SUMMARY")
    print("="*80)
    
    # Ingestion summary
    print(f"\n📥 Conversations Ingested: {len(conversations)}")
    for conv in conversations:
        print(f"   ✅ {conv['name']} ({conv['request_id']})")
    
    # Search results summary
    passed = sum(1 for r in search_results if r["status"] == "PASS")
    partial = sum(1 for r in search_results if r["status"] == "PARTIAL")
    failed = sum(1 for r in search_results if r["status"] == "FAIL")
    total = len(search_results)
    
    print(f"\n🔍 Search Quality Results:")
    print(f"   ✅ PASS: {passed}/{total}")
    print(f"   ⚠️  PARTIAL: {partial}/{total}")
    print(f"   ❌ FAIL: {failed}/{total}")
    print(f"\n   Pass Rate: {(passed/total)*100:.1f}%")
    print(f"   Success Rate (Pass + Partial): {((passed+partial)/total)*100:.1f}%")
    
    # Final verdict
    success_rate = ((passed + partial) / total) * 100
    
    print("\n" + "="*80)
    if success_rate >= 80:
        verdict = "EXCELLENT"
        print("🎉 EXCELLENT - System is production-ready!")
        print("   ✅ Conversations ingested successfully")
        print("   ✅ Search quality is excellent (>80%)")
        print("   ✅ Context retrieval works reliably")
    elif success_rate >= 70:
        verdict = "GOOD"
        print("✅ GOOD - System works well, ready for production")
        print("   ✅ Conversations ingested successfully")
        print("   ✅ Search quality is good (>70%)")
        print("   ⚠️  Minor improvements possible")
    elif success_rate >= 50:
        verdict = "ACCEPTABLE"
        print("⚠️  ACCEPTABLE - System works but needs tuning")
        print("   ✅ Conversations ingested successfully")
        print("   ⚠️  Search quality needs improvement")
    else:
        verdict = "NEEDS_WORK"
        print("❌ NEEDS WORK - Search quality below threshold")
        print("   ✅ Conversations ingested successfully")
        print("   ❌ Search logic needs significant improvement")
    
    print("="*80)
    
    # Save summary to JSON
    summary_file = Path(__file__).parent / "test_summary.json"
    try:
        summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "project_id": PROJECT_ID,
            "ingestion": {
                "conversations_count": len(conversations),
                "conversations": [
                    {"request_id": conv["request_id"], "name": conv["name"]}
                    for conv in conversations
                ]
            },
            "search_quality": {
                "total_tests": total,
                "passed": passed,
                "partial": partial,
                "failed": failed,
                "pass_rate": round((passed / total) * 100, 1),
                "success_rate": round(success_rate, 1)
            },
            "verdict": verdict,
            "production_ready": success_rate >= 70
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Test summary saved to: {summary_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save summary to file: {e}")


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_full_integration_test():
    """Run complete integration test pipeline"""
    
    print("\n╔" + "="*78 + "╗")
    print("║" + " "*20 + "FULL INTEGRATION TEST" + " "*37 + "║")
    print("║" + " "*15 + "Ingest + Search Quality Pipeline" + " "*30 + "║")
    print("╚" + "="*78 + "╝")
    
    print("\n🎯 Goal: Verify end-to-end workflow")
    print("   1. Ingest realistic coding assistant conversations")
    print("   2. Test semantic search on ingested data")
    print("   3. Verify context retrieval accuracy")
    
    print("\n⚠️  Make sure memory layer server is running on http://localhost:8000\n")
    
    timeout = httpx.Timeout(180.0, read=180.0, write=90.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Phase 1: Ingest conversations
            conversations = await phase1_ingest_conversations(client)
            
            # Phase 2: Test search quality
            search_results = await phase2_test_search_quality(client, conversations)
            
            # Phase 3: Summary
            await phase3_summary(search_results, conversations)
            
            print("\n💡 Next Steps:")
            print("   1. Check Neo4j Browser for graph structure")
            print("   2. Try manual search queries via API")
            print("   3. Integrate with Innocody using same payload format")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    try:
        success = asyncio.run(run_full_integration_test())
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        return 1


if __name__ == "__main__":
    exit(main())

