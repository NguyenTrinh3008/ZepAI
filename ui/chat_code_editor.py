#!/usr/bin/env python3
"""
Chat Code Editor - Tích hợp code editor vào chat interface
Giống như cách user và AI đang làm hiện tại
"""

import streamlit as st
import difflib
from typing import Dict, Any, Optional, Tuple
import json

def render_chat_code_editor(
    file_content: str = "",
    file_name: str = "file.py",
    language: str = "python",
    key: str = "chat_editor"
):
    """
    Render code editor tích hợp trong chat interface
    
    Args:
        file_content: Nội dung file hiện tại
        file_name: Tên file
        language: Ngôn ngữ lập trình
        key: Unique key cho Streamlit
    """
    
    # Tạo container cho editor
    with st.container():
        st.markdown(f"### 📝 **Editing: {file_name}**")
        
        # Editor với syntax highlighting
        edited_content = st.text_area(
            "Edit your code:",
            value=file_content,
            height=300,
            key=f"chat_editor_{key}",
            help=f"Edit {file_name} directly. Changes will be detected automatically.",
            label_visibility="collapsed"
        )
        
        # Detect changes
        if edited_content != file_content:
            st.info("🔍 **Changes detected!**")
            
            # Show inline diff
            render_chat_inline_diff(file_content, edited_content, file_name)
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 **Save Changes**", key=f"chat_save_{key}"):
                    st.success("✅ Changes saved!")
                    return edited_content, "saved"
            
            with col2:
                if st.button("🔄 **Reset**", key=f"chat_reset_{key}"):
                    st.rerun()
            
            with col3:
                if st.button("📤 **Apply & Continue**", key=f"chat_apply_{key}"):
                    return edited_content, "apply"
        else:
            # Show current content info
            st.caption(f"📄 **Current file:** {file_name} ({len(file_content.splitlines())} lines)")
    
    return edited_content, "no_change"

def render_chat_inline_diff(
    original: str,
    modified: str,
    file_name: str = "file.py"
):
    """
    Render inline diff trong chat interface
    """
    
    # Tạo diff
    diff_lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"{file_name} (original)",
        tofile=f"{file_name} (modified)",
        lineterm=""
    ))
    
    if not diff_lines:
        st.success("✅ No changes detected")
        return
    
    # Stats
    added_lines = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
    removed_lines = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Added", added_lines)
    with col2:
        st.metric("📉 Removed", removed_lines)
    with col3:
        st.metric("📊 Net", added_lines - removed_lines)
    
    # Compact diff view
    st.markdown("#### 🔍 **Changes Preview:**")
    
    # Tạo compact diff HTML
    diff_html = create_chat_diff_html(original, modified, file_name)
    st.components.v1.html(diff_html, height=200, scrolling=True)

