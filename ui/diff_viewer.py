#!/usr/bin/env python3
"""
Diff Viewer Component for Streamlit
Hiển thị sự thay đổi code giống như Cursor/VS Code
"""

import streamlit as st
import difflib
from typing import List, Dict, Any, Optional
import re

def render_diff_viewer(
    file_before: str,
    file_after: str,
    file_name: str = "file.py",
    line_start: int = 1,
    line_end: int = None,
    max_lines: int = 100
):
    """
    Render diff viewer giống Cursor/VS Code
    
    Args:
        file_before: Nội dung file trước khi thay đổi
        file_after: Nội dung file sau khi thay đổi  
        file_name: Tên file
        line_start: Dòng bắt đầu
        line_end: Dòng kết thúc
        max_lines: Số dòng tối đa hiển thị
    """
    
    if not file_before and not file_after:
        st.warning("Không có dữ liệu để hiển thị diff")
        return
    
    # Nếu chỉ có một file, hiển thị file đó
    if not file_before:
        st.info("📄 **File mới được tạo**")
        render_file_content(file_after, file_name, "new")
        return
    elif not file_after:
        st.info("🗑️ **File đã bị xóa**")
        render_file_content(file_before, file_name, "deleted")
        return
    
    # Tạo diff
    diff_lines = list(difflib.unified_diff(
        file_before.splitlines(keepends=True),
        file_after.splitlines(keepends=True),
        fromfile=f"{file_name} (before)",
        tofile=f"{file_name} (after)",
        lineterm=""
    ))
    
    if not diff_lines:
        st.success("✅ **Không có thay đổi nào**")
        return
    
    # Header
    st.markdown(f"### 📝 **Diff View: {file_name}**")
    
    # Stats
    added_lines = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
    removed_lines = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 Lines Added", added_lines)
    with col2:
        st.metric("📉 Lines Removed", removed_lines)
    with col3:
        st.metric("📊 Net Change", added_lines - removed_lines)
    with col4:
        st.metric("📄 Total Lines", len(file_after.splitlines()))
    
    # Diff content
    st.markdown("---")
    
    # Tạo diff HTML
    diff_html = create_diff_html(diff_lines, max_lines)
    st.components.v1.html(diff_html, height=600, scrolling=True)

def render_file_content(content: str, file_name: str, file_type: str = "normal"):
    """Render nội dung file đơn giản"""
    
    if file_type == "new":
        st.markdown("**📄 Nội dung file mới:**")
    elif file_type == "deleted":
        st.markdown("**🗑️ Nội dung file đã xóa:**")
    else:
        st.markdown(f"**📄 Nội dung {file_name}:**")
    
    # Syntax highlighting
    if file_name.endswith('.py'):
        st.code(content, language='python')
    elif file_name.endswith(('.js', '.ts')):
        st.code(content, language='javascript')
    elif file_name.endswith(('.html', '.htm')):
        st.code(content, language='html')
    elif file_name.endswith('.css'):
        st.code(content, language='css')
    elif file_name.endswith(('.json', '.jsonc')):
        st.code(content, language='json')
    else:
        st.code(content)

