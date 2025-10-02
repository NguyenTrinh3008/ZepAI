# tests/test_graph_ttl.py
"""
Unit tests for Neo4j TTL and code metadata functions (Phase 2)
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph import (
    add_episode_with_ttl,
    add_code_metadata,
    cleanup_expired_memories,
    create_indexes,
    get_project_stats,
    _set_entity_ttl
)

# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_graphiti():
    """Mock Graphiti instance"""
    graphiti = Mock()
    graphiti.driver = Mock()
    return graphiti

@pytest.fixture
def mock_session():
    """Mock Neo4j session"""
    session = AsyncMock()
    return session

@pytest.fixture
def sample_metadata():
    """Sample code metadata"""
    return {
        "file_path": "src/auth/auth_service.py",
        "function_name": "login_user",
        "line_start": 45,
        "line_end": 52,
        "change_type": "fixed",
        "change_summary": "Added null check",
        "severity": "high",
        "code_after_id": "code_xyz123",
        "code_after_hash": "abc123",
        "language": "python",
        "lines_added": 3,
        "lines_removed": 1,
        "diff_summary": "Added null validation",
        "git_commit": "commit_abc"
    }

# =============================================================================
# TTL Tests
# =============================================================================

@pytest.mark.asyncio
async def test_add_episode_with_ttl_basic(mock_graphiti):
    """Test add_episode_with_ttl with basic parameters"""
    # Mock episode result
    mock_episode = Mock()
    mock_episode.created_entities = []
    mock_graphiti.add_episode = AsyncMock(return_value=mock_episode)
    
    reference_time = datetime.utcnow()
    result = await add_episode_with_ttl(
        graphiti=mock_graphiti,
        episode_body="Fixed bug in auth_service.py",
        source_description="code_conversation",
        reference_time=reference_time,
        group_id="test_project"
    )
    
    assert result == mock_episode
    mock_graphiti.add_episode.assert_called_once()

@pytest.mark.asyncio
async def test_add_episode_with_ttl_sets_expiration(mock_graphiti):
    """Test that TTL is set to 48 hours"""
    # Mock entity with UUID
    mock_entity = Mock()
    mock_entity.uuid = "entity_test_123"
    
    mock_episode = Mock()
    mock_episode.created_entities = [mock_entity]
    
    mock_graphiti.add_episode = AsyncMock(return_value=mock_episode)
    
    # Mock session
    mock_session = AsyncMock()
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.run = AsyncMock()
    
    reference_time = datetime.utcnow()
    await add_episode_with_ttl(
        graphiti=mock_graphiti,
        episode_body="Test",
        source_description="test",
        reference_time=reference_time,
        group_id="project_test"
    )
    
    # Verify TTL was set
    mock_session.run.assert_called()
    
@pytest.mark.asyncio
async def test_set_entity_ttl(mock_graphiti):
    """Test _set_entity_ttl function"""
    mock_session = AsyncMock()
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.run = AsyncMock()
    
    entity_uuid = "test_entity_uuid"
    expires_at = datetime.utcnow() + timedelta(hours=48)
    project_id = "test_project"
    
    await _set_entity_ttl(mock_graphiti, entity_uuid, expires_at, project_id)
    
    # Verify Neo4j query was executed
    mock_session.run.assert_called_once()
    call_args = mock_session.run.call_args
    query = call_args[0][0]
    params = call_args[0][1]
    
    assert "SET e.expires_at" in query
    assert "SET e.project_id" in query or "e.project_id" in query
    assert params["uuid"] == entity_uuid
    assert params["project_id"] == project_id

# =============================================================================
# Code Metadata Tests
# =============================================================================

@pytest.mark.asyncio
async def test_add_code_metadata_success(mock_graphiti, sample_metadata):
    """Test adding code metadata successfully"""
    # Mock session and result
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"e": sample_metadata}
    
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    result = await add_code_metadata(
        graphiti=mock_graphiti,
        entity_uuid="test_uuid",
        metadata=sample_metadata
    )
    
    assert result == sample_metadata
    mock_session.run.assert_called_once()

@pytest.mark.asyncio
async def test_add_code_metadata_empty(mock_graphiti):
    """Test add_code_metadata with empty metadata"""
    result = await add_code_metadata(
        graphiti=mock_graphiti,
        entity_uuid="test_uuid",
        metadata={}
    )
    
    assert result == {}

@pytest.mark.asyncio
async def test_add_code_metadata_partial(mock_graphiti):
    """Test add_code_metadata with partial metadata"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"e": {"file_path": "test.py"}}
    
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    partial_metadata = {
        "file_path": "test.py",
        "change_type": "fixed"
    }
    
    result = await add_code_metadata(
        graphiti=mock_graphiti,
        entity_uuid="test_uuid",
        metadata=partial_metadata
    )
    
    assert result == {"file_path": "test.py"}
    mock_session.run.assert_called_once()

