"""
Test Conversation Context Transformation - Phase 1.5
Test transformation và graph creation trước khi implement full endpoint
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.conversation_adapter import transform_innocody_to_conversation, calculate_hash


def test_basic_transformation():
    """Test 1: Basic transformation từ Innocody output"""
    print("\n" + "="*80)
    print("TEST 1: Basic Transformation")
    print("="*80)
    
    # Mock Innocody output
    innocody_output = {
        "chat_meta": {
            "chat_id": "chat_test_001",
            "base_chat_id": "chat_base_001",
            "request_attempt_id": "attempt_001",
            "chat_mode": "AGENT",
            "force_initial_state": False
        },
        "messages": [
            {
                "role": "user",
                "content": "Fix the null pointer bug in auth_service.py login_user function",
                "usage": {"prompt_tokens": 120}
            },
            {
                "role": "assistant",
                "content": "I'll add a null check before accessing user.token to prevent the AttributeError when token is None.",
                "usage": {
                    "prompt_tokens": 520,
                    "completion_tokens": 84,
                    "total_tokens": 604
                },
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "function": {
                            "name": "update_textdoc",
                            "arguments": '{"file": "src/auth/auth_service.py", "edits": [...]}'
                        }
                    }
                ]
            }
        ],
        "context": [
            {
                "file": "src/auth/auth_service.py",
                "lines": [45, 52],
                "usefulness": 0.92,
                "source": "vecdb",
                "symbols": ["login_user", "get_token"],
                "content": "def login_user(username):\n    user = get_user(username)\n    token = user.token\n    return token"
            },
            {
                "file": "docs/error_handling.md",
                "lines": [10, 30],
                "usefulness": 0.78,
                "source": "ast",
                "symbols": [],
                "content": "# Error Handling Best Practices\n\nAlways check for None..."
            }
        ],
        "tool_calls": [
            {
                "id": "call_abc123",
                "tool": "update_textdoc",
                "status": "success",
                "execution_time_ms": 1250,
                "diff_chunk_id": "diff_001"
            }
        ],
        "checkpoints": [
            {
                "id": "cp_test_001_0006",
                "parent": "cp_test_001_0005",
                "workspace_dir": "~/.innocody/cache/shadow_git"
            }
        ],
        "model_response": {
            "model": "gpt-4-turbo",
            "finish_reason": "stop",
            "created": 1730548858.41,
            "cached": False
        }
    }
    
    # Transform
    try:
        payload = transform_innocody_to_conversation(
            request_id="req_test_001",
            project_id="test_project",
            chat_meta=innocody_output['chat_meta'],
            messages=innocody_output['messages'],
            context_files=innocody_output.get('context'),
            tool_calls=innocody_output.get('tool_calls'),
            code_changes=[],
            checkpoints=innocody_output.get('checkpoints'),
            model_response=innocody_output.get('model_response')
        )
        
        print("✅ Transformation successful!")
        print(f"\nPayload summary:")
        print(f"  Request ID: {payload.request_id}")
        print(f"  Project ID: {payload.project_id}")
        print(f"  Chat ID: {payload.chat_meta.chat_id}")
        print(f"  Messages: {len(payload.messages)}")
        print(f"  Context Files: {len(payload.context_files)}")
        print(f"  Tool Calls: {len(payload.tool_calls)}")
        print(f"  Checkpoints: {len(payload.checkpoints)}")
        
        # Validate messages
        print(f"\n  Message Details:")
        for msg in payload.messages:
            print(f"    [{msg.sequence}] {msg.role}: {msg.content_summary[:60]}...")
            if msg.tool_calls:
                print(f"        Tools: {[tc['tool'] for tc in msg.tool_calls]}")
            if msg.total_tokens:
                print(f"        Tokens: {msg.total_tokens}")
        
        # Validate context files
        print(f"\n  Context File Details:")
        for cf in payload.context_files:
            print(f"    - {cf.file_path} (usefulness: {cf.usefulness}, source: {cf.source})")
            if cf.symbols:
                print(f"      Symbols: {cf.symbols}")
        
        # Save to file for manual inspection
        output_file = Path(__file__).parent / "test_output_conversation_payload.json"
        with open(output_file, 'w') as f:
            f.write(payload.model_dump_json(indent=2))
        print(f"\n💾 Full payload saved to: {output_file}")
        
        return payload
        
    except Exception as e:
        print(f"❌ Transformation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_hash_consistency():
    """Test 2: Hash consistency check"""
    print("\n" + "="*80)
    print("TEST 2: Hash Consistency")
    print("="*80)
    
    content1 = "def login_user(username):\n    user = get_user(username)\n    token = user.token"
    content2 = "def login_user(username):\n    user = get_user(username)\n    token = user.token"  # Same
    content3 = "def login_user(username):\n    user = get_user(username)\n    token = user.token if user else None"  # Different
    
    hash1 = calculate_hash(content1)
    hash2 = calculate_hash(content2)
    hash3 = calculate_hash(content3)
    
    print(f"Content 1 hash: {hash1}")
    print(f"Content 2 hash: {hash2}")
    print(f"Content 3 hash: {hash3}")
    
    assert hash1 == hash2, "Same content should have same hash"
    assert hash1 != hash3, "Different content should have different hash"
    
    print("✅ Hash consistency validated")


def generate_neo4j_queries(payload):
    """Test 3: Generate Neo4j queries for manual testing"""
    print("\n" + "="*80)
    print("TEST 3: Neo4j Query Generation")
    print("="*80)
    
    queries = []
    
    # Query 1: Create Request node
    request_query = f"""
