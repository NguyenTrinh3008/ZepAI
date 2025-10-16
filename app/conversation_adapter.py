"""
Conversation Context Adapter - Phase 1.5
Transform Innocody output to conversation context for memory layer
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import logging

from .schemas import (
    IngestConversationContext,
    ChatMetadata,
    MessagePayload,
    ContextFilePayload,
    ToolCallPayload,
    CheckpointPayload,
    ModelResponseMetadata,
    CodeChangeMetadata,
)
from .config import LLMConfig

logger = logging.getLogger(__name__)


def calculate_hash(text: str) -> str:
    """Calculate SHA256 hash of text"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def transform_innocody_to_conversation(
    request_id: str,
    project_id: str,
    chat_meta: Dict[str, Any],
    messages: List[Dict[str, Any]],
    context_files: List[Dict[str, Any]] = None,
    tool_calls: List[Dict[str, Any]] = None,
    code_changes: List[Dict[str, Any]] = None,
    checkpoints: List[Dict[str, Any]] = None,
    model_response: Dict[str, Any] = None
) -> IngestConversationContext:
    """
    Transform Innocody output to IngestConversationContext
    
    Args:
        request_id: Unique request ID
        project_id: Project ID for isolation
        chat_meta: ChatMeta from Innocody (chat_id, chat_mode, etc.)
        messages: List of ChatMessage (role, content, tool_calls, usage)
        context_files: Optional context files from VecDB/AST
        tool_calls: Optional tool invocations
        code_changes: Optional DiffChunks
        checkpoints: Optional checkpoint data
        model_response: Optional model response metadata
    
    Returns:
        IngestConversationContext ready for /ingest/conversation
    
    Example Innocody payload:
        {
          "chat_meta": {
            "chat_id": "chat_312a",
            "chat_mode": "AGENT",
            ...
          },
          "messages": [
            {
              "role": "user",
              "content": "Fix login bug",
              "usage": {"prompt_tokens": 120}
            },
            {
              "role": "assistant",
              "content": "I'll add null check",
              "tool_calls": [...],
              "usage": {"prompt_tokens": 520, "completion_tokens": 84}
            }
          ],
          "context": [
            {
              "file": "auth.py",
              "lines": [1, 60],
              "usefulness": 0.92,
              "source": "vecdb"
            }
          ],
          ...
        }
    """
    
    # Parse chat metadata
    chat_metadata = ChatMetadata(
        chat_id=chat_meta.get('chat_id', 'unknown'),
        base_chat_id=chat_meta.get('base_chat_id'),
        request_attempt_id=chat_meta.get('request_attempt_id'),
        chat_mode=chat_meta.get('chat_mode', 'AGENT'),
        force_initial_state=chat_meta.get('force_initial_state', False),
        chat_remote=chat_meta.get('chat_remote')
    )
    
    # Transform messages
    message_payloads = []
    for idx, msg in enumerate(messages):
        # Summarize content (or use provided summary)
        content = msg.get('content', '')
        content_summary = msg.get('summary') or _summarize_content(
            content, 
            max_length=LLMConfig.SUMMARY_MAX_LENGTH,
            use_llm=LLMConfig.USE_LLM_SUMMARIZATION
        )
        content_hash = calculate_hash(content) if content else None
        
        # Parse usage
        usage = msg.get('usage', {})
        
        # Parse tool calls
        tool_call_refs = []
        for tc in msg.get('tool_calls', []):
            tool_call_refs.append({
                'id': tc.get('id'),
                'tool': tc.get('function', {}).get('name') or tc.get('tool'),
                'args_hash': calculate_hash(str(tc.get('function', {}).get('arguments', '')))
            })
        
        message_payloads.append(MessagePayload(
            role=msg.get('role', 'user'),
            content_summary=content_summary,
            content_hash=content_hash,
            prompt_tokens=usage.get('prompt_tokens'),
            completion_tokens=usage.get('completion_tokens'),
            total_tokens=usage.get('total_tokens'),
            tool_calls=tool_call_refs,
            sequence=idx
        ))
    
    # Transform context files
    context_file_payloads = []
    if context_files:
        for ctx in context_files:
            # Get file content for hashing (if available)
            file_content = ctx.get('content', '')
            content_hash = calculate_hash(file_content) if file_content else calculate_hash(ctx.get('file', ''))
            
            context_file_payloads.append(ContextFilePayload(
                file_path=ctx.get('file') or ctx.get('file_path'),
                line_start=ctx.get('lines', [1])[0] if 'lines' in ctx else ctx.get('line_start', 1),
                line_end=ctx.get('lines', [None])[1] if 'lines' in ctx else ctx.get('line_end'),
                usefulness=ctx.get('usefulness'),
                source=ctx.get('source', 'unknown'),
                symbols=ctx.get('symbols', []),
                content_hash=content_hash,
                language=ctx.get('language')
            ))
    
    # Transform tool calls
    tool_call_payloads = []
    if tool_calls:
        for tc in tool_calls:
            tool_call_payloads.append(ToolCallPayload(
                tool_call_id=tc.get('id') or tc.get('tool_call_id'),
                tool_name=tc.get('tool') or tc.get('tool_name'),
                arguments_hash=tc.get('args_hash') or tc.get('arguments_hash') or 'unknown',
                status=tc.get('status', 'success'),
                execution_time_ms=tc.get('execution_time_ms'),
                diff_chunk_id=tc.get('diff_chunk_id')
            ))
    
    # Transform code changes
    code_change_payloads = []
    if code_changes:
        for change in code_changes:
            timestamp = change.get('timestamp') or datetime.utcnow().isoformat() + "Z"
            file_path = change.get('file_path') or change.get('file')
            if not file_path:
                continue
            code_change_payloads.append(CodeChangeMetadata(
                name=change.get('name'),
                summary=change.get('summary'),
                description=change.get('description'),
                file_path=file_path,
                function_name=change.get('function_name'),
                line_start=change.get('line_start'),
                line_end=change.get('line_end'),
                change_type=change.get('change_type'),
                change_summary=change.get('change_summary') or change.get('summary'),
                severity=change.get('severity'),
                diff_summary=change.get('diff_summary'),
                lines_added=change.get('lines_added'),
                lines_removed=change.get('lines_removed'),
                code_before_hash=change.get('code_before_hash'),
                code_after_hash=change.get('code_after_hash'),
                code_before_id=change.get('code_before_id'),
                code_after_id=change.get('code_after_id'),
                language=change.get('language'),
                imports=change.get('imports'),
                git_commit=change.get('git_commit'),
                timestamp=timestamp
            ))

    # Transform checkpoints
    checkpoint_payloads = []
    if checkpoints:
        for cp in checkpoints:
            checkpoint_payloads.append(CheckpointPayload(
                checkpoint_id=cp.get('id') or cp.get('checkpoint_id'),
                parent_checkpoint=cp.get('parent') or cp.get('parent_checkpoint'),
                workspace_dir=cp.get('workspace_dir'),
                git_hash=cp.get('git_hash')
            ))
    
    # Transform model response
    model_response_metadata = None
    if model_response:
        model_response_metadata = ModelResponseMetadata(
            model=model_response.get('model', 'unknown'),
            finish_reason=model_response.get('finish_reason'),
            created=model_response.get('created'),
            cached=model_response.get('cached', False),
            compression_strength=model_response.get('compression_strength')
        )
    
    # Build final payload
    return IngestConversationContext(
        request_id=request_id,
        project_id=project_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        chat_meta=chat_metadata,
        messages=message_payloads,
        context_files=context_file_payloads,
        tool_calls=tool_call_payloads,
        code_changes=code_change_payloads,
        checkpoints=checkpoint_payloads,
        model_response=model_response_metadata,
        related_artifacts=[]
    )