def create_diff_html(diff_lines: List[str], max_lines: int = 100) -> str:
    """Tạo HTML cho diff viewer"""
    
    html = """
    <style>
        .diff-container {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
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
            padding: 2px 0;
        }
        .diff-line-number {
            width: 60px;
            text-align: right;
            padding-right: 16px;
            color: #6a6a6a;
            user-select: none;
            flex-shrink: 0;
        }
        .diff-line-content {
            flex: 1;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .diff-added {
            background-color: #0d5016;
            border-left: 3px solid #4caf50;
        }
        .diff-removed {
            background-color: #5c1a1a;
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
        }
    </style>
    
    <div class="diff-container">
        <div class="diff-header">
            📝 Code Changes Diff View
        </div>
    """
    
    line_count = 0
    current_line_num = 0
    
    for line in diff_lines:
        if line_count >= max_lines:
            html += f'<div class="diff-line diff-context"><div class="diff-line-number">...</div><div class="diff-line-content">... (showing first {max_lines} lines)</div></div>'
            break
            
        if line.startswith('+++') or line.startswith('---'):
            # File header
            html += f'<div class="diff-line diff-context"><div class="diff-line-number"></div><div class="diff-line-content">{line.rstrip()}</div></div>'
        elif line.startswith('@@'):
            # Hunk header
            html += f'<div class="diff-line diff-context"><div class="diff-line-number"></div><div class="diff-line-content">{line.rstrip()}</div></div>'
        elif line.startswith('+'):
            # Added line
            current_line_num += 1
            line_count += 1
            content = line[1:].rstrip()
            html += f'<div class="diff-line diff-added"><div class="diff-line-number">{current_line_num}</div><div class="diff-line-content">{content}</div></div>'
        elif line.startswith('-'):
            # Removed line
            line_count += 1
            content = line[1:].rstrip()
            html += f'<div class="diff-line diff-removed"><div class="diff-line-number"></div><div class="diff-line-content">{content}</div></div>'
        else:
            # Context line
            current_line_num += 1
            line_count += 1
            content = line.rstrip()
            html += f'<div class="diff-line diff-context"><div class="diff-line-number">{current_line_num}</div><div class="diff-line-content">{content}</div></div>'
    
    html += "</div>"
    return html

def render_simple_diff(
    lines_added: str,
    lines_removed: str,
    file_name: str = "file.py",
    line_start: int = 1,
    line_end: int = None
):
    """
    Render diff đơn giản từ lines_added và lines_removed
    """
    
    st.markdown(f"### 📝 **Code Changes: {file_name}**")
    
    # Stats
    added_count = len(lines_added.splitlines()) if lines_added else 0
    removed_count = len(lines_removed.splitlines()) if lines_removed else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Lines Added", added_count)
    with col2:
        st.metric("📉 Lines Removed", removed_count)
    with col3:
        st.metric("📊 Net Change", added_count - removed_count)
    
    st.markdown("---")
    
    # Side by side view
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔴 Removed Lines:**")
        if lines_removed:
            st.code(lines_removed, language='python')
        else:
            st.info("No lines removed")
    
    with col2:
        st.markdown("**🟢 Added Lines:**")
        if lines_added:
            st.code(lines_added, language='python')
        else:
            st.info("No lines added")

def render_code_changes_from_metadata(metadata: Dict[str, Any]):
    """
    Render diff từ metadata object với logic detect chính xác
    """
    
    file_name = metadata.get('file_name', 'unknown')
    file_path = metadata.get('file_path', file_name)
    change_type = metadata.get('change_type', 'modified')
    
    # Get code changes
    code_changes = metadata.get('code_changes', {})
    lines_added = code_changes.get('lines_added', '')
    lines_removed = code_changes.get('lines_removed', '')
    file_before = code_changes.get('file_before', '')
    file_after = code_changes.get('file_after', '')
    
    # Get line info
    line_start = metadata.get('line_start', 1)
    line_end = metadata.get('line_end', line_start + 10)
    
    # Render based on available data
    if file_before and file_after:
        # Full diff view với logic detect chính xác
        render_advanced_diff_viewer(file_before, file_after, file_path, line_start, line_end)
    elif lines_added or lines_removed:
        # Simple diff view
        render_simple_diff(lines_added, lines_removed, file_path, line_start, line_end)
    else:
        st.warning("Không có thông tin diff để hiển thị")

