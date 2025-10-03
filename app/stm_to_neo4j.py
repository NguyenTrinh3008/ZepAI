"""
Utilities to import Short Term Memory JSON into Neo4j.

Creates a simple graph model:
- (:Project {id})-[:HAS_MESSAGE]->(:STMMessage {id,...})
- (:Conversation {id})-[:HAS_MESSAGE]->(:STMMessage)
- Optional (:File {path})-[:MENTIONED_IN]->(:STMMessage)
- Optional (:Function {name, file_path})-[:MENTIONED_IN]->(:STMMessage)
"""

from __future__ import annotations

from typing import Any, Dict, List
import json
import uuid

from app.graph import get_graphiti


async def import_stm_json_content(json_text: str) -> Dict[str, Any]:
    """Import the provided Short Term Memory JSON text into Neo4j.

    Args:
        json_text: The JSON file content (as string)

    Returns:
        Summary dict with counts
    """
    data = json.loads(json_text)
    # Accept either {"messages": [...]} or a raw list of messages
    if isinstance(data, list):
        messages: List[Dict[str, Any]] = data
    else:
        # Try common wrappers
        messages = (
            data.get("messages")
            or data.get("records")
            or data.get("results")
            or []
        )

    graphiti = await get_graphiti()

    created = 0
    updated = 0

    async with graphiti.driver.session() as session:
        for msg in messages:
            # Accept both STM shape and flat shape
            md = msg.get("metadata", {}) if isinstance(msg, dict) else {}
            if not md and isinstance(msg, dict):
                # Build metadata from flat fields when no nested metadata
                md = {
                    "conversation_id": msg.get("conversation_id") or msg.get("group_id"),
                    "file_path": msg.get("file_path") or msg.get("file_name"),
                    "function_name": msg.get("function_name"),
                    "line_start": msg.get("line_start"),
                    "line_end": msg.get("line_end"),
                    "lines_added": msg.get("lines_added"),
                    "lines_removed": msg.get("lines_removed"),
                    "diff_summary": msg.get("diff_summary"),
                    "intent": msg.get("intent"),
                    "keywords": msg.get("keywords"),
                    "code_changes": msg.get("code_changes"),
                    "file_analysis": msg.get("file_analysis"),
                    "file_content": msg.get("file_content"),
                }

            mid = msg.get("id") if isinstance(msg, dict) else None
            if not mid:
                mid = str(uuid.uuid4())
            role = msg.get("role") if isinstance(msg, dict) else "assistant"
            content = msg.get("content") if isinstance(msg, dict) else None
            timestamp = msg.get("timestamp") if isinstance(msg, dict) else None
            project_id = msg.get("project_id") if isinstance(msg, dict) else None
            if not project_id:
                project_id = (md.get("project_id") if isinstance(md, dict) else None) or "default_project"
            conversation_id = md.get("conversation_id")
            file_path = md.get("file_path")
            function_name = md.get("function_name")
            line_start = md.get("line_start")
            line_end = md.get("line_end")
            lines_added = md.get("lines_added")
            lines_removed = md.get("lines_removed")
            diff_summary = md.get("diff_summary")
            intent = md.get("intent")
            keywords = md.get("keywords") or []
            change_obj = md.get("code_changes") or {}
            # Some sources may attach large nested maps (e.g., file_analysis, file_content)
            file_analysis = md.get("file_analysis") if isinstance(md.get("file_analysis"), dict) else None
            file_content = md.get("file_content") if isinstance(md.get("file_content"), str) else None

            # Serialize nested objects to JSON strings to satisfy Neo4j primitive property rule
            code_changes_json = json.dumps(change_obj, ensure_ascii=False) if change_obj else None
            file_analysis_json = json.dumps(file_analysis, ensure_ascii=False) if file_analysis else None

            cypher = """
            MERGE (p:Project {id: $project_id})
            MERGE (c:Conversation {id: $conversation_id})
            MERGE (m:STMMessage {id: $id})
            ON CREATE SET m.created_at = timestamp()
            SET m.role = $role,
                m.content = $content,
                m.timestamp = $timestamp,
                m.project_id = $project_id,
                m.conversation_id = $conversation_id,
                m.file_path = $file_path,
                m.function_name = $function_name,
                m.line_start = $line_start,
                m.line_end = $line_end,
                m.lines_added = $lines_added,
                m.lines_removed = $lines_removed,
                m.diff_summary = $diff_summary,
                m.intent = $intent,
                m.keywords = $keywords,
                m.code_changes_json = $code_changes_json,
                m.file_analysis_json = $file_analysis_json
            MERGE (p)-[:HAS_MESSAGE]->(m)
            MERGE (c)-[:HAS_MESSAGE]->(m)
            """

            params = {
                "id": mid,
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "project_id": project_id,
                "conversation_id": conversation_id,
                "file_path": file_path,
                "function_name": function_name,
                "line_start": line_start,
                "line_end": line_end,
                "lines_added": lines_added,
                "lines_removed": lines_removed,
                "diff_summary": diff_summary,
                "intent": intent,
                "keywords": keywords,
                "code_changes_json": code_changes_json,
                "file_analysis_json": file_analysis_json,
            }

            # Add File and Function nodes if present
            if file_path:
                cypher += "\nMERGE (f:File {path: $file_path})\nMERGE (f)-[:MENTIONED_IN]->(m)"
            if function_name:
                cypher += "\nMERGE (fn:Function {name: $function_name, file_path: $file_path})\nMERGE (fn)-[:MENTIONED_IN]->(m)"

            result = await session.run(cypher, params)
            await result.consume()
            created += 1

    return {"status": "success", "created_messages": created, "updated_messages": updated}