// Create Request node
CREATE (r:Request {{
  request_id: "{payload.request_id}",
  project_id: "{payload.project_id}",
  chat_id: "{payload.chat_meta.chat_id}",
  chat_mode: "{payload.chat_meta.chat_mode}",
  timestamp: "{payload.timestamp}",
  model: "{payload.model_response.model if payload.model_response else 'unknown'}",
  total_tokens: {payload.messages[-1].total_tokens if payload.messages[-1].total_tokens else 0},
  expires_at: datetime("{payload.timestamp}") + duration('P2D')
}})
RETURN r.request_id as created
"""
    queries.append(("Create Request", request_query))
    
    # Query 2: Create Message nodes
    for msg in payload.messages:
        # Escape content summary
        escaped_summary = msg.content_summary[:100].replace('"', "'").replace('\n', ' ')
        
        message_query = f"""
// Create Message node (sequence {msg.sequence})
MATCH (r:Request {{request_id: "{payload.request_id}"}})
CREATE (m:Message {{
  message_id: "{payload.request_id}_msg_{msg.sequence}",
  request_id: "{payload.request_id}",
  role: "{msg.role}",
  content_summary: "{escaped_summary}",
  content_hash: "{msg.content_hash or 'none'}",
  sequence: {msg.sequence},
  prompt_tokens: {msg.prompt_tokens or 0},
  completion_tokens: {msg.completion_tokens or 0},
  total_tokens: {msg.total_tokens or 0},
  timestamp: "{payload.timestamp}",
  expires_at: datetime("{payload.timestamp}") + duration('P2D')
}})
CREATE (r)-[:CONTAINS_MESSAGE {{sequence: {msg.sequence}}}]->(m)
RETURN m.message_id as created
"""
        queries.append((f"Create Message {msg.sequence}", message_query))
    
    # Query 3: Create ContextFile nodes
    for idx, cf in enumerate(payload.context_files):
        context_query = f"""
// Create ContextFile node {idx + 1}
MATCH (r:Request {{request_id: "{payload.request_id}"}})
CREATE (cf:ContextFile {{
  context_id: "{payload.request_id}_ctx_{idx}",
  request_id: "{payload.request_id}",
  file_path: "{cf.file_path}",
  line_start: {cf.line_start},
  line_end: {cf.line_end or 'null'},
  usefulness: {cf.usefulness or 0.0},
  source: "{cf.source}",
  symbols: {json.dumps(cf.symbols)},
  content_hash: "{cf.content_hash}",
  language: "{cf.language or 'unknown'}",
  timestamp: "{payload.timestamp}",
  expires_at: datetime("{payload.timestamp}") + duration('P2D')
}})
CREATE (r)-[:USES_CONTEXT {{usefulness: {cf.usefulness or 0.0}}}]->(cf)
RETURN cf.context_id as created
"""
        queries.append((f"Create ContextFile {idx + 1}", context_query))
    
    # Query 4: Create ToolCall nodes
    for idx, tc in enumerate(payload.tool_calls):
        tool_query = f"""
