# tests/test_schemas.py
"""
Unit tests for code context schemas
"""
import pytest
from datetime import datetime
from app.schemas import (
    CodeReference,
    CodeMetadata,
    IngestCodeContext,
    SearchCodeRequest
)

# =============================================================================
# CodeReference Tests
# =============================================================================

def test_code_reference_valid():
    """Test CodeReference with valid data"""
    ref = CodeReference(
        code_id="code_xyz123",
        code_hash="a3f5c8d2e9b1f4a7c6d8e2f3a4b5c6d7",
        language="python",
        line_count=10
    )
    assert ref.code_id == "code_xyz123"
    assert ref.language == "python"
    assert ref.line_count == 10

def test_code_reference_optional_line_count():
    """Test CodeReference with optional line_count"""
    ref = CodeReference(
        code_id="code_abc",
        code_hash="hash123",
        language="javascript"
    )
    assert ref.line_count is None

def test_code_reference_missing_required():
    """Test CodeReference fails without required fields"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        CodeReference(
            code_id="test",
            # Missing code_hash and language
        )

# =============================================================================
# CodeMetadata Tests
# =============================================================================

def test_code_metadata_minimal():
    """Test CodeMetadata with minimal required fields"""
    metadata = CodeMetadata(
        change_type="fixed",
        change_summary="Added null check",
        timestamp="2025-10-01T10:00:00Z"
    )
    assert metadata.change_type == "fixed"
    assert metadata.change_summary == "Added null check"
    assert metadata.file_path is None

def test_code_metadata_full():
    """Test CodeMetadata with all fields"""
    code_ref = CodeReference(
        code_id="code_123",
        code_hash="hash_abc",
        language="python",
        line_count=5
    )
    
    metadata = CodeMetadata(
        file_path="src/auth/auth_service.py",
        function_name="login_user",
        line_start=45,
        line_end=52,
        change_type="fixed",
        change_summary="Fixed null pointer bug",
        severity="high",
        code_before_ref=code_ref,
        code_after_ref=code_ref,
        lines_added=3,
        lines_removed=1,
        diff_summary="Added null check",
        git_commit="abc123def",
        timestamp="2025-10-01T10:00:00Z"
    )
    
    assert metadata.file_path == "src/auth/auth_service.py"
    assert metadata.function_name == "login_user"
    assert metadata.severity == "high"
    assert metadata.code_before_ref.code_id == "code_123"
    assert metadata.lines_added == 3

def test_code_metadata_change_types():
    """Test different change_type values"""
    change_types = ["modified", "fixed", "added", "refactored", "deleted"]
    
    for change_type in change_types:
        metadata = CodeMetadata(
            change_type=change_type,
            change_summary="Test change",
            timestamp="2025-10-01T10:00:00Z"
        )
        assert metadata.change_type == change_type

# =============================================================================
# IngestCodeContext Tests
# =============================================================================

def test_ingest_code_context_minimal():
    """Test IngestCodeContext with minimal data"""
    metadata = CodeMetadata(
        change_type="fixed",
        change_summary="Bug fix",
        timestamp="2025-10-01T10:00:00Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed bug",
        summary="Fixed null pointer bug in auth service",
        metadata=metadata,
        project_id="project_123"
    )
    
    assert ingest.name == "Fixed bug"
    assert ingest.project_id == "project_123"
    assert ingest.reference_time is None

def test_ingest_code_context_with_reference_time():
    """Test IngestCodeContext with reference_time"""
    metadata = CodeMetadata(
        change_type="added",
        change_summary="New feature",
        timestamp="2025-10-01T10:00:00Z"
    )
    
    ingest = IngestCodeContext(
        name="Added feature",
        summary="Added rate limiting middleware",
        metadata=metadata,
        project_id="project_abc",
        reference_time="2025-10-01T09:30:00Z"
    )
    
    assert ingest.reference_time == "2025-10-01T09:30:00Z"

def test_ingest_code_context_full_example():
    """Test IngestCodeContext with realistic full example"""
    code_before = CodeReference(
        code_id="code_original_xyz",
        code_hash="hash_before_123",
        language="python",
        line_count=5
    )
    
    code_after = CodeReference(
        code_id="code_fixed_abc",
        code_hash="hash_after_456",
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
        timestamp="2025-10-01T10:00:00Z"
    )
    
    ingest = IngestCodeContext(
        name="Fixed login null pointer bug",
        summary="Fixed critical null pointer exception in auth_service.py:login_user() function by adding null check before accessing user.token attribute. This prevents AttributeError when token is None.",
        metadata=metadata,
        project_id="project_auth_system"
    )
    
    assert ingest.name == "Fixed login null pointer bug"
    assert ingest.project_id == "project_auth_system"
    assert ingest.metadata.file_path == "src/auth/auth_service.py"
    assert ingest.metadata.code_before_ref.code_id == "code_original_xyz"
    assert ingest.metadata.lines_added == 3

# =============================================================================
# SearchCodeRequest Tests
# =============================================================================

def test_search_code_request_minimal():
    """Test SearchCodeRequest with minimal required fields"""
    search = SearchCodeRequest(
        query="authentication bug fix",
        project_id="project_123"
    )
    
    assert search.query == "authentication bug fix"
    assert search.project_id == "project_123"
    assert search.days_ago == 2  # Default value

def test_search_code_request_with_filters():
    """Test SearchCodeRequest with all filters"""
    search = SearchCodeRequest(
        query="null pointer fix",
        project_id="project_abc",
        file_filter="auth_service.py",
        function_filter="login_user",
        change_type_filter="fixed",
        days_ago=7,
        focal_node_uuid="node_xyz_123"
    )
    
    assert search.file_filter == "auth_service.py"
    assert search.function_filter == "login_user"
    assert search.change_type_filter == "fixed"
    assert search.days_ago == 7
    assert search.focal_node_uuid == "node_xyz_123"

def test_search_code_request_missing_project_id():
    """Test SearchCodeRequest fails without project_id"""
    with pytest.raises(Exception):  # Pydantic ValidationError
        SearchCodeRequest(
            query="test query"
            # Missing required project_id
        )

# =============================================================================
# Integration Tests
# =============================================================================

def test_nested_models():
    """Test that nested models work correctly"""
    # Create nested structure
    ref = CodeReference(
        code_id="nested_test",
        code_hash="hash_nested",
        language="python"
    )
    
    metadata = CodeMetadata(
        change_type="modified",
        change_summary="Nested test",
        timestamp="2025-10-01T10:00:00Z",
        code_after_ref=ref
    )
    
    ingest = IngestCodeContext(
        name="Test",
        summary="Testing nested models",
        metadata=metadata,
        project_id="test_project"
    )
    
    # Verify deep nesting works
    assert ingest.metadata.code_after_ref.code_id == "nested_test"
    assert ingest.metadata.code_after_ref.language == "python"

def test_model_dict_conversion():
    """Test that models can be converted to dict"""
    ref = CodeReference(
        code_id="dict_test",
        code_hash="hash_dict",
        language="javascript",
        line_count=20
    )
    
    # Convert to dict (Pydantic v2 uses model_dump())
    ref_dict = ref.model_dump()
    
    assert ref_dict["code_id"] == "dict_test"
    assert ref_dict["language"] == "javascript"
    assert ref_dict["line_count"] == 20

def test_model_json_conversion():
    """Test that models can be serialized to JSON"""
    metadata = CodeMetadata(
        file_path="test.py",
        change_type="added",
        change_summary="Test JSON",
        timestamp="2025-10-01T10:00:00Z"
    )
    
    # Serialize to JSON (Pydantic v2 uses model_dump_json())
    json_str = metadata.model_dump_json()
    
    assert "test.py" in json_str
    assert "added" in json_str

# =============================================================================
# Validation Tests
# =============================================================================

def test_timestamp_format():
    """Test that timestamps should be ISO8601 format"""
    # Note: Pydantic doesn't automatically validate ISO8601 for str fields
    # You may want to add custom validator if strict validation needed
    metadata = CodeMetadata(
        change_type="fixed",
        change_summary="Test timestamp",
        timestamp="2025-10-01T10:00:00Z"  # ISO8601
    )
    assert metadata.timestamp == "2025-10-01T10:00:00Z"
    
    # This will also pass (no automatic validation)
    metadata2 = CodeMetadata(
        change_type="fixed",
        change_summary="Test",
        timestamp="not-a-valid-timestamp"
    )
    assert metadata2.timestamp == "not-a-valid-timestamp"

def test_change_summary_length():
    """Test change_summary can handle various lengths"""
    # Short summary
    metadata = CodeMetadata(
        change_type="fixed",
        change_summary="Short",
        timestamp="2025-10-01T10:00:00Z"
    )
    assert len(metadata.change_summary) < 500
    
    # Long summary (up to 500 chars mentioned in docs)
    long_summary = "A" * 500
    metadata2 = CodeMetadata(
        change_type="fixed",
        change_summary=long_summary,
        timestamp="2025-10-01T10:00:00Z"
    )
    assert len(metadata2.change_summary) == 500
    
    # Very long summary (currently allowed, but may want to add max_length validator)
    very_long = "B" * 1000
    metadata3 = CodeMetadata(
        change_type="fixed",
        change_summary=very_long,
        timestamp="2025-10-01T10:00:00Z"
    )
    assert len(metadata3.change_summary) == 1000

if __name__ == "__main__":
    # Run with: python -m pytest tests/test_schemas.py -v
    pytest.main([__file__, "-v"])
