# app/innocody_adapter.py
"""
Innocody Integration Adapter

Chuyển đổi DiffChunk từ Innocody sang IngestCodeContext format
và tự động sinh metadata bổ sung (summary, severity, hash, etc.)
"""

import hashlib
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel


# =============================================================================
# Innocody Data Models
# =============================================================================

class DiffChunk(BaseModel):
    """DiffChunk từ Innocody"""
    file_name: str
    file_action: str  # edit, add, remove, rename
    line1: int  # 1-based start line
    line2: int  # 1-based end line
    lines_remove: str  # text cũ
    lines_add: str  # text mới
    file_name_rename: Optional[str] = None
    application_details: Optional[str] = ""
    is_file: bool = True


class InnocodyResponse(BaseModel):
    """Response từ Innocody /v1/file-edit-tool/dry-run"""
    file_before: str
    file_after: str
    chunks: List[DiffChunk]


class ChatMeta(BaseModel):
    """Metadata từ Innocody chat context"""
    chat_id: Optional[str] = None
    request_attempt_id: Optional[str] = None
    chat_mode: Optional[str] = None
    project_id: Optional[str] = "default_project"


# =============================================================================
# Adapter Functions
# =============================================================================

def calculate_hash(text: str) -> str:
    """Tính SHA256 hash của text"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def count_lines(text: str) -> int:
    """Đếm số dòng trong text"""
    if not text:
        return 0
    return len(text.splitlines())


def extract_function_name(code: str, line_start: int) -> Optional[str]:
    """
    Cố gắng extract function name từ code context
    
    Tìm def/function/class gần line_start nhất
    Priority: class > def (để tránh lấy __init__ thay vì class name)
    """
    lines = code.splitlines()
    
    found_class = None
    found_function = None
    
    # Tìm ngược từ line_start
    for i in range(max(0, line_start - 1), max(0, line_start - 20), -1):
        if i >= len(lines):
            continue
        line = lines[i].strip()
        
        # Python: class ClassName (priority 1)
        if not found_class:
            match = re.match(r'class\s+(\w+)', line)
            if match:
                found_class = match.group(1)
        
        # Python: def function_name( (priority 2)
        if not found_function:
            match = re.match(r'def\s+(\w+)\s*\(', line)
            if match:
                func = match.group(1)
                # Skip __init__, __str__, etc. if we're looking for class context
                if not func.startswith('__'):
                    found_function = func
        
        # JavaScript/TypeScript: function functionName(
        if not found_function:
            match = re.match(r'function\s+(\w+)\s*\(', line)
            if match:
                found_function = match.group(1)
        
        # JavaScript: const functionName = (
        if not found_function:
            match = re.match(r'const\s+(\w+)\s*=\s*\(', line)
            if match:
                found_function = match.group(1)
    
    # Return class name if found, otherwise function name
    return found_class or found_function


def detect_language(file_path: str) -> str:
    """Detect ngôn ngữ từ file extension"""
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.rs': 'rust',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
    }
    
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    
    return 'unknown'


def infer_severity(chunk: DiffChunk, file_path: str) -> str:
    """
    Suy luận severity dựa trên heuristics
    
    Rules (priority order):
    1. Test files → low (check first!)
    2. Docs → low
    3. Critical files (auth, security, database) → high/critical
    4. Many lines changed → medium/high
    5. Config files → medium
    """
    lines_add_count = count_lines(chunk.lines_add)
    lines_remove_count = count_lines(chunk.lines_remove)
    total_changes = lines_add_count + lines_remove_count
    
    file_lower = file_path.lower()
    
    # Test files (check FIRST to avoid false positives with 'test_auth.py')
    if 'test' in file_lower or file_path.endswith('_test.py'):
        return 'low'
    
    # Docs
    if any(file_path.endswith(x) for x in ['.md', '.txt', '.rst']):
        return 'low'
    
    # Critical files
    critical_keywords = ['auth', 'security', 'password', 'token', 'database', 'db', 'payment']
    for keyword in critical_keywords:
        if keyword in file_lower:
            if total_changes > 20:
                return 'critical'
            return 'high'
    
    # API/Core files
    if any(x in file_lower for x in ['api', 'core', 'main', 'app']):
        if total_changes > 50:
            return 'high'
        return 'medium'
    
    # Based on change size
    if total_changes > 100:
        return 'high'
    elif total_changes > 30:
        return 'medium'
    else:
        return 'low'


def normalize_change_type(file_action: str) -> str:
    """
    Normalize Innocody file_action sang memory layer change_type
    
    Innocody: edit, add, remove, rename
    Memory Layer: fixed, added, refactored, removed, updated
    """
    mapping = {
        'add': 'added',
        'remove': 'removed',
        'rename': 'refactored',
        'edit': 'updated',  # default, có thể refine thêm
    }
    return mapping.get(file_action.lower(), 'updated')


def determine_entity_type(chunk: DiffChunk) -> str:
    """
    Xác định entity type cho Phase 1 schema extensions
    
    Returns:
        'code_change' - Change event entity (for CodeChange label)
    
    Note: We create separate CodeFile entities in create_file_entity()
    """
    return 'code_change'


def extract_module_name(file_path: str) -> Optional[str]:
    """
    Extract module name from file path
    
    Examples:
        src/auth/login.py -> auth
        src/api/users/service.js -> api.users
        migrations/001_create.sql -> migrations
    """
    parts = file_path.split('/')
    # Remove filename, keep directory structure
    if len(parts) <= 1:
        return None
    
    # Remove 'src' prefix if exists
    dirs = [p for p in parts[:-1] if p not in ['src', 'lib', 'app']]
    
    if not dirs:
        return None
    
    return '.'.join(dirs)


def create_file_entity(chunk: DiffChunk, language: str) -> Dict[str, Any]:
    """
    Create CodeFile entity metadata
    
    Returns:
        Dict with file entity metadata for separate ingestion
    """
    module_name = extract_module_name(chunk.file_name)
    
    return {
        "entity_type": "code_file",
        "file_path": chunk.file_name,
        "language": language,
        "module": module_name,
        "file_action": chunk.file_action,  # For tracking add/remove
    }


def create_module_entity(module_name: str, file_path: str) -> Dict[str, Any]:
    """
    Create Module entity metadata
    
    Returns:
        Dict with module entity metadata
    """
    # Extract module path (directory)
    parts = file_path.split('/')
    module_path = '/'.join(parts[:-1]) + '/'
    
    return {
        "entity_type": "module",
        "name": module_name,
        "path": module_path,
    }


def extract_imports(code: str, language: str) -> List[str]:
    """
    Extract import statements từ code
    
    Args:
        code: Source code text
        language: Programming language (python, javascript, etc.)
    
    Returns:
        List of imported module/file names
    """
    imports = []
    
    if language == 'python':
        # Python: import x, from x import y
        import_pattern = r'(?:from|import)\s+([a-zA-Z0-9_.]+)'
        imports = re.findall(import_pattern, code)
    
    elif language in ['javascript', 'typescript']:
        # JavaScript/TypeScript: import x from 'y', require('y')
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        imports.extend(re.findall(import_pattern, code))
        
        require_pattern = r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        imports.extend(re.findall(require_pattern, code))
    
    elif language == 'go':
        # Go: import "package"
        import_pattern = r'import\s+"([^"]+)"'
        imports = re.findall(import_pattern, code)
    
    elif language == 'java':
        # Java: import package.Class;
        import_pattern = r'import\s+([a-zA-Z0-9_.]+)\s*;'
        imports = re.findall(import_pattern, code)
    
    elif language == 'rust':
        # Rust: use crate::module;
        import_pattern = r'use\s+([a-zA-Z0-9_:]+)\s*;'
        imports = re.findall(import_pattern, code)
    
    return list(set(imports))  # Remove duplicates


async def generate_summary_with_llm(
    chunk: DiffChunk,
    file_before: str,
    file_after: str,
    api_key: Optional[str] = None
) -> str:
    """
    Sinh summary từ diff sử dụng LLM
    
    Args:
        chunk: DiffChunk từ Innocody
        file_before: Nội dung file trước khi thay đổi
        file_after: Nội dung file sau khi thay đổi
        api_key: OpenAI API key (optional, sẽ lấy từ env nếu None)
        
    Returns:
        Human-readable summary string
    """
    import os
    from openai import OpenAI
    
    key = api_key or os.getenv('OPENAI_API_KEY')
    if not key:
        # Fallback: generate simple summary without LLM
        return generate_simple_summary(chunk)
    
    try:
        client = OpenAI(api_key=key)
        
        # Build prompt
        prompt = f"""Analyze this code change and generate a concise summary (max 200 chars).

