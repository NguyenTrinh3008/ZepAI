# tests/test_innocody_adapter.py
"""
Test suite for Innocody adapter
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import asyncio
from app.innocody_adapter import (
    DiffChunk,
    InnocodyResponse,
    ChatMeta,
    calculate_hash,
    count_lines,
    extract_function_name,
    detect_language,
    infer_severity,
    normalize_change_type,
    generate_simple_summary,
    convert_innocody_to_memory_layer,
    generate_mock_innocody_response,
    generate_mock_examples
)


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================

def test_calculate_hash():
    """Test hash calculation"""
    text = "def hello():\n    print('hello')"
    hash1 = calculate_hash(text)
    hash2 = calculate_hash(text)
    
    assert hash1 == hash2  # Same text → same hash
    assert len(hash1) == 16  # Truncated to 16 chars
    
    hash3 = calculate_hash("different text")
    assert hash1 != hash3  # Different text → different hash


def test_count_lines():
    """Test line counting"""
    assert count_lines("") == 0
    assert count_lines("single line") == 1
    assert count_lines("line 1\nline 2") == 2
    assert count_lines("line 1\nline 2\nline 3") == 3


def test_detect_language():
    """Test language detection"""
    assert detect_language("main.py") == "python"
    assert detect_language("app.js") == "javascript"
    assert detect_language("component.tsx") == "typescript"
    assert detect_language("server.go") == "go"
    assert detect_language("main.rs") == "rust"
    assert detect_language("unknown.xyz") == "unknown"


def test_extract_function_name():
    """Test function name extraction"""
    code = """
def helper():
    pass

def login_user(username, password):
    user = get_user(username)
    return user.token
"""
    
    # Line 5 (def login_user) should return "login_user"
    func_name = extract_function_name(code, 6)
    assert func_name == "login_user"
    
    # Test class extraction
    code_with_class = """
class AuthService:
    def __init__(self):
        pass
