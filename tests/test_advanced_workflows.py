"""
ADVANCED INNOCODY WORKFLOWS - Complex Multi-Step Scenarios
Mô phỏng các workflow phức tạp, multi-file, team collaboration
"""

import asyncio
import httpx
from datetime import datetime
import hashlib
import uuid as uuid_lib

from dotenv import load_dotenv
load_dotenv()

BASE_URL = "http://localhost:8000"
PROJECT_ID = "advanced_workflow_project"


# =============================================================================
# HELPER FUNCTIONS (reuse)
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
    ext_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.go': 'go', '.rs': 'rust', '.java': 'java', '.sql': 'sql',
        '.yaml': 'yaml', '.json': 'json', '.md': 'markdown'
    }
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


def make_code_change(
    file_path: str,
    change_summary: str,
    **kwargs
) -> dict:
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


def create_conversation_payload(
    request_id: str,
    chat_id: str,
    user_message: str,
    assistant_message: str,
    context_files: list,
    tool_calls: list,
    model: str = "gpt-4o",
    code_changes: list = None,
):
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
# ADVANCED SCENARIO 1: MICROSERVICES MIGRATION
# =============================================================================

async def scenario_microservices_migration(client: httpx.AsyncClient):
    """
    Complex: Break monolith into microservices
    - Multiple files changed
    - Database migration
    - Docker configuration
    - API gateway setup
    """
    print("\n" + "="*80)
    print("🏗️  ADVANCED 1: MICROSERVICES MIGRATION - Break monolith")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_microservices_001",
        chat_id="chat_migration_microservices",
        user_message=(
            "Our monolithic app is too slow. Can you help me extract the notification system "
            "into a separate microservice? It should communicate via RabbitMQ message queue."
        ),
        assistant_message=(
            "I've successfully extracted the notification system into a microservice! Here's the migration:\n\n"
            "**Architecture Changes:**\n\n"
            "**Before:** Monolith\n"
            "```\n"
            "main_app/\n"
            "├── api/\n"
            "├── notifications/  ← Tightly coupled\n"
            "└── database/\n"
            "```\n\n"
            "**After:** Microservices\n"
            "```\n"
            "main_app/          notification_service/\n"
            "├── api/           ├── api/\n"
            "└── database/      ├── workers/\n"
            "                   ├── database/\n"
            "                   └── Dockerfile\n"
            "        ↓ RabbitMQ ↑\n"
            "```\n\n"
            "**Changes Made:**\n\n"
            "1. **New Notification Service:**\n"
            "   - Created standalone FastAPI service\n"
            "   - Port: 8001\n"
            "   - Endpoints: /send-email, /send-sms, /send-push\n"
            "   - Database: Separate PostgreSQL instance\n\n"
            "2. **Message Queue Integration:**\n"
            "   - RabbitMQ for async communication\n"
            "   - Exchanges: `notifications.email`, `notifications.sms`, `notifications.push`\n"
            "   - Consumer workers with retry logic (3 attempts)\n"
            "   - Dead letter queue for failed messages\n\n"
            "3. **Main App Changes:**\n"
            "   - Removed notification code (850 lines deleted!)\n"
            "   - Added RabbitMQ publisher client\n"
            "   - Updated API to publish messages instead of direct calls\n"
            "   - Response time: 2.3s → 450ms (async!)\n\n"
            "4. **Infrastructure:**\n"
            "   - Docker Compose with 3 services\n"
            "   - Kubernetes deployment manifests\n"
            "   - Service mesh configuration (Istio)\n"
            "   - Load balancer rules\n\n"
            "5. **Database Migration:**\n"
            "   - Extracted notification tables to new DB\n"
            "   - Created migration scripts (up/down)\n"
            "   - Zero downtime deployment strategy\n\n"
            "6. **Monitoring:**\n"
            "   - Prometheus metrics for queue depth\n"
            "   - Grafana dashboard for latency\n"
            "   - Alert rules for failed deliveries\n\n"
            "**Deployment Steps:**\n"
            "```bash\n"
            "# 1. Start RabbitMQ\n"
            "docker-compose up -d rabbitmq\n\n"
            "# 2. Run database migration\n"
            "python migrate_notifications.py\n\n"
            "# 3. Deploy notification service\n"
            "docker-compose up -d notification_service\n\n"
            "# 4. Deploy main app (updated)\n"
            "docker-compose up -d main_app\n"
            "```\n\n"
            "**Benefits:**\n"
            "✅ 81% faster response time (async)\n"
            "✅ Independent scaling (notifications get 90% of load)\n"
            "✅ Better fault isolation\n"
            "✅ Technology flexibility (can switch to Go later)\n\n"
            "Migration complete! System is production-ready."
        ),
        context_files=[
            make_context_file("main_app/notifications/email.py", 0.96, "vecdb", ["send_email"]),
            make_context_file("main_app/notifications/sms.py", 0.94, "vecdb", ["send_sms"]),
            make_context_file("main_app/models/notification.py", 0.91, "ast", ["Notification"]),
            make_context_file("main_app/api/users.py", 0.88, "ast", ["create_user"]),
            make_context_file("docker-compose.yml", 0.82, "vecdb", []),
            make_context_file("main_app/config/settings.py", 0.78, "vecdb", []),
            make_context_file("infrastructure/kubernetes/main-app.yaml", 0.75, "ast", [])
        ],
        tool_calls=[
            make_tool_call("read_file", "success", 450),
            make_tool_call("read_file", "success", 380),
            make_tool_call("read_file", "success", 320),
            make_tool_call("create_directory", "success", 50),
            make_tool_call("create_file", "success", 890),  # New service
            make_tool_call("create_file", "success", 650),  # Docker config
            make_tool_call("create_file", "success", 540),  # K8s manifest
            make_tool_call("edit_file", "success", 720),  # Update main app
            make_tool_call("edit_file", "success", 480),
            make_tool_call("run_migration", "success", 4500),
            make_tool_call("run_tests", "success", 8900),
            make_tool_call("docker_build", "success", 35000),
            make_tool_call("docker_compose_up", "success", 12000)
        ],
        code_changes=[
            make_code_change(
                "notification_service/main.py",
                "Created new FastAPI microservice for notification handling with RabbitMQ consumer",
                change_type="added",
                severity="high",
                lines_added=234,
                imports=["fastapi", "pika", "celery"],
                function_name="main"
            ),
            make_code_change(
                "notification_service/workers/email_worker.py",
                "Implemented RabbitMQ consumer worker for email notifications with retry logic",
                change_type="added",
                severity="medium",
                lines_added=156,
                imports=["pika", "smtplib"],
                function_name="consume_email_queue"
            ),
            make_code_change(
                "main_app/api/users.py",
                "Replaced direct notification calls with async RabbitMQ message publishing",
                change_type="refactored",
                severity="high",
                lines_added=23,
                lines_removed=87,
                imports=["pika"],
                function_name="create_user"
            ),
            make_code_change(
                "main_app/notifications/email.py",
                "Removed notification implementation (moved to microservice)",
                change_type="removed",
                severity="medium",
                lines_added=0,
                lines_removed=412
            ),
            make_code_change(
                "docker-compose.yml",
                "Added RabbitMQ and notification service to Docker Compose configuration",
                change_type="modified",
                severity="medium",
                lines_added=45,
                lines_removed=8,
                language="yaml"
            ),
            make_code_change(
                "database/migrations/008_extract_notifications.sql",
                "Database migration to extract notification tables for microservice",
                change_type="added",
                severity="high",
                lines_added=89,
                language="sql"
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"✅ Microservices migration ingested: {result['request_uuid']}")
    print(f"   Files changed: 6 created, 3 modified, 1 removed")
    print(f"   Complexity: HIGH (multi-service, database, infrastructure)")


# =============================================================================
# ADVANCED SCENARIO 2: SECURITY VULNERABILITY PATCH
# =============================================================================

async def scenario_security_vulnerability(client: httpx.AsyncClient):
    """
    Critical: SQL Injection vulnerability found
    - Multiple attack vectors
    - Patch across multiple files
    - Add security tests
    - Update dependencies
    """
    print("\n" + "="*80)
    print("🔐 ADVANCED 2: SECURITY PATCH - SQL Injection vulnerability")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_security_sqli_001",
        chat_id="chat_security_patch",
        user_message=(
            "URGENT: Security scan found SQL injection vulnerabilities in our search endpoints! "
            "CVE-2024-XXXXX severity 9.8/10. We need to patch this immediately across all affected endpoints."
        ),
        assistant_message=(
            "🚨 CRITICAL SECURITY PATCH APPLIED!\n\n"
            "**Vulnerability Analysis:**\n"
            "Found SQL injection in 7 endpoints across 4 files:\n\n"
            "**Attack Vector Example:**\n"
            "```\n"
            "GET /api/search?q=test' OR '1'='1\n"
            "→ Executes: SELECT * FROM users WHERE name='test' OR '1'='1'\n"
            "→ Returns ALL users! (data breach)\n"
            "```\n\n"
            "**Affected Files:**\n"
            "1. `api/search.py` - 3 vulnerable endpoints\n"
            "2. `api/reports.py` - 2 vulnerable queries\n"
            "3. `database/raw_queries.py` - 2 string concatenations\n"
            "4. `admin/export.py` - 1 dynamic query\n\n"
            "**Patches Applied:**\n\n"
            "1. **Parameterized Queries:**\n"
            "   ```python\n"
            "   # ❌ BEFORE (VULNERABLE):\n"
            "   query = f\"SELECT * FROM users WHERE name='{user_input}'\"\n"
            "   cursor.execute(query)\n"
            "   \n"
            "   # ✅ AFTER (SAFE):\n"
            "   query = \"SELECT * FROM users WHERE name = %s\"\n"
            "   cursor.execute(query, (user_input,))\n"
            "   ```\n\n"
            "2. **ORM Usage:**\n"
            "   - Replaced raw SQL with SQLAlchemy where possible\n"
            "   - Automatic parameterization\n"
            "   - Type-safe queries\n\n"
            "3. **Input Validation:**\n"
            "   - Added Pydantic validators for all search inputs\n"
            "   - Max length limits\n"
            "   - Character whitelist (alphanumeric + safe chars)\n"
            "   - Reject SQL keywords in input\n\n"
            "4. **Escaping Functions:**\n"
            "   - For unavoidable raw SQL (reports)\n"
            "   - Use `psycopg2.extensions.adapt()`\n"
            "   - Double-check all escaping\n\n"
            "**Security Tests Added:**\n"
            "- Test SQL injection attempts (20+ payloads)\n"
            "- Test XSS in search results\n"
            "- Test command injection\n"
            "- Fuzzing with sqlmap\n\n"
            "**Additional Hardening:**\n"
            "- Database user has read-only on production tables\n"
            "- Added WAF rules (ModSecurity)\n"
            "- Rate limiting on search endpoints (10 req/min)\n"
            "- Logging all rejected malicious inputs\n\n"
            "**Verification:**\n"
            "✅ All 7 vulnerabilities patched\n"
            "✅ Security tests passing (0 vulnerabilities)\n"
            "✅ Code review completed\n"
            "✅ Penetration test scheduled\n\n"
            "**Deployment:**\n"
            "🚀 Hotfix deployed to production in 45 minutes\n"
            "📧 Security advisory sent to users\n"
            "📝 Incident report filed\n\n"
            "System is now secure ✅"
        ),
        context_files=[
            make_context_file("api/search.py", 0.98, "vecdb", ["search_users", "search_posts"]),
            make_context_file("api/reports.py", 0.95, "vecdb", ["generate_report"]),
            make_context_file("database/raw_queries.py", 0.93, "ast", ["execute_raw_query"]),
            make_context_file("admin/export.py", 0.90, "ast", ["export_data"]),
            make_context_file("tests/test_security.py", 0.85, "vecdb", []),
            make_context_file("config/waf_rules.conf", 0.78, "ast", [])
        ],
        tool_calls=[
            make_tool_call("security_scan", "success", 8900),
            make_tool_call("read_file", "success", 340),
            make_tool_call("read_file", "success", 290),
            make_tool_call("read_file", "success", 270),
            make_tool_call("edit_file", "success", 680),  # Patch 1
            make_tool_call("edit_file", "success", 540),  # Patch 2
            make_tool_call("edit_file", "success", 490),  # Patch 3
            make_tool_call("edit_file", "success", 320),  # Patch 4
            make_tool_call("create_file", "success", 780),  # Security tests
            make_tool_call("run_tests", "success", 5600),
            make_tool_call("security_scan", "success", 9200),  # Re-scan
            make_tool_call("deploy_hotfix", "success", 45000)
        ],
        code_changes=[
            make_code_change(
                "api/search.py",
                "Fixed SQL injection by replacing string concatenation with parameterized queries",
                change_type="fixed",
                severity="critical",
                lines_added=15,
                lines_removed=18,
                imports=["sqlalchemy"],
                function_name="search_users"
            ),
            make_code_change(
                "api/reports.py",
                "Patched SQL injection in report generation using SQLAlchemy ORM",
                change_type="fixed",
                severity="critical",
                lines_added=12,
                lines_removed=8,
                function_name="generate_report"
            ),
            make_code_change(
                "database/raw_queries.py",
                "Replaced all raw SQL with parameterized queries and added input validation",
                change_type="fixed",
                severity="critical",
                lines_added=23,
                lines_removed=34,
                function_name="execute_raw_query"
            ),
            make_code_change(
                "admin/export.py",
                "Fixed SQL injection in data export by using query builder",
                change_type="fixed",
                severity="high",
                lines_added=8,
                lines_removed=6,
                function_name="export_data"
            ),
            make_code_change(
                "tests/test_security.py",
                "Added comprehensive SQL injection test suite with 20+ attack payloads",
                change_type="added",
                severity="medium",
                lines_added=234,
                imports=["pytest", "sqlmap"]
            ),
            make_code_change(
                "api/validators.py",
                "Added input validation and sanitization for all search parameters",
                change_type="added",
                severity="high",
                lines_added=67,
                imports=["pydantic", "re"]
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"✅ Security patch ingested: {result['request_uuid']}")
    print(f"   Severity: CRITICAL (CVE-2024-XXXXX)")
    print(f"   Vulnerabilities fixed: 7 across 4 files")
    print(f"   Deployment: Hotfix to production in 45min")


# =============================================================================
# ADVANCED SCENARIO 3: DATABASE SCHEMA MIGRATION
# =============================================================================

async def scenario_database_migration(client: httpx.AsyncClient):
    """
    Complex: Add multi-tenancy to existing single-tenant app
    - Major schema changes
    - Data migration
    - Zero downtime deployment
    """
    print("\n" + "="*80)
    print("🗄️  ADVANCED 3: DATABASE MIGRATION - Add multi-tenancy")
    print("="*80)
    
    payload = create_conversation_payload(
        request_id="req_migration_multitenancy_001",
        chat_id="chat_db_migration",
        user_message=(
            "We need to add multi-tenancy to our app. Currently all data is in a single schema, "
            "but we need to isolate data by organization. How do we migrate 2M+ rows without downtime?"
        ),
        assistant_message=(
            "I've designed and executed a zero-downtime multi-tenancy migration! Here's the strategy:\n\n"
            "**Migration Strategy: Blue-Green with Shadow Tables**\n\n"
            "**Phase 1: Schema Evolution (No Downtime)**\n"
            "```sql\n"
            "-- Add tenant_id to all tables\n"
            "ALTER TABLE users ADD COLUMN tenant_id UUID;\n"
            "ALTER TABLE projects ADD COLUMN tenant_id UUID;\n"
            "ALTER TABLE tasks ADD COLUMN tenant_id UUID;\n"
            "-- ... 23 tables total\n"
            "\n"
            "-- Add indexes\n"
            "CREATE INDEX idx_users_tenant ON users(tenant_id);\n"
            "CREATE INDEX idx_projects_tenant ON projects(tenant_id, created_at);\n"
            "-- ... composite indexes for query optimization\n"
            "```\n\n"
            "**Phase 2: Data Migration (Background Job)**\n"
            "- Created default tenant: 'legacy_tenant'\n"
            "- Batch updates: 10,000 rows per transaction\n"
            "- Progress tracking: 2.1M / 2.1M rows (100%)\n"
            "- Duration: 4 hours 23 minutes\n"
            "- Zero user-facing errors ✅\n\n"
            "**Phase 3: Application Changes**\n\n"
            "1. **Authentication:**\n"
            "   - JWT now includes `tenant_id` claim\n"
            "   - All API requests scoped to tenant\n"
            "   - Middleware auto-injects tenant filter\n\n"
            "2. **Database Layer:**\n"
            "   ```python\n"
            "   # Before:\n"
            "   users = db.query(User).filter(User.email == email).all()\n"
            "   \n"
            "   # After:\n"
            "   users = db.query(User).filter(\n"
            "       User.tenant_id == current_tenant_id,\n"
            "       User.email == email\n"
            "   ).all()\n"
            "   ```\n\n"
            "3. **Query Optimization:**\n"
            "   - Added tenant_id to ALL queries (safety)\n"
            "   - Index usage: 99.7% (excellent!)\n"
            "   - Query time unchanged (optimized indexes)\n\n"
            "**Phase 4: Data Isolation Verification**\n"
            "- Created test tenants: A, B, C\n"
            "- Verified cross-tenant data isolation\n"
            "- No data leaks found ✅\n"
            "- Passed security audit ✅\n\n"
            "**Phase 5: Add NOT NULL Constraint (Final Step)**\n"
            "```sql\n"
            "-- After all data migrated:\n"
            "ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;\n"
            "ALTER TABLE projects ALTER COLUMN tenant_id SET NOT NULL;\n"
            "-- ... enforce at database level\n"
            "```\n\n"
            "**New Features Enabled:**\n"
            "- ✅ Multiple organizations per installation\n"
            "- ✅ Complete data isolation\n"
            "- ✅ Per-tenant billing\n"
            "- ✅ Per-tenant settings/customization\n"
            "- ✅ Tenant-specific backups\n\n"
            "**Performance Impact:**\n"
            "- Query time: No change (optimized indexes)\n"
            "- Storage: +8% (tenant_id columns + indexes)\n"
            "- Migration downtime: 0 seconds ✅\n\n"
            "**Rollback Strategy:**\n"
            "- Shadow tables maintained for 7 days\n"
            "- One-click rollback script ready\n"
            "- Tested rollback in staging ✅\n\n"
            "Multi-tenancy migration complete! Ready for enterprise customers."
        ),
        context_files=[
            make_context_file("database/migrations/009_add_tenant_id.sql", 0.97, "vecdb"),
            make_context_file("database/migrations/010_migrate_data.py", 0.94, "vecdb", ["migrate_batch"]),
            make_context_file("models/base.py", 0.91, "ast", ["BaseModel"]),
            make_context_file("middleware/tenant.py", 0.88, "vecdb", ["TenantMiddleware"]),
            make_context_file("api/auth.py", 0.85, "ast", ["create_token"]),
            make_context_file("database/session.py", 0.82, "ast", ["get_db_session"]),
            make_context_file("tests/test_multitenancy.py", 0.78, "ast", [])
        ],
        tool_calls=[
            make_tool_call("analyze_schema", "success", 2300),
            make_tool_call("create_file", "success", 890),  # Migration SQL
            make_tool_call("create_file", "success", 1200),  # Data migration script
            make_tool_call("run_migration", "success", 15780000),  # 4h 23min
            make_tool_call("edit_file", "success", 680),
            make_tool_call("edit_file", "success", 540),
            make_tool_call("edit_file", "success", 490),
            make_tool_call("create_file", "success", 780),  # Tests
            make_tool_call("run_tests", "success", 8900),
            make_tool_call("verify_isolation", "success", 4500)
        ],
        code_changes=[
            make_code_change(
                "database/migrations/009_add_tenant_id.sql",
                "Added tenant_id column to 23 tables with indexes for multi-tenancy support",
                change_type="added",
                severity="high",
                lines_added=187,
                language="sql"
            ),
            make_code_change(
                "database/migrations/010_migrate_data.py",
                "Background job to migrate 2.1M rows to default tenant in batches",
                change_type="added",
                severity="critical",
                lines_added=234,
                imports=["sqlalchemy", "tqdm"],
                function_name="migrate_batch"
            ),
            make_code_change(
                "models/base.py",
                "Added tenant_id to BaseModel for automatic tenant filtering across all models",
                change_type="modified",
                severity="high",
                lines_added=12,
                lines_removed=2
            ),
            make_code_change(
                "middleware/tenant.py",
                "Created TenantMiddleware to automatically inject tenant_id into all queries",
                change_type="added",
                severity="high",
                lines_added=89,
                imports=["fastapi", "contextvars"],
                function_name="TenantMiddleware"
            ),
            make_code_change(
                "api/auth.py",
                "Updated JWT token generation to include tenant_id claim",
                change_type="modified",
                severity="medium",
                lines_added=8,
                lines_removed=3,
                imports=["pyjwt"],
                function_name="create_token"
            ),
            make_code_change(
                "tests/test_multitenancy.py",
                "Comprehensive test suite for tenant data isolation and cross-tenant security",
                change_type="added",
                severity="medium",
                lines_added=298,
                imports=["pytest", "faker"]
            )
        ]
    )
    
    response = await client.post(f"{BASE_URL}/ingest/conversation", json=payload)
    response.raise_for_status()
    result = response.json()
    print(f"✅ Database migration ingested: {result['request_uuid']}")
    print(f"   Migrated: 2.1M rows across 23 tables")
    print(f"   Downtime: 0 seconds (zero-downtime migration)")
    print(f"   Duration: 4h 23min (background)")


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

async def run_advanced_scenarios():
    """Run all advanced scenarios"""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*12 + "ADVANCED INNOCODY WORKFLOWS TEST" + " "*33 + "║")
    print("╚" + "="*78 + "╝")
    print("\n📝 Testing complex multi-step workflows")
    print("⚠️  Make sure memory layer server is running on http://localhost:8000\n")
    
    timeout = httpx.Timeout(180.0, read=180.0, write=90.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            await scenario_microservices_migration(client)
            await asyncio.sleep(4)
            
            await scenario_security_vulnerability(client)
            await asyncio.sleep(4)
            
            await scenario_database_migration(client)
            await asyncio.sleep(3)
            
            # Summary
            print("\n" + "="*80)
            print("🎉 ALL ADVANCED SCENARIOS COMPLETED!")
            print("="*80)
            print("\n📊 Advanced Workflows Tested:")
            print("   1. ✅ Microservices Migration (monolith → services)")
            print("   2. ✅ Security Vulnerability Patch (SQL injection)")
            print("   3. ✅ Database Migration (multi-tenancy, 2.1M rows)")
            
            print("\n💡 These scenarios demonstrate:")
            print("   • Multi-file complex changes")
            print("   • Infrastructure modifications")
            print("   • Critical security patches")
            print("   • Large-scale data migrations")
            print("   • Zero-downtime deployments")
            
            # Test search for security
            print("\n🔍 Testing search: 'security SQL injection vulnerability'")
            search_response = await client.post(
                f"{BASE_URL}/search",
                json={
                    "query": "security SQL injection vulnerability critical patch",
                    "group_id": PROJECT_ID
                }
            )
            search_results = search_response.json()
            print(f"   Found {len(search_results.get('results', []))} security-related memories")
            
            print("\n✅ Memory layer successfully captured complex workflows!")
            print("   Advanced scenarios ready for production!")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    try:
        success = asyncio.run(run_advanced_scenarios())
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        return 1


if __name__ == "__main__":
    exit(main())

