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
from app.short_term_extractor import get_extractor


async def import_stm_json_content(json_text: str, use_llm: bool = False) -> Dict[str, Any]:
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
    extractor = get_extractor() if use_llm else None

    created = 0
    updated = 0
    # For FOLLOWS and RELATES_TO
    last_message_by_conv: Dict[str, Dict[str, Any]] = {}
    recent_by_conv: Dict[str, List[Dict[str, Any]]] = {}

    def _norm_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip().strip('`"\'')
        # Collapse whitespace and lowercase for stable identity
        text = " ".join(text.split())
        return text

    def _slug(value: Any) -> str | None:
        norm = _norm_text(value)
        if norm is None:
            return None
        return (
            norm.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("\\", "-")
        )[:128]

    def _norm_path(value: Any) -> str | None:
        norm = _norm_text(value)
        if norm is None:
            return None
        # unify path separators
        norm = norm.replace("\\", "/")
        return norm

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
            file_path = _norm_path(md.get("file_path"))
            function_name = _norm_text(md.get("function_name"))
            line_start = md.get("line_start")
            line_end = md.get("line_end")
            lines_added = md.get("lines_added")
            lines_removed = md.get("lines_removed")
            diff_summary = md.get("diff_summary")
            intent = md.get("intent")
            # Normalize keywords to avoid duplicates
            raw_keywords = md.get("keywords") or []
            keywords = []
            seen_kw: set[str] = set()
            for kw in raw_keywords:
                s = _norm_text(kw)
                if s and s.lower() not in seen_kw:
                    keywords.append(s)
                    seen_kw.add(s.lower())
            embedding = md.get("embedding") if isinstance(md.get("embedding"), list) else None

            # LLM enrichment: fill missing intent/keywords/embedding from content
            if use_llm and extractor is not None:
                if not (keywords and isinstance(keywords, list)) or not embedding:
                    try:
                        info = await extractor.extract_message_info(
                            content=content or "",
                            role=role or "assistant",
                            project_id=project_id or "default_project",
                            conversation_id=conversation_id or "default_conversation",
                        )
                        keywords = keywords or info.get("keywords", [])
                        intent = info.get("intent") or intent
                        embedding = embedding or info.get("embedding")
                    except Exception:
                        pass
            change_obj = md.get("code_changes") or {}
            # Some sources may attach large nested maps (e.g., file_analysis, file_content)
            file_analysis = md.get("file_analysis") if isinstance(md.get("file_analysis"), dict) else None
            file_content = md.get("file_content") if isinstance(md.get("file_content"), str) else None

            # Serialize nested objects to JSON strings to satisfy Neo4j primitive property rule
            code_changes_json = json.dumps(change_obj, ensure_ascii=False) if change_obj else None
            file_analysis_json = json.dumps(file_analysis, ensure_ascii=False) if file_analysis else None

            cypher = """
            MERGE (p:Project:Entity {id: $project_id})
            MERGE (c:Conversation:Entity {id: $conversation_id})
            MERGE (m:STMMessage:Message:Entity {id: $id})
            ON CREATE SET m.created_at = timestamp()
            SET m.role = $role,
                m.content = $content,
                m.timestamp = $timestamp,
                m.project_id = $project_id,
                m.conversation_id = $conversation_id,
                m.group_id = $conversation_id,
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

            function_key = None
            if function_name:
                function_key = f"{function_name}@{file_path or 'unknown'}"

            params = {
                "id": mid,
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "project_id": project_id,
                "conversation_id": conversation_id,
                "file_path": file_path,
                "function_name": function_name,
                "function_key": function_key,
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
                cypher += "\nMERGE (f:File:Entity {path: $file_path})\nMERGE (f)-[:MENTIONED_IN]->(m)"
            if function_name:
                cypher += "\nMERGE (fn:Function:Entity {key: $function_key})\nSET fn.name=$function_name, fn.file_path=$file_path\nMERGE (fn)-[:MENTIONED_IN]->(m)"

            result = await session.run(cypher, params)
            await result.consume()
            created += 1

            # Create Concept nodes and MENTIONS edges
            if keywords:
                concept_rows = [{"name": k, "slug": _slug(k)} for k in keywords if _slug(k)]
                if concept_rows:
                    await session.run(
                        """
                        UNWIND $rows AS row
                        MATCH (m:STMMessage {id:$mid})
                        MERGE (k:Concept:Entity {slug: row.slug})
                        ON CREATE SET k.name = row.name
                        SET k.name = coalesce(k.name, row.name)
                        MERGE (m)-[:MENTIONS {weight: 1.0}]->(k)
                        """,
                        {"rows": concept_rows, "mid": mid},
                    )

            # Create CodeChange node if we have change info
            if (line_start is not None or line_end is not None) or change_obj:
                cc_id = f"{mid}:{file_path}:{line_start}-{line_end}"
                change_type = (change_obj.get("change_type") if isinstance(change_obj, dict) else None) or "modified"
                await session.run(
                    """
                    MATCH (m:STMMessage {id:$mid})
                    MERGE (cc:CodeChange {id:$cc_id})
                    SET cc.change_type=$change_type,
                        cc.line_start=$line_start,
                        cc.line_end=$line_end,
                        cc.lines_added=$lines_added,
                        cc.lines_removed=$lines_removed,
                        cc.diff_summary=$diff_summary
                    MERGE (m)-[:CHANGED]->(cc)
                    FOREACH (_ IN CASE WHEN $file_path IS NULL THEN [] ELSE [1] END |
                      MERGE (f:File:Entity {path:$file_path})
                      MERGE (cc)-[:APPLIES_TO]->(f)
                    )
                    """,
                    {
                        "mid": mid,
                        "cc_id": cc_id,
                        "change_type": change_type,
                        "line_start": line_start,
                        "line_end": line_end,
                        "lines_added": lines_added,
                        "lines_removed": lines_removed,
                        "diff_summary": diff_summary,
                        "file_path": file_path,
                    },
                )

            # FOLLOWS within conversation
            if conversation_id:
                prev = last_message_by_conv.get(conversation_id)
                last_message_by_conv[conversation_id] = {"id": mid, "timestamp": timestamp}
                if prev:
                    await session.run(
                        """
                        MATCH (m1:STMMessage {id:$prev}), (m2:STMMessage {id:$cur})
                        MERGE (m1)-[:FOLLOWS]->(m2)
                        """,
                        {"prev": prev["id"], "cur": mid},
                    )

            # RELATES_TO by embedding similarity (top-3 above threshold)
            if embedding and use_llm and extractor is not None and conversation_id:
                history = recent_by_conv.setdefault(conversation_id, [])
                scored: List[tuple[str, float]] = []
                for item in history[-50:]:
                    try:
                        score = extractor.calculate_similarity(embedding, item["embedding"])  # type: ignore
                        scored.append((item["id"], score))
                    except Exception:
                        continue
                scored.sort(key=lambda x: x[1], reverse=True)
                for other_id, score in scored[:3]:
                    if score >= 0.7:
                        await session.run(
                            """
                            MATCH (a:STMMessage {id:$a}),(b:STMMessage {id:$b})
                            MERGE (a)-[r:RELATES_TO]->(b)
                            SET r.score=$score
                            """,
                            {"a": mid, "b": other_id, "score": float(score)},
                        )
                history.append({"id": mid, "embedding": embedding})

    return {"status": "success", "created_messages": created, "updated_messages": updated}


