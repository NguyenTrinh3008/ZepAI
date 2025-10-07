"""
Utilities to import source code into Neo4j as explicit nodes for better retrieval.

Creates nodes:
- (:CodeFile {path, repo, language, hash, lines, last_modified, group_id})
- (:CodeSymbol {name, kind, file_path, start_line, end_line, signature, group_id})

Relationships:
- (CodeFile)-[:CONTAINS]->(CodeSymbol)
- (CodeSymbol)-[:CALLS]->(CodeSymbol)
"""

from __future__ import annotations

import ast
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class ParsedSymbol:
    name: str
    kind: str  # function | class
    start_line: int
    end_line: int
    signature: Optional[str]
    calls: List[str]


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_python_symbols(content: str) -> List[ParsedSymbol]:
    """Parse Python source to extract functions/classes and call references.

    We keep it conservative and only extract top-level/class-level defs.
    """
    try:
        tree = ast.parse(content)
    except Exception:
        return []

    symbols: List[ParsedSymbol] = []

    class CallCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.called: List[str] = []

        def visit_Call(self, node: ast.Call) -> Any:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name:
                self.called.append(name)
            self.generic_visit(node)

    def _signature_from_args(args: ast.arguments) -> str:
        arg_names = [a.arg for a in list(args.posonlyargs) + list(args.args)]
        if args.vararg:
            arg_names.append("*" + args.vararg.arg)
        if args.kwonlyargs:
            arg_names.extend([a.arg for a in args.kwonlyargs])
        if args.kwarg:
            arg_names.append("**" + args.kwarg.arg)
        return ", ".join(arg_names)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            collector = CallCollector()
            collector.visit(node)
            signature = f"def {node.name}({_signature_from_args(node.args)})"
            end_line = getattr(node, "end_lineno", node.lineno)
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    kind="function",
                    start_line=node.lineno,
                    end_line=end_line,
                    signature=signature,
                    calls=collector.called,
                )
            )
        elif isinstance(node, ast.ClassDef):
            end_line = getattr(node, "end_lineno", node.lineno)
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    kind="class",
                    start_line=node.lineno,
                    end_line=end_line,
                    signature=f"class {node.name}",
                    calls=[],
                )
            )

    return symbols


async def ingest_code_file(
    graphiti,
    file_path: str,
    file_content: str,
    project_id: str,
    repo: Optional[str] = None,
) -> Dict[str, Any]:
    """Create CodeFile/CodeSymbol nodes for a single file.

    Args:
        graphiti: Graphiti instance (for driver.session())
        file_path: logical path to store
        file_content: text content
        project_id: group_id/project isolation
        repo: optional repo name
    """
    language = _detect_language(file_path)
    lines = file_content.count("\n") + 1 if file_content else 0
    file_hash = _hash_content(file_content)
    last_modified = datetime.utcnow().isoformat()

    symbols: List[ParsedSymbol] = []
    if language == "python":
        symbols = parse_python_symbols(file_content)

    file_params = {
        "path": file_path,
        "group_id": project_id,
        "repo": repo or _repo_from_path(file_path),
        "language": language,
        "hash": file_hash,
        "lines": lines,
        "last_modified": last_modified,
    }

    # Build queries
    merge_file = (
        "MERGE (f:CodeFile {path:$path, group_id:$group_id})\n"
        "SET f.repo=$repo, f.language=$language, f.hash=$hash, f.lines=$lines, f.last_modified=datetime($last_modified)"
    )

    symbol_records: List[Dict[str, Any]] = []
    for s in symbols:
        symbol_records.append(
            {
                "file_path": file_path,
                "group_id": project_id,
                "name": s.name,
                "kind": s.kind,
                "start": s.start_line,
                "end": s.end_line,
                "signature": s.signature or "",
                "calls": s.calls,
            }
        )

    async with graphiti.driver.session() as session:
        await session.run(merge_file, file_params)

        for r in symbol_records:
            merge_symbol = (
                "MATCH (f:CodeFile {path:$file_path, group_id:$group_id})\n"
                "MERGE (s:CodeSymbol {file_path:$file_path, name:$name, kind:$kind, group_id:$group_id})\n"
                "SET s.start_line=$start, s.end_line=$end, s.signature=$signature\n"
                "MERGE (f)-[:CONTAINS]->(s)"
            )
            await session.run(merge_symbol, r)

        # Create CALLS relationships (name-based within same file/group)
        for r in symbol_records:
            for callee in r["calls"]:
                params = {
                    "file_path": r["file_path"],
                    "group_id": r["group_id"],
                    "src": r["name"],
                    "dst": callee,
                }
                query_calls = (
                    "MATCH (a:CodeSymbol {file_path:$file_path, name:$src, group_id:$group_id})\n"
                    "MATCH (b:CodeSymbol {file_path:$file_path, name:$dst, group_id:$group_id})\n"
                    "MERGE (a)-[:CALLS]->(b)"
                )
                await session.run(query_calls, params)

    return {
        "file_path": file_path,
        "group_id": project_id,
        "language": language,
        "symbols": len(symbol_records),
    }


