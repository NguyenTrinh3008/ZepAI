"""
REALISTIC INNOCODY SCENARIOS - Extended Test Cases
Mô phỏng các workflow thực tế khi user dùng AI coding assistant
WITH LANGFUSE TRACING INTEGRATION
"""

import asyncio
import httpx
from datetime import datetime
import hashlib
import uuid as uuid_lib
import logging

from dotenv import load_dotenv
load_dotenv()

# Import tracing helpers
from test_tracing_helpers import (
    init_test_session, trace_test_scenario, trace_conversation_ingest,
    trace_error, flush_test_traces, log_test_summary
)

BASE_URL = "http://localhost:8000"
PROJECT_ID = "innocody_test_project"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS (reuse from test_full_pipeline.py)
# =============================================================================

def make_context_file(file_path: str, usefulness: float, source: str = "vecdb", symbols: list = None) -> dict:
    """Helper: Create context file payload"""
    return {
        "file_path": file_path,
        "usefulness": usefulness,
        "content_hash": hashlib.sha256(file_path.encode()).hexdigest(),
        "source": source,
        "symbols": symbols or [],
        "language": _detect_language(file_path)
    }


def _detect_language(file_path: str) -> str:
    """Detect language from file extension"""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
    }
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    return 'unknown'


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
    imports: list = None,
    function_name: str = None,
) -> dict:
    """Helper: Create code change payload"""
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
        "language": language or _detect_language(file_path),
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
    model: str = "gpt-4o-mini",
    code_changes: list = None,
):
    """Helper: Tạo realistic Innocody conversation payload"""
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
# SCENARIO 1: REFACTORING - User refactors async/await
# =============================================================================

async def scenario_refactoring_async(client: httpx.AsyncClient):
    """
    User: "Convert get_user_data() to async/await pattern"
    Assistant: Refactors from sync to async, updates all callers
    """
    with trace_test_scenario("Refactoring - Convert to async/await", "refactoring"):
        print("\n" + "="*80)
        print("[SCENARIO 1] REFACTORING - Convert to async/await")
        print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_refactor_async_001",
        chat_id="chat_refactor_async",
        user_message=(
            "Can you refactor the get_user_data() function in database/users.py to use async/await? "
            "It's currently blocking and causing performance issues."
        ),
        assistant_message=(
            "I've refactored get_user_data() to async/await pattern:\n\n"
            "**Changes Made:**\n"
            "1. Converted `get_user_data()` → `async def get_user_data()`\n"
            "2. Updated database connection to use `asyncpg` instead of `psycopg2`\n"
            "3. Added `await` to all DB queries\n"
            "4. Updated 3 callers: `api/users.py`, `services/auth.py`, `tasks/sync.py`\n\n"
            "**Performance Improvement:**\n"
            "- Response time: 450ms → 85ms (81% faster)\n"
            "- Can now handle 10x concurrent requests\n\n"
            "**Code Example:**\n"
            "```python\n"
            "# Before: user = get_user_data(user_id)\n"
            "# After:  user = await get_user_data(user_id)\n"
            "```\n\n"
            "All tests passing ✅"
        ),
        context_files=[
            make_context_file("database/users.py", 0.98, "vecdb", ["get_user_data", "UserModel"]),
            make_context_file("database/connection.py", 0.92, "ast", ["get_db_connection"]),
            make_context_file("api/users.py", 0.85, "ast", ["get_user_endpoint"]),
            make_context_file("services/auth.py", 0.78, "vecdb", ["validate_user"]),
            make_context_file("tests/test_database.py", 0.70, "ast", ["test_get_user_data"])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 245),
            make_tool_call("grep_search", "success", 380),  # Find all callers
            make_tool_call("edit_file", "success", 520),
            make_tool_call("edit_file", "success", 312),  # Update callers
            make_tool_call("edit_file", "success", 289),
            make_tool_call("run_tests", "success", 3450)
        ],
        code_changes=[
            make_code_change(
                "database/users.py",
                "Converted get_user_data() from synchronous to async/await pattern using asyncpg",
                change_type="refactored",
                severity="medium",
                lines_added=8,
                lines_removed=6,
                imports=["asyncpg", "asyncio"],
                function_name="get_user_data"
            ),
            make_code_change(
                "api/users.py",
                "Updated get_user_endpoint to await async get_user_data() call",
                change_type="modified",
                severity="low",
                lines_added=2,
                lines_removed=1,
                function_name="get_user_endpoint"
            ),
            make_code_change(
                "services/auth.py",
                "Updated validate_user to await async get_user_data()",
                change_type="modified",
                severity="low",
                lines_added=1,
                lines_removed=1,
                function_name="validate_user"
            )
        ]
    )
    
    with trace_conversation_ingest("refactoring", "req_refactor_async_001"):
        response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"[OK] Refactoring conversation ingested: {result['request_uuid']}")
        print(f"   Code changes: 3 files modified")
        print(f"   Tools used: {result['metadata']['tool_call_count']}")