// Create ToolCall node {idx + 1}
MATCH (r:Request {{request_id: "{payload.request_id}"}})
CREATE (tc:ToolCall {{
  tool_call_id: "{tc.tool_call_id}",
  request_id: "{payload.request_id}",
  tool_name: "{tc.tool_name}",
  arguments_hash: "{tc.arguments_hash}",
  status: "{tc.status}",
  execution_time_ms: {tc.execution_time_ms or 0},
  timestamp: "{payload.timestamp}",
  expires_at: datetime("{payload.timestamp}") + duration('P2D')
}})
CREATE (r)-[:INVOKES_TOOL]->(tc)
RETURN tc.tool_call_id as created
"""
        queries.append((f"Create ToolCall {idx + 1}", tool_query))
    
    # Save queries to file
    output_file = Path(__file__).parent / "test_output_neo4j_queries.cypher"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("// ============================================\n")
        f.write("// Neo4j Queries for Manual Testing\n")
        f.write("// Phase 1.5 - Conversation Context\n")
        f.write("// ============================================\n\n")
        
        for name, query in queries:
            f.write(f"// {name}\n")
            f.write(query)
            f.write("\n\n")
        
        # Add search queries
        f.write("// ============================================\n")
        f.write("// Search Queries\n")
        f.write("// ============================================\n\n")
        
        search_queries = [
            ("Full Conversation Flow", f"""
// Show complete conversation for request
MATCH (r:Request {{request_id: "{payload.request_id}"}})
OPTIONAL MATCH (r)-[:CONTAINS_MESSAGE]->(m:Message)
OPTIONAL MATCH (r)-[:USES_CONTEXT]->(cf:ContextFile)
OPTIONAL MATCH (r)-[:INVOKES_TOOL]->(tc:ToolCall)
RETURN r, m, cf, tc
ORDER BY m.sequence
"""),
            ("Context Attribution", f"""
// Which files influenced this request?
MATCH (r:Request {{request_id: "{payload.request_id}"}})
MATCH (r)-[:USES_CONTEXT]->(cf:ContextFile)
RETURN cf.file_path, cf.usefulness, cf.source, cf.symbols
ORDER BY cf.usefulness DESC
"""),
            ("Tool Execution Flow", f"""
// Tool calls and their results
MATCH (r:Request {{request_id: "{payload.request_id}"}})
MATCH (r)-[:INVOKES_TOOL]->(tc:ToolCall)
RETURN tc.tool_name, tc.status, tc.execution_time_ms
"""),
            ("Message Sequence", f"""
// Message flow with metadata
MATCH (r:Request {{request_id: "{payload.request_id}"}})
MATCH (r)-[:CONTAINS_MESSAGE]->(m:Message)
RETURN m.sequence, m.role, m.content_summary, m.total_tokens
ORDER BY m.sequence
""")
        ]
        
        for name, query in search_queries:
            f.write(f"// {name}\n")
            f.write(query)
            f.write("\n\n")
    
    print(f"✅ Generated {len(queries)} creation queries")
    print(f"✅ Generated {len(search_queries)} search queries")
    print(f"💾 Saved to: {output_file}")
    print(f"\n📋 Next steps:")
    print(f"   1. Open Neo4j Browser (http://localhost:7474)")
    print(f"   2. Copy queries from {output_file}")
    print(f"   3. Run creation queries first")
    print(f"   4. Run search queries to validate")


def test_search_scenarios():
    """Test 4: Generate search scenario queries"""
    print("\n" + "="*80)
    print("TEST 4: Search Scenario Queries")
    print("="*80)
    
    scenarios = [
        {
            "name": "Most Used Context Files",
            "description": "Which files are most frequently used as context?",
            "query": """
MATCH (r:Request)-[:USES_CONTEXT]->(cf:ContextFile)
WHERE r.project_id = 'test_project'
  AND r.timestamp > datetime() - duration('P7D')