def _summarize_content(content: str, max_length: int = 200, use_llm: bool = True) -> str:
    """
    Intelligent content summarization
    
    Logic:
    - If content <= max_length: Keep original (no summarization needed)
    - If content > max_length: Summarize to exactly max_length chars
    
    Args:
        content: Full message content
        max_length: Target summary length (default 200 chars)
        use_llm: Use LLM for intelligent summary (default True)
    
    Returns:
        Original content if short enough, otherwise intelligent summary
    """
    # Keep original if already short enough
    if len(content) <= max_length:
        return content
    
    # Content is too long, need summarization
    logger.info(f"Content length {len(content)} > {max_length}, summarizing...")
    
    # Option 1: LLM-based intelligent summary (preserves key points)
    if use_llm:
        try:
            import os
            from openai import OpenAI
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("No OpenAI API key, falling back to truncation")
                return content[:max_length-3] + "..."
            
            client = OpenAI(api_key=api_key)
            
            # Build prompt for summarization
            prompt = f"""Summarize this message in EXACTLY {max_length} characters or less. Preserve the most important information.

**Instructions:**
- Maximum length: {max_length} characters (strictly enforced)
- Focus on: main action, key technical details (files/functions/errors), proposed solution
- Be concise but complete
- Don't add "Summary:" prefix or extra text

**Message to summarize:**
{content}

**{max_length}-character summary:**"""
            
            response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', LLMConfig.MODEL_NAME),
                messages=[{"role": "user", "content": prompt}],
                temperature=LLMConfig.SUMMARY_TEMPERATURE,
                max_tokens=LLMConfig.SUMMARY_MAX_TOKENS,
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Remove common prefixes that LLM might add
            prefixes_to_remove = ["Summary:", "Summary -", "Here's the summary:"]
            for prefix in prefixes_to_remove:
                if summary.startswith(prefix):
                    summary = summary[len(prefix):].strip()
            
            # Strictly enforce max_length
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
                logger.debug(f"Truncated LLM summary from {len(response.choices[0].message.content)} to {max_length} chars")
            
            logger.info(f"✓ LLM summarized: {len(content)} → {len(summary)} chars")
            return summary
            
        except Exception as e:
            # Fallback to truncation on any error
            logger.warning(f"LLM summarization failed: {e}, using truncation")
            return content[:max_length-3] + "..."
    
    # Option 2: Simple truncation (fallback when use_llm=False)
    logger.info(f"Using truncation: {len(content)} → {max_length} chars")
    return content[:max_length-3] + "..."