# =============================================================================
# SCENARIO 2: BUG INVESTIGATION - User reports stack trace
# =============================================================================

async def scenario_bug_investigation(client: httpx.AsyncClient):
    """
    User: Pastes stack trace of KeyError
    Assistant: Investigates, finds root cause, fixes defensive programming
    """
    with trace_test_scenario('Bug Investigation - Stack trace debugging', 'bug_fix'):
        print("\n" + "="*80)
        print("[SCENARIO 2] BUG INVESTIGATION - Stack trace debugging")
        print("="*80)
        
        payload = create_conversation_payload(
            request_id="req_bug_keyerror_001",
            chat_id="chat_debug_keyerror",
            user_message=(
                "I'm getting this error in production:\n\n"
                "```\n"
                "KeyError: 'user_preferences'\n"
                "File 'api/profile.py', line 67, in get_profile\n"
                "  theme = user_data['user_preferences']['theme']\n"
                "```\n\n"
                "It's happening randomly for some users. Can you help debug this?"
            ),
            assistant_message=(
                "Found the issue! The KeyError occurs when users haven't set preferences yet.\n\n"
                "**Root Cause:**\n"
                "- New users don't have `user_preferences` key in their data\n"
                "- Code assumes all users have preferences without checking\n\n"
                "**Investigation Steps:**\n"
                "1. Checked database schema → `user_preferences` is nullable\n"
                "2. Found 847 users without preferences (12% of user base)\n"
                "3. Code doesn't handle this edge case\n\n"
                "**Fix Applied:**\n"
                "```python\n"
                "# Before:\n"
                "theme = user_data['user_preferences']['theme']\n\n"
                "# After:\n"
                "preferences = user_data.get('user_preferences', {})\n"
                "theme = preferences.get('theme', 'default')\n"
                "```\n\n"
                "**Additional Improvements:**\n"
                "- Added default preferences initialization for new users\n"
                "- Added migration script for existing users\n"
                "- Added test for users without preferences\n\n"
                "Error should be resolved ✅"
            ),
            context_files=[
                make_context_file("api/profile.py", 0.96, "vecdb", ["get_profile", "update_profile"]),
                make_context_file("models/user.py", 0.91, "ast", ["UserModel", "UserPreferences"]),
                make_context_file("database/migrations/004_add_preferences.sql", 0.82, "vecdb", []),
                make_context_file("tests/test_profile.py", 0.75, "ast", ["test_get_profile"])
            ],
            tool_calls=[
                make_tool_call("read_file", "success", 189),
                make_tool_call("grep_search", "success", 245),  # Search for user_preferences usage
                make_tool_call("run_query", "success", 1250),  # Database query to check users
                make_tool_call("edit_file", "success", 412),
                make_tool_call("edit_file", "success", 234),  # Add test
                make_tool_call("run_tests", "success", 2890)
            ],
            code_changes=[
                make_code_change(
                    "api/profile.py",
                    "Added defensive programming for missing user_preferences with default fallback",
                    change_type="fixed",
                    severity="high",
                    lines_added=5,
                    lines_removed=2,
                    imports=["typing"],
                    function_name="get_profile"
                ),
                make_code_change(
                    "tests/test_profile.py",
                    "Added test case for users without preferences to prevent regression",
                    change_type="added",
                    severity="low",
                    lines_added=12,
                    lines_removed=0,
                    function_name="test_profile_without_preferences"
                )
            ]
        )
    
        with trace_conversation_ingest("bug_investigation", "req_bug_keyerror_001"):
            response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
            response.raise_for_status()
            result = response.json()
            print(f"[OK] Bug investigation ingested: {result['request_uuid']}")
            print(f"   Fixed: KeyError in production")
            print(f"   Severity: HIGH")


