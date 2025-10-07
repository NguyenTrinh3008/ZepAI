# -*- coding: utf-8 -*-
"""
Simple JSON Upload Script

Script đơn giản để upload short_term.json lên Graphiti
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def upload_json_file(file_path: str, project_id: str):
    """Upload JSON file với timeout dài hơn"""
    
    print(f"File: {file_path}")
    print(f"Size: {os.path.getsize(file_path)} bytes")
    print(f"Project ID: {project_id}")
    print("-" * 50)
    
    # Tăng timeout cho file lớn
    timeout = httpx.Timeout(300.0, read=300.0, write=60.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print("Starting upload...")
            
            # Đọc file để phân tích trước
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"ERROR: Invalid JSON format: {e}")
                    return False
            
            # Phân tích và tách theo conversation_id và code files
            conversations = {}  # {conversation_id: {code_files: [], regular_data: []}}
            code_files = []
            regular_data = data
            
            if isinstance(data, dict):
                if "code_files" in data:
                    # Format: {"code_files": [...]}
                    code_files = data.get("code_files", [])
                    regular_data = {k: v for k, v in data.items() if k != "code_files"}
                elif data.get("entity_type") in ["context_file", "code_file"]:
                    # Single code file object
                    code_files = [data]
                    regular_data = None
            elif isinstance(data, list):
                # List of objects - check each
                code_files = []
                regular_items = []
                for item in data:
                    if isinstance(item, dict) and item.get("entity_type") in ["context_file", "code_file"]:
                        code_files.append(item)
                    else:
                        regular_items.append(item)
                regular_data = regular_items if regular_items else None
            
            # Phân chia theo conversation_id
            if isinstance(regular_data, list):
                for item in regular_data:
                    if isinstance(item, dict):
                        conv_id = item.get("conversation_id") or item.get("group_id") or "default_conversation"
                        if conv_id not in conversations:
                            conversations[conv_id] = {"code_files": [], "regular_data": []}
                        conversations[conv_id]["regular_data"].append(item)
            elif isinstance(regular_data, dict):
                conv_id = regular_data.get("conversation_id") or regular_data.get("group_id") or "default_conversation"
                if conv_id not in conversations:
                    conversations[conv_id] = {"code_files": [], "regular_data": []}
                conversations[conv_id]["regular_data"].append(regular_data)
            
            # Phân chia code files theo conversation_id
            for cf in code_files:
                conv_id = cf.get("conversation_id") or cf.get("group_id") or "default_conversation"
                if conv_id not in conversations:
                    conversations[conv_id] = {"code_files": [], "regular_data": []}
                conversations[conv_id]["code_files"].append(cf)
            
            # Upload từng conversation riêng biệt
            total_code_files = 0
            total_episodes = 0
            successful_conversations = 0
            
            print(f"Found {len(conversations)} conversation(s) to process:")
            for conv_id, conv_data in conversations.items():
                print(f"  - {conv_id}: {len(conv_data['regular_data'])} messages, {len(conv_data['code_files'])} code files")
            
            print("\n" + "="*60)
            
            for conv_id, conv_data in conversations.items():
                print(f"\n🔄 Processing conversation: {conv_id}")
                print("-" * 40)
                
                conv_success = True
                
                # Upload code files cho conversation này
                if conv_data["code_files"]:
                    print(f"  📁 Uploading {len(conv_data['code_files'])} code file(s)...")
                    try:
                        # Cập nhật group_id = conversation_id cho code files
                        for cf in conv_data["code_files"]:
                            cf["group_id"] = conv_id
                        
                        code_payload = {"code_files": conv_data["code_files"]} if len(conv_data["code_files"]) > 1 else conv_data["code_files"][0]
                        code_response = await client.post(
                            f"{BASE_URL}/graph/import-code-json",
                            json=code_payload
                        )
                        if code_response.status_code == 200:
                            code_result = code_response.json()
                            files_uploaded = code_result.get("files", 0)
                            symbols_uploaded = code_result.get("symbols", 0)
                            total_code_files += files_uploaded
                            print(f"    ✓ Code files: {files_uploaded} files, {symbols_uploaded} symbols")
                        else:
                            print(f"    ⚠️ Code files failed: {code_response.status_code}")
                            conv_success = False
                    except Exception as e:
                        print(f"    ❌ Code files error: {e}")
                        conv_success = False
                
                # Upload regular data cho conversation này
                if conv_data["regular_data"]:
                    print(f"  💬 Uploading {len(conv_data['regular_data'])} message(s)...")
                    try:
                        # Tạo temporary JSON file cho conversation này
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
                            json.dump(conv_data["regular_data"], temp_file, ensure_ascii=False, indent=2)
                            temp_file_path = temp_file.name
                        
                        # Upload với conversation_id làm project_id
                        with open(temp_file_path, 'rb') as f:
                            files = {"file": (f"conversation_{conv_id}.json", f, "application/json")}
                            data = {
                                "project_id": conv_id,  # Sử dụng conversation_id làm project_id
                                "use_llm": "false"
                            }
                            
                            response = await client.post(
                                f"{BASE_URL}/upload/json-to-graph",
                                files=files,
                                data=data
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                episodes_created = result.get('episodes_created', 0)
                                total_episodes += episodes_created
                                print(f"    ✓ Episodes: {episodes_created} created")
                            else:
                                print(f"    ⚠️ Episodes failed: {response.status_code}")
                                conv_success = False
                        
                        # Cleanup temp file
                        os.unlink(temp_file_path)
                        
                    except Exception as e:
                        print(f"    ❌ Episodes error: {e}")
                        conv_success = False
                
                if conv_success:
                    successful_conversations += 1
                    print(f"  ✅ Conversation {conv_id} processed successfully")
                else:
                    print(f"  ❌ Conversation {conv_id} had errors")
            
            # Tóm tắt kết quả
            print("\n" + "="*60)
            print("📊 UPLOAD SUMMARY:")
            print(f"  Conversations processed: {successful_conversations}/{len(conversations)}")
            print(f"  Total code files: {total_code_files}")
            print(f"  Total episodes: {total_episodes}")
            print("="*60)
            
            return successful_conversations > 0
                    
    except httpx.TimeoutException:
        print("ERROR: Request timeout - file qua lon hoac xu ly lau")
        print("   Thu chia nho file hoac tang timeout")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def check_upload_result(project_id: str):
    """Kiểm tra kết quả upload"""
    
    print(f"\nChecking entities for project: {project_id}")
    print("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/graphiti/entities/stats")
            response.raise_for_status()
            stats = response.json()
            
            print("Entity Statistics:")
            total_stats = stats.get('total_stats', {})
            print(f"   Total entities: {total_stats.get('total_entities', 0)}")
            print(f"   Unique groups: {total_stats.get('unique_groups', 0)}")
            
            # Tim entities cua project nay
            by_group = stats.get('by_group', [])
            project_entities = 0
            for group in by_group:
                if project_id in group.get('group_id', ''):
                    project_entities += group.get('entity_count', 0)
                    print(f"   {group.get('group_id')}: {group.get('entity_count', 0)} entities")
            
            print(f"   Total for '{project_id}': {project_entities} entities")
            
            # Hien thi top entities
            top_entities = stats.get('top_entities', [])
            if top_entities:
                print(f"\nRecent entities:")
                for i, entity in enumerate(top_entities[:5], 1):
                    name = entity.get('name', 'Unknown')
                    group = entity.get('group_id', 'Unknown')
                    
                    if project_id in group:
                        print(f"   {i}. {name}")
                        summary = entity.get('summary', '')
                        if summary:
                            # Lam sach summary de tranh loi Unicode
                            summary_clean = summary.encode('ascii', 'ignore').decode('ascii')
                            if summary_clean:
                                print(f"      Summary: {summary_clean[:60]}...")
            
            return True
            
    except Exception as e:
        print(f"WARNING: Could not get entity stats: {e}")
        return False

async def main():
    """Main function"""
    print("JSON Upload to Graphiti")
    print("=" * 50)
    
    # Lấy tham số từ command line
    file_path = sys.argv[1] if len(sys.argv) > 1 else "short_term.json"
    project_id = sys.argv[2] if len(sys.argv) > 2 else "uploaded_stm"
    
    print(f"File: {file_path}")
    print(f"Project ID: {project_id}")
    print()
    
    # Kiem tra file ton tai
    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found!")
        return False
    
    # Upload file
    success = await upload_json_file(file_path, project_id)
    
    if success:
        # Kiem tra ket qua
        await check_upload_result(project_id)
        
        print("\n" + "=" * 50)
        print("Upload completed successfully!")
        print("\nNext steps:")
        print("   1. Check Neo4j browser to see created entities")
        print("   2. Use /search endpoint to query the knowledge graph")
        print("   3. Entities are now available for semantic search")
        print(f"   4. Project ID '{project_id}' contains your data")
    else:
        print("\nUpload failed!")
        print("\nTroubleshooting:")
        print("   1. Check if server is running: curl http://localhost:8000/")
        print("   2. Try with smaller file or increase timeout")
        print("   3. Check server logs for errors")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