async def ingest_code_dir(
    graphiti,
    root_dir: str,
    project_id: str,
    repo: Optional[str] = None,
    extensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Walk a directory and ingest supported files. Default: .py only."""
    exts = set((extensions or [".py"]))
    total_files = 0
    total_symbols = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            _, ext = os.path.splitext(name)
            if ext.lower() not in exts:
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                rel = os.path.relpath(path, root_dir)
                result = await ingest_code_file(
                    graphiti=graphiti,
                    file_path=rel.replace("\\", "/"),
                    file_content=content,
                    project_id=project_id,
                    repo=repo or os.path.basename(os.path.abspath(root_dir)),
                )
                total_files += 1
                total_symbols += int(result.get("symbols", 0))
            except Exception:
                # Skip unreadable files silently
                continue

    return {"files": total_files, "symbols": total_symbols, "group_id": project_id}


def _detect_language(file_path: str) -> str:
    _, ext = os.path.splitext(file_path.lower())
    if ext in {".py"}:
        return "python"
    if ext in {".ts", ".tsx"}:
        return "typescript"
    if ext in {".js", ".jsx"}:
        return "javascript"
    if ext in {".java"}:
        return "java"
    return ext.strip(".") or "text"


def _repo_from_path(file_path: str) -> str:
    # Best-effort fallback; caller can override
    parts = file_path.replace("\\", "/").split("/")
    return parts[0] if parts else "repo"


async def ingest_code_json(graphiti, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest code-file metadata JSON to CodeFile/CodeSymbol nodes.

    Supported formats:
    - { "code_files": [ { ... }, ... ] }
    - Single object { ... }
    Each object may contain: entity_type, group_id, file_path, name, summary,
    request_id, source, usefulness, content_hash, line_start, line_end,
    symbols (list of string or dict), expires_at, created_at, uuid.
    """
    items: List[Dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("code_files"), list):
        items = payload["code_files"]
    else:
        items = [payload]

    created = 0
    total_symbols = 0

    async with graphiti.driver.session() as session:
        for obj in items:
            if not isinstance(obj, dict):
                continue
            group_id = obj.get("group_id")
            file_path = obj.get("file_path")
            if not group_id or not file_path:
                continue
            language = _detect_language(file_path)
            repo = _repo_from_path(file_path)
            content_hash = obj.get("content_hash")
            lines = int(obj.get("line_end") or 0) or int(obj.get("lines") or 0)
            created_at = obj.get("created_at") or datetime.utcnow().isoformat()
            last_modified = created_at
            name = obj.get("name")
            summary = obj.get("summary")
            usefulness = obj.get("usefulness")
            request_id = obj.get("request_id")
            source = obj.get("source")
            line_start = obj.get("line_start")
            line_end = obj.get("line_end")
            expires_at = obj.get("expires_at")
            uuid_val = obj.get("uuid")

            merge_file = (
                "MERGE (f:CodeFile {path:$path, group_id:$group_id})\n"
                "SET f.repo=$repo, f.language=$language, f.hash=$hash, f.lines=$lines, "
                "f.last_modified=datetime($last_modified)"
            )
            params = {
                "path": file_path,
                "group_id": group_id,
                "repo": repo,
                "language": language,
                "hash": content_hash,
                "lines": lines,
                "last_modified": last_modified,
            }
            await session.run(merge_file, params)

            # Optional properties
            opt_sets = []
            opt_params: Dict[str, Any] = {"path": file_path, "group_id": group_id}
            def _set_opt(prop: str, val: Any, is_datetime: bool = False):
                if val is None:
                    return
                key = f"_{prop}"
                opt_params[key] = val
                if is_datetime:
                    opt_sets.append(f"f.{prop} = datetime(${key})")
                else:
                    opt_sets.append(f"f.{prop} = ${key}")

            _set_opt("name", name)
            _set_opt("summary", summary)
            _set_opt("usefulness", usefulness)
            _set_opt("request_id", request_id)
            _set_opt("source", source)
            _set_opt("line_start", line_start)
            _set_opt("line_end", line_end)
            _set_opt("created_at", created_at, is_datetime=True)
            _set_opt("expires_at", expires_at, is_datetime=True)
            _set_opt("uuid", uuid_val)

            if opt_sets:
                q = (
                    "MATCH (f:CodeFile {path:$path, group_id:$group_id})\n"
                    f"SET {', '.join(opt_sets)}"
                )
                await session.run(q, opt_params)

            # Symbols
            sym_list = obj.get("symbols") or []
            for sym in sym_list:
                if isinstance(sym, str):
                    s_name, s_kind, s_start, s_end, s_sig = sym, "symbol", None, None, None
                elif isinstance(sym, dict):
                    s_name = sym.get("name")
                    s_kind = sym.get("kind") or "symbol"
                    s_start = sym.get("start_line") or sym.get("line_start")
                    s_end = sym.get("end_line") or sym.get("line_end")
                    s_sig = sym.get("signature")
                else:
                    continue
                if not s_name:
                    continue
                total_symbols += 1
                await session.run(
                    "MATCH (f:CodeFile {path:$file_path, group_id:$group_id})\n"
                    "MERGE (s:CodeSymbol {file_path:$file_path, name:$name, group_id:$group_id})\n"
                    "SET s.kind=$kind, s.start_line=$start, s.end_line=$end, s.signature=$sig\n"
                    "MERGE (f)-[:CONTAINS]->(s)",
                    {
                        "file_path": file_path,
                        "group_id": group_id,
                        "name": s_name,
                        "kind": s_kind,
                        "start": s_start,
                        "end": s_end,
                        "sig": s_sig,
                    },
                )

            created += 1

    return {"files": created, "symbols": total_symbols}