# =============================================================================
# SCENARIO 3: NEW FEATURE - Add API endpoint with validation
# =============================================================================

async def scenario_new_feature(client: httpx.AsyncClient):
    """
    User: "Add endpoint to upload profile pictures"
    Assistant: Creates endpoint with validation, storage, tests
    """
    print("\n" + "="*80)
    print("[SCENARIO 3] NEW FEATURE - Add profile picture upload")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_feature_upload_001",
        chat_id="chat_feature_upload",
        user_message=(
            "I need to add a feature for users to upload profile pictures. "
            "It should validate file type (only jpg/png), size (max 5MB), "
            "and store in S3. Can you implement this?"
        ),
        assistant_message=(
            "I've implemented the profile picture upload feature! Here's what I created:\n\n"
            "**New Components:**\n"
            "1. `POST /api/users/{user_id}/profile-picture` endpoint\n"
            "2. File validation middleware (type, size, dimensions)\n"
            "3. S3 upload service with presigned URLs\n"
            "4. Image processing (resize to 512x512, optimize)\n"
            "5. Database schema update for profile_picture_url\n\n"
            "**Validation Rules:**\n"
            "- File types: JPG, PNG only\n"
            "- Max size: 5MB\n"
            "- Min dimensions: 200x200px\n"
            "- Max dimensions: 4096x4096px\n\n"
            "**Security Features:**\n"
            "- Content-Type validation\n"
            "- Magic byte checking (prevents fake extensions)\n"
            "- Virus scanning (ClamAV integration)\n"
            "- Rate limiting: 3 uploads per hour\n\n"
            "**Storage:**\n"
            "- S3 bucket: `user-profiles-prod`\n"
            "- Path: `{user_id}/profile/{timestamp}.jpg`\n"
            "- CloudFront CDN enabled\n\n"
            "**Tests Added:**\n"
            "- Valid upload ✅\n"
            "- Invalid file type ✅\n"
            "- File too large ✅\n"
            "- Image too small ✅\n"
            "- Unauthorized upload ✅\n\n"
            "Feature complete and tested!"
        ),
        context_files=[
            make_context_file("api/users.py", 0.94, "vecdb", ["UserAPI", "get_user", "update_user"]),
            make_context_file("services/storage.py", 0.89, "vecdb", ["S3Service", "upload_file"]),
            make_context_file("middleware/validation.py", 0.82, "ast", ["validate_file"]),
            make_context_file("config/settings.py", 0.75, "vecdb", ["AWS_CONFIG"]),
            make_context_file("tests/test_uploads.py", 0.70, "ast", [])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 298),
            make_tool_call("read_file", "success", 245),
            make_tool_call("create_file", "success", 580),  # New endpoint
            make_tool_call("edit_file", "success", 420),  # Add validation
            make_tool_call("create_file", "success", 890),  # Tests
            make_tool_call("run_tests", "success", 4200),
            make_tool_call("run_command", "success", 1200)  # Database migration
        ],
        code_changes=[
            make_code_change(
                "api/users.py",
                "Added POST /users/{user_id}/profile-picture endpoint with multipart file upload",
                change_type="added",
                severity="low",
                lines_added=45,
                lines_removed=0,
                imports=["fastapi.UploadFile", "services.storage"],
                function_name="upload_profile_picture"
            ),
            make_code_change(
                "middleware/validation.py",
                "Added file validation middleware for image uploads with type, size, dimension checks",
                change_type="added",
                severity="medium",
                lines_added=67,
                lines_removed=0,
                imports=["PIL", "magic"],
                function_name="validate_image_upload"
            ),
            make_code_change(
                "services/storage.py",
                "Enhanced S3Service with image processing (resize, optimize) before upload",
                change_type="modified",
                severity="low",
                lines_added=34,
                lines_removed=5,
                imports=["PIL.Image", "boto3"],
                function_name="upload_profile_picture"
            ),
            make_code_change(
                "tests/test_uploads.py",
                "Created comprehensive test suite for profile picture upload feature",
                change_type="added",
                severity="low",
                lines_added=125,
                lines_removed=0,
                imports=["pytest", "io", "PIL"]
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"[OK] New feature ingested: {result['request_uuid']}")
    print(f"   Added: Profile picture upload endpoint")
    print(f"   Files created: 2, Files modified: 2")


# =============================================================================
# SCENARIO 4: CODE REVIEW - User asks for review
# =============================================================================

async def scenario_code_review(client: httpx.AsyncClient):
    """
    User: "Can you review my payment processing code?"
    Assistant: Reviews for security, performance, best practices
    """
    print("\n" + "="*80)
    print("[SCENARIO 4] CODE REVIEW - Payment processing security")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_review_payment_001",
        chat_id="chat_review_payment",
        user_message=(
            "I just finished implementing the payment processing module. "
            "Can you review payment/processor.py for security issues and best practices?"
        ),
        assistant_message=(
            "I've reviewed your payment processing code. Here's my analysis:\n\n"
            "**🔴 Critical Issues Found:**\n\n"
            "1. **API Key Exposure** (Line 23)\n"
            "   - Stripe key hardcoded in source\n"
            "   - **Fix:** Move to environment variable\n\n"
            "2. **Missing Input Validation** (Line 67)\n"
            "   - Amount not validated (could be negative!)\n"
            "   - **Fix:** Add amount > 0 check\n\n"
            "3. **No Idempotency Key** (Line 89)\n"
            "   - Duplicate charges possible on retry\n"
            "   - **Fix:** Generate and use idempotency key\n\n"
            "**🟡 Warnings:**\n\n"
            "4. **Error Messages Too Detailed** (Line 145)\n"
            "   - Exposing internal error details to users\n"
            "   - **Fix:** Generic error messages, log details server-side\n\n"
            "5. **Missing Audit Logging** (Throughout)\n"
            "   - No logging of payment attempts\n"
            "   - **Fix:** Add structured logging for compliance\n\n"
            "6. **Synchronous Processing** (Line 112)\n"
            "   - Blocks request during Stripe API call\n"
            "   - **Fix:** Use async/await or background jobs\n\n"
            "**✅ Good Practices Found:**\n"
            "- ✅ Using try-except for error handling\n"
            "- ✅ Transaction rollback on failure\n"
            "- ✅ Proper type hints\n\n"
            "**Recommended Priority:**\n"
            "1. Fix API key exposure (CRITICAL)\n"
            "2. Add input validation (CRITICAL)\n"
            "3. Implement idempotency (HIGH)\n"
            "4. Add audit logging (MEDIUM)\n\n"
            "I can apply these fixes if you'd like. Shall I proceed?"
        ),
        context_files=[
            make_context_file("payment/processor.py", 0.98, "vecdb", ["process_payment", "validate_card"]),
            make_context_file("payment/models.py", 0.85, "ast", ["Payment", "PaymentStatus"]),
            make_context_file("config/settings.py", 0.79, "vecdb", ["STRIPE_CONFIG"]),
            make_context_file("docs/security_guidelines.md", 0.72, "vecdb", []),
            make_context_file("tests/test_payments.py", 0.68, "ast", [])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 450),
            make_tool_call("security_scan", "success", 2300),  # Static analysis
            make_tool_call("grep_search", "success", 380),  # Check for patterns
        ],
        code_changes=[]  # Review only, no changes yet
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"[OK] Code review ingested: {result['request_uuid']}")
    print(f"   Found: 3 critical, 3 warnings")
    print(f"   Recommendations: Security improvements")


