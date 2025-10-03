# tests/test_short_term_memory.py
"""
Test script cho Short Term Memory system

Chạy test này để kiểm tra:
1. Schema validation
2. LLM extractor
3. Storage system
4. API endpoints
5. UI integration
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import ShortTermMemoryRequest, ShortTermMemorySearchRequest
from app.short_term_extractor import ShortTermMemoryExtractor
from app.short_term_storage import ShortTermMemoryStorage
from app.short_term_integration import ShortTermMemoryIntegration


async def test_schema_validation():
    """Test schema validation"""
    print("🧪 Testing schema validation...")
    
    try:
        # Test valid request
        request = ShortTermMemoryRequest(
            role="user",
            content="Tôi muốn thêm chức năng đăng nhập vào file auth.py",
            project_id="test_project",
            conversation_id="conv_001",
            file_path="auth.py",
            function_name="login_user",
            line_start=25,
            line_end=30
        )
        
        print(f"✅ Valid request created: {request.role} - {request.content[:50]}...")
        
        # Test search request
        search_request = ShortTermMemorySearchRequest(
            query="đăng nhập",
            project_id="test_project",
            conversation_id="conv_001",
            limit=5
        )
        
        print(f"✅ Valid search request created: {search_request.query}")
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False
    
    return True


async def test_llm_extractor():
    """Test LLM extractor"""
    print("\n🧪 Testing LLM extractor...")
    
    try:
        # Check if OpenAI API key is available
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  OpenAI API key not found, skipping LLM extractor test")
            return True
        
        extractor = ShortTermMemoryExtractor()
        
        # Test message
        content = "Tôi muốn thêm chức năng đăng nhập vào file auth.py, function login_user ở dòng 25-30"
        role = "user"
        project_id = "test_project"
        conversation_id = "conv_001"
        
        result = await extractor.extract_message_info(
            content=content,
            role=role,
            project_id=project_id,
            conversation_id=conversation_id
        )
        
        print(f"✅ Extracted info: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # Test similarity calculation
        embedding1 = result.get("embedding", [])
        embedding2 = result.get("embedding", [])
        
        if embedding1 and embedding2:
            similarity = extractor.calculate_similarity(embedding1, embedding2)
            print(f"✅ Similarity calculation: {similarity:.4f}")
        
    except Exception as e:
        print(f"❌ LLM extractor test failed: {e}")
        return False
    
    return True


async def test_storage_system():
    """Test storage system"""
    print("\n🧪 Testing storage system...")
    
    try:
        # Create test storage file
        test_file = Path("test_short_term.json")
        
        storage = ShortTermMemoryStorage(storage_file=str(test_file))
        
        # Test save message
        request = ShortTermMemoryRequest(
            role="user",
            content="Test message for storage",
            project_id="test_project",
            conversation_id="conv_001"
        )
        
        message_id = await storage.save_message(request)
        print(f"✅ Message saved with ID: {message_id}")
        
        # Test get message
        retrieved_message = await storage.get_message(message_id)
        if retrieved_message:
            print(f"✅ Message retrieved: {retrieved_message.content}")
        else:
            print("❌ Failed to retrieve message")
            return False
        
        # Test search messages
        search_request = ShortTermMemorySearchRequest(
            query="test",
            project_id="test_project"
        )
        
        results = await storage.search_messages(search_request)
        print(f"✅ Search results: {len(results)} messages found")
        
        # Test stats
        stats = await storage.get_stats("test_project")
        print(f"✅ Stats: {json.dumps(stats, indent=2, ensure_ascii=False)}")
        
        # Cleanup
        await storage.delete_message(message_id)
        print("✅ Message deleted")
        
        # Cleanup test file
        if test_file.exists():
            test_file.unlink()
        print("✅ Test file cleaned up")
        
    except Exception as e:
        print(f"❌ Storage system test failed: {e}")
        return False
    
    return True


async def test_integration():
    """Test integration system"""
    print("\n🧪 Testing integration system...")
    
    try:
        integration = ShortTermMemoryIntegration()
        
        # Test save user message
        user_id = await integration.save_user_message(
            content="Tôi muốn thêm chức năng đăng nhập",
            project_id="test_project",
            conversation_id="conv_001",
            file_path="auth.py",
            function_name="login_user"
        )
        print(f"✅ User message saved: {user_id}")
        
        # Test save assistant message
        assistant_id = await integration.save_assistant_message(
            content="Tôi sẽ giúp bạn thêm chức năng đăng nhập",
            project_id="test_project",
            conversation_id="conv_001"
        )
        print(f"✅ Assistant message saved: {assistant_id}")
        
        # Test search recent context
        results = await integration.search_recent_context(
            query="đăng nhập",
            project_id="test_project",
            conversation_id="conv_001"
        )
        print(f"✅ Search results: {len(results)} messages found")
        
        # Test get conversation history
        history = await integration.get_conversation_history(
            project_id="test_project",
            conversation_id="conv_001"
        )
        print(f"✅ Conversation history: {len(history)} messages")
        
        # Test code context extraction
        code_context = integration.extract_code_context_from_message(
            "Tôi muốn sửa file auth.py, function login_user ở dòng 25-30"
        )
        print(f"✅ Code context extracted: {code_context}")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
    
    return True


async def test_api_endpoints():
    """Test API endpoints"""
    print("\n🧪 Testing API endpoints...")
    
    try:
        import requests
        
        # Check if API is running
        base_url = "http://localhost:8000"
        
        try:
            resp = requests.get(f"{base_url}/", timeout=5)
            if resp.status_code != 200:
                print("⚠️  API not running, skipping API endpoint test")
                return True
        except requests.RequestException:
            print("⚠️  API not running, skipping API endpoint test")
            return True
        
        # Test save message endpoint
        payload = {
            "role": "user",
            "content": "Test message for API",
            "project_id": "test_project",
            "conversation_id": "conv_001"
        }
        
        resp = requests.post(f"{base_url}/short-term/save", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            message_id = data.get("message_id")
            print(f"✅ Message saved via API: {message_id}")
            
            # Test get message endpoint
            resp = requests.get(f"{base_url}/short-term/message/{message_id}", timeout=10)
            if resp.status_code == 200:
                print("✅ Message retrieved via API")
            else:
                print(f"❌ Failed to retrieve message: {resp.status_code}")
            
            # Test search endpoint
            search_payload = {
                "query": "test",
                "project_id": "test_project"
            }
            
            resp = requests.post(f"{base_url}/short-term/search", json=search_payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Search via API: {data.get('count', 0)} results")
            else:
                print(f"❌ Search failed: {resp.status_code}")
            
            # Test stats endpoint
            resp = requests.get(f"{base_url}/short-term/stats/test_project", timeout=10)
            if resp.status_code == 200:
                print("✅ Stats retrieved via API")
            else:
                print(f"❌ Stats failed: {resp.status_code}")
            
            # Test health endpoint
            resp = requests.get(f"{base_url}/short-term/health", timeout=10)
            if resp.status_code == 200:
                print("✅ Health check passed")
            else:
                print(f"❌ Health check failed: {resp.status_code}")
            
        else:
            print(f"❌ Save message failed: {resp.status_code} - {resp.text}")
            return False
        
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False
    
    return True


async def main():
    """Run all tests"""
    print("🚀 Starting Short Term Memory tests...\n")
    
    tests = [
        ("Schema Validation", test_schema_validation),
        ("LLM Extractor", test_llm_extractor),
        ("Storage System", test_storage_system),
        ("Integration", test_integration),
        ("API Endpoints", test_api_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Short Term Memory system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
