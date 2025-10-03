# examples/short_term_memory_demo.py
"""
Demo script cho Short Term Memory system

Chạy script này để xem cách sử dụng Short Term Memory:
1. Lưu messages với LLM analysis
2. Tìm kiếm semantic search
3. Quản lý conversation context
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.short_term_integration import ShortTermMemoryIntegration


async def demo_short_term_memory():
    """Demo Short Term Memory system"""
    print("🚀 Short Term Memory Demo")
    print("=" * 50)
    
    # Initialize integration
    integration = ShortTermMemoryIntegration()
    
    project_id = "demo_project"
    conversation_id = "demo_conversation"
    
    print(f"📁 Project ID: {project_id}")
    print(f"💬 Conversation ID: {conversation_id}")
    print()
    
    # Demo 1: Save user messages with different intents
    print("1️⃣ Saving User Messages...")
    print("-" * 30)
    
    user_messages = [
        {
            "content": "Xin chào! Tôi muốn học về Python programming",
            "context": "greeting + learning request"
        },
        {
            "content": "Tôi muốn thêm chức năng đăng nhập vào file auth.py, function login_user ở dòng 25-30",
            "context": "code modification request"
        },
        {
            "content": "Có lỗi gì trong function validate_email không?",
            "context": "bug investigation"
        },
        {
            "content": "Cảm ơn bạn đã giúp đỡ!",
            "context": "gratitude"
        }
    ]
    
    saved_messages = []
    
    for i, msg in enumerate(user_messages, 1):
        print(f"💬 User message {i}: {msg['content']}")
        print(f"   Context: {msg['context']}")
        
        # Extract code context
        code_context = integration.extract_code_context_from_message(msg['content'])
        
        # Save to short term memory
        message_id = await integration.save_user_message(
            content=msg['content'],
            project_id=project_id,
            conversation_id=conversation_id,
            **code_context
        )
        
        if message_id:
            saved_messages.append(message_id)
            print(f"   ✅ Saved with ID: {message_id[:8]}...")
        else:
            print(f"   ❌ Failed to save")
        
        print()
    
    # Demo 2: Save assistant responses
    print("2️⃣ Saving Assistant Responses...")
    print("-" * 30)
    
    assistant_messages = [
        "Xin chào! Tôi rất vui được giúp bạn học Python. Bạn muốn bắt đầu từ đâu?",
        "Tôi sẽ giúp bạn thêm chức năng đăng nhập. Trước tiên, hãy xem code hiện tại của function login_user trong file auth.py.",
        "Hãy để tôi kiểm tra function validate_email. Tôi thấy có thể có vấn đề với regex pattern ở dòng 15.",
        "Không có gì! Tôi rất vui được giúp đỡ bạn. Chúc bạn học tập tốt!"
    ]
    
    for i, msg in enumerate(assistant_messages, 1):
        print(f"🤖 Assistant response {i}: {msg}")
        
        # Save to short term memory
        message_id = await integration.save_assistant_message(
            content=msg,
            project_id=project_id,
            conversation_id=conversation_id
        )
        
        if message_id:
            saved_messages.append(message_id)
            print(f"   ✅ Saved with ID: {message_id[:8]}...")
        else:
            print(f"   ❌ Failed to save")
        
        print()
    
    # Demo 3: Search recent context
    print("3️⃣ Searching Recent Context...")
    print("-" * 30)
    
    search_queries = [
        "đăng nhập",
        "Python",
        "lỗi",
        "cảm ơn"
    ]
    
    for query in search_queries:
        print(f"🔍 Searching for: '{query}'")
        
        results = await integration.search_recent_context(
            query=query,
            project_id=project_id,
            conversation_id=conversation_id,
            limit=3
        )
        
        print(f"   Found {len(results)} relevant messages:")
        for j, result in enumerate(results, 1):
            similarity = result.get('similarity', 0)
            content = result.get('content', '')[:50]
            role = result.get('role', 'unknown')
            print(f"   {j}. [{role}] {content}... (similarity: {similarity:.3f})")
        
        print()
    
    # Demo 4: Get conversation history
    print("4️⃣ Getting Conversation History...")
    print("-" * 30)
    
    history = await integration.get_conversation_history(
        project_id=project_id,
        conversation_id=conversation_id,
        limit=10
    )
    
    print(f"📚 Conversation history ({len(history)} messages):")
    for i, msg in enumerate(history, 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')[:60]
        timestamp = msg.get('timestamp', 'unknown')
        print(f"   {i}. [{role}] {content}... ({timestamp})")
    
    print()
    
    # Demo 5: Show stats
    print("5️⃣ Short Term Memory Stats...")
    print("-" * 30)
    
    try:
        from app.short_term_storage import get_storage
        storage = get_storage()
        stats = await storage.get_stats(project_id)
        
        print(f"📊 Statistics for project '{project_id}':")
        print(f"   Total messages: {stats.get('total_messages', 0)}")
        print(f"   Cache loaded: {stats.get('cache_loaded', False)}")
        
        if stats.get('by_role'):
            print("   By role:")
            for role, count in stats['by_role'].items():
                print(f"     - {role}: {count}")
        
        if stats.get('by_intent'):
            print("   By intent:")
            for intent, count in stats['by_intent'].items():
                print(f"     - {intent}: {count}")
        
        if stats.get('by_conversation'):
            print("   By conversation:")
            for conv_id, count in stats['by_conversation'].items():
                print(f"     - {conv_id}: {count}")
        
    except Exception as e:
        print(f"   ❌ Error getting stats: {e}")
    
    print()
    
    # Demo 6: Code context extraction
    print("6️⃣ Code Context Extraction...")
    print("-" * 30)
    
    code_messages = [
        "Tôi muốn sửa file auth.py, function login_user ở dòng 25-30",
        "Có lỗi trong file utils.py, function validate_email ở dòng 15",
        "Thêm function send_email vào file notification.py",
        "Xóa function old_function trong file legacy.py từ dòng 100-120"
    ]
    
    for msg in code_messages:
        print(f"💻 Message: {msg}")
        context = integration.extract_code_context_from_message(msg)
        print(f"   Extracted context: {json.dumps(context, indent=2, ensure_ascii=False)}")
        print()
    
    print("🎉 Demo completed!")
    print(f"📝 Total messages saved: {len(saved_messages)}")
    print(f"💾 All messages are stored in: short_term.json")


async def demo_api_usage():
    """Demo API usage"""
    print("\n🌐 API Usage Demo")
    print("=" * 50)
    
    try:
        import requests
        
        base_url = "http://localhost:8000"
        
        # Check if API is running
        try:
            resp = requests.get(f"{base_url}/", timeout=5)
            if resp.status_code != 200:
                print("⚠️  API not running. Please start the API server first.")
                return
        except requests.RequestException:
            print("⚠️  API not running. Please start the API server first.")
            return
        
        print("✅ API is running!")
        
        # Demo save message
        print("\n1️⃣ Saving message via API...")
        payload = {
            "role": "user",
            "content": "Tôi muốn học về machine learning với Python",
            "project_id": "api_demo_project",
            "conversation_id": "api_demo_conv"
        }
        
        resp = requests.post(f"{base_url}/short-term/save", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            message_id = data.get("message_id")
            print(f"✅ Message saved: {message_id}")
            
            # Demo search
            print("\n2️⃣ Searching via API...")
            search_payload = {
                "query": "machine learning",
                "project_id": "api_demo_project"
            }
            
            resp = requests.post(f"{base_url}/short-term/search", json=search_payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Found {data.get('count', 0)} results")
                for result in data.get('results', [])[:3]:
                    content = result.get('content', '')[:50]
                    similarity = result.get('similarity', 0)
                    print(f"   - {content}... (similarity: {similarity:.3f})")
            
            # Demo stats
            print("\n3️⃣ Getting stats via API...")
            resp = requests.get(f"{base_url}/short-term/stats/api_demo_project", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                stats = data.get('stats', {})
                print(f"✅ Stats: {stats.get('total_messages', 0)} messages")
            
            # Demo health check
            print("\n4️⃣ Health check...")
            resp = requests.get(f"{base_url}/short-term/health", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Health: {data.get('status', 'unknown')}")
        
    except Exception as e:
        print(f"❌ API demo failed: {e}")


async def main():
    """Main demo function"""
    print("🎯 Short Term Memory System Demo")
    print("=" * 60)
    print()
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found in environment variables.")
        print("   Some features may not work properly.")
        print("   Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        print()
    
    # Run demos
    await demo_short_term_memory()
    await demo_api_usage()
    
    print("\n" + "=" * 60)
    print("🎉 Demo completed successfully!")
    print()
    print("Next steps:")
    print("1. Start the API server: python -m uvicorn app.main:app --reload")
    print("2. Start the UI: streamlit run ui/streamlit_app.py")
    print("3. Test the integration in the web interface")
    print("4. Check the Debug tab for short term memory stats")


if __name__ == "__main__":
    asyncio.run(main())