# =============================================================================
# SCENARIO 5: PERFORMANCE OPTIMIZATION - Slow API endpoint
# =============================================================================

async def scenario_performance_optimization(client: httpx.AsyncClient):
    """
    User: "Why is /api/dashboard so slow?"
    Assistant: Profiles, finds N+1 queries, optimizes with caching
    """
    print("\n" + "="*80)
    print("[SCENARIO 5] PERFORMANCE OPTIMIZATION - N+1 query problem")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_perf_dashboard_001",
        chat_id="chat_perf_dashboard",
        user_message=(
            "The /api/dashboard endpoint is taking 8-12 seconds to load! "
            "Users are complaining. Can you figure out what's wrong and fix it?"
        ),
        assistant_message=(
            "Found the performance bottleneck! Classic N+1 query problem.\n\n"
            "**Problem Diagnosis:**\n"
            "- Dashboard loads 100 projects per user\n"
            "- For each project, makes separate query for:\n"
            "  * Team members (100 queries)\n"
            "  * Recent activity (100 queries)\n"
            "  * Task counts (100 queries)\n"
            "- Total: 301 database queries! (1 + 300)\n"
            "- Average query time: 30ms → 9,030ms total\n\n"
            "**Performance Before:**\n"
            "- Response time: 9.5s\n"
            "- Database load: 301 queries\n"
            "- Memory: 450MB\n\n"
            "**Optimizations Applied:**\n\n"
            "1. **Query Optimization:**\n"
            "   - Used `select_related()` for team members\n"
            "   - Used `prefetch_related()` for activities\n"
            "   - Added aggregation query for task counts\n"
            "   - Reduced: 301 queries → 4 queries ✅\n\n"
            "2. **Caching:**\n"
            "   - Added Redis cache for dashboard data (5min TTL)\n"
            "   - Cache key: `dashboard:{user_id}:{timestamp}`\n"
            "   - Hit rate expected: ~80%\n\n"
            "3. **Database Indexes:**\n"
            "   - Added index on projects.user_id\n"
            "   - Added composite index on (project_id, created_at)\n\n"
            "4. **Response Optimization:**\n"
            "   - Reduced payload size: 2.3MB → 450KB\n"
            "   - Removed unnecessary nested objects\n\n"
            "**Performance After:**\n"
            "- Response time: 350ms (96% faster!) 🚀\n"
            "- Database load: 4 queries\n"
            "- Memory: 120MB\n"
            "- With cache: 45ms\n\n"
            "Load testing shows system can now handle 10x traffic!"
        ),
        context_files=[
            make_context_file("api/dashboard.py", 0.97, "vecdb", ["get_dashboard", "DashboardResponse"]),
            make_context_file("database/queries.py", 0.93, "ast", ["get_user_projects", "get_project_stats"]),
            make_context_file("services/cache.py", 0.88, "vecdb", ["CacheService", "get_cached"]),
            make_context_file("models/project.py", 0.82, "ast", ["Project", "ProjectMember"]),
            make_context_file("tests/test_performance.py", 0.75, "ast", [])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 340),
            make_tool_call("profile_code", "success", 8500),  # Performance profiling
            make_tool_call("analyze_queries", "success", 1200),  # SQL analysis
            make_tool_call("edit_file", "success", 680),
            make_tool_call("edit_file", "success", 420),
            make_tool_call("run_migration", "success", 2100),  # Add indexes
            make_tool_call("run_tests", "success", 5200),
            make_tool_call("load_test", "success", 12000)  # Performance validation
        ],
        code_changes=[
            make_code_change(
                "api/dashboard.py",
                "Added Redis caching for dashboard data with 5-minute TTL to reduce DB load",
                change_type="modified",
                severity="medium",
                lines_added=15,
                lines_removed=3,
                imports=["services.cache", "redis"],
                function_name="get_dashboard"
            ),
            make_code_change(
                "database/queries.py",
                "Optimized get_user_projects with select_related and prefetch_related to eliminate N+1 queries",
                change_type="refactored",
                severity="high",
                lines_added=12,
                lines_removed=25,
                imports=["django.db.models"],
                function_name="get_user_projects"
            ),
            make_code_change(
                "database/migrations/007_add_indexes.sql",
                "Added database indexes on project queries for 10x faster dashboard loading",
                change_type="added",
                severity="medium",
                lines_added=8,
                lines_removed=0,
                language="sql"
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"[OK] Performance optimization ingested: {result['request_uuid']}")
    print(f"   Improvement: 9.5s -> 350ms (96% faster)")
    print(f"   Technique: N+1 query fix + caching")


# =============================================================================
# SCENARIO 6: DOCUMENTATION - Generate API docs
# =============================================================================

async def scenario_generate_docs(client: httpx.AsyncClient):
    """
    User: "Generate API documentation for auth endpoints"
    Assistant: Analyzes code, generates OpenAPI docs
    """
    print("\n" + "="*80)
    print("[SCENARIO 6] DOCUMENTATION - Generate API docs from code")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_docs_api_001",
        chat_id="chat_docs_generation",
        user_message=(
            "Can you generate comprehensive API documentation for all endpoints in api/auth.py? "
            "We need it in OpenAPI format for our developer portal."
        ),
        assistant_message=(
            "I've generated comprehensive API documentation! Here's what I created:\n\n"
            "**Documentation Created:**\n\n"
            "1. **OpenAPI Specification** (`docs/openapi/auth.yaml`)\n"
            "   - 8 endpoints documented\n"
            "   - Request/response schemas\n"
            "   - Authentication requirements\n"
            "   - Error responses\n\n"
            "2. **Code Examples** (`docs/examples/`)\n"
            "   - Python client examples\n"
            "   - cURL examples\n"
            "   - JavaScript/TypeScript examples\n\n"
            "3. **Inline Documentation**\n"
            "   - Added docstrings to all functions\n"
            "   - Added type hints\n"
            "   - Added example values in Pydantic models\n\n"
            "**Endpoints Documented:**\n"
            "- POST /auth/register - User registration\n"
            "- POST /auth/login - User login\n"
            "- POST /auth/logout - User logout\n"
            "- POST /auth/refresh - Token refresh\n"
            "- POST /auth/forgot-password - Password reset request\n"
            "- POST /auth/reset-password - Password reset confirm\n"
            "- GET /auth/verify-email - Email verification\n"
            "- POST /auth/resend-verification - Resend verification email\n\n"
            "**Documentation Quality:**\n"
            "- ✅ Request parameters explained\n"
            "- ✅ Response codes documented (200, 400, 401, 403, 500)\n"
            "- ✅ Example requests/responses\n"
            "- ✅ Authentication flow diagrams\n"
            "- ✅ Rate limiting documented\n"
            "- ✅ Error handling examples\n\n"
            "**Preview Available:**\n"
            "Run `npm run docs:serve` to view in Swagger UI"
        ),
        context_files=[
            make_context_file("api/auth.py", 0.98, "vecdb", ["register", "login", "logout", "refresh_token"]),
            make_context_file("models/user.py", 0.89, "ast", ["User", "UserCreate", "UserResponse"]),
            make_context_file("api/schemas.py", 0.85, "ast", ["LoginRequest", "TokenResponse"]),
            make_context_file("docs/openapi/base.yaml", 0.75, "vecdb", [])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 520),
            make_tool_call("read_file", "success", 340),
            make_tool_call("generate_openapi", "success", 3400),  # AI generates OpenAPI spec
            make_tool_call("create_file", "success", 890),
            make_tool_call("create_file", "success", 450),  # Examples
            make_tool_call("edit_file", "success", 620),  # Add docstrings
        ],
        code_changes=[
            make_code_change(
                "docs/openapi/auth.yaml",
                "Generated comprehensive OpenAPI 3.0 specification for all auth endpoints",
                change_type="added",
                severity="low",
                lines_added=342,
                lines_removed=0,
                language="yaml"
            ),
            make_code_change(
                "api/auth.py",
                "Enhanced with detailed docstrings and type hints for auto-documentation",
                change_type="modified",
                severity="low",
                lines_added=67,
                lines_removed=12,
                function_name="register"
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"[OK] Documentation generation ingested: {result['request_uuid']}")
    print(f"   Generated: OpenAPI spec + examples")
    print(f"   Endpoints: 8 auth endpoints")


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

async def run_all_scenarios():
    """Run all realistic scenarios sequentially with Langfuse tracing"""
    # Initialize test session
    session_id = init_test_session("realistic_scenarios")
    
    print("\n" + "="*80)
    print("REALISTIC INNOCODY SCENARIOS TEST")
    print("WITH LANGFUSE TRACING")
    print("="*80)
    print(f"Session ID: {session_id}")
    print("\nTesting 6 realistic coding assistant workflows")
    print("Make sure memory layer server is running on http://localhost:8000\n")
    
    timeout = httpx.Timeout(150.0, read=150.0, write=60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Run scenarios with delays for Graphiti processing
            await scenario_refactoring_async(client)
            await asyncio.sleep(3)
            
            await scenario_bug_investigation(client)
            await asyncio.sleep(3)
            
            await scenario_new_feature(client)
            await asyncio.sleep(3)
            
            await scenario_code_review(client)
            await asyncio.sleep(3)
            
            await scenario_performance_optimization(client)
            await asyncio.sleep(3)
            
            await scenario_generate_docs(client)
            await asyncio.sleep(2)
            
            # Summary
            print("\n" + "="*80)
            print("ALL SCENARIOS COMPLETED!")
            print("="*80)
            print("\nScenarios Tested:")
            print("   1. [OK] Refactoring (async/await conversion)")
            print("   2. [OK] Bug Investigation (stack trace debugging)")
            print("   3. [OK] New Feature (file upload endpoint)")
            print("   4. [OK] Code Review (security analysis)")
            print("   5. [OK] Performance Optimization (N+1 queries)")
            print("   6. [OK] Documentation (API spec generation)")
            
            # Test search across all scenarios
            print("\nTesting cross-scenario search...")
            search_response = await client.post(
                f"{BASE_URL}/search",
                json={
                    "query": "async performance optimization refactoring",
                    "group_id": PROJECT_ID,
                    "limit": 10
                }
            )
            
            # Check response status
            if search_response.status_code != 200:
                print(f"   ⚠️  Search failed with status {search_response.status_code}")
                print(f"   Response: {search_response.text}")
                search_results = {"results": []}
            else:
                try:
                    search_results = search_response.json()
                except Exception as e:
                    print(f"   ⚠️  Failed to parse JSON: {e}")
                    print(f"   Response text: {search_response.text}")
                    search_results = {"results": []}
            
            print(f"   Found {len(search_results.get('results', []))} relevant memories")
            
            print("\n[SUCCESS] Memory layer successfully captured all coding workflows!")
            print("   Ready for production use with Innocody integration!")
            
            # Log test summary and flush traces
            log_test_summary()
            flush_test_traces()
            
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Error during scenario execution: {e}")
            trace_error(str(e), {"session_id": session_id})
            import traceback
            traceback.print_exc()
            flush_test_traces()
            return False


def main():
    """Entry point"""
    try:
        success = asyncio.run(run_all_scenarios())
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n[WARNING] Test interrupted by user")
        return 1


if __name__ == "__main__":
    exit(main())
