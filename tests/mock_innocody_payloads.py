"""
Mock Innocody Payloads - Realistic Examples
Chuẩn output format từ Innocody để test Memory Layer

Use cases:
1. Code analysis request
2. Bug fix request  
3. Feature implementation
4. Code review
5. Refactoring
"""

from datetime import datetime
from typing import List, Dict, Any


class InnocodyPayloadBuilder:
    """Helper class để build realistic Innocody payloads"""
    
    @staticmethod
    def base_payload(
        request_id: str,
        project_id: str,
        chat_id: str,
        chat_mode: str = "AGENT"
    ) -> Dict[str, Any]:
        """Base payload structure"""
        timestamp = datetime.utcnow().isoformat() + "Z"
        return {
            "request_id": request_id,
            "project_id": project_id,
            "timestamp": timestamp,
            "chat_meta": {
                "chat_id": chat_id,
                "base_chat_id": chat_id.split("_")[0] if "_" in chat_id else chat_id,
                "request_attempt_id": f"attempt_{request_id[-3:]}",
                "chat_mode": chat_mode
            },
            "messages": [],
            "context_files": [],
            "tool_calls": [],
            "checkpoints": [],
            "code_changes": [],
            "model_response": {
                "model": "gpt-4-turbo",
                "finish_reason": "stop"
            }
        }
    
    @staticmethod
    def add_message(
        payload: Dict[str, Any],
        role: str,
        content_summary: str,
        tokens: int = 0
    ):
        """Add message to payload"""
        timestamp = payload["timestamp"]
        sequence = len(payload["messages"])
        
        payload["messages"].append({
            "sequence": sequence,
            "role": role,
            "content_summary": content_summary,
            "timestamp": timestamp,
            "total_tokens": tokens,
            "metadata": {}
        })
        
        # Update total tokens in last message
        if payload["messages"]:
            total = sum(m.get("total_tokens", 0) for m in payload["messages"])
            payload["messages"][-1]["total_tokens"] = total
    
    @staticmethod
    def add_context_file(
        payload: Dict[str, Any],
        file_path: str,
        usefulness: float
    ):
        """Add context file to payload"""
        import hashlib
        content_hash = hashlib.sha256(file_path.encode()).hexdigest()
        
        payload["context_files"].append({
            "file_path": file_path,
            "usefulness": usefulness,
            "content_hash": content_hash,
            "source": "vecdb",
            "symbols": []
        })
    
    @staticmethod
    def add_tool_call(
        payload: Dict[str, Any],
        tool_name: str,
        status: str = "success",
        execution_time_ms: int = 200
    ):
        """Add tool call to payload"""
        import hashlib
        import uuid
        
        tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
        args_hash = hashlib.sha256(f"{tool_name}:args".encode()).hexdigest()
        
        payload["tool_calls"].append({
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments_hash": args_hash,
            "status": status,
            "execution_time_ms": execution_time_ms
        })


# =============================================================================
# EXAMPLE 1: Code Analysis Request
# =============================================================================
def mock_code_analysis_request(project_id: str = "zepai_prod") -> Dict[str, Any]:
    """
    User: "Analyze the authentication system"
    Innocody: Đọc code, explain architecture
    """
    payload = InnocodyPayloadBuilder.base_payload(
        request_id="req_analyze_auth_001",
        project_id=project_id,
        chat_id="chat_20250103_analyze",
        chat_mode="AGENT"
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="user",
        content_summary="Can you analyze the authentication system? I need to understand how user login works.",
        tokens=0
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="assistant",
        content_summary=(
            "I've analyzed the authentication system. Key findings:\n"
            "1. JWT-based authentication with 24h token expiration\n"
            "2. Password hashing using bcrypt (cost factor 12)\n"
            "3. Session management via Redis\n"
            "4. Rate limiting: 5 attempts per minute per IP\n"
            "5. Missing: 2FA, account lockout policy\n\n"
            "Main files: auth/login.py (login endpoint), auth/session.py (session mgmt), models/user.py (user model)"
        ),
        tokens=856
    )
    
    # Context files
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/login.py",
        usefulness=0.95
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/session.py",
        usefulness=0.88
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/models/user.py",
        usefulness=0.82
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/middleware.py",
        usefulness=0.75
    )
    
    # Tool calls
    InnocodyPayloadBuilder.add_tool_call(payload, "read_file", "success", 245)
    InnocodyPayloadBuilder.add_tool_call(payload, "grep_search", "success", 180)
    InnocodyPayloadBuilder.add_tool_call(payload, "find_by_name", "success", 120)
    
    return payload


