#!/usr/bin/env python3
"""
Code Editor Component for Streamlit
Tự chỉnh sửa file code trực tiếp giống Cursor
"""

import streamlit as st
import difflib
from typing import List, Dict, Any, Optional, Tuple
import re
import json

def render_code_editor(
    file_content: str = "",
    file_name: str = "file.py",
    language: str = "python",
    height: int = 400,
    key: str = "code_editor"
):
    """
    Render code editor giống Cursor
    
    Args:
        file_content: Nội dung file hiện tại
        file_name: Tên file
        language: Ngôn ngữ lập trình
        height: Chiều cao editor
        key: Unique key cho Streamlit
    """
    
    st.markdown(f"### 📝 **Code Editor: {file_name}**")
    
    # Editor với syntax highlighting
    edited_content = st.text_area(
        "Edit your code:",
        value=file_content,
        height=height,
        key=f"editor_{key}",
        help=f"Edit {file_name} directly. Changes will be detected automatically."
    )
    
    # Detect changes
    if edited_content != file_content:
        st.info("🔍 **Changes detected!**")
        
        # Show diff
        render_inline_diff(file_content, edited_content, file_name)
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 **Save Changes**", key=f"save_{key}"):
                st.success("✅ Changes saved!")
                return edited_content, "saved"
        
        with col2:
            if st.button("🔄 **Reset**", key=f"reset_{key}"):
                st.rerun()
        
        with col3:
            if st.button("📤 **Apply to File**", key=f"apply_{key}"):
                return edited_content, "apply"
    
    return edited_content, "no_change"

def render_inline_diff(
    original: str,
    modified: str,
    file_name: str = "file.py",
    max_lines: int = 50
):
    """
    Render inline diff giống Cursor
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
    
    # Inline diff view
    st.markdown("#### 🔍 **Changes Preview:**")
    
    # Tạo diff HTML
    diff_html = create_inline_diff_html(original, modified, file_name, max_lines)
    st.components.v1.html(diff_html, height=300, scrolling=True)

def create_inline_diff_html(
    original: str,
    modified: str,
    file_name: str,
    max_lines: int = 50
) -> str:
    """
    Tạo HTML cho inline diff
    """
    
    html = """
    <style>
        .inline-diff {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.4;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
        }
        .diff-line {
            display: flex;
            min-height: 20px;
            padding: 1px 0;
        }
        .diff-line-number {
            width: 50px;
            text-align: right;
            padding-right: 12px;
            color: #6a6a6a;
            user-select: none;
            flex-shrink: 0;
            font-size: 12px;
        }
        .diff-line-content {
            flex: 1;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .diff-added {
            background-color: rgba(0, 255, 0, 0.1);
            border-left: 3px solid #4caf50;
        }
        .diff-removed {
            background-color: rgba(255, 0, 0, 0.1);
            border-left: 3px solid #f44336;
        }
        .diff-context {
            background-color: transparent;
        }
        .diff-header {
            background-color: #2d2d30;
            color: #cccccc;
            font-weight: bold;
            padding: 8px 16px;
            margin: -16px -16px 16px -16px;
            border-radius: 8px 8px 0 0;
            font-size: 12px;
        }
    </style>
    
    <div class="inline-diff">
        <div class="diff-header">
            📝 Changes in {file_name}
        </div>
    """
    
    # Tạo side-by-side diff
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()
    
    # Sử dụng SequenceMatcher để tạo diff chính xác
    matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)
    
    line_count = 0
    orig_line_num = 0
    mod_line_num = 0
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if line_count >= max_lines:
            html += f'<div class="diff-line diff-context"><div class="diff-line-number">...</div><div class="diff-line-content">... (showing first {max_lines} changes)</div></div>'
            break
            
        if tag == "equal":
            # Context lines
            for i in range(i1, i2):
                orig_line_num += 1
                mod_line_num += 1
                line_count += 1
                content = original_lines[i]
                html += f'<div class="diff-line diff-context"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "delete":
            # Removed lines
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = original_lines[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "insert":
            # Added lines
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = modified_lines[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "replace":
            # Replaced lines
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = original_lines[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
            
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = modified_lines[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
    
    html += "</div>"
    return html

def detect_code_changes_advanced(
    original: str,
    modified: str,
    file_name: str = "file.py"
) -> Dict[str, Any]:
    """
    Detect code changes với logic chính xác như Cursor
    
    Args:
        original: File content trước khi thay đổi
        modified: File content sau khi thay đổi
        file_name: Tên file
    
    Returns:
        Dict chứa thông tin changes chi tiết
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

def render_file_editor_tab():
    """
    Render tab file editor chính
    """
    
    st.subheader("📝 **Code Editor**")
    st.markdown("Edit files directly like in Cursor")
    
    # File selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        file_name = st.text_input(
            "File Name",
            value="main.py",
            help="Enter the file name to edit",
            key="editor_file_name"
        )
    
    with col2:
        language = st.selectbox(
            "Language",
            ["python", "javascript", "typescript", "html", "css", "json", "markdown"],
            key="editor_language"
        )
    
    # Load existing file content
    if st.button("📁 Load File", key="load_file"):
        # TODO: Implement file loading from memory or file system
        st.info("File loading feature coming soon!")
    
    # Editor
    file_content = st.text_area(
        "Code Editor",
        value="# Enter your code here...\nprint('Hello, World!')",
        height=400,
        key="main_editor",
        help="Edit your code directly. Changes will be detected automatically."
    )
    
    # Detect changes
    if st.button("🔍 Detect Changes", key="detect_changes"):
        # Simulate original content for demo
        original_content = "# Original code\nprint('Hello, World!')"
        
        changes = detect_code_changes_advanced(original_content, file_content, file_name)
        
        if changes.get("error"):
            st.error(changes["error"])
        else:
            st.success("✅ Changes detected!")
            
            # Display changes
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Lines Added", changes["lines_added"])
            with col2:
                st.metric("Lines Removed", changes["lines_removed"])
            with col3:
                st.metric("Net Change", changes["net_change"])
            
            # Show diff
            render_inline_diff(original_content, file_content, file_name)
            
            # Show detailed changes
            with st.expander("📊 Detailed Changes", expanded=False):
                st.json(changes)
    
    # Save changes
    if st.button("💾 Save Changes", key="save_changes"):
        st.success("✅ Changes saved to memory!")
        # TODO: Implement saving to memory system