def render_advanced_diff_viewer(
    file_before: str,
    file_after: str,
    file_name: str = "file.py",
    line_start: int = 1,
    line_end: int = None,
    max_lines: int = 100
):
    """
    Advanced diff viewer với logic detect chính xác như Cursor
    """
    
    if not file_before and not file_after:
        st.warning("Không có dữ liệu để hiển thị diff")
        return
    
    # Nếu chỉ có một file, hiển thị file đó
    if not file_before:
        st.info("📄 **File mới được tạo**")
        render_file_content(file_after, file_name, "new")
        return
    elif not file_after:
        st.info("🗑️ **File đã bị xóa**")
        render_file_content(file_before, file_name, "deleted")
        return
    
    # Detect changes với logic chính xác
    import difflib
    matcher = difflib.SequenceMatcher(None, file_before.splitlines(), file_after.splitlines())
    
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
                removed_lines.append(file_before.splitlines()[i])
                line_changes.append({
                    "type": "removed",
                    "line_number": orig_line_num,
                    "content": file_before.splitlines()[i]
                })
        
        elif tag == "insert":
            # Lines added
            for j in range(j1, j2):
                mod_line_num += 1
                added_lines.append(file_after.splitlines()[j])
                line_changes.append({
                    "type": "added",
                    "line_number": mod_line_num,
                    "content": file_after.splitlines()[j]
                })
        
        elif tag == "replace":
            # Lines replaced
            for i in range(i1, i2):
                orig_line_num += 1
                removed_lines.append(file_before.splitlines()[i])
                line_changes.append({
                    "type": "removed",
                    "line_number": orig_line_num,
                    "content": file_before.splitlines()[i]
                })
            
            for j in range(j1, j2):
                mod_line_num += 1
                added_lines.append(file_after.splitlines()[j])
                line_changes.append({
                    "type": "added",
                    "line_number": mod_line_num,
                    "content": file_after.splitlines()[j]
                })
        
        elif tag == "equal":
            # Context lines
            orig_line_num += (i2 - i1)
            mod_line_num += (j2 - j1)
    
    # Header
    st.markdown(f"### 📝 **Advanced Diff: {file_name}**")
    
    # Stats
    net_change = len(added_lines) - len(removed_lines)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📈 Lines Added", len(added_lines))
    with col2:
        st.metric("📉 Lines Removed", len(removed_lines))
    with col3:
        st.metric("📊 Net Change", net_change)
    with col4:
        st.metric("📄 Total Lines", len(file_after.splitlines()))
    
    # Change type
    if not added_lines and not removed_lines:
        change_type = "unchanged"
    elif not added_lines:
        change_type = "deleted"
    elif not removed_lines:
        change_type = "added"
    else:
        change_type = "modified"
    
    st.info(f"**Change Type:** {change_type.upper()}")
    
    # Diff content
    st.markdown("---")
    
    # Tạo diff HTML với logic chính xác
    diff_html = create_advanced_diff_html(file_before, file_after, file_name, max_lines)
    st.components.v1.html(diff_html, height=600, scrolling=True)

def create_advanced_diff_html(
    file_before: str,
    file_after: str,
    file_name: str,
    max_lines: int = 100
) -> str:
    """
    Tạo HTML cho advanced diff với logic chính xác
    """
    
    html = """
    <style>
        .advanced-diff {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
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
            padding: 2px 0;
        }
        .diff-line-number {
            width: 60px;
            text-align: right;
            padding-right: 16px;
            color: #6a6a6a;
            user-select: none;
            flex-shrink: 0;
        }
        .diff-line-content {
            flex: 1;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .diff-added {
            background-color: rgba(0, 255, 0, 0.15);
            border-left: 3px solid #4caf50;
        }
        .diff-removed {
            background-color: rgba(255, 0, 0, 0.15);
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
        }
    </style>
    
    <div class="advanced-diff">
        <div class="diff-header">
            📝 Advanced Diff: {file_name}
        </div>
    """
    
    # Sử dụng SequenceMatcher để tạo diff chính xác
    import difflib
    matcher = difflib.SequenceMatcher(None, file_before.splitlines(), file_after.splitlines())
    
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
                content = file_before.splitlines()[i]
                html += f'<div class="diff-line diff-context"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "delete":
            # Removed lines
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = file_before.splitlines()[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "insert":
            # Added lines
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = file_after.splitlines()[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
        
        elif tag == "replace":
            # Replaced lines - show removed first, then added
            for i in range(i1, i2):
                orig_line_num += 1
                line_count += 1
                content = file_before.splitlines()[i]
                html += f'<div class="diff-line diff-removed"><div class="diff-line-number">{orig_line_num}</div><div class="diff-line-content">{content}</div></div>'
            
            for j in range(j1, j2):
                mod_line_num += 1
                line_count += 1
                content = file_after.splitlines()[j]
                html += f'<div class="diff-line diff-added"><div class="diff-line-number">{mod_line_num}</div><div class="diff-line-content">{content}</div></div>'
    
    html += "</div>"
    return html