"""
    class_name = extract_function_name(code_with_class, 3)
    assert class_name == "AuthService"


def test_normalize_change_type():
    """Test change type normalization"""
    assert normalize_change_type("add") == "added"
    assert normalize_change_type("remove") == "removed"
    assert normalize_change_type("edit") == "updated"
    assert normalize_change_type("rename") == "refactored"


def test_infer_severity():
    """Test severity inference"""
    # Critical file
    chunk = DiffChunk(
        file_name="src/auth/auth_service.py",
        file_action="edit",
        line1=1,
        line2=10,
        lines_remove="a\nb\nc",
        lines_add="a\nb\nc\nd\ne"
    )
    severity = infer_severity(chunk, "src/auth/security.py")
    assert severity in ["high", "critical"]
    
    # Test file
    test_chunk = DiffChunk(
        file_name="test_auth.py",
        file_action="edit",
        line1=1,
        line2=5,
        lines_remove="a",
        lines_add="a\nb"
    )
    severity = infer_severity(test_chunk, "test_auth.py")
    assert severity == "low"
    
    # Large change
    large_chunk = DiffChunk(
        file_name="api/routes.py",
        file_action="edit",
        line1=1,
        line2=150,
        lines_remove="\n" * 100,
        lines_add="\n" * 120
    )
    severity = infer_severity(large_chunk, "api/routes.py")
    assert severity in ["medium", "high"]


def test_generate_simple_summary():
    """Test simple summary generation"""
    chunk = DiffChunk(
        file_name="src/auth/auth_service.py",
        file_action="edit",
        line1=1,
        line2=5,
        lines_remove="line1\nline2",
        lines_add="line1\nline2\nline3\nline4"
    )
    
    summary = generate_simple_summary(chunk)
    assert "auth_service.py" in summary
    assert "4" in summary  # 4 lines added
    
    # Test add action
    add_chunk = DiffChunk(
        file_name="new_file.py",
        file_action="add",
        line1=1,
        line2=10,
        lines_remove="",
        lines_add="a\nb\nc"
    )
    summary = generate_simple_summary(add_chunk)
    assert "Added" in summary
    assert "new_file.py" in summary


# =============================================================================
# Integration Tests - Full Conversion
# =============================================================================

@pytest.mark.asyncio
async def test_convert_mock_response():
    """Test converting mock Innocody response"""
    mock_response = generate_mock_innocody_response()
    
    # Convert without LLM (faster for testing)
    payloads = await convert_innocody_to_memory_layer(
        mock_response,
        use_llm_summary=False
    )
    
    assert len(payloads) > 0
    
    payload = payloads[0]
    
    # Check required fields
    assert "name" in payload
    assert "summary" in payload
    assert "metadata" in payload
    assert "project_id" in payload
    
    # Check metadata
    meta = payload["metadata"]
    assert "file_path" in meta
    assert "change_type" in meta
    assert "severity" in meta
    assert "lines_added" in meta
    assert "lines_removed" in meta
    assert "timestamp" in meta
    
    # Check change type normalization
    assert meta["change_type"] in ["fixed", "added", "refactored", "removed", "updated"]


@pytest.mark.asyncio
async def test_convert_with_chat_meta():
    """Test conversion with ChatMeta"""
    mock_response = generate_mock_innocody_response()
    chat_meta = ChatMeta(
        chat_id="test_chat_123",
        project_id="my_awesome_project"
    )
    
    payloads = await convert_innocody_to_memory_layer(
        mock_response,
        chat_meta=chat_meta,
        use_llm_summary=False
    )
    
    assert len(payloads) > 0
    payload = payloads[0]
    
    # Check project_id được set từ chat_meta
    assert payload["project_id"] == "my_awesome_project"


@pytest.mark.asyncio
async def test_convert_multiple_examples():
    """Test converting multiple mock examples"""
    examples = generate_mock_examples()
    
    for idx, example in enumerate(examples):
        payloads = await convert_innocody_to_memory_layer(
            example,
            use_llm_summary=False
        )
        
        assert len(payloads) > 0, f"Example {idx} failed"
        
        for payload in payloads:
            # Validate structure
            assert "name" in payload
            assert "summary" in payload
            assert "metadata" in payload
            
            # Validate metadata completeness
            meta = payload["metadata"]
            assert "file_path" in meta
            assert "change_type" in meta
            assert "lines_added" in meta
            assert "lines_removed" in meta


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_empty_chunks():
    """Test handling empty chunks"""
    response = InnocodyResponse(
        file_before="",
        file_after="",
        chunks=[]
    )
    
    payloads = await convert_innocody_to_memory_layer(
        response,
        use_llm_summary=False
    )
    
    assert len(payloads) == 0


@pytest.mark.asyncio
async def test_add_file_action():
    """Test add file action"""
    response = InnocodyResponse(
        file_before="",
        file_after="new file content",
        chunks=[
            DiffChunk(
                file_name="new_module.py",
                file_action="add",
                line1=1,
                line2=10,
                lines_remove="",
                lines_add="new file content\nwith multiple lines"
            )
        ]
    )
    
    payloads = await convert_innocody_to_memory_layer(
        response,
        use_llm_summary=False
    )
    
    assert len(payloads) == 1
    payload = payloads[0]
    
    assert payload["metadata"]["change_type"] == "added"
    assert payload["metadata"]["lines_removed"] == 0
    assert payload["metadata"]["lines_added"] > 0


@pytest.mark.asyncio
async def test_remove_file_action():
    """Test remove file action"""
    response = InnocodyResponse(
        file_before="old file content",
        file_after="",
        chunks=[
            DiffChunk(
                file_name="deprecated.py",
                file_action="remove",
                line1=1,
                line2=5,
                lines_remove="old file content",
                lines_add=""
            )
        ]
    )
    
    payloads = await convert_innocody_to_memory_layer(
        response,
        use_llm_summary=False
    )
    
    assert len(payloads) == 1
    payload = payloads[0]
    
    assert payload["metadata"]["change_type"] == "removed"
    assert payload["metadata"]["lines_added"] == 0
    assert payload["metadata"]["lines_removed"] > 0


def test_mock_data_generation():
    """Test mock data generators"""
    # Single mock
    mock = generate_mock_innocody_response()
    assert isinstance(mock, InnocodyResponse)
    assert len(mock.chunks) > 0
    
    # Multiple examples
    examples = generate_mock_examples()
    assert len(examples) > 0
    
    for ex in examples:
        assert isinstance(ex, InnocodyResponse)
        assert len(ex.chunks) > 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