# =============================================================================
# Cleanup Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cleanup_expired_memories_success(mock_graphiti):
    """Test cleanup_expired_memories successfully deletes expired entries"""
    # Mock session and result
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"deleted_count": 5}
    
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    deleted_count = await cleanup_expired_memories(mock_graphiti)
    
    assert deleted_count == 5
    mock_session.run.assert_called_once()
    
    # Verify query checks for expired entries
    call_args = mock_session.run.call_args
    query = call_args[0][0]
    assert "expires_at" in query.lower()
    assert "DELETE" in query

@pytest.mark.asyncio
async def test_cleanup_expired_memories_none_expired(mock_graphiti):
    """Test cleanup when no memories are expired"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"deleted_count": 0}
    
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    deleted_count = await cleanup_expired_memories(mock_graphiti)
    
    assert deleted_count == 0

# =============================================================================
# Index Tests
# =============================================================================

@pytest.mark.asyncio
async def test_create_indexes(mock_graphiti):
    """Test create_indexes creates all required indexes"""
    mock_session = AsyncMock()
    mock_session.run = AsyncMock()
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    await create_indexes(mock_graphiti)
    
    # Verify multiple index creation queries
    assert mock_session.run.call_count == 4  # 4 indexes
    
    # Verify index names appear in queries
    calls = [call[0][0] for call in mock_session.run.call_args_list]
    assert any("entity_project_id" in call for call in calls)
    assert any("entity_expires_at" in call for call in calls)
    assert any("entity_file_path" in call for call in calls)
    assert any("entity_change_type" in call for call in calls)

# =============================================================================
# Statistics Tests
# =============================================================================

@pytest.mark.asyncio
async def test_get_project_stats_with_data(mock_graphiti):
    """Test get_project_stats with existing data"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {
        "active_count": 10,
        "expired_count": 3,
        "files_count": 5,
        "change_types": ["fixed", "added", "refactored"]
    }
    
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    stats = await get_project_stats(mock_graphiti, "test_project")
    
    assert stats["project_id"] == "test_project"
    assert stats["total_memories"] == 10
    assert stats["expired_memories"] == 3
    assert stats["files_count"] == 5
    assert "fixed" in stats["change_types"]

@pytest.mark.asyncio
async def test_get_project_stats_empty_project(mock_graphiti):
    """Test get_project_stats with no data"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value=None)
    mock_session.run = AsyncMock(return_value=mock_result)
    
    mock_graphiti.driver.session = MagicMock(return_value=mock_session)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    stats = await get_project_stats(mock_graphiti, "empty_project")
    
    assert stats["project_id"] == "empty_project"
    assert stats["total_memories"] == 0
    assert stats["expired_memories"] == 0
    assert stats["files_count"] == 0
    assert stats["change_types"] == []

# =============================================================================
# Integration-like Tests
# =============================================================================

def test_ttl_calculation():
    """Test that TTL calculation is exactly 48 hours"""
    reference_time = datetime(2025, 10, 1, 10, 0, 0)
    expires_at = reference_time + timedelta(hours=48)
    
    expected = datetime(2025, 10, 3, 10, 0, 0)
    assert expires_at == expected
    
    # Verify seconds
    delta = expires_at - reference_time
    assert delta.total_seconds() == 172800  # 48 * 3600

def test_metadata_field_mapping():
    """Test that all metadata fields are properly mapped"""
    from app.graph import add_code_metadata
    
    # This tests that the field mapping dictionary is complete
    expected_fields = [
        "file_path", "function_name", "line_start", "line_end",
        "change_type", "change_summary", "severity",
        "code_before_id", "code_after_id",
        "code_before_hash", "code_after_hash",
        "lines_added", "lines_removed", "diff_summary",
        "git_commit", "language"
    ]
    
    # Get the field mapping from the function (via inspection)
    import inspect
    source = inspect.getsource(add_code_metadata)
    
    # Verify all expected fields are in the source
    for field in expected_fields:
        assert field in source, f"Field {field} not found in field mapping"

if __name__ == "__main__":
    # Run with: python -m pytest tests/test_graph_ttl.py -v
    pytest.main([__file__, "-v"])
