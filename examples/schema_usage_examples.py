# examples/schema_usage_examples.py
"""
Usage examples for code context schemas
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.schemas import (
    CodeReference,
    CodeMetadata,
    IngestCodeContext,
    SearchCodeRequest
)
from datetime import datetime

# =============================================================================
# Example 1: Simple Bug Fix (No Code References)
# =============================================================================

def example_simple_bug_fix():
    """User reports and fixes a bug in conversation"""
    
    metadata = CodeMetadata(
        file_path="src/auth/auth_service.py",
        function_name="login_user",
        line_start=45,
        line_end=52,
        change_type="fixed",
        change_summary="Added null check before accessing user.token",
        severity="high",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed login null pointer bug",
        summary="Fixed null pointer exception in auth_service.py:login_user() by adding null check before accessing user.token attribute. This prevents AttributeError when token is None.",
        metadata=metadata,
        project_id="project_auth_system"
    )
    
    print("Example 1: Simple Bug Fix")
    print(f"Name: {ingest.name}")
    print(f"File: {ingest.metadata.file_path}")
    print(f"Change Type: {ingest.metadata.change_type}")
    print(f"Severity: {ingest.metadata.severity}")
    print()

# =============================================================================
# Example 2: Bug Fix with Code References
# =============================================================================

def example_bug_fix_with_code_refs():
    """Bug fix with references to external code storage"""
    
    # Reference to original buggy code (stored in long-term system)
    code_before = CodeReference(
        code_id="code_buggy_xyz123",
        code_hash="a3f5c8d2e9b1f4a7c6d8e2f3a4b5c6d7",
        language="python",
        line_count=5
    )
    
    # Reference to fixed code
    code_after = CodeReference(
        code_id="code_fixed_abc456",
        code_hash="b7e9d1a3c4f6e8a2d5b7c9e1f3a5c7d9",
        language="python",
        line_count=8
    )
    
    metadata = CodeMetadata(
        file_path="src/auth/auth_service.py",
        function_name="login_user",
        line_start=45,
        line_end=52,
        change_type="fixed",
        change_summary="Added null validation before accessing user.token",
        severity="high",
        code_before_ref=code_before,
        code_after_ref=code_after,
        lines_added=3,
        lines_removed=1,
        diff_summary="Added 3 lines for null check, removed 1 unsafe line",
        git_commit="abc123def456",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed login null pointer bug",
        summary="Fixed critical null pointer exception in auth_service.py:login_user() function by adding comprehensive null check before accessing user.token attribute. This prevents AttributeError when token is None. Change includes validation for both user object and token attribute.",
        metadata=metadata,
        project_id="project_auth_system",
        reference_time="2025-10-01T10:30:00Z"
    )
    
    print("Example 2: Bug Fix with Code References")
    print(f"Name: {ingest.name}")
    print(f"Code Before ID: {ingest.metadata.code_before_ref.code_id}")
    print(f"Code After ID: {ingest.metadata.code_after_ref.code_id}")
    print(f"Lines Added: {ingest.metadata.lines_added}")
    print(f"Lines Removed: {ingest.metadata.lines_removed}")
    print(f"Git Commit: {ingest.metadata.git_commit}")
    print()

# =============================================================================
# Example 3: Feature Addition
# =============================================================================

def example_feature_addition():
    """Adding a new feature"""
    
    code_ref = CodeReference(
        code_id="code_rate_limit_new789",
        code_hash="c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
        language="python",
        line_count=25
    )
    
    metadata = CodeMetadata(
        file_path="src/api/middleware.py",
        function_name="rate_limit_middleware",
        line_start=120,
        line_end=145,
        change_type="added",
        change_summary="Implemented rate limiting using Redis with 100 req/min limit",
        code_after_ref=code_ref,
        lines_added=25,
        lines_removed=0,
        diff_summary="Added 25 lines for new rate limiting middleware",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    ingest = IngestCodeContext(
        name="Added rate limiting middleware",
        summary="Implemented rate limiting middleware in api/middleware.py using Redis as backend. Configured limit of 100 requests per minute per IP address. Includes error handling and custom response messages for rate limit exceeded.",
        metadata=metadata,
        project_id="project_api_system"
    )
    
    print("Example 3: Feature Addition")
    print(f"Name: {ingest.name}")
    print(f"Change Type: {ingest.metadata.change_type}")
    print(f"Lines Added: {ingest.metadata.lines_added}")
    print()

# =============================================================================
# Example 4: Refactoring
# =============================================================================

def example_refactoring():
    """Code refactoring without bug fix"""
    
    code_before = CodeReference(
        code_id="code_sync_old",
        code_hash="old_hash_123",
        language="python",
        line_count=15
    )
    
    code_after = CodeReference(
        code_id="code_async_new",
        code_hash="new_hash_456",
        language="python",
        line_count=18
    )
    
    metadata = CodeMetadata(
        file_path="src/db/repository.py",
        function_name="get_user_by_id",
        line_start=30,
        line_end=48,
        change_type="refactored",
        change_summary="Migrated from synchronous to async/await pattern",
        code_before_ref=code_before,
        code_after_ref=code_after,
        lines_added=5,
        lines_removed=2,
        diff_summary="Converted to async pattern, added 5 lines, removed 2",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    ingest = IngestCodeContext(
        name="Refactored user repository to async",
        summary="Refactored UserRepository.get_user_by_id() from synchronous to async/await pattern for 50% performance improvement. Updated database connection handling to use async context manager. All callers updated accordingly.",
        metadata=metadata,
        project_id="project_db_layer"
    )
    
    print("Example 4: Refactoring")
    print(f"Name: {ingest.name}")
    print(f"Change Type: {ingest.metadata.change_type}")
    print(f"Summary: {ingest.metadata.change_summary}")
    print()

# =============================================================================
# Example 5: Search Queries
# =============================================================================

def example_search_queries():
    """Different search query patterns"""
    
    # Basic search
    search1 = SearchCodeRequest(
        query="authentication bug fixes",
        project_id="project_auth_system"
    )
    print("Example 5a: Basic Search")
    print(f"Query: {search1.query}")
    print(f"Project: {search1.project_id}")
    print(f"Days Ago: {search1.days_ago} (default)")
    print()
    
    # Search with file filter
    search2 = SearchCodeRequest(
        query="null pointer fixes",
        project_id="project_auth_system",
        file_filter="auth_service.py"
    )
    print("Example 5b: Search with File Filter")
    print(f"Query: {search2.query}")
    print(f"File Filter: {search2.file_filter}")
    print()
    
    # Search with multiple filters
    search3 = SearchCodeRequest(
        query="recent bug fixes",
        project_id="project_auth_system",
        file_filter="auth_service.py",
        function_filter="login_user",
        change_type_filter="fixed",
        days_ago=7
    )
    print("Example 5c: Search with Multiple Filters")
    print(f"Query: {search3.query}")
    print(f"File: {search3.file_filter}")
    print(f"Function: {search3.function_filter}")
    print(f"Change Type: {search3.change_type_filter}")
    print(f"Days Ago: {search3.days_ago}")
    print()

# =============================================================================
# Example 6: JSON Serialization
# =============================================================================

def example_json_serialization():
    """Convert models to JSON for API"""
    
    metadata = CodeMetadata(
        file_path="src/auth/auth_service.py",
        function_name="login_user",
        change_type="fixed",
        change_summary="Added null check",
        severity="high",
        timestamp="2025-10-01T10:00:00Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed bug",
        summary="Fixed null pointer bug",
        metadata=metadata,
        project_id="test_project"
    )
    
    # Convert to dict
    data_dict = ingest.model_dump()
    print("Example 6: JSON Serialization")
    print("As Dict:")
    print(data_dict)
    print()
    
    # Convert to JSON string
    json_str = ingest.model_dump_json(indent=2)
    print("As JSON:")
    print(json_str)
    print()

# =============================================================================
# Example 7: Real Conversation Flow
# =============================================================================

def example_real_conversation_flow():
    """Simulate real chatbot conversation flow"""
    
    print("Example 7: Real Conversation Flow")
    print("=" * 60)
    
    # Turn 1: User reports bug
    print("\nTurn 1: User reports bug")
    print('User: "Mình tìm thấy bug null pointer trong auth_service.py"')
    print('Bot: "Bug ở function nào? Bạn có error message không?"')
    
    # Turn 2: User provides details
    print("\nTurn 2: User provides details")
    print('User: "Ở login_user(), khi user.token = None thì bị crash"')
    print('Bot: "Vậy cần thêm null check. Bạn muốn mình suggest fix không?"')
    
    # Turn 3: User fixes
    print("\nTurn 3: User fixes bug")
    print('User: "Mình đã fix rồi, thêm if user.token is not None"')
    
    # System ingests to memory
    print("\n[System: Summarizing conversation and ingesting to memory...]")
    
    metadata = CodeMetadata(
        file_path="src/auth/auth_service.py",
        function_name="login_user",
        line_start=45,
        line_end=47,
        change_type="fixed",
        change_summary="Added null check for user.token before access",
        severity="high",
        lines_added=2,
        diff_summary="Added null validation check",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed null pointer in login_user",
        summary="Fixed null pointer exception in auth_service.py:login_user() function when user.token is None. Added null check before accessing token attribute to prevent AttributeError crashes.",
        metadata=metadata,
        project_id="project_auth_system"
    )
    
    print(f"\n[Ingested to Memory]")
    print(f"  Name: {ingest.name}")
    print(f"  File: {ingest.metadata.file_path}")
    print(f"  Function: {ingest.metadata.function_name}")
    print(f"  Change: {ingest.metadata.change_type}")
    print(f"  Severity: {ingest.metadata.severity}")
    
    # Later conversation - retrieval
    print("\n" + "=" * 60)
    print("Later Conversation (3 hours later):")
    print('User: "Tôi cần refactor auth_service.py, có gì cần lưu ý?"')
    
    print("\n[System: Searching memory...]")
    search = SearchCodeRequest(
        query="auth_service modifications recent changes",
        project_id="project_auth_system",
        file_filter="auth_service.py",
        days_ago=1
    )
    
    print(f"\n[Search Query]")
    print(f"  Query: {search.query}")
    print(f"  File Filter: {search.file_filter}")
    print(f"  Time Window: Last {search.days_ago} day(s)")
    
    print("\n[Memory Retrieved]")
    print(f"  Found: Fixed null pointer in login_user")
    print(f"  Context: Remember to keep null check when refactoring!")
    
    print("\nBot: \"Khi refactor auth_service.py, nhớ giữ null check ở")
    print("      login_user() nhé! Vừa fix bug null pointer ở đó 3 giờ trước.\"")
    print()

# =============================================================================
# Run all examples
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CODE CONTEXT SCHEMAS - USAGE EXAMPLES")
    print("=" * 70)
    print()
    
    example_simple_bug_fix()
    example_bug_fix_with_code_refs()
    example_feature_addition()
    example_refactoring()
    example_search_queries()
    example_json_serialization()
    example_real_conversation_flow()
    
    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)