RETURN cf.file_path, 
       count(*) as usage_count,
       avg(cf.usefulness) as avg_usefulness,
       collect(DISTINCT cf.source) as sources
ORDER BY usage_count DESC
LIMIT 10
"""
        },
        {
            "name": "Tool Success Rate",
            "description": "Success rate of each tool",
            "query": """
MATCH (tc:ToolCall)
WHERE tc.timestamp > datetime() - duration('P7D')
WITH tc.tool_name as tool,
     count(*) as total,
     sum(CASE WHEN tc.status = 'success' THEN 1 ELSE 0 END) as successes,
     avg(tc.execution_time_ms) as avg_time
RETURN tool, 
       total,
       successes,
       (successes * 100.0 / total) as success_rate,
       avg_time
ORDER BY total DESC
"""
        },
        {
            "name": "Context Source Effectiveness",
            "description": "VecDB vs AST - which provides better context?",
            "query": """
MATCH (cf:ContextFile)
WHERE cf.timestamp > datetime() - duration('P7D')
WITH cf.source as source,
     count(*) as usage_count,
     avg(cf.usefulness) as avg_usefulness
RETURN source, usage_count, avg_usefulness
ORDER BY avg_usefulness DESC
"""
        },
        {
            "name": "Conversation Timeline",
            "description": "Timeline of all requests in project",
            "query": """
MATCH (r:Request {project_id: 'test_project'})
OPTIONAL MATCH (r)-[:CONTAINS_MESSAGE]->(m:Message)
WITH r, count(m) as message_count
RETURN r.request_id, 
       r.timestamp, 
       r.chat_id,
       message_count,
       r.total_tokens
ORDER BY r.timestamp DESC
LIMIT 20
"""
        },
        {
            "name": "High Value Context Attribution",
            "description": "Which files are most useful (usefulness > 0.8)?",
            "query": """
MATCH (cf:ContextFile)
WHERE cf.usefulness > 0.8
  AND cf.timestamp > datetime() - duration('P7D')
RETURN cf.file_path,
       avg(cf.usefulness) as avg_usefulness,
       count(*) as usage_count,
       collect(DISTINCT cf.source) as sources
ORDER BY avg_usefulness DESC, usage_count DESC
LIMIT 10
"""
        }
    ]
    
    output_file = Path(__file__).parent / "test_output_search_scenarios.cypher"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("// ============================================\n")
        f.write("// Search Scenario Queries\n")
        f.write("// Use these to validate Phase 1.5 value\n")
        f.write("// ============================================\n\n")
        
        for scenario in scenarios:
            f.write(f"// Scenario: {scenario['name']}\n")
            f.write(f"// {scenario['description']}\n")
            f.write(scenario['query'])
            f.write("\n\n")
    
    print(f"✅ Generated {len(scenarios)} search scenarios")
    print(f"💾 Saved to: {output_file}")
    
    print(f"\n📊 Scenarios:")
    for idx, scenario in enumerate(scenarios, 1):
        print(f"   {idx}. {scenario['name']}")
        print(f"      → {scenario['description']}")


def main():
    """Run all tests"""
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "Phase 1.5 Test Suite - Conversation Context" + " "*15 + "║")
    print("╚" + "="*78 + "╝")
    
    # Test 1: Transformation
    payload = test_basic_transformation()
    if not payload:
        print("\n❌ Transformation failed - stopping tests")
        return
    
    # Test 2: Hash consistency
    test_hash_consistency()
    
    # Test 3: Generate Neo4j queries
    generate_neo4j_queries(payload)
    
    # Test 4: Search scenarios
    test_search_scenarios()
    
    print("\n" + "="*80)
    print("🎉 All Tests Complete!")
    print("="*80)
    print("\n📋 Next Steps:")
    print("   1. Review test_output_conversation_payload.json")
    print("   2. Run queries in test_output_neo4j_queries.cypher")
    print("   3. Test search scenarios in test_output_search_scenarios.cypher")
    print("   4. Validate that queries return expected results")
    print("   5. If valuable → Implement full endpoint")
    print("\n💡 To run queries:")
    print("   - Open Neo4j Browser: http://localhost:7474")
    print("   - Database: neo4j (default)")
    print("   - Copy-paste queries from generated files")


if __name__ == "__main__":
    main()