# =============================================================================
# Example Usage
# =============================================================================

def example_usage():
    """Example: Transform Innocody output to conversation context"""
    
    # Simulate Innocody output
    innocody_output = {
        "chat_meta": {
            "chat_id": "chat_312a",
            "base_chat_id": "chat_104",
            "request_attempt_id": "attempt_17",
            "chat_mode": "AGENT"
        },
        "messages": [
            {
                "role": "user",
                "content": "Fix the null pointer bug in auth_service.py login function",
                "usage": {"prompt_tokens": 120}
            },
            {
                "role": "assistant",
                "content": "I'll add a null check before accessing user.token to prevent the AttributeError...",
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "function": {
                            "name": "update_textdoc",
                            "arguments": '{"file": "auth.py", ...}'
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 520,
                    "completion_tokens": 84,
                    "total_tokens": 604
                }
            }
        ],
        "context": [
            {
                "file": "src/auth/auth_service.py",
                "lines": [1, 60],
                "usefulness": 0.92,
                "source": "vecdb",
                "symbols": ["login_user", "get_token"],
                "content": "def login_user(username):\n    user = get_user(username)\n    token = user.token\n    ..."
            }
        ],
        "tool_calls": [
            {
                "id": "call_abc123",
                "tool": "update_textdoc",
                "status": "success",
                "execution_time_ms": 1250
            }
        ],
        "checkpoints": [
            {
                "id": "cp_chat_312a_0006",
                "parent": "cp_chat_312a_0005",
                "workspace_dir": "~/.innocody/cache/shadow_git"
            }
        ],
        "model_response": {
            "model": "gpt-code-1",
            "finish_reason": "stop",
            "created": 1730548858.41,
            "cached": False
        }
    }
    
    # Transform
    conversation_payload = transform_innocody_to_conversation(
        request_id="req_20251003_110105",
        project_id="my_project",
        chat_meta=innocody_output['chat_meta'],
        messages=innocody_output['messages'],
        context_files=innocody_output.get('context'),
        tool_calls=innocody_output.get('tool_calls'),
        code_changes=[],  # Will be added from DiffChunk processing
        checkpoints=innocody_output.get('checkpoints'),
        model_response=innocody_output.get('model_response')
    )
    
    # Now POST to /ingest/conversation
    # requests.post("http://localhost:8000/ingest/conversation", json=conversation_payload.dict())
    
    return conversation_payload


if __name__ == "__main__":
    # Test the transformation
    payload = example_usage()
    print("Transformed payload:")
    print(payload.model_dump_json(indent=2))
