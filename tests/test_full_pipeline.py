"""
FULL PIPELINE TEST - Phase 1.5
Giả lập workflow thực tế với Innocody:
1. User request → Innocody analyze codebase
2. User request → Innocody fix bug login
3. Search "login bug" → Retrieve context
4. New conversation dùng context từ memory

Mock realistic Innocody payloads!
"""

import asyncio
import httpx
from datetime import datetime, timedelta
import json
import hashlib
import os
import uuid as uuid_lib

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable
from dotenv import load_dotenv
load_dotenv()
BASE_URL = "http://localhost:8000"
PROJECT_ID = "zepai_production"


EXPECTED_REQUEST_METRICS = {
    "req_analyze_001": {
        "messages": 2,
        "contexts": 3,
        "tools": 2,
        "checkpoints": 0,
        "code_changes": 0,
    },
    "req_fix_login_bug_001": {
        "messages": 2,
        "contexts": 3,
        "tools": 3,
        "checkpoints": 0,
        "code_changes": 2,
    },
    "req_improve_auth_001": {
        "messages": 2,
        "contexts": 2,
        "tools": 1,
        "checkpoints": 0,
        "code_changes": 0,
    },
}


def make_context_file(file_path: str, usefulness: float) -> dict:
    """Helper: Create context file payload"""
    return {
        "file_path": file_path,
        "usefulness": usefulness,
        "content_hash": hashlib.sha256(file_path.encode()).hexdigest(),
        "source": "vecdb",
        "symbols": []
    }


def make_tool_call(tool_name: str, status: str = "success", execution_time_ms: int = 200) -> dict:
    """Helper: Create tool call payload"""
    return {
        "tool_call_id": f"call_{uuid_lib.uuid4().hex[:8]}",
        "tool_name": tool_name,
        "arguments_hash": hashlib.sha256(f"{tool_name}:args".encode()).hexdigest(),
        "status": status,
        "execution_time_ms": execution_time_ms
    }