**File:** {chunk.file_name}
**Action:** {chunk.file_action}
**Lines:** {chunk.line1}-{chunk.line2}

**Code Removed:**
```
{chunk.lines_remove[:500]}
```

**Code Added:**
```
{chunk.lines_add[:500]}
```

Generate a summary in this format:
"[Action] [what was changed] in [file/function] to [purpose/reason]"

Examples:
- "Fixed null pointer exception in auth_service.py:login_user() by adding null check"
- "Added rate limiting middleware to API endpoints using Redis"
- "Refactored database queries to use async/await pattern for better performance"

Summary:"""
        
        response = client.chat.completions.create(
            model=os.getenv('MODEL_NAME', 'gpt-4o-mini'),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100,
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Remove quotes if present
        summary = summary.strip('"\'')
        
        return summary
        
    except Exception as e:
        # Fallback on error
        return generate_simple_summary(chunk)


def generate_simple_summary(chunk: DiffChunk) -> str:
    """
    Generate simple summary without LLM (fallback)
    """
    action_map = {
        'add': 'Added',
        'remove': 'Removed',
        'edit': 'Modified',
        'rename': 'Renamed',
    }
    
    action = action_map.get(chunk.file_action.lower(), 'Changed')
    
    lines_add_count = count_lines(chunk.lines_add)
    lines_remove_count = count_lines(chunk.lines_remove)
    
    if chunk.file_action == 'add':
        return f"{action} {chunk.file_name} with {lines_add_count} lines"
    elif chunk.file_action == 'remove':
        return f"{action} {chunk.file_name}"
    elif chunk.file_action == 'rename':
        return f"{action} {chunk.file_name} to {chunk.file_name_rename}"
    else:
        return f"{action} {lines_add_count} lines in {chunk.file_name} (removed {lines_remove_count} lines)"


async def convert_innocody_to_memory_layer(
    innocody_response: InnocodyResponse,
    chat_meta: Optional[ChatMeta] = None,
    use_llm_summary: bool = True
) -> List[Dict[str, Any]]:
    """
    Convert Innocody response sang memory layer format
    
    Args:
        innocody_response: Response từ Innocody
        chat_meta: Chat metadata (optional)
        use_llm_summary: Có dùng LLM để generate summary không (default: True)
        
    Returns:
        List of payloads ready để POST /ingest/code-context
    """
    results = []
    
    for chunk in innocody_response.chunks:
        # Tính toán metadata
        lines_add_count = count_lines(chunk.lines_add)
        lines_remove_count = count_lines(chunk.lines_remove)
        
        code_before_hash = calculate_hash(chunk.lines_remove)
        code_after_hash = calculate_hash(chunk.lines_add)
        
        language = detect_language(chunk.file_name)
        severity = infer_severity(chunk, chunk.file_name)
        change_type = normalize_change_type(chunk.file_action)
        
        # Extract function name từ context
        function_name = extract_function_name(innocody_response.file_after, chunk.line1)
        
        # Phase 1 Schema Extensions
        entity_type = determine_entity_type(chunk)
        imports = extract_imports(chunk.lines_add, language)
        
        # Generate summary
        if use_llm_summary:
            summary = await generate_summary_with_llm(
                chunk, 
                innocody_response.file_before,
                innocody_response.file_after
            )
        else:
            summary = generate_simple_summary(chunk)
        
        # Generate name từ summary (first 50 chars)
        name = summary[:50] + "..." if len(summary) > 50 else summary
        
        # Build payload
        payload = {
            "name": name,
            "summary": summary,
            "metadata": {
                # Core metadata
                "file_path": chunk.file_name,
                "function_name": function_name,
                "line_start": chunk.line1,
                "line_end": chunk.line2,
                "change_type": change_type,
                "change_summary": summary[:200],  # Truncate for change_summary
                "severity": severity,
                
                # Phase 1 Schema Extensions
                "entity_type": entity_type,  # 'code_change' for CodeChange label
                "imports": imports,  # List of imported modules
                "language": language,
                
                # Code references
                "code_before_ref": {
                    "code_id": f"innocody_{code_before_hash}",
                    "code_hash": code_before_hash,
                    "language": language,
                    "line_count": lines_remove_count
                } if chunk.lines_remove else None,
                "code_after_ref": {
                    "code_id": f"innocody_{code_after_hash}",
                    "code_hash": code_after_hash,
                    "language": language,
                    "line_count": lines_add_count
                } if chunk.lines_add else None,
                
                # Change metrics
                "lines_added": lines_add_count,
                "lines_removed": lines_remove_count,
                "diff_summary": f"Added {lines_add_count} lines, removed {lines_remove_count} lines",
                
                # Other
                "git_commit": None,  # Innocody không cung cấp, có thể bổ sung sau
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "project_id": chat_meta.project_id if chat_meta else "default_project",
            "reference_time": datetime.utcnow().isoformat()
        }
        
        results.append(payload)
    
    return results


# =============================================================================
# Mock Data Generator for Testing
# =============================================================================

def generate_mock_innocody_response() -> InnocodyResponse:
    """Generate mock Innocody response để test"""
    return InnocodyResponse(
        file_before="""def login_user(username, password):
    user = get_user(username)
    token = user.token
    return token