# =============================================================================
# EXAMPLE 2: Bug Fix Request
# =============================================================================
def mock_bug_fix_request(project_id: str = "zepai_prod") -> Dict[str, Any]:
    """
    User: "Fix login bug - users locked out permanently"
    Innocody: Tìm bug, fix code, run tests
    """
    payload = InnocodyPayloadBuilder.base_payload(
        request_id="req_fix_bug_login_001",
        project_id=project_id,
        chat_id="chat_20250103_bugfix",
        chat_mode="AGENT"
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="user",
        content_summary=(
            "URGENT BUG: Users are getting locked out permanently after 5 failed login attempts. "
            "The rate limiter never resets. Please investigate and fix!"
        ),
        tokens=0
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="assistant",
        content_summary=(
            "Bug identified and fixed!\n\n"
            "**Root Cause**: Rate limiter in auth/login.py uses Redis without TTL. "
            "Failed login counters never expire, causing permanent lockouts.\n\n"
            "**Fix Applied**:\n"
            "1. Added 15-minute TTL to rate limit counter: redis.setex(key, 900, attempts)\n"
            "2. Created clear_rate_limit() admin function\n"
            "3. Added logging for locked accounts\n"
            "4. Updated tests to verify TTL behavior\n\n"
            "All tests passing. Bug resolved!"
        ),
        tokens=1243
    )
    
    # Context files (bug fix context)
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/login.py",
        usefulness=0.98
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/rate_limiter.py",
        usefulness=0.92
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="tests/test_auth.py",
        usefulness=0.88
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/core/redis_client.py",
        usefulness=0.65
    )
    
    # Tool calls (investigation + fix)
    InnocodyPayloadBuilder.add_tool_call(payload, "read_file", "success", 198)
    InnocodyPayloadBuilder.add_tool_call(payload, "grep_search", "success", 156)
    InnocodyPayloadBuilder.add_tool_call(payload, "edit_file", "success", 421)
    InnocodyPayloadBuilder.add_tool_call(payload, "run_command", "success", 2340)
    InnocodyPayloadBuilder.add_tool_call(payload, "read_file", "success", 112)
    
    return payload


# =============================================================================
# EXAMPLE 3: Feature Implementation
# =============================================================================
def mock_feature_implementation(project_id: str = "zepai_prod") -> Dict[str, Any]:
    """
    User: "Add 2FA support to login"
    Innocody: Design, implement, test
    """
    payload = InnocodyPayloadBuilder.base_payload(
        request_id="req_feat_2fa_001",
        project_id=project_id,
        chat_id="chat_20250103_feature",
        chat_mode="AGENT"
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="user",
        content_summary=(
            "We need to add Two-Factor Authentication (2FA) to the login flow. "
            "Use TOTP (Google Authenticator compatible). Can you implement this?"
        ),
        tokens=0
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="assistant",
        content_summary=(
            "2FA implementation complete!\n\n"
            "**Implementation**:\n"
            "1. Added pyotp library for TOTP generation\n"
            "2. New User fields: totp_secret, is_2fa_enabled\n"
            "3. New endpoints:\n"
            "   - POST /auth/2fa/setup (generate QR code)\n"
            "   - POST /auth/2fa/verify (verify TOTP code)\n"
            "   - POST /auth/2fa/disable (disable 2FA)\n"
            "4. Updated login flow: check is_2fa_enabled → require TOTP\n"
            "5. Added 2FA recovery codes (10 single-use codes)\n\n"
            "Tests added, all passing. Ready for review!"
        ),
        tokens=1876
    )
    
    # Context files
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/totp.py",
        usefulness=0.95
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/login.py",
        usefulness=0.90
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/models/user.py",
        usefulness=0.88
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/routers/auth_router.py",
        usefulness=0.85
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="tests/test_2fa.py",
        usefulness=0.82
    )
    
    # Tool calls
    InnocodyPayloadBuilder.add_tool_call(payload, "read_file", "success", 234)
    InnocodyPayloadBuilder.add_tool_call(payload, "write_to_file", "success", 567)
    InnocodyPayloadBuilder.add_tool_call(payload, "edit_file", "success", 389)
    InnocodyPayloadBuilder.add_tool_call(payload, "run_command", "success", 3450)
    
    return payload


