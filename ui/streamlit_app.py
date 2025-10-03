import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List

import requests
import streamlit as st
from dotenv import load_dotenv

# Add parent directory to path to import prompts module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.prompts import format_decision_prompt, format_system_prompt, format_summarization_prompt, PROMPT_CONFIG

# Import token tracker
from token_tracker import get_tracker, display_token_metrics, format_token_badge

# Import Graphiti token tracker UI
from graphiti_token_ui import render_graphiti_token_tab, display_graphiti_compact_metrics, get_graphiti_tracker

# Import short term memory integration
from app.short_term_integration import get_integration, save_chat_message

# Force reload to ensure latest version
import importlib
import app.short_term_integration
importlib.reload(app.short_term_integration)
from app.short_term_integration import get_integration, save_chat_message

# Load .env placed at memory_layer/.env so UI and API share config
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


def get_api_base_url() -> str:
    env_url = os.getenv("MEMORY_LAYER_API", "http://127.0.0.1:8000")
    return env_url.rstrip("/")


def post_json(path: str, payload: dict):
    base = get_api_base_url()
    url = f"{base}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as exc:
        return False, {"error": str(exc), "url": url}


def post_json_timeout(path: str, payload: dict, timeout_sec: int = 8):
    base = get_api_base_url()
    url = f"{base}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=timeout_sec)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as exc:
        return False, {"error": str(exc), "url": url}