""",
        file_after="""def login_user(username, password):
    user = get_user(username)
    if user is None:
        raise ValueError("User not found")
    if user.token is None:
        raise ValueError("Token not available")
    token = user.token
    return token
""",
        chunks=[
            DiffChunk(
                file_name="src/auth/auth_service.py",
                file_action="edit",
                line1=2,
                line2=4,
                lines_remove="    user = get_user(username)\n    token = user.token\n    return token",
                lines_add="    user = get_user(username)\n    if user is None:\n        raise ValueError(\"User not found\")\n    if user.token is None:\n        raise ValueError(\"Token not available\")\n    token = user.token\n    return token"
            )
        ]
    )


def generate_mock_examples() -> List[InnocodyResponse]:
    """Generate nhiều mock examples"""
    return [
        # Example 1: Bug fix
        InnocodyResponse(
            file_before="def process_payment(amount):\n    charge(amount)\n    return True",
            file_after="def process_payment(amount):\n    if amount <= 0:\n        raise ValueError('Invalid amount')\n    charge(amount)\n    return True",
            chunks=[
                DiffChunk(
                    file_name="src/api/payment.py",
                    file_action="edit",
                    line1=1,
                    line2=3,
                    lines_remove="def process_payment(amount):\n    charge(amount)",
                    lines_add="def process_payment(amount):\n    if amount <= 0:\n        raise ValueError('Invalid amount')\n    charge(amount)"
                )
            ]
        ),
        
        # Example 2: New file
        InnocodyResponse(
            file_before="",
            file_after="class RateLimiter:\n    def __init__(self, max_requests=100):\n        self.max_requests = max_requests\n    \n    def check(self, user_id):\n        # Implementation\n        pass",
            chunks=[
                DiffChunk(
                    file_name="src/middleware/rate_limiter.py",
                    file_action="add",
                    line1=1,
                    line2=7,
                    lines_remove="",
                    lines_add="class RateLimiter:\n    def __init__(self, max_requests=100):\n        self.max_requests = max_requests\n    \n    def check(self, user_id):\n        # Implementation\n        pass"
                )
            ]
        ),
        
        # Example 3: Refactor
        InnocodyResponse(
            file_before="def get_user(id):\n    result = db.query('SELECT * FROM users WHERE id = ?', id)\n    return result",
            file_after="async def get_user(id):\n    result = await db.async_query('SELECT * FROM users WHERE id = ?', id)\n    return result",
            chunks=[
                DiffChunk(
                    file_name="src/db/repository.py",
                    file_action="edit",
                    line1=1,
                    line2=3,
                    lines_remove="def get_user(id):\n    result = db.query('SELECT * FROM users WHERE id = ?', id)",
                    lines_add="async def get_user(id):\n    result = await db.async_query('SELECT * FROM users WHERE id = ?', id)"
                )
            ]
        )
    ]


# =============================================================================
# Convenience Functions
# =============================================================================

async def process_innocody_webhook(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process webhook từ Innocody và convert sang memory layer format
    
    Usage:
        payload = request.json()  # From FastAPI/Flask
        memory_payloads = await process_innocody_webhook(payload)
        
        # Ingest to memory layer
        for mp in memory_payloads:
            await ingest_code_context(mp)
    """
    innocody_resp = InnocodyResponse(**payload)
    return await convert_innocody_to_memory_layer(innocody_resp, use_llm_summary=True)
