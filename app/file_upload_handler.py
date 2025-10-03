#!/usr/bin/env python3
"""
File upload handler để xử lý file code và trích xuất thông tin code changes
"""

import os
import json
import uuid
import difflib
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import tempfile

from app.schemas import ShortTermMemoryRequest, ShortTermMemoryMetadata
from app.short_term_storage import get_storage
from app.short_term_extractor import get_extractor

class FileUploadHandler:
    """Handler để xử lý file upload và trích xuất code changes"""
    
    def __init__(self):
        self.storage = get_storage()
        self.extractor = get_extractor()
        self.temp_dir = Path(tempfile.gettempdir()) / "zepai_uploads"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def process_file_upload(self, 
                                 file_content: str,
                                 file_name: str,
                                 project_id: str,
                                 conversation_id: str,
                                 role: str = "assistant",
                                 content: str = "",
                                 **kwargs) -> Dict[str, Any]:
        """
        Xử lý file upload và trích xuất code changes
        
        Args:
            file_content: Nội dung file code
            file_name: Tên file (ví dụ: "src/auth/auth_service.py")
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            role: Role của message ("user", "assistant", "system")
            content: Nội dung message mô tả thay đổi
            **kwargs: Các tham số khác
            
        Returns:
            Dict chứa thông tin code changes được trích xuất
        """
        try:
            # Lưu file tạm thời để phân tích
            temp_file_path = self.temp_dir / f"{uuid.uuid4()}_{file_name}"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            
            # Phân tích file để trích xuất thông tin
            file_analysis = await self._analyze_file(temp_file_path, file_name)
            
            # Tạo code_changes object
            code_changes = {
                "change_type": kwargs.get("change_type", "modified"),
                "description": kwargs.get("description", "File uploaded and analyzed"),
                "file_analysis": file_analysis,
                "file_content": file_content,
                "file_name": file_name
            }
            
            # Trích xuất thông tin từ file analysis
            line_start = file_analysis.get("line_start")
            line_end = file_analysis.get("line_end")
            function_name = file_analysis.get("function_name")
            lines_added = file_analysis.get("lines_added", 0)
            lines_removed = file_analysis.get("lines_removed", 0)
            diff_summary = file_analysis.get("diff_summary", "")
            
            # Tạo ShortTermMemoryRequest
            request = ShortTermMemoryRequest(
                role=role,
                content=content or f"Uploaded and analyzed file: {file_name}",
                project_id=project_id,
                conversation_id=conversation_id,
                file_path=file_name,
                function_name=function_name,
                line_start=line_start,
                line_end=line_end,
                code_changes=code_changes,
                lines_added=lines_added,
                lines_removed=lines_removed,
                diff_summary=diff_summary,
                intent=kwargs.get("intent"),
                keywords=kwargs.get("keywords"),
                ttl=kwargs.get("ttl", 3600)
            )
            
            # Lưu vào short term memory
            message_id = await self.storage.save_message(request)
            
            # Cleanup temp file
            temp_file_path.unlink(missing_ok=True)
            
            return {
                "status": "success",
                "message_id": message_id,
                "file_analysis": file_analysis,
                "code_changes": code_changes
            }
            
        except Exception as e:
            # Cleanup temp file on error
            if 'temp_file_path' in locals():
                temp_file_path.unlink(missing_ok=True)
            raise e
    
    async def process_code_changes_payload(self, 
                                         payload: Dict[str, Any],
                                         project_id: str,
                                         conversation_id: str,
                                         role: str = "assistant") -> Dict[str, Any]:
        """
        Xử lý payload code changes từ IDE/editor
        
        Args:
            payload: Payload chứa file_before, file_after, chunks
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            role: Role của message
            
        Returns:
            Dict chứa thông tin code changes được xử lý
        """
        try:
            file_before = payload.get("file_before", "")
            file_after = payload.get("file_after", "")
            chunks = payload.get("chunks", [])
            
            results = []
            
            for chunk in chunks:
                file_name = chunk.get("file_name", "")
                file_action = chunk.get("file_action", "edit")
                line1 = chunk.get("line1", 1)
                line2 = chunk.get("line2", 1)
                lines_remove = chunk.get("lines_remove", "")
                lines_add = chunk.get("lines_add", "")
                
                # Tạo code_changes object chi tiết
                code_changes = {
                    "change_type": file_action,
                    "description": f"Code changes in {file_name}",
                    "file_action": file_action,
                    "line_range": {
                        "start": line1,
                        "end": line2
                    },
                    "lines_removed": lines_remove,
                    "lines_added": lines_add,
                    "file_before": file_before,
                    "file_after": file_after
                }
                
                # Tính toán lines_added và lines_removed
                lines_added = len(lines_add.split('\n')) if lines_add else 0
                lines_removed = len(lines_remove.split('\n')) if lines_remove else 0
                
                # Tạo diff_summary
                diff_summary = f"Added {lines_added} lines, removed {lines_removed} lines in {file_name}"
                
                # Tạo ShortTermMemoryRequest
                request = ShortTermMemoryRequest(
                    role=role,
                    content=f"Code changes in {file_name}: {file_action}",
                    project_id=project_id,
                    conversation_id=conversation_id,
                    file_path=file_name,
                    function_name=self._extract_function_name(lines_add or lines_remove),
                    line_start=line1,
                    line_end=line2,
                    code_changes=code_changes,
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    diff_summary=diff_summary,
                    intent="code_modification",
                    keywords=self._extract_keywords(lines_add or lines_remove),
                    ttl=3600
                )
                
                # Lưu vào short term memory
                message_id = await self.storage.save_message(request)
                
                results.append({
                    "message_id": message_id,
                    "file_name": file_name,
                    "file_action": file_action,
                    "line_range": f"{line1}-{line2}",
                    "lines_added": lines_added,
                    "lines_removed": lines_removed
                })
            
            return {
                "status": "success",
                "results": results,
                "total_changes": len(results)
            }
            
        except Exception as e:
            raise e
    
    async def _analyze_file(self, file_path: Path, file_name: str) -> Dict[str, Any]:
        """
        Phân tích file để trích xuất thông tin code
        
        Args:
            file_path: Đường dẫn file
            file_name: Tên file
            
        Returns:
            Dict chứa thông tin phân tích file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            total_lines = len(lines)
            
            # Tìm function definitions
            functions = []
            for i, line in enumerate(lines, 1):
                if line.strip().startswith('def ') or line.strip().startswith('function '):
                    functions.append({
                        "name": self._extract_function_name(line),
                        "line": i
                    })
            
            # Tìm class definitions
            classes = []
            for i, line in enumerate(lines, 1):
                if line.strip().startswith('class '):
                    classes.append({
                        "name": self._extract_class_name(line),
                        "line": i
                    })
            
            # Tìm imports
            imports = []
            for i, line in enumerate(lines, 1):
                if line.strip().startswith(('import ', 'from ')):
                    imports.append({
                        "statement": line.strip(),
                        "line": i
                    })
            
            return {
                "file_name": file_name,
                "total_lines": total_lines,
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "line_start": 1,
                "line_end": total_lines,
                "function_name": functions[0]["name"] if functions else None,
                "lines_added": 0,
                "lines_removed": 0,
                "diff_summary": f"Analyzed {total_lines} lines in {file_name}"
            }
            
        except Exception as e:
            return {
                "file_name": file_name,
                "error": str(e),
                "line_start": 1,
                "line_end": 1,
                "lines_added": 0,
                "lines_removed": 0
            }
    
    def _extract_function_name(self, code: str) -> Optional[str]:
        """Trích xuất tên function từ code"""
        import re
        patterns = [
            r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
            r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
            r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*{'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                return match.group(1)
        return None
    
    def _extract_class_name(self, code: str) -> Optional[str]:
        """Trích xuất tên class từ code"""
        import re
        match = re.search(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)', code)
        return match.group(1) if match else None
    
    def _extract_keywords(self, code: str) -> List[str]:
        """Trích xuất keywords từ code"""
        import re
        
        keywords = []
        
        # Tìm function calls
        function_calls = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', code)
        keywords.extend(function_calls)
        
        # Tìm variable names
        variables = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=', code)
        keywords.extend(variables)
        
        # Tìm string literals
        strings = re.findall(r'"([^"]*)"', code)
        keywords.extend(strings)
        
        return list(set(keywords))[:10]  # Limit to 10 keywords
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """Trích xuất các khối code từ văn bản (ví dụ: markdown code blocks)"""
        # Tìm code blocks trong markdown format
        code_blocks = re.findall(r'```(?:[a-zA-Z0-9_]+)?\n(.*?)\n```', text, re.DOTALL)
        if code_blocks:
            return code_blocks
        
        # Nếu không có code blocks, tìm code trong text thường
        # Tìm các dòng bắt đầu bằng def, class, import, etc.
        lines = text.split('\n')
        code_lines = []
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(('def ', 'class ', 'import ', 'from ', 'if ', 'for ', 'while ', 'try:', 'except:', 'finally:', 'with ', 'async def ')) or
                stripped.endswith(':') or
                (in_code_block and (stripped.startswith('    ') or stripped.startswith('\t') or stripped == ''))):
                code_lines.append(line)
                in_code_block = True
            elif in_code_block and stripped == '':
                code_lines.append(line)
            elif in_code_block and not (stripped.startswith('    ') or stripped.startswith('\t')):
                break
        
        if code_lines:
            return ['\n'.join(code_lines)]
        
        # Nếu không tìm thấy code blocks, return empty list
        return []
    
    def _compare_code_changes(self, 
                             original_content: str, 
                             modified_content: str, 
                             file_name: str,
                             change_type: str = "modified") -> Dict[str, Any]:
        """
        So sánh nội dung file gốc với nội dung đã chỉnh sửa và trả về payload code_changes.
        
        Args:
            original_content: Nội dung file gốc.
            modified_content: Nội dung file đã được AI chỉnh sửa.
            file_name: Tên file.
            change_type: Loại thay đổi (mặc định là "modified").
            
        Returns:
            Dict[str, Any]: Payload code_changes theo schema.
        """
        
        # Normalize line endings
        original_lines = original_content.replace('\r\n', '\n').splitlines(keepends=True)
        modified_lines = modified_content.replace('\r\n', '\n').splitlines(keepends=True)
        
        # Tạo unified diff
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
            lineterm=''
        )
        
        chunks = []
        current_chunk = None
        line_num_original = 0
        line_num_modified = 0
        
        # Bỏ qua 2 dòng header của unified diff
        diff_lines = list(diff)[2:] 
        
        print(f"DEBUG: Diff lines count: {len(diff_lines)}")
        print(f"DEBUG: First few diff lines: {[line.encode('ascii', 'replace').decode('ascii') for line in diff_lines[:5]]}")

        for line in diff_lines:
            if line.startswith('@@'):
                # Bắt đầu một chunk mới
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Parse header: @@ -start_orig,len_orig +start_mod,len_mod @@
                header_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if header_match:
                    line_num_original = int(header_match.group(1))
                    line_num_modified = int(header_match.group(3))
                    
                    current_chunk = {
                        "file_name": file_name,
                        "file_action": change_type,
                        "line1": line_num_original,
                        "line2": line_num_original,
                        "lines_remove": "",
                        "lines_add": "",
                        "file_name_rename": None,
                        "application_details": ""
                    }
                    print(f"DEBUG: New chunk starting at line {line_num_original}")
                continue

            if current_chunk:
                if line.startswith('-'):
                    current_chunk["lines_remove"] += line[1:]  # Remove '-' prefix
                    current_chunk["line2"] = line_num_original
                    line_num_original += 1
                elif line.startswith('+'):
                    current_chunk["lines_add"] += line[1:]  # Remove '+' prefix
                    line_num_modified += 1
                elif line.startswith(' '):
                    # Context line, advance both line numbers
                    line_num_original += 1
                    line_num_modified += 1
        
        if current_chunk:
            chunks.append(current_chunk)

        # Determine overall line_start and line_end for the entire change
        overall_line_start = None
        overall_line_end = None
        if chunks:
            # Find the earliest start line and latest end line across all chunks
            overall_line_start = min(c["line1"] for c in chunks)
            overall_line_end = max(c["line2"] for c in chunks)
            print(f"DEBUG: Found {len(chunks)} chunks, line range: {overall_line_start}-{overall_line_end}")

        return {
            "file_before": original_content,
            "file_after": modified_content,
            "chunks": chunks,
            "line_start": overall_line_start,
            "line_end": overall_line_end,
            "function_name": self._extract_function_name(modified_content)
        }
    
    async def process_ai_code_response(self, 
                                     original_file_content: str,
                                     ai_response: str,
                                     file_name: str,
                                     project_id: str,
                                     conversation_id: str,
                                     role: str = "assistant") -> Dict[str, Any]:
        """
        Xử lý response từ AI có chứa code và so sánh với file gốc
        
        Args:
            original_file_content: Nội dung file gốc
            ai_response: Response từ AI có thể chứa code
            file_name: Tên file
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            role: Role của message
            
        Returns:
            Dict chứa thông tin code changes được xử lý
        """
        try:
            # Trích xuất code blocks từ AI response
            code_blocks = self._extract_code_blocks(ai_response)
            
            if not code_blocks:
                return {
                    "status": "no_code",
                    "message": "No code blocks found in AI response"
                }
            
            # Lấy code block lớn nhất (thường là file đã được chỉnh sửa)
            modified_content = max(code_blocks, key=len)
            
            # Debug logging
            print(f"DEBUG: Found {len(code_blocks)} code blocks")
            print(f"DEBUG: Using code block with {len(modified_content)} characters")
            print(f"DEBUG: Original content length: {len(original_file_content)}")
            print(f"DEBUG: Modified content preview: {modified_content[:200]}...")
            
            # So sánh với file gốc
            code_changes = self._compare_code_changes(
                original_file_content,
                modified_content,
                file_name,
                "modified"
            )
            
            # Tạo payload theo format mẫu
            payload = {
                "file_before": code_changes["file_before"],
                "file_after": code_changes["file_after"],
                "chunks": code_changes["chunks"]
            }
            
            # Xử lý payload code changes
            result = await self.process_code_changes_payload(
                payload=payload,
                project_id=project_id,
                conversation_id=conversation_id,
                role=role
            )
            
            # Thêm thông tin diff vào result
            result["diff_info"] = {
                "line_start": code_changes["line_start"],
                "line_end": code_changes["line_end"],
                "function_name": code_changes["function_name"],
                "total_chunks": len(code_changes["chunks"])
            }
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing AI code response: {str(e)}"
            }


# Global instance
_file_upload_handler = None

def get_file_upload_handler() -> FileUploadHandler:
    """Get global file upload handler instance"""
    global _file_upload_handler
    if _file_upload_handler is None:
        _file_upload_handler = FileUploadHandler()
    return _file_upload_handler