def save_to_short_term_memory(role: str, content: str, project_id: str, conversation_id: str, **kwargs):
    """
    Helper function để lưu message vào short term memory
    
    Args:
        role: "user", "assistant", "system"
        content: Nội dung message
        project_id: ID dự án
        conversation_id: ID cuộc trò chuyện
        **kwargs: Các tham số khác (file_path, function_name, etc.)
    """
    try:
        # Sử dụng asyncio để chạy async function
        import asyncio
        
        # Tạo event loop nếu chưa có
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Chạy async function
        message_id = loop.run_until_complete(
            save_chat_message(role, content, project_id, conversation_id, **kwargs)
        )
        
        if message_id:
            st.session_state.setdefault("short_term_saved", []).append({
                "role": role,
                "message_id": message_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        return message_id
        
    except Exception as e:
        st.error(f"Error saving to short term memory: {e}")
        return None


def extract_code_context_from_message(content: str):
    """
    Trích xuất thông tin code context từ message content
    
    Args:
        content: Nội dung message
        
        Returns:
            Dict chứa file_path, function_name, line_start, line_end, code_changes
            - line_start/line_end: Vị trí dòng nơi code changes được thêm vào
    """
    import re
    
    code_info = {
        "file_path": None,
        "function_name": None,
        "line_start": None,
        "line_end": None,
        "code_changes": None
    }
    
    try:
        # Tìm file path patterns
        file_patterns = [
            r'file\s+([^\s]+\.(py|js|ts|java|cpp|c|h|html|css|json|yaml|yml|xml|md|txt))',
            r'([^\s]+\.(py|js|ts|java|cpp|c|h|html|css|json|yaml|yml|xml|md|txt))',
            r'path\s+([^\s]+)',
            r'đường\s+dẫn\s+([^\s]+)'
        ]
        
        for pattern in file_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code_info["file_path"] = match.group(1)
                break
        
        # Tìm function name patterns
        function_patterns = [
            r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
            r'hàm\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        for pattern in function_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code_info["function_name"] = match.group(1)
                break
        
        # Tìm line number patterns
        line_patterns = [
            r'dòng\s+(\d+)',
            r'line\s+(\d+)',
            r'(\d+)\s*dòng',
            r'(\d+)\s*line'
        ]
        
        for pattern in line_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                line_num = int(match.group(1))
                code_info["line_start"] = line_num
                code_info["line_end"] = line_num
                break
        
        # Tìm range patterns
        range_patterns = [
            r'dòng\s+(\d+)\s*-\s*(\d+)',
            r'line\s+(\d+)\s*-\s*(\d+)',
            r'(\d+)\s*-\s*(\d+)\s*dòng',
            r'(\d+)\s*-\s*(\d+)\s*line'
        ]
        
        for pattern in range_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code_info["line_start"] = int(match.group(1))
                code_info["line_end"] = int(match.group(2))
                break
        
        # Phát hiện code changes (AI đã chỉnh sửa code)
        code_change_patterns = [
            r'```(\w+)?\n(.*?)\n```',  # Code blocks
            r'đã thêm\s+(.*?)(?:\n|$)',  # "đã thêm ..."
            r'đã sửa\s+(.*?)(?:\n|$)',   # "đã sửa ..."
            r'đã xóa\s+(.*?)(?:\n|$)',   # "đã xóa ..."
            r'đã refactor\s+(.*?)(?:\n|$)',  # "đã refactor ..."
            r'da them\s+(.*?)(?:\n|$)',  # "da them ..."
            r'da sua\s+(.*?)(?:\n|$)',   # "da sua ..."
            r'da xoa\s+(.*?)(?:\n|$)',   # "da xoa ..."
            r'da refactor\s+(.*?)(?:\n|$)',  # "da refactor ..."
        ]
        
        for pattern in code_change_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                # Tạo code_changes object
                code_changes = {
                    "change_type": "modified",  # Default
                    "description": "Code changes detected",
                    "code_blocks": []
                }
                
                for match in matches:
                    if isinstance(match, tuple):
                        language, code = match
                        code_changes["code_blocks"].append({
                            "language": language or "text",
                            "code": code.strip()
                        })
                    else:
                        code_changes["code_blocks"].append({
                            "language": "text",
                            "code": match.strip()
                        })
                
                # Xác định change_type dựa trên keywords
                if any(word in content.lower() for word in ['thêm', 'them', 'added', 'add']):
                    code_changes["change_type"] = "added"
                elif any(word in content.lower() for word in ['xóa', 'xoa', 'deleted', 'delete', 'remove']):
                    code_changes["change_type"] = "deleted"
                elif any(word in content.lower() for word in ['refactor', 'refactored']):
                    code_changes["change_type"] = "refactored"
                
                code_info["code_changes"] = code_changes
                break
        
        return code_info
        
    except Exception as e:
        st.error(f"Error extracting code context: {e}")
        return code_info


def get_json(path: str):
    """GET request to API"""
    base = get_api_base_url()
    url = f"{base}{path}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return True, resp.json()
    except requests.RequestException as exc:
        return False, {"error": str(exc), "url": url}


st.set_page_config(page_title="Graphiti Memory Layer UI", page_icon="🧠", layout="centered")
st.title("🧠 Graphiti Memory Layer - Demo UI")
st.caption("Chat, ingest episodes and run search against the FastAPI server")

api_base = get_api_base_url()
st.info(f"API base: {api_base}")

# Initialize token trackers
tracker = get_tracker()
graphiti_tracker = get_graphiti_tracker()

tabs = st.tabs(["Chat", "Ingest", "Search", "Cache", "Token Usage", "Graphiti Tokens", "Debug"])

# ---------------------------- Chat Tab ----------------------------
with tabs[0]:
    st.subheader("Chat with Memory")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # list of {role, content}

    # Initialize session states first
    if "group_id" not in st.session_state:
        import uuid
        st.session_state.group_id = f"chat-{uuid.uuid4()}"
    
    # Buffers for grouped ingest
    if "mem_buffer" not in st.session_state:
        st.session_state.mem_buffer = []  # list[str] lines "role: content"
    if "mem_user_count" not in st.session_state:
        st.session_state.mem_user_count = 0

    # Create chat container (displays at top, messages scroll)
    chat_container = st.container()
    
    # --- Settings and Controls (rendered first but display at bottom) ---
    st.markdown("---")  # Divider
    
    # Settings row
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        chat_name = st.text_input("Conversation name", value=st.session_state.get("chat_name", "agent_chat"), key="chat_name_input")
        st.session_state.chat_name = chat_name
    with col2:
        auto_save = st.checkbox("Auto-save turns", value=st.session_state.get("auto_save", True), key="auto_save_cb")
        st.session_state.auto_save = auto_save
    with col3:
        show_memories = st.checkbox("Show related memories", value=st.session_state.get("show_memories", True), key="show_mem_cb")
        st.session_state.show_memories = show_memories
    
    # Short term memory controls
    col4, col5, col6 = st.columns([1, 1, 1])
    with col4:
        enable_short_term = st.checkbox("Enable Short Term Memory", value=st.session_state.get("enable_short_term_memory", True), key="short_term_cb",
                                      help="Automatically save messages to short term memory with LLM analysis")
        st.session_state.enable_short_term_memory = enable_short_term
    with col5:
        project_id = st.text_input("Project ID", value=st.session_state.get("project_id", "default_project"), key="project_id_input",
                                 help="Project identifier for short term memory")
        st.session_state.project_id = project_id
    with col6:
        if st.button("View Short Term Stats", key="short_term_stats_btn"):
            st.session_state.show_short_term_stats = True

    col4, col5, col6 = st.columns([1, 1, 1])
    with col4:
        pause_saving = st.checkbox("Pause saving to KG", value=st.session_state.get("pause_saving", False), key="pause_cb")
        st.session_state.pause_saving = pause_saving
    with col5:
        ingest_every_n_user_turns = st.selectbox("Mid-term: Ingest every N turns", [1, 2, 3, 5, 10], index=3, key="ingest_n_select",
                                                   help="N=1: Save each turn. N≥2: Summarize N turns into 1 fact")
        st.session_state.ingest_every_n = ingest_every_n_user_turns
    with col6:
        short_term_window = st.selectbox("Short-term: Keep last N turns", [3, 5, 10, 20], index=1, key="short_term_select",
                                          help="Number of recent conversation turns to keep as context")
        st.session_state.short_term_window = short_term_window
    
    # Token breakdown toggle
    col7_token = st.columns(1)[0]
    with col7_token:
        show_token_breakdown = st.checkbox("Show token breakdown (In/Out)", value=st.session_state.get("show_token_breakdown", False), key="token_breakdown_cb",
                                          help="Show detailed Input/Output token breakdown for each message")
        st.session_state.show_token_breakdown = show_token_breakdown
    
    col7, col8, col9 = st.columns([1, 1, 1])
    with col7:
        if st.button("Clear conversation", key="clear_btn"):
            st.session_state.chat_messages = []
            st.session_state.mem_buffer = []
            st.session_state.mem_user_count = 0
            # Auto-generate new group_id when clearing conversation
            import uuid
            st.session_state.group_id = f"chat-{uuid.uuid4()}"
            st.success(f"Conversation cleared. New group_id: {st.session_state.group_id}")
            st.rerun()

    # Info about current memory configuration
    current_n = st.session_state.get("ingest_every_n", 5)
    current_window = st.session_state.get("short_term_window", 5)
    
    st.markdown("### 🧠 Memory Configuration")
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    with col_info1:
        if current_n == 1:
            st.info("💾 **Mid-term:** Direct save - Each turn → KG immediately")
        else:
            st.info(f"📝 **Mid-term:** Every {current_n} turns → Summarize → KG")
    with col_info2:
        st.info(f"⚡ **Short-term:** Last {current_window} turns kept as context")
    with col_info3:
        # Display token usage for CURRENT conversation only
        current_group_id = st.session_state.get("group_id")
        if tracker.usage_history and current_group_id:
            totals = tracker.get_total_tokens(group_id=current_group_id)
            cost = tracker.get_total_cost(group_id=current_group_id)
            st.info(f"🔢 **This Chat:** {totals['total_tokens']:,}\n\n"
                   f"↗️ In: {totals['prompt_tokens']:,} | ↘️ Out: {totals['completion_tokens']:,}\n\n"
                   f"💰 **Cost:** ${cost:.4f}")
        else:
            st.info("🔢 **This Chat:** 0\n\nNo usage yet")
    with col_info4:
        # Display Graphiti token usage (if any)
        display_graphiti_compact_metrics(graphiti_tracker)

    # Group ID Management
    st.markdown("### 🔑 Conversation Group ID")
    
    col_gid1, col_gid2 = st.columns([3, 1])
    with col_gid1:
        # Text input to manually set group_id
        manual_group_id = st.text_input(
            "Group ID (để tiếp tục chat cũ, paste group_id cũ vào đây)",
            value=st.session_state.group_id,
            key="manual_group_id_input",
            help="Copy group_id từ conversation cũ để truy cập memories của nó"
        )
        
        # Update session state if user changes it
        if manual_group_id != st.session_state.group_id:
            # Warn if there are unsaved messages
            if st.session_state.chat_messages:
                st.warning("⚠️ **Warning:** Bạn đang có messages trong chat hiện tại!")
                st.info("💡 **Lưu ý:** Memories mới sẽ được lưu vào group_id mới này. Messages cũ (nếu chưa save) có thể bị mất.")
            
            st.session_state.group_id = manual_group_id
            st.session_state.mem_buffer = []
            st.session_state.mem_user_count = 0
            st.success(f"✓ Switched to group_id: {manual_group_id}")
            st.info("💡 Tất cả memories mới sẽ được lưu vào conversation này!")
    
    with col_gid2:
        # Button to generate new group_id
        if st.button("New Chat", key="regen_btn"):
            import uuid
            new_group_id = f"chat-{uuid.uuid4()}"
            st.session_state.group_id = new_group_id
            st.session_state.mem_buffer = []
            st.session_state.mem_user_count = 0
            st.session_state.chat_messages = []  # Also clear messages
            st.success(f"New conversation started!")
            st.rerun()
    
    # Copy button helper
    st.caption(f"💡 **Tip:** Copy group_id này để tiếp tục conversation sau khi reload page")
    st.code(st.session_state.group_id, language=None)
    
    # Export button
    st.markdown("### 💾 Export Conversation")
    if st.button("📥 Export to JSON", key="export_btn"):
        import json
        success, data = get_json(f"/export/{st.session_state.group_id}")
        if success:
            # Create download link
            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="💾 Download JSON",
                data=json_str,
                file_name=f"conversation_{st.session_state.group_id}.json",
                mime="application/json",
                key="download_json"
            )
            st.success(f"✓ Exported {data.get('entity_count', 0)} entities")
            st.info(f"💡 File contains all facts and entities from this conversation")
        else:
            st.error(f"Export failed: {data}")

    # OpenAI config
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("MODEL_NAME", "gpt-4.1-mini")

    # Process user input if exists (will be rendered at bottom)
    user_input = st.session_state.get("_pending_input", None)
    if user_input:
        # Clear pending input
        st.session_state.pop("_pending_input", None)
        # Get current config values
        chat_name = st.session_state.get("chat_name", "agent_chat")
        auto_save = st.session_state.get("auto_save", True)
        show_memories = st.session_state.get("show_memories", True)
        pause_saving = st.session_state.get("pause_saving", False)
        ingest_every_n_user_turns = st.session_state.get("ingest_every_n", 2)
        
        # Auto-determine if should summarize based on N
        summarize_to_memory = (ingest_every_n_user_turns > 1)
        
        # Append user message locally (no tokens yet)
        st.session_state.chat_messages.append({
            "role": "user", 
            "content": user_input,
            "token_usage": None  # User messages don't consume tokens
        })
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Save user message to short term memory
        if st.session_state.get("enable_short_term_memory", True):
            try:
                # Check if this is a file upload message
                uploaded_file = st.session_state.get("uploaded_file")
                if uploaded_file and ("Please analyze this file:" in user_input or 
                                    "Please review and fix any issues in this file:" in user_input or 
                                    "Please improve this code:" in user_input or
                                    "Please work on this file:" in user_input or
                                    "Please add comprehensive error handling to this file:" in user_input or
                                    "Please optimize the performance of this file:" in user_input or
                                    "Please add comprehensive documentation and comments to this file:" in user_input):
                    # This is a file upload message, save file to short term memory
                    try:
                        base = get_api_base_url()
                        project_id = st.session_state.get("project_id", "default_project")
                        conversation_id = st.session_state.group_id
                        
                        # Upload file to API
                        files = {'file': (uploaded_file["name"], uploaded_file["content"], 'text/plain')}
                        data = {
                            'project_id': project_id,
                            'conversation_id': conversation_id,
                            'role': 'user',
                            'content': f'Uploaded file: {uploaded_file["name"]}',
                            'change_type': 'modified',
                            'description': 'File uploaded for AI analysis'
                        }
                        
                        response = requests.post(f"{base}/upload/file", files=files, data=data, timeout=30)
                        response.raise_for_status()
                        result = response.json()
                        
                        if result.get("status") == "success":
                            st.caption(f"📁 File uploaded to short term memory: {result['result']['message_id'][:8]}...")
                            
                            # Show file analysis
                            analysis = result['result']['file_analysis']
                            st.caption(f"📊 File analysis: {analysis.get('total_lines', 0)} lines, {len(analysis.get('functions', []))} functions, {len(analysis.get('classes', []))} classes")
                        else:
                            st.error(f"Failed to upload file: {result.get('message', 'Unknown error')}")
                            st.caption(f"🔍 Debug: Full upload result = {result}")
                            
                    except Exception as e:
                        st.error(f"Error uploading file to short term memory: {e}")
                    
                    # Keep uploaded file in session state so assistant reply can diff against it
                    # st.session_state.pop("uploaded_file", None)
                
                # Extract code context from user input
                code_context = extract_code_context_from_message(user_input)
                
                # Save to short term memory
                message_id = save_to_short_term_memory(
                    role="user",
                    content=user_input,
                    project_id=st.session_state.get("project_id", "default_project"),
                    conversation_id=st.session_state.group_id,
                    **code_context
                )
                
                if message_id:
                    st.caption(f"💾 Saved to short term memory: {message_id[:8]}...")
                else:
                    st.caption("⚠️ Failed to save user message to short term memory")
                    
            except Exception as e:
                st.error(f"Error saving user message to short term memory: {e}")

        # Save this user turn
        if auto_save and not pause_saving and not summarize_to_memory:
            # Optional: Translate to English for consistent entity summaries
            message_for_kg = user_input
            if st.session_state.get("normalize_language_to_english", False):
                # Translation would happen here
                # message_for_kg = translate_to_english(user_input)
                pass
            
            lines = [f"user: {message_for_kg}"]
            payload = {
                "name": chat_name,
                "messages": lines,
                "reference_time": datetime.utcnow().isoformat(),
                "source_description": "chat",
                "group_id": st.session_state.group_id,
            }
            post_json_timeout("/ingest/message", payload, timeout_sec=5)

        # Always add to grouped buffer when summarization is on
        if summarize_to_memory:
            st.session_state.mem_buffer.append(f"user: {user_input}")
            st.session_state.mem_user_count += 1
            
            # Debug: Show progress to KG ingest
            turns_remaining = ingest_every_n_user_turns - st.session_state.mem_user_count
            if show_memories:
                if turns_remaining > 0:
                    st.caption(f"🔄 Progress: {st.session_state.mem_user_count}/{ingest_every_n_user_turns} turns (ingest in {turns_remaining} more turns)")
                else:
                    st.caption(f"⚡ Triggering KG ingest now! ({st.session_state.mem_user_count}/{ingest_every_n_user_turns} turns reached)")

        # Decide whether to query KG (LLM-only decision when key is set)
        wants_kg = False
        results = []
        search_data = None

        if openai_key:
            # Ask LLM to decide if KG is needed
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                decision_prompt = format_decision_prompt(user_input)
                decision_config = PROMPT_CONFIG.get("decision", {})
                
                decision = client.chat.completions.create(
                    model=openai_model,
                    messages=[{"role": "user", "content": decision_prompt}],
                    temperature=decision_config.get("temperature", 0.0),
                    max_tokens=decision_config.get("max_tokens", 10),
                )
                wants_kg = decision.choices[0].message.content.strip().upper().startswith("Y")
                
                # Track token usage for decision
                decision_usage = tracker.track_from_response(
                    operation="decision",
                    response=decision,
                    group_id=st.session_state.group_id,
                    metadata={
                        "query": user_input[:50],
                        "result": "YES" if wants_kg else "NO"
                    }
                )
                
                # Display decision tokens (optional, only in debug mode)
                if show_memories and decision_usage and wants_kg:
                    st.caption(f"🔍 Decision: Query KG → {decision_usage.total_tokens} tokens")
            except Exception:
                pass

        if wants_kg:
            ok_search, search_data = post_json_timeout("/search", {
                "query": user_input, 
                "focal_node_uuid": None,
                "group_id": st.session_state.group_id  # Filter by current conversation
            }, timeout_sec=10)
            if ok_search and isinstance(search_data, dict):
                results = search_data.get("results", []) or []
            if show_memories and search_data is not None:
                with st.expander("Related memories", expanded=False):
                    st.json(search_data)

        # Generate assistant reply (normal convo; ground with KG only if used)
        assistant_reply = None
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                
                # Short-term memory: Keep only last N turns (default: 5)
                # This creates a sliding window of recent context
                short_term_window = st.session_state.get("short_term_window", 5)
                all_messages = st.session_state.chat_messages
                
                if len(all_messages) > short_term_window * 2:  # *2 for user+assistant pairs
                    # Keep last N user-assistant pairs
                    history = all_messages[-(short_term_window * 2):]
                else:
                    history = all_messages
                
                history = [{"role": m["role"], "content": m["content"]} for m in history]
                
                # Build facts list from KG results (mid-term memory)
                top_facts = []
                if results:
                    for r in results[:8]:
                        if isinstance(r, dict):
                            txt = r.get("text") or r.get("fact") or r.get("name") or str(r)
                        else:
                            txt = str(r)
                        top_facts.append(txt)
                
                # Format system prompt with memories
                system_content = format_system_prompt(top_facts if top_facts else None)
                chat_config = PROMPT_CONFIG.get("chat", {})
                
                # Debug: Show current config and memory usage
                if show_memories:
                    st.info(f"🔧 LLM Config: max_tokens={chat_config.get('max_tokens', 5000)}, temp={chat_config.get('temperature', 0.7)}")
                    st.caption(f"⚡ Short-term: Using last {len(history)} messages ({len(history)//2} turns)")
                    
                    if top_facts:
                        st.caption(f"📝 Mid-term: {len(top_facts)} facts from KG")
                        with st.expander("📝 Facts injected into prompt", expanded=False):
                            for i, fact in enumerate(top_facts, 1):
                                st.markdown(f"{i}. {fact}")
                    else:
                        st.caption("ℹ️ No relevant memories found from KG")

                messages_for_llm = [{"role": "system", "content": system_content}] + history
                
                # Debug: Show full LLM input
                if show_memories:
                    with st.expander("🔍 Full LLM Input (Debug)", expanded=False):
                        st.markdown("### System Prompt")
                        st.code(system_content, language=None)
                        
                        st.markdown("### Conversation History (Short-term)")
                        for i, msg in enumerate(history, 1):
                            role_icon = "👤" if msg["role"] == "user" else "🤖"
                            st.markdown(f"**{i}. {role_icon} {msg['role'].upper()}:**")
                            st.code(msg["content"], language=None)
                        
                        st.markdown("### Complete Payload")
                        st.json(messages_for_llm, expanded=False)
                completion = client.chat.completions.create(
                    model=openai_model,
                    messages=messages_for_llm,
                    temperature=chat_config.get("temperature", 0.7),
                    max_tokens=chat_config.get("max_tokens", 5000),  # Fallback to 5000 if config fails
                )
                assistant_reply = completion.choices[0].message.content.strip()
                
                # Track token usage for chat
                chat_usage = tracker.track_from_response(
                    operation="chat",
                    response=completion,
                    group_id=st.session_state.group_id,
                    metadata={
                        "turn": len(st.session_state.chat_messages) // 2 + 1,
                        "kg_used": bool(results),
                        "facts_count": len(top_facts)
                    }
                )
                
                # Store token usage for this message
                message_token_usage = None
                if chat_usage:
                    message_token_usage = {
                        "prompt_tokens": chat_usage.prompt_tokens,
                        "completion_tokens": chat_usage.completion_tokens,
                        "total_tokens": chat_usage.total_tokens,
                        "cost": chat_usage.cost,
                        "model": chat_usage.model,
                        "kg_used": bool(results),
                        "facts_count": len(top_facts)
                    }
                
                # Check if response was truncated
                if completion.choices[0].finish_reason == "length":
                    st.warning("⚠️ Response was truncated due to max_tokens limit. Consider increasing it.")
            except Exception as e:
                st.warning(f"LLM error, using echo: {e}")
                assistant_reply = f"Bạn đã nói: {user_input}"
        else:
            assistant_reply = f"Bạn đã nói: {user_input}"
            message_token_usage = None  # No OpenAI call, no tokens

        # Append assistant message with token usage
        st.session_state.chat_messages.append({
            "role": "assistant", 
            "content": assistant_reply,
            "token_usage": message_token_usage
        })
        
        with st.chat_message("assistant"):
            st.markdown(assistant_reply)
            
            # Save assistant message to short term memory
            if st.session_state.get("enable_short_term_memory", True):
                try:
                    # Check if assistant made file modifications
                    uploaded_file = st.session_state.get("uploaded_file")
                    if uploaded_file and ("```" in assistant_reply or "def " in assistant_reply or "class " in assistant_reply or "import " in assistant_reply):
                        # Assistant provided code modifications, use new diffing functionality
                        try:
                            base = get_api_base_url()
                            project_id = st.session_state.get("project_id", "default_project")
                            conversation_id = st.session_state.group_id
                            
                            # Use new AI code response processing
                            from app.file_upload_handler import get_file_upload_handler
                            handler = get_file_upload_handler()
                            
                            import asyncio
                            result = asyncio.run(handler.process_ai_code_response(
                                original_file_content=uploaded_file["content"],
                                ai_response=assistant_reply,
                                file_name=uploaded_file["name"],
                                project_id=project_id,
                                conversation_id=conversation_id,
                                role="assistant"
                            ))
                            
                            # Debug logging
                            st.caption(f"🔍 Debug: AI code response result = {result.get('status', 'unknown')}")
                            
                            if result.get("status") == "success":
                                st.caption(f"🔧 Code changes saved to short term memory: {result['result']['results'][0]['message_id'][:8]}...")
                                
                                # Show detailed changes summary
                                changes = result['result']['results'][0]
                                diff_info = result.get('diff_info', {})
                                
                                st.caption(f"📝 Changes: {changes['file_name']} - {changes['file_action']} lines {changes['line_range']}")
                                st.caption(f"📊 Diff: Lines {diff_info.get('line_start', 'N/A')}-{diff_info.get('line_end', 'N/A')}, {diff_info.get('total_chunks', 0)} chunks")
                                
                                if diff_info.get('function_name'):
                                    st.caption(f"🔧 Function: {diff_info['function_name']}")
                                
                            elif result.get("status") == "no_code":
                                st.caption("ℹ️ No code blocks detected in AI response")
                            else:
                                st.error(f"Failed to process code changes: {result.get('message', 'Unknown error')}")
                                # Show full result for debugging
                                st.caption(f"🔍 Full result: {result}")
                                
                        except Exception as e:
                            st.error(f"Error processing AI code response: {e}")
                            import traceback
                            st.caption(f"🔍 Debug traceback: {traceback.format_exc()}")
                    
                    # Extract code context from assistant reply
                    code_context = extract_code_context_from_message(assistant_reply)
                    
                    # Save to short term memory
                    message_id = save_to_short_term_memory(
                        role="assistant",
                        content=assistant_reply,
                        project_id=st.session_state.get("project_id", "default_project"),
                        conversation_id=st.session_state.group_id,
                        **code_context
                    )
                    
                    if message_id:
                        st.caption(f"💾 Saved to short term memory: {message_id[:8]}...")
                    else:
                        st.caption("⚠️ Failed to save to short term memory")
                        
                except Exception as e:
                    st.error(f"Error saving assistant message to short term memory: {e}")
            
            # Display token usage badge for this message
            if message_token_usage:
                show_breakdown = st.session_state.get("show_token_breakdown", False)
                col1, col2 = st.columns([3, 1])
                with col2:
                    # Format badge with optional breakdown
                    badge = format_token_badge(
                        tokens=message_token_usage['total_tokens'],
                        cost=message_token_usage['cost'],
                        prompt_tokens=message_token_usage.get('prompt_tokens'),
                        completion_tokens=message_token_usage.get('completion_tokens'),
                        show_breakdown=show_breakdown
                    )
                    st.caption(badge)
                    
                    if message_token_usage.get('kg_used'):
                        st.caption(f"📚 {message_token_usage.get('facts_count', 0)} facts from KG")

        # Save assistant turn if auto-save and not summarizing
        if auto_save and not pause_saving and not summarize_to_memory:
            payload = {
                "name": chat_name,
                "messages": [f"assistant: {assistant_reply}"],
                "reference_time": datetime.utcnow().isoformat(),
                "source_description": "chat",
                "group_id": st.session_state.group_id,
            }
            post_json_timeout("/ingest/message", payload, timeout_sec=5)

        # If summarizing, append assistant and maybe ingest summary
        if summarize_to_memory:
            st.session_state.mem_buffer.append(f"assistant: {assistant_reply}")
            # Ingest when reached N user turns
            if st.session_state.mem_user_count >= ingest_every_n_user_turns and not pause_saving:
                summary_text = None
                if openai_key:
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_key)
                        
                        # Get last N turns for summarization
                        recent_turns = st.session_state.mem_buffer[-(2*ingest_every_n_user_turns):]
                        sum_prompt = format_summarization_prompt(recent_turns)
                        sum_config = PROMPT_CONFIG.get("summarization", {})
                        
                        comp = client.chat.completions.create(
                            model=openai_model,
                            messages=[{"role": "user", "content": sum_prompt}],
                            temperature=sum_config.get("temperature", 0.2),
                            max_tokens=sum_config.get("max_tokens", 250),  # Increased for multiple facts
                        )
                        summary_text = comp.choices[0].message.content.strip()
                        
                        # Track token usage for summarization
                        sum_usage = tracker.track_from_response(
                            operation="summarization",
                            response=comp,
                            group_id=st.session_state.group_id,
                            metadata={
                                "turns_summarized": ingest_every_n_user_turns
                            }
                        )
                        
                        # Display summarization notification with tokens
                        if show_memories and sum_usage:
                            st.info(f"📝 **AI Summarized {ingest_every_n_user_turns} turns**\n\n"
                                   f"🎫 {sum_usage.total_tokens:,} tokens • ${sum_usage.cost:.4f}\n\n"
                                   f"Model: {sum_usage.model}")
                    except Exception:
                        summary_text = None
                if not summary_text:
                    # Fallback simple compression
                    last_lines = st.session_state.mem_buffer[-(2*ingest_every_n_user_turns):]
                    joined = "; ".join(last_lines)
                    summary_text = (joined[:180] + "…") if len(joined) > 180 else joined

                # Parse multiple facts from summary (one per line starting with "- ")
                facts = []
                if summary_text:
                    for line in summary_text.split('\n'):
                        line = line.strip()
                        if line.startswith('- '):
                            facts.append(line[2:].strip())
                        elif line and not line.startswith('**'):  # Skip markdown headers
                            facts.append(line)
                
                # Ingest each fact separately with importance filtering
                if facts:
                    from app.importance import get_scorer
                    scorer = get_scorer()
                    
                    ingested_count = 0
                    filtered_count = 0
                    
                    # Show progress
                    if show_memories:
                        st.info(f"📝 Ingesting {len(facts)} facts to Knowledge Graph...")
                        progress_bar = st.progress(0)
                    
                    for idx, fact in enumerate(facts):
                        if len(fact) > 10:  # Skip very short lines
                            # Check importance before ingesting
                            should_ingest, score_info = scorer.should_ingest(fact, threshold=0.3)
                            
                            if should_ingest:
                                payload = {
                                    "name": chat_name,
                                    "text": fact,
                                    "reference_time": datetime.utcnow().isoformat(),
                                    "source_description": "chat_summary",
                                    "group_id": st.session_state.group_id,
                                }
                                
                                # Retry logic with exponential backoff
                                max_retries = 2
                                success = False
                                for attempt in range(max_retries):
                                    success, response = post_json_timeout("/ingest/text", payload, timeout_sec=30)
                                    if success:
                                        break
                                    else:
                                        if attempt < max_retries - 1:
                                            import time
                                            wait_time = 2 ** attempt  # 1s, 2s
                                            if show_memories:
                                                st.caption(f"⏳ Retry {attempt+1}/{max_retries-1} in {wait_time}s...")
                                            time.sleep(wait_time)
                                
                                if success:
                                    ingested_count += 1
                                else:
                                    if show_memories:
                                        st.warning(f"⚠️ Failed to ingest fact after {max_retries} attempts: {fact[:50]}...")
                                    filtered_count += 1
                            else:
                                filtered_count += 1
                                if show_memories:
                                    st.caption(f"⚠️ Filtered low-importance fact: {fact[:50]}... (score: {score_info['score']})")
                        
                        # Update progress
                        if show_memories:
                            progress_bar.progress((idx + 1) / len(facts))
                    
                    if show_memories and filtered_count > 0:
                        st.info(f"💡 Filtered {filtered_count} low-importance facts, ingested {ingested_count}")
                else:
                    # Fallback: ingest as single blob
                    payload = {
                        "name": chat_name,
                        "text": summary_text,
                        "reference_time": datetime.utcnow().isoformat(),
                        "source_description": "chat_summary",
                        "group_id": st.session_state.group_id,
                    }
                    post_json_timeout("/ingest/text", payload, timeout_sec=6)
                # reset counter, keep buffer trimmed
                st.session_state.mem_user_count = 0

    # Manual persist full transcript
    if st.button("Save full conversation transcript"):
        lines = [f"{m['role']}: {m['content']}" for m in st.session_state.chat_messages]
        payload = {
            "name": chat_name,
            "messages": lines,
            "reference_time": datetime.utcnow().isoformat(),
            "source_description": "chat",
            "group_id": st.session_state.group_id,
        }
        ok, data = post_json("/ingest/message", payload)
        if ok:
            st.success("Transcript saved")
        else:
            st.error("Failed to save transcript")
    
    # Render chat history in the container (at top)
    with chat_container:
        show_breakdown = st.session_state.get("show_token_breakdown", False)
        
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
                # Display token usage for this message if available
                if msg.get("token_usage") and msg["role"] == "assistant":
                    usage = msg["token_usage"]
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        # Format badge with optional breakdown
                        badge = format_token_badge(
                            tokens=usage['total_tokens'],
                            cost=usage['cost'],
                            prompt_tokens=usage.get('prompt_tokens'),
                            completion_tokens=usage.get('completion_tokens'),
                            show_breakdown=show_breakdown
                        )
                        st.caption(badge)
                        
                        if usage.get('kg_used'):
                            st.caption(f"📚 {usage.get('facts_count', 0)} facts from KG")
    
    # File upload section
    st.markdown("---")
    st.markdown("### 📁 Upload File for AI Analysis")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a code file to upload",
            type=['py', 'js', 'ts', 'java', 'cpp', 'c', 'cs', 'php', 'rb', 'go', 'rs', 'txt', 'md','tsx','json'],
            help="Upload a file for AI to read and analyze. AI can then make modifications based on your requests.",
            key="chat_file_uploader"
        )
    
    with col2:
        if uploaded_file is not None:
            st.success(f"📄 {uploaded_file.name} ready!")
    
    # Show file content if uploaded
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode('utf-8')
            st.markdown("**File Content Preview:**")
            st.code(file_content, language='python' if uploaded_file.name.endswith('.py') else 'text')
            
            # Add file info to session state
            st.session_state["uploaded_file"] = {
                "name": uploaded_file.name,
                "content": file_content,
                "size": len(file_content)
            }
            
            # Custom description input
            st.markdown("**📝 Describe what you want AI to do with this file:**")
            custom_description = st.text_area(
                "Task description",
                placeholder="e.g., Add error handling to all functions, optimize performance, fix bugs, add new features...",
                height=100,
                key="file_task_description"
            )
            
            # Action buttons
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🔍 Analyze File", key="analyze_file_btn"):
                    # Create analysis message
                    analysis_msg = f"Please analyze this file: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = analysis_msg
                    st.rerun()
            
            with col2:
                if st.button("🛠️ Fix Issues", key="fix_file_btn"):
                    # Create fix message
                    fix_msg = f"Please review and fix any issues in this file: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = fix_msg
                    st.rerun()
            
            with col3:
                if st.button("📝 Improve Code", key="improve_file_btn"):
                    # Create improve message
                    improve_msg = f"Please improve this code: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = improve_msg
                    st.rerun()
            
            with col4:
                if st.button("🚀 Send with Description", key="send_with_description_btn"):
                    if custom_description.strip():
                        # Create custom message with description
                        custom_msg = f"Please work on this file: {uploaded_file.name}\n\nTask: {custom_description}\n\nFile content:\n```\n{file_content}\n```"
                        st.session_state["_pending_input"] = custom_msg
                        st.rerun()
                    else:
                        st.warning("Please enter a task description first!")
            
            # Quick examples
            st.markdown("**💡 Quick Examples:**")
            example_cols = st.columns(3)
            with example_cols[0]:
                if st.button("Add Error Handling", key="example_error_handling"):
                    example_msg = f"Please add comprehensive error handling to this file: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = example_msg
                    st.rerun()
            
            with example_cols[1]:
                if st.button("Optimize Performance", key="example_optimize"):
                    example_msg = f"Please optimize the performance of this file: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = example_msg
                    st.rerun()
            
            with example_cols[2]:
                if st.button("Add Documentation", key="example_docs"):
                    example_msg = f"Please add comprehensive documentation and comments to this file: {uploaded_file.name}\n\nFile content:\n```\n{file_content}\n```"
                    st.session_state["_pending_input"] = example_msg
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error reading file: {e}")
    
    # Chat input at the very bottom
    chat_input = st.chat_input("Type your message or upload a file above")
    if chat_input:
        st.session_state["_pending_input"] = chat_input
        st.rerun()

    # Import STM JSON into Neo4j (always visible)
    st.markdown("---")
    st.markdown("### 🧠 Import Short Term Memory JSON to Neo4j")
    stm_json = st.file_uploader(
        "Choose a short_term.json to import",
        type=["json"],
        key="stm_json_uploader"
    )
    use_llm = st.checkbox("Use LLM to enrich graph (Concepts, RELATES_TO)", value=False, key="stm_use_llm")
    if stm_json is not None:
        with st.expander("Preview JSON (first 2 KB)"):
            try:
                preview = stm_json.getvalue()[:2048].decode("utf-8", errors="replace")
            except Exception:
                preview = "<binary>"
            st.code(preview)
        if st.button("📤 Import to Neo4j", key="import_stm_json_btn"):
            try:
                base = get_api_base_url()
                files = {"file": (stm_json.name, stm_json.getvalue(), "application/json")}
                data = {"use_llm": str(use_llm).lower()}
                import requests
                resp = requests.post(f"{base}/graph/import-stm-json", files=files, data=data, timeout=120)
                # Don't raise; surface error body
                try:
                    data = resp.json()
                except Exception:
                    data = {"status": "error", "detail": resp.text}
                if resp.status_code != 200:
                    st.error(f"Import failed ({resp.status_code}): {data.get('detail', data)}")
                    st.stop()
                if data.get("status") == "success":
                    summary = data.get("summary", {})
                    st.success(
                        f"Imported: {summary.get('created_messages', 0)} messages into Neo4j"
                    )
                else:
                    st.error(f"Failed to import: {data}")
            except Exception as e:
                st.error(f"Error importing STM JSON: {e}")