def create_chat_diff_html(
    original: str,
    modified: str,
    file_name: str
) -> str:
    """
    Tạo HTML cho chat diff (compact version)
    """
    
    html = """
    <style>
        .chat-diff {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.3;
            background: #f8f9fa;
            color: #333;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #e9ecef;
            overflow-x: auto;
        }
        .diff-line {
            display: flex;
            min-height: 18px;
            padding: 1px 0;
        }
        .diff-line-number {
            width: 40px;
            text-align: right;
            padding-right: 8px;
            color: #6c757d;
            user-select: none;
            flex-shrink: 0;
            font-size: 11px;
        }
        .diff-line-content {
            flex: 1;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .diff-added {
            background-color: rgba(40, 167, 69, 0.1);
            border-left: 2px solid #28a745;
        }
        .diff-removed {
            background-color: rgba(220, 53, 69, 0.1);
            border-left: 2px solid #dc3545;
        }
        .diff-context {
            background-color: transparent;
        }
    </style>
    
    <div class="chat-diff">
    """
    
    # Sử dụng SequenceMatcher để tạo diff chính xác
    matcher = difflib.SequenceMatcher(None, original.splitlines(), modified.splitlines())
    
    line_count = 0
    orig_line_num = 0
    mod_line_num = 0
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if line_count >= 20:  # Limit for chat
            html += f'<div class="diff-line diff-context"><div class="diff-line-number">...</div><div class="diff-line-content">... (showing first 20 changes)</div></div>'
            break
            
        if tag == "equal":
            # Context lines
            for i in range(i1, i2):
                orig_line_num += 1
                mod_line_num += 1
                line_count += 1
                content = original.splitlines()[i]
                html += f'<div class="diff-line diff-context"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "delete":
            # Removed lines
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = original.splitlines()[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "insert":
            # Added lines
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = modified.splitlines()[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "replace":
            # Replaced lines
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = original.splitlines()[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
            
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = modified.splitlines()[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
    
    html += "</div>"
    return html

def detect_chat_code_changes(
    original: str,
    modified: str,
    file_name: str = "file.py"
) -> Dict[str, Any]:
    """
    Detect code changes cho chat interface
    """
    
    if not original and not modified:
        return {"error": "No content to compare"}
    
    if not original:
        return {
            "change_type": "created",
            "file_action": "created",
            "lines_added": len(modified.splitlines()),
            "lines_removed": 0,
            "file_before": "",
            "file_after": modified,
            "diff_summary": f"Created new file {file_name}",
            "intent": "file_creation"
        }
    
    if not modified:
        return {
            "change_type": "deleted",
            "file_action": "deleted", 
            "lines_added": 0,
            "lines_removed": len(original.splitlines()),
            "file_before": original,
            "file_after": "",
            "diff_summary": f"Deleted file {file_name}",
            "intent": "file_deletion"
        }
    
    # Sử dụng SequenceMatcher để detect changes chính xác
    matcher = difflib.SequenceMatcher(None, original.splitlines(), modified.splitlines())
    
    added_lines = []
    removed_lines = []
    line_changes = []
    
    orig_line_num = 0
    mod_line_num = 0
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            # Lines removed
            for i in range(i1, i2):
                orig_line_num += 1
                removed_lines.append(original.splitlines()[i])
                line_changes.append({
                    "type": "removed",
                    "line_number": orig_line_num,
                    "content": original.splitlines()[i]
                })
        
        elif tag == "insert":
            # Lines added
            for j in range(j1, j2):
                mod_line_num += 1
                added_lines.append(modified.splitlines()[j])
                line_changes.append({
                    "type": "added",
                    "line_number": mod_line_num,
                    "content": modified.splitlines()[j]
                })
        
        elif tag == "replace":
            # Lines replaced
            for i in range(i1, i2):
                orig_line_num += 1
                removed_lines.append(original.splitlines()[i])
                line_changes.append({
                    "type": "removed",
                    "line_number": orig_line_num,
                    "content": original.splitlines()[i]
                })
            
            for j in range(j1, j2):
                mod_line_num += 1
                added_lines.append(modified.splitlines()[j])
                line_changes.append({
                    "type": "added",
                    "line_number": mod_line_num,
                    "content": modified.splitlines()[j]
                })
        
        elif tag == "equal":
            # Context lines
            orig_line_num += (i2 - i1)
            mod_line_num += (j2 - j1)
    
    # Determine change type
    if not added_lines and not removed_lines:
        change_type = "unchanged"
        file_action = "unchanged"
    elif not added_lines:
        change_type = "deleted"
        file_action = "deleted"
    elif not removed_lines:
        change_type = "added"
        file_action = "added"
    else:
        change_type = "modified"
        file_action = "modified"
    
    # Calculate line ranges
    if line_changes:
        line_start = min(change["line_number"] for change in line_changes)
        line_end = max(change["line_number"] for change in line_changes)
    else:
        line_start = 1
        line_end = 1
    
    # Create summary
    net_change = len(added_lines) - len(removed_lines)
    if net_change > 0:
        diff_summary = f"Added {len(added_lines)} lines, removed {len(removed_lines)} lines in {file_name}"
    elif net_change < 0:
        diff_summary = f"Removed {len(removed_lines)} lines, added {len(added_lines)} lines in {file_name}"
    else:
        diff_summary = f"Modified {len(added_lines)} lines in {file_name}"
    
    return {
        "change_type": change_type,
        "file_action": file_action,
        "file_name": file_name,
        "lines_added": len(added_lines),
        "lines_removed": len(removed_lines),
        "line_start": line_start,
        "line_end": line_end,
        "file_before": original,
        "file_after": modified,
        "lines_added_content": "\n".join(added_lines),
        "lines_removed_content": "\n".join(removed_lines),
        "diff_summary": diff_summary,
        "intent": f"code_{change_type}",
        "line_changes": line_changes,
        "net_change": net_change
    }