# =============================================================================
# EXAMPLE 4: Code Review Request
# =============================================================================
def mock_code_review(project_id: str = "zepai_prod") -> Dict[str, Any]:
    """
    User: "Review my authentication refactoring PR"
    Innocody: Analyze changes, provide feedback
    """
    payload = InnocodyPayloadBuilder.base_payload(
        request_id="req_review_001",
        project_id=project_id,
        chat_id="chat_20250103_review",
        chat_mode="AGENT"
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="user",
        content_summary=(
            "Can you review my authentication refactoring PR? "
            "I've split the monolithic auth module into smaller components. "
            "Check for potential issues and suggest improvements."
        ),
        tokens=0
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="assistant",
        content_summary=(
            "Code review complete! Overall good refactoring.\n\n"
            "**Strengths**:\n"
            "✓ Clear separation of concerns\n"
            "✓ Improved testability\n"
            "✓ Better error handling\n\n"
            "**Issues Found**:\n"
            "1. ⚠️ auth/validators.py: Missing input sanitization for email\n"
            "2. ⚠️ auth/token.py: Hardcoded JWT secret (use env var)\n"
            "3. ⚠️ Missing docstrings in auth/exceptions.py\n\n"
            "**Suggestions**:\n"
            "• Add integration tests for the new structure\n"
            "• Consider using dependency injection for Redis client\n"
            "• Update API documentation\n\n"
            "Approve with minor changes requested."
        ),
        tokens=1456
    )
    
    # Context files
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/validators.py",
        usefulness=0.92
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/token.py",
        usefulness=0.89
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/exceptions.py",
        usefulness=0.85
    )
    
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/login.py",
        usefulness=0.88
    )
    
    # Tool calls
    InnocodyPayloadBuilder.add_tool_call(payload, "read_file", "success", 178)
    InnocodyPayloadBuilder.add_tool_call(payload, "grep_search", "success", 234)
    InnocodyPayloadBuilder.add_tool_call(payload, "find_by_name", "success", 145)
    
    return payload


# =============================================================================
# EXAMPLE 5: Quick Question (Short conversation)
# =============================================================================
def mock_quick_question(project_id: str = "zepai_prod") -> Dict[str, Any]:
    """
    User: "What hashing algorithm are we using for passwords?"
    Innocody: Quick answer from code
    """
    payload = InnocodyPayloadBuilder.base_payload(
        request_id="req_quick_001",
        project_id=project_id,
        chat_id="chat_20250103_quick",
        chat_mode="AGENT"
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="user",
        content_summary="What hashing algorithm are we using for passwords?",
        tokens=0
    )
    
    InnocodyPayloadBuilder.add_message(
        payload,
        role="assistant",
        content_summary=(
            "We're using bcrypt with cost factor 12 for password hashing. "
            "Implementation in backend/auth/password.py using passlib library."
        ),
        tokens=234
    )
    
    # Minimal context
    InnocodyPayloadBuilder.add_context_file(
        payload,
        file_path="backend/auth/password.py",
        usefulness=0.95
    )
    
    InnocodyPayloadBuilder.add_tool_call(payload, "grep_search", "success", 123)
    
    return payload


# =============================================================================
# Export all mock payloads
# =============================================================================
MOCK_PAYLOADS = {
    "code_analysis": mock_code_analysis_request,
    "bug_fix": mock_bug_fix_request,
    "feature_implementation": mock_feature_implementation,
    "code_review": mock_code_review,
    "quick_question": mock_quick_question
}


def get_mock_payload(scenario: str, project_id: str = "zepai_prod") -> Dict[str, Any]:
    """Get mock payload by scenario name"""
    if scenario not in MOCK_PAYLOADS:
        raise ValueError(f"Unknown scenario: {scenario}. Available: {list(MOCK_PAYLOADS.keys())}")
    
    return MOCK_PAYLOADS[scenario](project_id)


def print_payload_summary(payload: Dict[str, Any]):
    """Pretty print payload summary"""
    print(f"\n📦 Payload Summary:")
    print(f"   Request ID: {payload['request_id']}")
    print(f"   Chat ID: {payload['chat_meta']['chat_id']}")
    print(f"   Messages: {len(payload['messages'])}")
    print(f"   Context Files: {len(payload['context_files'])}")
    print(f"   Tool Calls: {len(payload['tool_calls'])}")
    if payload['messages']:
        last_msg = payload['messages'][-1]
        print(f"   Total Tokens: {last_msg.get('total_tokens', 0)}")


if __name__ == "__main__":
    print("="*80)
    print("MOCK INNOCODY PAYLOADS")
    print("="*80)
    
    for scenario_name, builder_func in MOCK_PAYLOADS.items():
        print(f"\n{scenario_name.upper().replace('_', ' ')}:")
        print("-" * 80)
        payload = builder_func()
        print_payload_summary(payload)
        
        # Show user message
        if payload['messages']:
            user_msg = next((m for m in payload['messages'] if m['role'] == 'user'), None)
            if user_msg:
                print(f"\n   User: \"{user_msg['content_summary'][:80]}...\"")
        
        # Show top context files
        if payload['context_files']:
            print(f"\n   Top Context Files:")
            for cf in payload['context_files'][:2]:
                print(f"   - {cf['file_path']} (usefulness: {cf['usefulness']:.2f})")
    
    print("\n" + "="*80)
    print("✅ Mock payloads ready for testing!")
    print("\nUsage:")
    print("   from mock_innocody_payloads import get_mock_payload")
    print("   payload = get_mock_payload('bug_fix', project_id='my_project')")
