# examples/innocody_integration_examples.py
"""
Code examples để integrate Innocody với Memory Layer
"""

import asyncio
import requests
from typing import Dict, Any


# =============================================================================
# Example 1: Direct Webhook Call (Simplest)
# =============================================================================

def example_1_simple_webhook():
    """
    Cách đơn giản nhất: POST trực tiếp Innocody output
    """
    print("=" * 70)
    print("EXAMPLE 1: Simple Direct Webhook")
    print("=" * 70)
    
    # Innocody output (minimal)
    innocody_output = {
        "file_before": """def login_user(username, password):
    user = get_user(username)
    token = user.token
    return token""",
        
        "file_after": """def login_user(username, password):
    user = get_user(username)
    if user is None:
        raise ValueError("User not found")
    if user.token is None:
        raise ValueError("Token not available")
    token = user.token
    return token""",
        
        "chunks": [
            {
                "file_name": "src/auth/auth_service.py",
                "file_action": "edit",
                "line1": 2,
                "line2": 4,
                "lines_remove": "    user = get_user(username)\n    token = user.token\n    return token",
                "lines_add": "    user = get_user(username)\n    if user is None:\n        raise ValueError(\"User not found\")\n    if user.token is None:\n        raise ValueError(\"Token not available\")\n    token = user.token\n    return token"
            }
        ],
        
        "meta": {
            "project_id": "my_project"
        }
    }
    
    # Send to webhook
    try:
        response = requests.post(
            "http://localhost:8000/innocody/webhook",
            json=innocody_output,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"   Ingested: {result['ingested_count']} changes")
            print(f"   Summaries:")
            for summary in result['summaries']:
                print(f"     - {summary}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


# =============================================================================
# Example 2: Batch Webhook (Multiple Files)
# =============================================================================

def example_2_batch_webhook():
    """
    Batch processing: Gửi nhiều diffs cùng lúc
    """
    print("=" * 70)
    print("EXAMPLE 2: Batch Webhook (Multiple Files)")
    print("=" * 70)
    
    batch_payloads = [
        # File 1: Bug fix
        {
            "file_before": "def process_payment(amount):\n    charge(amount)",
            "file_after": "def process_payment(amount):\n    if amount <= 0:\n        raise ValueError('Invalid amount')\n    charge(amount)",
            "chunks": [{
                "file_name": "src/api/payment.py",
                "file_action": "edit",
                "line1": 1,
                "line2": 2,
                "lines_remove": "def process_payment(amount):\n    charge(amount)",
                "lines_add": "def process_payment(amount):\n    if amount <= 0:\n        raise ValueError('Invalid amount')\n    charge(amount)"
            }],
            "meta": {"project_id": "my_project"}
        },
        
        # File 2: New feature
        {
            "file_before": "",
            "file_after": "class RateLimiter:\n    def __init__(self):\n        self.max_requests = 100",
            "chunks": [{
                "file_name": "src/middleware/rate_limiter.py",
                "file_action": "add",
                "line1": 1,
                "line2": 3,
                "lines_remove": "",
                "lines_add": "class RateLimiter:\n    def __init__(self):\n        self.max_requests = 100"
            }],
            "meta": {"project_id": "my_project"}
        }
    ]
    
    try:
        response = requests.post(
            "http://localhost:8000/innocody/webhook/batch",
            json=batch_payloads,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"   Total payloads: {result['total_payloads']}")
            print(f"   Total chunks: {result['total_chunks']}")
            print(f"   Summaries:")
            for summary in result['summaries']:
                print(f"     - {summary}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


# =============================================================================
# Example 3: Using Python SDK (Advanced)
# =============================================================================

async def example_3_python_sdk():
    """
    Sử dụng Python SDK để convert trước khi send
    """
    print("=" * 70)
    print("EXAMPLE 3: Using Python SDK")
    print("=" * 70)
    
    from app.innocody_adapter import (
        InnocodyResponse,
        ChatMeta,
        convert_innocody_to_memory_layer
    )
    
    # Parse Innocody output
    innocody_data = {
        "file_before": "old code",
        "file_after": "new code",
        "chunks": [{
            "file_name": "test.py",
            "file_action": "edit",
            "line1": 1,
            "line2": 1,
            "lines_remove": "old code",
            "lines_add": "new code"
        }]
    }
    
    response = InnocodyResponse(**innocody_data)
    chat_meta = ChatMeta(project_id="sdk_test_project")
    
    # Convert to memory layer format
    payloads = await convert_innocody_to_memory_layer(
        response,
        chat_meta=chat_meta,
        use_llm_summary=False  # Dùng simple summary để test nhanh
    )
    
    print(f"Generated {len(payloads)} payloads:")
    for idx, payload in enumerate(payloads, 1):
        print(f"\nPayload {idx}:")
        print(f"  Name: {payload['name']}")
        print(f"  Summary: {payload['summary']}")
        print(f"  File: {payload['metadata']['file_path']}")
        print(f"  Change Type: {payload['metadata']['change_type']}")
        print(f"  Severity: {payload['metadata']['severity']}")
        print(f"  Lines +{payload['metadata']['lines_added']} -{payload['metadata']['lines_removed']}")
    
    # Optionally send to API
    # for payload in payloads:
    #     requests.post("http://localhost:8000/ingest/code-context", json=payload)
    
    print()


# =============================================================================
# Example 4: Mock Data Testing (No Innocody Required)
# =============================================================================

def example_4_mock_testing():
    """
    Test hệ thống với mock data (không cần Innocody)
    """
    print("=" * 70)
    print("EXAMPLE 4: Mock Data Testing")
    print("=" * 70)
    
    try:
        response = requests.post(
            "http://localhost:8000/innocody/test/mock",
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"   Status: {result['status']}")
            print(f"   Message: {result['message']}")
            
            if 'payload' in result:
                payload = result['payload']
                print(f"\n   Generated payload:")
                print(f"     Name: {payload['name']}")
                print(f"     File: {payload['metadata']['file_path']}")
                print(f"     Summary: {payload['summary'][:100]}...")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


# =============================================================================
# Example 5: Integration from Innocody (Pseudo-code)
# =============================================================================

def example_5_innocody_integration():
    """
    Pseudo-code: Làm sao integrate từ Innocody system
    """
    print("=" * 70)
    print("EXAMPLE 5: Innocody Integration Pattern")
    print("=" * 70)
    
    pseudo_code = """
# Trong Innocody system, sau khi process diff:

def handle_file_edit_completion(diff_result):
    '''Callback sau khi Innocody xử lý xong file edit'''
    
    # 1. Extract data từ Innocody
    payload = {
        "file_before": diff_result.file_before_content,
        "file_after": diff_result.file_after_content,
        "chunks": [
            {
                "file_name": chunk.file_name,
                "file_action": chunk.action,  # edit/add/remove
                "line1": chunk.start_line,
                "line2": chunk.end_line,
                "lines_remove": chunk.removed_text,
                "lines_add": chunk.added_text
            }
            for chunk in diff_result.chunks
        ],
        "meta": {
            "chat_id": current_chat.id,
            "project_id": current_project.id
        }
    }
    
    # 2. Send to Memory Layer (async recommended)
    try:
        response = requests.post(
            MEMORY_LAYER_WEBHOOK_URL,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Memory layer: Ingested {result['ingested_count']} changes")
        else:
            logger.error(f"Memory layer failed: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Memory layer error: {e}")
        # Continue - không block Innocody flow
    
    # 3. Continue với Innocody logic khác
    return diff_result
"""
    
    print(pseudo_code)
    print()


# =============================================================================
# Example 6: Search Code Memories After Ingest
# =============================================================================

def example_6_search_memories():
    """
    Search code memories sau khi đã ingest
    """
    print("=" * 70)
    print("EXAMPLE 6: Search Code Memories")
    print("=" * 70)
    
    # Search query
    search_payload = {
        "query": "authentication bug fixes",
        "project_id": "my_project",
        "days_ago": 7
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/search/code",
            json=search_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Found {result['count']} results:\n")
            
            for idx, item in enumerate(result['results'][:5], 1):
                print(f"{idx}. {item['text'][:100]}...")
                print(f"   File: {item.get('file_path', 'N/A')}")
                print(f"   Function: {item.get('function_name', 'N/A')}")
                print(f"   Type: {item.get('change_type', 'N/A')}")
                print(f"   Severity: {item.get('severity', 'N/A')}")
                print()
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


# =============================================================================
# Example 7: With Custom Severity Logic
# =============================================================================

async def example_7_custom_severity():
    """
    Override severity logic với custom rules
    """
    print("=" * 70)
    print("EXAMPLE 7: Custom Severity Logic")
    print("=" * 70)
    
    from app.innocody_adapter import (
        InnocodyResponse,
        convert_innocody_to_memory_layer,
        infer_severity
    )
    
    # Mock data
    innocody_data = {
        "file_before": "",
        "file_after": "# CRITICAL SECURITY FIX\nfixed_code_here",
        "chunks": [{
            "file_name": "src/api/important.py",
            "file_action": "edit",
            "line1": 1,
            "line2": 2,
            "lines_remove": "",
            "lines_add": "# CRITICAL SECURITY FIX\nfixed_code_here"
        }]
    }
    
    response = InnocodyResponse(**innocody_data)
    
    # Convert (sẽ dùng infer_severity() để tự động detect)
    payloads = await convert_innocody_to_memory_layer(
        response,
        use_llm_summary=False
    )
    
    print(f"Auto-detected severity: {payloads[0]['metadata']['severity']}")
    print()
    print("💡 To customize severity logic, edit infer_severity() in innocody_adapter.py")
    print()


# =============================================================================
# Run All Examples
# =============================================================================

async def run_all_examples():
    """Run tất cả examples"""
    print("\n" + "=" * 70)
    print("INNOCODY INTEGRATION EXAMPLES")
    print("=" * 70 + "\n")
    
    # Example 1: Simple webhook
    example_1_simple_webhook()
    
    # Example 2: Batch webhook
    example_2_batch_webhook()
    
    # Example 3: Python SDK
    await example_3_python_sdk()
    
    # Example 4: Mock testing
    example_4_mock_testing()
    
    # Example 5: Integration pattern
    example_5_innocody_integration()
    
    # Example 6: Search memories
    example_6_search_memories()
    
    # Example 7: Custom severity
    await example_7_custom_severity()
    
    print("=" * 70)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_all_examples())
