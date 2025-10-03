# tests/test_ui_integration.py
"""
Quick test to verify Graphiti token tracking UI integration

Run this to check if everything is set up correctly.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from app.graphiti_token_tracker import GraphitiTokenTracker, get_global_tracker
        print("[OK] graphiti_token_tracker imports OK")
    except Exception as e:
        print(f"[FAIL] graphiti_token_tracker import failed: {e}")
        return False
    
    try:
        from app.graphiti_integration import create_tracked_graphiti, enable_global_openai_tracking
        print("[OK] graphiti_integration imports OK")
    except Exception as e:
        print(f"[FAIL] graphiti_integration import failed: {e}")
        return False
    
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ui"))
        from graphiti_token_ui import render_graphiti_token_tab, get_graphiti_tracker
        print("[OK] graphiti_token_ui imports OK")
    except Exception as e:
        print(f"[FAIL] graphiti_token_ui import failed: {e}")
        return False
    
    return True


def test_tracker_functionality():
    """Test basic tracker functionality"""
    print("\nTesting tracker functionality...")
    
    from app.graphiti_token_tracker import GraphitiTokenTracker
    
    tracker = GraphitiTokenTracker()
    
    # Test tracking
    tracker.set_episode_context("test_ep_001")
    tracker.track("entity_extraction", "gpt-4o-mini", 250, 80)
    tracker.track("fact_extraction", "gpt-4o-mini", 400, 120)
    tracker.clear_episode_context()
    
    # Verify data
    stats = tracker.get_total_stats()
    assert stats['total_calls'] == 2, "Should have 2 calls"
    assert stats['total_tokens'] == 850, "Should have 850 tokens (250+80+400+120)"
    assert stats['unique_episodes'] == 1, "Should have 1 episode"
    
    # Test episode summary
    ep_stats = tracker.get_episode_summary("test_ep_001")
    assert ep_stats['call_count'] == 2, "Episode should have 2 calls"
    
    # Test breakdown
    breakdown = tracker.get_operation_breakdown()
    assert 'entity_extraction' in breakdown, "Should have entity_extraction"
    assert 'fact_extraction' in breakdown, "Should have fact_extraction"
    
    print("[OK] Tracker functionality OK")
    return True


def test_ui_components():
    """Test that UI components can be instantiated"""
    print("\nTesting UI components...")
    
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ui"))
    
    try:
        from graphiti_token_ui import (
            display_graphiti_overview,
            display_operation_breakdown,
            display_episode_details,
            display_cost_projections,
            display_recent_calls,
            display_export_options
        )
        print("[OK] All UI components import OK")
        return True
    except Exception as e:
        print(f"[FAIL] UI components import failed: {e}")
        return False


def test_data_export():
    """Test export functionality"""
    print("\nTesting export functionality...")
    
    from app.graphiti_token_tracker import GraphitiTokenTracker
    import json
    import tempfile
    
    tracker = GraphitiTokenTracker()
    tracker.track("test_op", "gpt-4o-mini", 100, 50)
    
    # Test JSON export
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        tracker.export_to_json(temp_file)
        
        # Verify file was created and is valid JSON
        with open(temp_file, 'r') as f:
            data = json.load(f)
        
        assert 'total_stats' in data, "Should have total_stats"
        assert 'operation_breakdown' in data, "Should have operation_breakdown"
        assert 'history' in data, "Should have history"
        
        print("[OK] Export functionality OK")
        return True
    except Exception as e:
        print(f"[FAIL] Export failed: {e}")
        return False
    finally:
        # Cleanup
        import os
        if os.path.exists(temp_file):
            os.remove(temp_file)


def test_summary_text():
    """Test summary text generation"""
    print("\nTesting summary text generation...")
    
    from app.graphiti_token_tracker import GraphitiTokenTracker
    
    tracker = GraphitiTokenTracker()
    tracker.track("entity_extraction", "gpt-4o-mini", 250, 80, episode_id="ep1")
    tracker.track("fact_extraction", "gpt-4o-mini", 400, 120, episode_id="ep1")
    
    summary = tracker.get_summary_text()
    
    assert "Graphiti Token Usage Summary" in summary, "Should have title"
    assert "Total LLM Calls: 2" in summary, "Should show 2 calls"
    assert "entity_extraction" in summary.lower(), "Should mention entity_extraction"
    
    print("[OK] Summary text generation OK")
    return True


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("Graphiti Token Tracking UI Integration Tests")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Tracker Functionality", test_tracker_functionality),
        ("UI Components", test_ui_components),
        ("Data Export", test_data_export),
        ("Summary Text", test_summary_text),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Integration is working correctly.")
        return True
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please review.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