# ---------------------------- Ingest Tab ----------------------------
with tabs[1]:
    st.subheader("Ingest")

    with st.expander("Ingest Text", expanded=True):
        with st.form("ingest_text_form"):
            name = st.text_input("Name", value="sample-text")
            text = st.text_area("Text", height=150)
            ref_time_enabled = st.checkbox("Set reference time (ISO 8601)")
            reference_time = st.text_input("Reference time", value=datetime.utcnow().isoformat(), disabled=not ref_time_enabled)
            source_description = st.text_input("Source description", value="app")
            submitted = st.form_submit_button("Ingest Text")
            if submitted:
                payload = {
                    "name": name,
                    "text": text,
                    "reference_time": reference_time if ref_time_enabled else None,
                    "source_description": source_description,
                }
                ok, data = post_json("/ingest/text", payload)
                if ok:
                    st.success("Text ingested")
                    st.json(data)
                else:
                    st.error("Failed to ingest text")
                    st.json(data)

    with st.expander("Ingest Messages"):
        with st.form("ingest_messages_form"):
            name = st.text_input("Name", value="sample-chat")
            messages_raw = st.text_area(
                "Messages (one per line, e.g., 'user: hello')",
                height=150,
            )
            ref_time_enabled = st.checkbox("Set reference time (ISO 8601)", key="msg_ref")
            reference_time = st.text_input("Reference time", value=datetime.utcnow().isoformat(), disabled=not ref_time_enabled, key="msg_ref_input")
            source_description = st.text_input("Source description", value="chat", key="msg_src")
            submitted = st.form_submit_button("Ingest Messages")
            if submitted:
                messages: List[str] = [line.strip() for line in messages_raw.splitlines() if line.strip()]
                payload = {
                    "name": name,
                    "messages": messages,
                    "reference_time": reference_time if ref_time_enabled else None,
                    "source_description": source_description,
                }
                ok, data = post_json("/ingest/message", payload)
                if ok:
                    st.success("Messages ingested")
                    st.json(data)
                else:
                    st.error("Failed to ingest messages")
                    st.json(data)

    with st.expander("Ingest JSON"):
        with st.form("ingest_json_form"):
            name = st.text_input("Name", value="sample-json")
            json_text = st.text_area("JSON payload", value='{"key": "value"}', height=150)
            ref_time_enabled = st.checkbox("Set reference time (ISO 8601)", key="json_ref")
            reference_time = st.text_input("Reference time", value=datetime.utcnow().isoformat(), disabled=not ref_time_enabled, key="json_ref_input")
            source_description = st.text_input("Source description", value="json", key="json_src")
            submitted = st.form_submit_button("Ingest JSON")
            if submitted:
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
                else:
                    payload = {
                        "name": name,
                        "json": parsed,  # alias for data
                        "reference_time": reference_time if ref_time_enabled else None,
                        "source_description": source_description,
                    }
                    ok, data = post_json("/ingest/json", payload)
                    if ok:
                        st.success("JSON ingested")
                        st.json(data)
                    else:
                        st.error("Failed to ingest JSON")
                        st.json(data)
    
    with st.expander("💻 Ingest Code Change", expanded=True):
        st.markdown("**Track code commits, bug fixes, refactors with LLM importance scoring**")
        
        with st.form("ingest_code_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                code_project_id = st.text_input("Project ID", value="my_project", key="code_proj")
                code_name = st.text_input("Name", value="fix_auth", key="code_name")
                code_change_type = st.selectbox(
                    "Change Type", 
                    ["fixed", "added", "refactored", "removed", "updated"],
                    key="code_type"
                )
            
            with col2:
                code_severity = st.selectbox(
                    "Severity",
                    ["critical", "high", "medium", "low"],
                    index=2,
                    key="code_sev"
                )
                code_file_path = st.text_input("File Path", value="src/auth/login.py", key="code_file")
            
            code_summary = st.text_area(
                "Summary (describe what was changed)",
                value="Fixed SQL injection vulnerability in user login endpoint",
                height=100,
                key="code_summary"
            )
            
            code_submitted = st.form_submit_button("🚀 Ingest Code Change")
            
            if code_submitted:
                payload = {
                    "project_id": code_project_id,
                    "name": code_name,
                    "change_type": code_change_type,
                    "severity": code_severity,
                    "file_path": code_file_path,
                    "summary": code_summary,
                }
                
                with st.spinner("Scoring importance with LLM..."):
                    ok, data = post_json("/ingest/code", payload)
                
                if ok:
                    st.success("✅ Code change ingested!")
                    
                    # Show importance score
                    if "importance_score" in data:
                        score = data["importance_score"]
                        category = data.get("category", "unknown")
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Importance Score", f"{score:.2f}")
                        with col_b:
                            st.metric("Category", category)
                        with col_c:
                            episode_uuid = data.get("episode_uuid", "N/A")[:12]
                            st.metric("Episode ID", episode_uuid)
                        
                        # Color-coded alert based on score
                        if score >= 0.9:
                            st.error(f"🔴 **CRITICAL**: This is a high-priority change!")
                        elif score >= 0.7:
                            st.warning(f"🟡 **IMPORTANT**: This change is significant")
                        else:
                            st.info(f"🟢 **NORMAL**: Standard code change")
                    
                    with st.expander("📄 Full Response"):
                        st.json(data)
                else:
                    st.error("❌ Failed to ingest code")
                    st.json(data)
        
        # Quick test examples
        st.markdown("### 📝 Quick Test Examples")
        st.caption("Click to copy, then paste into form above:")
        
        examples = [
            {
                "name": "Critical Security Fix",
                "summary": "Fixed SQL injection vulnerability allowing unauthorized database access",
                "change_type": "fixed",
                "severity": "critical",
                "file_path": "src/auth/database.py"
            },
            {
                "name": "New Payment Feature",
                "summary": "Integrated Stripe payment gateway with webhook support",
                "change_type": "added",
                "severity": "high",
                "file_path": "src/api/payment.py"
            },
            {
                "name": "Code Formatting",
                "summary": "Applied black formatter to entire codebase",
                "change_type": "refactored",
                "severity": "low",
                "file_path": "**/*.py"
            }
        ]
        
        for idx, ex in enumerate(examples, 1):
            with st.expander(f"Example {idx}: {ex['name']}", expanded=False):
                st.code(f"""
Project ID: my_project
Name: {ex['name'].lower().replace(' ', '_')}
Change Type: {ex['change_type']}
Severity: {ex['severity']}
File Path: {ex['file_path']}
Summary: {ex['summary']}
                """, language=None)
    
    with st.expander("🔧 Ingest Code Context (Complex Schema)", expanded=False):
        st.markdown("**Full metadata tracking for production systems - Git hooks, IDE plugins**")
        st.caption("⚠️ This is for advanced use cases with detailed code tracking")
        
        with st.form("ingest_code_context_form"):
            st.markdown("#### Basic Info")
            col_basic1, col_basic2 = st.columns(2)
            
            with col_basic1:
                ctx_project_id = st.text_input("Project ID", value="project_abc123", key="ctx_proj")
                ctx_name = st.text_input("Change Name", value="Fixed login null pointer bug", key="ctx_name")
            
            with col_basic2:
                ctx_ref_time = st.text_input(
                    "Reference Time (ISO)", 
                    value=datetime.utcnow().isoformat(), 
                    key="ctx_ref_time"
                )
            
            ctx_summary = st.text_area(
                "Summary (detailed description)",
                value="Fixed null pointer exception in auth_service.py:login_user() function by adding null check before accessing user.token attribute. This prevents AttributeError when token is None.",
                height=100,
                key="ctx_summary"
            )
            
            st.markdown("#### Metadata - Location")
            col_loc1, col_loc2, col_loc3 = st.columns(3)
            
            with col_loc1:
                ctx_file_path = st.text_input("File Path", value="src/auth/auth_service.py", key="ctx_file")
            with col_loc2:
                ctx_function = st.text_input("Function Name (optional)", value="login_user", key="ctx_func")
            with col_loc3:
                col_line1, col_line2 = st.columns(2)
                with col_line1:
                    ctx_line_start = st.number_input("Line Start", value=45, min_value=1, key="ctx_line_start")
                with col_line2:
                    ctx_line_end = st.number_input("Line End", value=52, min_value=1, key="ctx_line_end")
            
            st.markdown("#### Metadata - Change Details")
            col_change1, col_change2, col_change3 = st.columns(3)
            
            with col_change1:
                ctx_change_type = st.selectbox(
                    "Change Type",
                    ["fixed", "added", "refactored", "removed", "updated"],
                    key="ctx_change_type"
                )
            with col_change2:
                ctx_severity = st.selectbox(
                    "Severity",
                    ["critical", "high", "medium", "low"],
                    index=1,
                    key="ctx_severity"
                )
            with col_change3:
                ctx_language = st.text_input("Language", value="python", key="ctx_lang")
            
            ctx_change_summary = st.text_input(
                "Change Summary",
                value="Added null validation",
                key="ctx_change_sum"
            )
            
            st.markdown("#### Code References (NOT actual code - just metadata)")
            col_ref1, col_ref2 = st.columns(2)
            
            with col_ref1:
                st.markdown("**Before:**")
                ctx_code_before_id = st.text_input("Code ID (before)", value="code_xyz123", key="ctx_before_id")
                ctx_code_before_hash = st.text_input("Code Hash (before)", value="a3f5c8d2e9f1b4a7", key="ctx_before_hash")
                ctx_before_lines = st.number_input("Line Count (before)", value=5, min_value=0, key="ctx_before_lines")
            
            with col_ref2:
                st.markdown("**After:**")
                ctx_code_after_id = st.text_input("Code ID (after)", value="code_xyz456", key="ctx_after_id")
                ctx_code_after_hash = st.text_input("Code Hash (after)", value="b7e9d1a3c5f2b8d4", key="ctx_after_hash")
                ctx_after_lines = st.number_input("Line Count (after)", value=8, min_value=0, key="ctx_after_lines")
            
            st.markdown("#### Diff & Git Info")
            col_diff1, col_diff2, col_diff3 = st.columns(3)
            
            with col_diff1:
                ctx_lines_added = st.number_input("Lines Added", value=3, min_value=0, key="ctx_added")
            with col_diff2:
                ctx_lines_removed = st.number_input("Lines Removed", value=1, min_value=0, key="ctx_removed")
            with col_diff3:
                ctx_git_commit = st.text_input("Git Commit Hash", value="abc123def456", key="ctx_git")
            
            ctx_diff_summary = st.text_input(
                "Diff Summary",
                value="Added 3 lines for null check, removed 1 line",
                key="ctx_diff_sum"
            )
            
            ctx_submitted = st.form_submit_button("🚀 Ingest Code Context (Complex)", type="primary")
            
            if ctx_submitted:
                # Build complex payload
                payload = {
                    "name": ctx_name,
                    "summary": ctx_summary,
                    "project_id": ctx_project_id,
                    "reference_time": ctx_ref_time,
                    "metadata": {
                        "file_path": ctx_file_path,
                        "function_name": ctx_function if ctx_function else None,
                        "line_start": int(ctx_line_start),
                        "line_end": int(ctx_line_end),
                        "change_type": ctx_change_type,
                        "change_summary": ctx_change_summary,
                        "severity": ctx_severity,
                        "code_before_ref": {
                            "code_id": ctx_code_before_id,
                            "code_hash": ctx_code_before_hash,
                            "language": ctx_language,
                            "line_count": int(ctx_before_lines)
                        } if ctx_code_before_id else None,
                        "code_after_ref": {
                            "code_id": ctx_code_after_id,
                            "code_hash": ctx_code_after_hash,
                            "language": ctx_language,
                            "line_count": int(ctx_after_lines)
                        } if ctx_code_after_id else None,
                        "lines_added": int(ctx_lines_added),
                        "lines_removed": int(ctx_lines_removed),
                        "diff_summary": ctx_diff_summary,
                        "git_commit": ctx_git_commit if ctx_git_commit else None,
                        "timestamp": ctx_ref_time
                    }
                }
                
                with st.spinner("Ingesting code context with full metadata..."):
                    ok, data = post_json("/ingest/code-context", payload)
                
                if ok:
                    st.success("✅ Code context ingested successfully!")
                    
                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        # API returns "episode_id" not "episode_uuid"
                        episode_id = data.get("episode_id", data.get("episode_uuid", "N/A"))
                        if episode_id != "N/A":
                            st.metric("Episode ID", episode_id[:16] + "...")
                        else:
                            st.metric("Episode ID", "N/A")
                    with col_res2:
                        expires_at = data.get("expires_at", "N/A")
                        if expires_at != "N/A":
                            # Show TTL in human-readable format
                            from datetime import datetime
                            try:
                                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                                st.metric("Expires At", exp_time.strftime("%Y-%m-%d %H:%M"))
                            except:
                                st.metric("Expires (48h)", "2 days")
                        else:
                            st.metric("TTL", "48 hours")
                    
                    st.info("💡 **Tip:** Entities are being extracted by Graphiti AI in background. Check Neo4j browser in 5-10 seconds to see the full graph with entities and relationships!")
                    
                    with st.expander("📄 Full Response"):
                        st.json(data)
                else:
                    st.error("❌ Failed to ingest code context")
                    st.json(data)
        
        st.markdown("---")
        st.markdown("### 📋 Complex Schema Use Cases")
        st.markdown("""
        **When to use:**
        - ✅ IDE plugins (auto-track code changes)
        - ✅ Git hooks (post-commit metadata)
        - ✅ CI/CD pipelines (deployment tracking)
        - ✅ Code review systems (change analysis)
        
        **What gets stored:**
        - File path, function name, line numbers
        - Code hashes (NOT actual code)
        - Diff statistics (lines added/removed)
        - Git metadata (commit hash, branch)
        - Timestamps and relationships
        
        **What does NOT get stored:**
        - ❌ Actual source code (only references)
        - ❌ Sensitive data
        - ❌ Large binaries
        """)
    
    with st.expander("🚀 Bulk Test - Ingest Multiple Code Changes", expanded=False):
        st.markdown("**Paste JSON array of code changes for quick testing**")
        
        # Default test cases
        default_test_cases = [
            {
                "project_id": "payment_system",
                "name": "fix_sql_injection",
                "change_type": "fixed",
                "severity": "critical",
                "file_path": "src/auth/database.py",
                "summary": "Fixed SQL injection vulnerability allowing unauthorized database access"
            },
            {
                "project_id": "payment_system",
                "name": "stripe_integration",
                "change_type": "added",
                "severity": "high",
                "file_path": "src/api/payment.py",
                "summary": "Integrated Stripe payment gateway with webhook support"
            },
            {
                "project_id": "payment_system",
                "name": "optimize_queries",
                "change_type": "refactored",
                "severity": "medium",
                "file_path": "src/db/repository.py",
                "summary": "Optimized database queries reducing response time by 40%"
            },
            {
                "project_id": "payment_system",
                "name": "code_format",
                "change_type": "refactored",
                "severity": "low",
                "file_path": "**/*.py",
                "summary": "Applied black formatter to entire codebase"
            },
            {
                "project_id": "user_service",
                "name": "fix_memory_leak",
                "change_type": "fixed",
                "severity": "high",
                "file_path": "src/session/handler.py",
                "summary": "Fixed memory leak in user session management"
            }
        ]
        
        bulk_input = st.text_area(
            "JSON Array (one change per object)",
            value=json.dumps(default_test_cases, indent=2),
            height=300,
            key="bulk_code_input"
        )
        
        col_bulk1, col_bulk2 = st.columns([1, 3])
        
        with col_bulk1:
            if st.button("🚀 Ingest All", key="bulk_ingest_btn", type="primary"):
                try:
                    changes = json.loads(bulk_input)
                    
                    if not isinstance(changes, list):
                        st.error("Input must be a JSON array!")
                    else:
                        st.info(f"📝 Ingesting {len(changes)} code changes...")
                        
                        results = []
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for idx, change in enumerate(changes):
                            status_text.text(f"Processing {idx+1}/{len(changes)}: {change.get('name', 'unknown')}")
                            
                            ok, data = post_json("/ingest/code", change)
                            
                            results.append({
                                "name": change.get("name"),
                                "success": ok,
                                "score": data.get("importance_score") if ok else None,
                                "category": data.get("category") if ok else None,
                                "error": data.get("error") if not ok else None
                            })
                            
                            progress_bar.progress((idx + 1) / len(changes))
                        
                        status_text.empty()
                        
                        # Summary
                        success_count = sum(1 for r in results if r["success"])
                        fail_count = len(results) - success_count
                        
                        if fail_count == 0:
                            st.success(f"✅ All {success_count} changes ingested successfully!")
                        else:
                            st.warning(f"⚠️ {success_count} succeeded, {fail_count} failed")
                        
                        # Results table
                        st.markdown("### 📊 Results")
                        for r in results:
                            if r["success"]:
                                score = r["score"]
                                category = r["category"]
                                
                                # Color-coded icon
                                if score >= 0.9:
                                    icon = "🔴"
                                elif score >= 0.7:
                                    icon = "🟡"
                                else:
                                    icon = "🟢"
                                
                                st.markdown(f"{icon} **{r['name']}**: Score={score:.2f}, Category={category}")
                            else:
                                st.markdown(f"❌ **{r['name']}**: {r['error']}")
                        
                        # Full JSON
                        with st.expander("📄 Full Results JSON"):
                            st.json(results)
                        
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with col_bulk2:
            st.markdown("**💡 Quick Tips:**")
            st.caption("- Each object = one code change")
            st.caption("- All fields required: project_id, name, change_type, severity, file_path, summary")
            st.caption("- LLM will score each change automatically")
            st.caption("- Results show color-coded importance")
        
        st.markdown("---")
        st.markdown("### 📝 More Test Templates")
        
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            if st.button("Load: Security Fixes", key="template_security"):
                template = [
                    {
                        "project_id": "security_audit",
                        "name": "fix_xss",
                        "change_type": "fixed",
                        "severity": "critical",
                        "file_path": "src/templates/render.py",
                        "summary": "Fixed XSS vulnerability in HTML template rendering"
                    },
                    {
                        "project_id": "security_audit",
                        "name": "fix_csrf",
                        "change_type": "fixed",
                        "severity": "high",
                        "file_path": "src/api/middleware.py",
                        "summary": "Added CSRF token validation to all POST endpoints"
                    }
                ]
                st.session_state["bulk_code_input"] = json.dumps(template, indent=2)
                st.rerun()
        
        with col_t2:
            if st.button("Load: New Features", key="template_features"):
                template = [
                    {
                        "project_id": "feature_dev",
                        "name": "oauth_integration",
                        "change_type": "added",
                        "severity": "high",
                        "file_path": "src/auth/oauth.py",
                        "summary": "Implemented OAuth2 authentication with Google and GitHub"
                    },
                    {
                        "project_id": "feature_dev",
                        "name": "websocket_support",
                        "change_type": "added",
                        "severity": "medium",
                        "file_path": "src/api/websocket.py",
                        "summary": "Added WebSocket support for real-time notifications"
                    }
                ]
                st.session_state["bulk_code_input"] = json.dumps(template, indent=2)
                st.rerun()

    st.caption("Tip: Set environment variable MEMORY_LAYER_API to point to a different API base URL.")

# ---------------------------- Search Tab ----------------------------
with tabs[2]:
    st.subheader("Search")
    query = st.text_input("Query", value="hello", key="search_query")
    focal = st.text_input("Focal node UUID (optional)", key="search_focal")
    group_filter = st.text_input("Group ID (optional - filter by conversation)", key="search_group")
    if st.button("Run Search", key="search_button"):
        payload = {
            "query": query, 
            "focal_node_uuid": focal or None,
            "group_id": group_filter or None
        }
        ok, data = post_json("/search", payload)
        if ok:
            st.success("Search complete")
            st.json(data)
        else:
            st.error("Search failed")
            st.json(data)

# ---------------------------- Cache Tab ----------------------------
with tabs[3]:
    st.subheader("Cache Management")
    
    # Cache stats
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Get Cache Stats"):
            ok, data = post_json("/cache/stats", {})
            if ok:
                st.success("Cache stats retrieved")
                st.json(data)
            else:
                st.error("Failed to get cache stats")
                st.json(data)
    
    with col2:
        if st.button("Check Cache Health"):
            ok, data = post_json("/cache/health", {})
            if ok:
                if data.get("status") == "healthy":
                    st.success("Cache is healthy")
                else:
                    st.warning("Cache is empty")
                st.json(data)
            else:
                st.error("Failed to check cache health")
                st.json(data)
    
    # Cache management
    st.subheader("Cache Management Actions")
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        if st.button("Clear All Cache", type="secondary"):
            ok, data = post_json("/cache/clear", {})
            if ok:
                st.success("All cache cleared")
            else:
                st.error("Failed to clear cache")
                st.json(data)
    
    with col4:
        if st.button("Clear Search Cache", type="secondary"):
            ok, data = post_json("/cache/clear-search", {})
            if ok:
                st.success("Search cache cleared")
            else:
                st.error("Failed to clear search cache")
                st.json(data)
    
    with col5:
        node_uuid = st.text_input("Node UUID to clear", key="clear_node_uuid")
        if st.button("Clear Node Cache", type="secondary"):
            if node_uuid:
                ok, data = post_json(f"/cache/clear-node/{node_uuid}", {})
                if ok:
                    st.success(f"Cache for node {node_uuid} cleared")
                else:
                    st.error("Failed to clear node cache")
                    st.json(data)
            else:
                st.warning("Please enter a node UUID")
    
    # Cache information
    st.subheader("Cache Information")
    st.info("""
    **Cache Types:**
    - **Search Cache**: Cached search results (TTL: 30 minutes)
    - **Node Cache**: Cached node data (TTL: 1 hour)
    - **Connection Cache**: Cached node connections (TTL: 30 minutes)
    
    **Cache Invalidation:**
    - Search cache is automatically cleared when new data is ingested
    - Node cache can be manually cleared for specific nodes
    - All caches can be cleared manually for maintenance
    """)

# ---------------------------- Token Usage Tab ----------------------------
with tabs[4]:
    st.subheader("📊 Token Usage Analytics")
    
    # Filter by conversation
    all_group_ids = tracker.get_all_group_ids()
    
    if all_group_ids:
        st.markdown("### 🔍 Filter by Conversation")
        
        col_filter1, col_filter2 = st.columns([3, 1])
        
        with col_filter1:
            # Add "All Conversations" option
            filter_options = ["All Conversations"] + all_group_ids
            selected_filter = st.selectbox(
                "Select Conversation",
                options=filter_options,
                key="token_filter_group_id",
                help="Filter token usage by conversation group_id"
            )
        
        with col_filter2:
            # Show current conversation
            current_gid = st.session_state.get("group_id", "")
            if st.button("📍 Current Chat", key="filter_current"):
                st.session_state.token_filter_group_id = current_gid
                st.rerun()
        
        # Determine filter value
        filter_group_id = None if selected_filter == "All Conversations" else selected_filter
        
        # Display metrics with filter
        display_token_metrics(tracker, compact=False, group_id=filter_group_id)
        
        # Breakdown by conversation
        st.markdown("---")
        st.markdown("### 💬 Token Usage by Conversation")
        
        by_group = tracker.get_by_group_id()
        
        if by_group:
            group_data = []
            for gid, stats in by_group.items():
                # Format operations
                ops_str = ", ".join([f"{op}({count})" for op, count in stats['operations'].items()])
                
                group_data.append({
                    "Conversation": gid[:12] + "..." if len(gid) > 12 else gid,
                    "Calls": stats['count'],
                    "Tokens": f"{stats['total_tokens']:,}",
                    "Cost": f"${stats['cost']:.4f}",
                    "Operations": ops_str,
                    "Is Current": "✓" if gid == current_gid else ""
                })
            
            # Sort by cost (highest first)
            group_data.sort(key=lambda x: float(x['Cost'].replace('$', '')), reverse=True)
            
            st.dataframe(group_data, use_container_width=True)
            
            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Conversations", len(by_group))
            with col2:
                avg_cost = sum(s['cost'] for s in by_group.values()) / len(by_group)
                st.metric("Avg Cost/Conversation", f"${avg_cost:.4f}")
            with col3:
                max_cost = max(s['cost'] for s in by_group.values())
                st.metric("Most Expensive", f"${max_cost:.4f}")
        else:
            st.info("No conversation data available")
    else:
        # No group_ids yet
        display_token_metrics(tracker, compact=False)
    
    # Session controls
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Stats", key="refresh_token_stats"):
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Token History", key="clear_token_history", type="secondary"):
            tracker.clear()
            st.success("Token history cleared!")
            st.rerun()
    
    with col3:
        if st.button("📥 Export to JSON", key="export_tokens"):
            data = tracker.export_to_dict()
            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="💾 Download JSON",
                data=json_str,
                file_name=f"token_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_token_json"
            )
    
    # Cost projection
    if tracker.usage_history:
        st.markdown("---")
        st.markdown("### 💰 Cost Projection")
        
        total_cost = tracker.get_total_cost()
        total_calls = len(tracker.usage_history)
        avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Avg Cost/Call", f"${avg_cost_per_call:.4f}")
        
        with col2:
            proj_100 = avg_cost_per_call * 100
            st.metric("100 Calls", f"${proj_100:.2f}")
        
        with col3:
            proj_1000 = avg_cost_per_call * 1000
            st.metric("1,000 Calls", f"${proj_1000:.2f}")
        
        with col4:
            proj_10000 = avg_cost_per_call * 10000
            st.metric("10,000 Calls", f"${proj_10000:.2f}")
        
        # Cost by model
        st.markdown("### 🤖 Model Usage")
        model_usage = {}
        for usage in tracker.usage_history:
            model = usage.model
            if model not in model_usage:
                model_usage[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            model_usage[model]["calls"] += 1
            model_usage[model]["tokens"] += usage.total_tokens
            model_usage[model]["cost"] += usage.cost
        
        model_data = []
        for model, stats in model_usage.items():
            model_data.append({
                "Model": model,
                "Calls": stats["calls"],
                "Total Tokens": f"{stats['tokens']:,}",
                "Total Cost": f"${stats['cost']:.4f}",
                "Avg Tokens/Call": f"{stats['tokens'] // stats['calls']:,}"
            })
        
        st.dataframe(model_data, use_container_width=True)
    
    # Tips and info
    st.markdown("---")
    st.markdown("### 💡 Token Optimization Tips")
    st.info("""
    **Reduce Token Usage:**
    - ✅ Use shorter prompts when possible
    - ✅ Increase summarization interval (N=5 instead of N=2)
    - ✅ Reduce short-term memory window
    - ✅ Use gpt-4o-mini instead of gpt-4 (cheaper)
    - ✅ Enable importance filtering (threshold ≥ 0.3)
    
    **Tracked Operations:**
    - 💬 **Chat**: Main conversation messages
    - 🔍 **Decision**: LLM decides if KG search needed
    - 📝 **Summarization**: Multi-turn conversation summaries
    - 🌐 **Translation**: Query translation for better search
    - ⭐ **Importance**: Fact importance scoring
    """)

# ---------------------------- Graphiti Tokens Tab ----------------------------
with tabs[5]:
    render_graphiti_token_tab()

# ---------------------------- Debug Tab ----------------------------
with tabs[6]:
    st.subheader("Debug Tools")
    
    st.markdown("### Check Episodes by Group ID")
    debug_group_id = st.text_input(
        "Enter Group ID to debug", 
        value=st.session_state.get("group_id", ""),
        key="debug_group_id"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Show Episodes", key="debug_episodes"):
            if debug_group_id:
                try:
                    import requests
                    base = get_api_base_url()
                    resp = requests.get(f"{base}/debug/episodes/{debug_group_id}", timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    st.success(f"Found {data.get('count', 0)} episodes")
                    st.json(data)
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter a group_id")
    
    with col2:
        if st.button("Show Edges/Facts", key="debug_edges"):
            if debug_group_id:
                try:
                    import requests
                    base = get_api_base_url()
                    resp = requests.get(f"{base}/debug/edges/{debug_group_id}", timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    st.success(f"Found {data.get('count', 0)} edges")
                    st.json(data)
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter a group_id")
    
    st.markdown("---")
    
    
    # Short Term Memory Stats
    st.markdown("### Short Term Memory Stats")
    if st.button("Get Short Term Memory Stats", key="short_term_stats"):
        try:
            base = get_api_base_url()
            project_id = st.session_state.get("project_id", "default_project")
            resp = requests.get(f"{base}/short-term/stats/{project_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "success":
                stats = data.get("stats", {})
                st.success(f"Short Term Memory Stats for project: {project_id}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Messages", stats.get("total_messages", 0))
                with col2:
                    st.metric("Cache Loaded", "Yes" if stats.get("cache_loaded", False) else "No")
                with col3:
                    st.metric("Conversations", len(stats.get("by_conversation", {})))
                
                # Show breakdown by role
                if stats.get("by_role"):
                    st.markdown("**By Role:**")
                    for role, count in stats["by_role"].items():
                        st.write(f"- {role}: {count}")
                
                # Show breakdown by intent
                if stats.get("by_intent"):
                    st.markdown("**By Intent:**")
                    for intent, count in stats["by_intent"].items():
                        st.write(f"- {intent}: {count}")
                
                # Show conversations
                if stats.get("by_conversation"):
                    st.markdown("**Conversations:**")
                    for conv_id, count in list(stats["by_conversation"].items())[:5]:  # Show first 5
                        st.write(f"- {conv_id}: {count} messages")
                
            else:
                st.error(f"Error getting stats: {data.get('message', 'Unknown error')}")
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    # Short Term Memory Health Check
    if st.button("Check Short Term Memory Health", key="short_term_health"):
        try:
            base = get_api_base_url()
            resp = requests.get(f"{base}/short-term/health", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "healthy":
                st.success("Short Term Memory is healthy")
                st.json(data)
            else:
                st.error(f"Short Term Memory is unhealthy: {data.get('error', 'Unknown error')}")
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    # Cleanup expired messages
    if st.button("Cleanup Expired Messages", key="short_term_cleanup"):
        try:
            base = get_api_base_url()
            resp = requests.post(f"{base}/short-term/cleanup", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "success":
                deleted_count = data.get("deleted_count", 0)
                st.success(f"Cleaned up {deleted_count} expired messages")
            else:
                st.error(f"Error: {data.get('message', 'Unknown error')}")
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.markdown("---")
    st.markdown("### Current Session Info")
    st.json({
        "current_group_id": st.session_state.get("group_id", "Not set"),
        "chat_messages_count": len(st.session_state.get("chat_messages", [])),
        "mem_buffer_size": len(st.session_state.get("mem_buffer", [])),
        "mem_user_count": st.session_state.get("mem_user_count", 0),
        "short_term_saved": len(st.session_state.get("short_term_saved", [])),
        "project_id": st.session_state.get("project_id", "default_project"),
        "enable_short_term_memory": st.session_state.get("enable_short_term_memory", True)
    })