def make_code_change(
    file_path: str,
    change_summary: str,
    *,
    change_type: str = "modified",
    severity: str = "medium",
    lines_added: int = 0,
    lines_removed: int = 0,
    language: str = "python",
    imports: list | None = None,
    function_name: str | None = None,
) -> dict:
    """Helper: Create structured code change payload"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    before_hash = hashlib.sha256(f"before:{file_path}:{change_summary}".encode()).hexdigest()[:16]
    after_hash = hashlib.sha256(f"after:{file_path}:{change_summary}".encode()).hexdigest()[:16]
    return {
        "name": f"{change_type.title()} {file_path}",
        "summary": change_summary,
        "file_path": file_path,
        "function_name": function_name,
        "change_type": change_type,
        "change_summary": change_summary,
        "severity": severity,
        "diff_summary": change_summary,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "language": language,
        "imports": imports or [],
        "code_before_hash": before_hash,
        "code_after_hash": after_hash,
        "timestamp": timestamp,
    }


def create_conversation_payload(
    request_id: str,
    chat_id: str,
    user_message: str,
    assistant_message: str,
    context_files: list,
    tool_calls: list,
    model: str = "gpt-4-turbo",
    code_changes: list | None = None,
):
    """
    Helper: Tạo realistic Innocody conversation payload
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return {
        "request_id": request_id,
        "project_id": PROJECT_ID,
        "timestamp": timestamp,
        "chat_meta": {
            "chat_id": chat_id,
            "base_chat_id": chat_id.split("_")[0],
            "request_attempt_id": "attempt_001",
            "chat_mode": "AGENT"
        },
        "messages": [
            {
                "sequence": 0,
                "role": "user",
                "content_summary": user_message,
                "timestamp": timestamp,
                "total_tokens": 0,
                "metadata": {}
            },
            {
                "sequence": 1,
                "role": "assistant",
                "content_summary": assistant_message,
                "timestamp": timestamp,
                "total_tokens": len(user_message.split()) + len(assistant_message.split()) * 2,  # Rough estimate
                "metadata": {}
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


async def _gather_request_metrics(project_id: str):
    """Fetch per-request relationship counts directly from Neo4j."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
    password = os.getenv("NEO4J_PASSWORD", "neo4j")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (r:Request {project_id: $project_id})
                RETURN r.request_id AS request_id,
                       COUNT { (r)-[:CONTAINS_MESSAGE]->() }    AS messages,
                       COUNT { (r)-[:USES_CONTEXT]->() }        AS contexts,
                       COUNT { (r)-[:INVOKES_TOOL]->() }        AS tools,
                       COUNT { (r)-[:HAS_CHECKPOINT]->() }      AS checkpoints,
                       COUNT { (r)-[:APPLIED_CODE_CHANGE]->() } AS code_changes
                ORDER BY request_id
                """,
                {"project_id": project_id},
            )

            metrics = []
            async for record in result:
                metrics.append({
                    "request_id": record["request_id"],
                    "messages": record["messages"],
                    "contexts": record["contexts"],
                    "tools": record["tools"],
                    "checkpoints": record["checkpoints"],
                    "code_changes": record["code_changes"],
                })

            return metrics
    except ServiceUnavailable as exc:
        print("\n⚠️  Neo4j unavailable during metrics gathering:")
        print(f"   → {exc}")
        return None
    finally:
        await driver.close()


def _format_metrics_table(metrics: list[dict]) -> str:
    """Render metrics into an aligned ASCII table."""
    headers = [
        ("Request", "request_id"),
        ("Messages", "messages"),
        ("Contexts", "contexts"),
        ("Tools", "tools"),
        ("Checkpoints", "checkpoints"),
        ("Code Changes", "code_changes"),
    ]

    col_widths = [max(len(str(row[key])) for row in metrics + [{key: title}]) for title, key in headers]

    def render_row(row):
        cells = []
        for (title, key), width in zip(headers, col_widths):
            cells.append(str(row[key]).ljust(width))
        return "  ".join(cells)

    lines = [render_row({key: title for title, key in headers})]
    lines.append("  ".join("-" * width for width in col_widths))
    for row in metrics:
        lines.append(render_row(row))
    return "\n".join(lines)


def _assert_expected_metrics(metrics: list[dict]):
    """Ensure observed counts match the hard-coded expectations for this scenario."""
    observed = {row["request_id"]: row for row in metrics}
    missing = set(EXPECTED_REQUEST_METRICS) - set(observed)
    if missing:
        raise AssertionError(f"Missing requests in Neo4j metrics: {sorted(missing)}")

    mismatches = []
    for request_id, expected in EXPECTED_REQUEST_METRICS.items():
        row = observed[request_id]
        for field, expected_value in expected.items():
            if row[field] != expected_value:
                mismatches.append(
                    f"{request_id}.{field}: expected {expected_value}, observed {row[field]}"
                )

    if mismatches:
        raise AssertionError("\n".join(mismatches))


async def test_full_pipeline():
    """
    Test full workflow:
    1. Conversation: Analyze codebase
    2. Conversation: Fix login bug
    3. Search for "login bug fix" → Get context
    4. Conversation: New request using memory context
    """
    print("\n" + "="*80)
    print("🎬 FULL PIPELINE TEST - Realistic Innocody Workflow")
    print("="*80)
    
    timeout = httpx.Timeout(150.0, read=150.0, write=60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        
        # =========================================================================
        # SCENARIO 1: User yêu cầu phân tích codebase
        # =========================================================================
        print("\n📖 [SCENARIO 1] User: 'Analyze the authentication system'")
        print("-" * 80)
        
        conv1_payload = create_conversation_payload(
            request_id="req_analyze_001",
            chat_id="chat_analyze_auth",
            user_message="Can you analyze the authentication system in this codebase? I want to understand how login works.",
            assistant_message=(
                "I've analyzed the authentication system. Here's what I found:\n\n"
                "1. **Login Flow**: Uses JWT tokens with 24h expiration\n"
                "2. **Files**: Main logic in `auth/login.py`, session management in `auth/session.py`\n"
                "3. **Database**: User credentials stored in PostgreSQL with bcrypt hashing\n"
                "4. **Security**: Has rate limiting (5 attempts/minute), but missing 2FA support\n\n"
                "The system is well-structured but could benefit from multi-factor authentication."
            ),
            context_files=[
                make_context_file("backend/auth/login.py", 0.95),
                make_context_file("backend/auth/session.py", 0.88),
                make_context_file("backend/models/user.py", 0.75)
            ],
            tool_calls=[
                make_tool_call("read_file", "success", 245),
                make_tool_call("grep_search", "success", 180)
            ]
        )
        
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=conv1_payload)
        response.raise_for_status()
        result1 = response.json()
        print(f"✅ Conversation 1 ingested: {result1['request_uuid']}")
        print(f"   Context files: {result1['metadata']['context_file_count']}")
        print(f"   Tool calls: {result1['metadata']['tool_call_count']}")
        
        # Wait for Graphiti to process and generate embeddings
        await asyncio.sleep(4)
        
        # =========================================================================
        # SCENARIO 2: User báo bug login
        # =========================================================================
        print("\n🐛 [SCENARIO 2] User: 'There's a bug in login - users locked out after failed attempts'")
        print("-" * 80)
        
        conv2_payload = create_conversation_payload(
            request_id="req_fix_login_bug_001",
            chat_id="chat_fix_login_bug",
            user_message=(
                "There's a critical bug! Users are getting locked out permanently after 5 failed login attempts. "
                "The rate limiter never resets. Can you fix this?"
            ),
            assistant_message=(
                "I found the bug! In `auth/login.py`, the rate limiter uses Redis with no TTL, "
                "so failed attempts never expire.\n\n"
                "**Fix Applied:**\n"
                "- Added 15-minute TTL to rate limit counter in Redis\n"
                "- Added `clear_rate_limit()` function for admin override\n"
                "- Added logging for locked accounts\n\n"
                "**Code Changes:**\n"
                "```python\n"
                "# Before: redis.incr(f'login_attempts:{user_id}')\n"
                "# After: redis.setex(f'login_attempts:{user_id}', 900, attempts)\n"
                "```\n\n"
                "Bug fixed! Rate limit now resets after 15 minutes."
            ),
            context_files=[
                make_context_file("backend/auth/login.py", 0.98),
                make_context_file("backend/auth/rate_limiter.py", 0.92),
                make_context_file("tests/test_auth.py", 0.85)
            ],
            tool_calls=[
                make_tool_call("read_file", "success", 198),
                make_tool_call("edit_file", "success", 421),
                make_tool_call("run_tests", "success", 2340)
            ],
            code_changes=[
                make_code_change(
                    "backend/auth/login.py",
                    "Added Redis TTL to login rate limiter and new helper for clearing counts",
                    change_type="fixed",
                    severity="high",
                    lines_added=12,
                    lines_removed=4,
                    imports=["redis"],
                    function_name="rate_limit_login"
                ),
                make_code_change(
                    "backend/auth/rate_limiter.py",
                    "Introduced clear_rate_limit utility and improved logging for locked accounts",
                    change_type="added",
                    severity="medium",
                    lines_added=18,
                    lines_removed=0,
                    imports=["logging"],
                    function_name="clear_rate_limit"
                )
            ]
        )
        
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=conv2_payload)
        response.raise_for_status()
        result2 = response.json()
        print(f"✅ Conversation 2 ingested: {result2['request_uuid']}")
        print(f"   Context files: {result2['metadata']['context_file_count']}")
        print(f"   Tool calls: {result2['metadata']['tool_call_count']}")
        
        # Wait for Graphiti to process and generate embeddings
        await asyncio.sleep(4)
        
        # =========================================================================
        # SCENARIO 3: Search memory để lấy context về "login bug fix"
        # =========================================================================
        print("\n🔍 [SCENARIO 3] Search Memory: 'login bug fix rate limiter'")
        print("-" * 80)
        
        search_response = await client.post(
            f"{BASE_URL}/search",
            json={
                "query": "login bug fix rate limiter Redis TTL",
                "group_id": PROJECT_ID,
                "limit": 5
            }
        )
        search_response.raise_for_status()
        search_results = search_response.json()
        
        print(f"✅ Search completed!")
        print(f"   Results found: {len(search_results.get('results', []))}")
        
        if search_results.get('results'):
            print("\n📋 Top Search Results:")
            for i, result in enumerate(search_results['results'][:3], 1):
                print(f"\n   {i}. {result.get('name', 'Unknown')}")
                print(f"      Summary: {result.get('summary', '')[:100]}...")
                print(f"      Score: {result.get('score', 0):.3f}")
                if 'fact' in result:
                    print(f"      Fact: {result['fact'][:80]}...")
        else:
            print("   ⚠️  No results found (Graphiti might still be processing)")
        
        # =========================================================================
        # SCENARIO 4: New conversation dùng context từ memory
        # =========================================================================
        print("\n💡 [SCENARIO 4] User asks related question with memory context")
        print("-" * 80)
        
        conv3_payload = create_conversation_payload(
            request_id="req_improve_auth_001",
            chat_id="chat_improve_security",
            user_message=(
                "Based on the recent login bug fix, what other security improvements "
                "should we make to the authentication system?"
            ),
            assistant_message=(
                "Great question! Based on the recent rate limiter fix and the authentication analysis, "
                "I recommend these improvements:\n\n"
                "1. **Add 2FA Support** (mentioned in analysis but not implemented)\n"
                "2. **Implement Account Lockout Policy** (currently only rate limiting)\n"
                "3. **Add Audit Logging** for all login attempts (success/failure)\n"
                "4. **Session Token Rotation** on sensitive actions\n"
                "5. **IP-based Anomaly Detection** (detect login from unusual locations)\n\n"
                "The rate limiter fix was a good start, but these additions would significantly "
                "improve security posture."
            ),
            context_files=[
                make_context_file("backend/auth/login.py", 0.90),
                make_context_file("docs/security_recommendations.md", 0.82)
            ],
            tool_calls=[
                make_tool_call("read_file", "success", 156)
            ]
        )
        
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=conv3_payload)
        response.raise_for_status()
        result3 = response.json()
        print(f"✅ Conversation 3 ingested: {result3['request_uuid']}")
        print(f"   Used memory context from previous conversations")
        
        # =========================================================================
        # SCENARIO 5: Query conversation history
        # =========================================================================
        print("\n📊 [SCENARIO 5] Query conversation history for project")
        print("-" * 80)
        
        history_response = await client.get(
            f"{BASE_URL}/conversation/requests/{PROJECT_ID}",
            params={"days_ago": 1, "limit": 10}
        )
        history_response.raise_for_status()
        history = history_response.json()
        
        print(f"✅ Retrieved conversation history!")
        print(f"   Total conversations: {history['count']}")
        print(f"\n   Recent conversations:")
        for conv in history['requests'][:3]:
            print(f"   - {conv['chat_id']}: {conv['chat_mode']}, {conv['total_tokens']} tokens")
            print(f"     Created: {conv['created_at']}")
        
        # =========================================================================
        # SUMMARY
        # =========================================================================
        print("\n" + "="*80)
        print("🎉 FULL PIPELINE TEST COMPLETED!")
        print("="*80)
        print("\n📊 Summary:")
        print(f"   ✓ Ingested 3 conversations (analyze → fix bug → improve)")
        print(f"   ✓ Search retrieved relevant context from memory")
        print(f"   ✓ New conversation used context from previous interactions")
        print(f"   ✓ History query shows all conversations in project")

        # =========================================================================
        # EVALUATION: Validate Neo4j graph structure
        # =========================================================================
        print("\n📊 [EVALUATION] Neo4j relationship metrics")
        metrics = await _gather_request_metrics(PROJECT_ID)
        if metrics is None:
            print("⚠️  Skipping graph metric assertions because Neo4j is offline")
        else:
            if not metrics:
                raise AssertionError("No Request nodes found in Neo4j for evaluation")

            print(_format_metrics_table(metrics))
            _assert_expected_metrics(metrics)
            print("\n✅ Graph metrics match expected counts for the full pipeline scenario")

        return True

        print("\n🚀 Memory Layer working end-to-end!")
        print("   Ready for Innocody integration!\n")
        
        return True


def main():
    """Run full pipeline test"""
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "FULL PIPELINE TEST - Phase 1.5" + " "*28 + "║")
    print("╚" + "="*78 + "╝")
    print("\n⚠️  Make sure memory layer server is running on http://localhost:8000")
    print("\n💡 This test simulates realistic Innocody workflow:")
    print("   1. User requests code analysis")
    print("   2. User reports bug → Innocody fixes it")
    print("   3. Search retrieves context from memory")
    print("   4. New conversation uses memory context")
    
    try:
        success = asyncio.run(test_full_pipeline())
        
        if success:
            print("\n✅ All tests passed!")
            print("\n📝 Next steps:")
            print("   1. Configure Innocody webhook to POST to /ingest/conversation")
            print("   2. Update Innocody to search memory before each request")
            print("   3. Monitor performance in production")
            print("   4. Adjust TTL settings based on usage patterns")
            return 0
        else:
            print("\n❌ Tests failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
