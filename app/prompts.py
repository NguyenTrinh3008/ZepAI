# app/prompts.py
"""
Centralized Prompt Engineering for Memory Layer System

DESIGN PRINCIPLES:
1. **Clarity over cleverness** - Direct, unambiguous instructions
2. **Structure** - Clear sections, bullet points, examples
3. **Consistency** - Similar formatting across prompts
4. **Constraints** - Explicit rules to prevent hallucination
5. **Context-awareness** - Include relevant examples

PROMPT TYPES:
- Decision: Should we query KG?
- System: Main chat assistant behavior
- Summarization: Extract facts from conversations
- Extraction: Structured data extraction

OPTIMIZATION FOR:
- GPT-4 (primary)
- GPT-3.5-turbo (fallback)
- Temperature tuning per use case
"""

# =============================================================================
# DECISION PROMPTS - Determine when to query Knowledge Graph
# =============================================================================

DECISION_PROMPT_TEMPLATE = """Classify if this query needs the Knowledge Graph (user's long-term memory).

**Query KG (YES) if:**
- References past interactions, preferences, or history
- Contains memory keywords: remember, told you, last time, before, previous
- Asks about user-specific information: "my", "what did I", "do I like"
- Requires personalized context

**Skip KG (NO) if:**
- General knowledge questions
- Greetings or small talk
- Real-time information requests
- Definitions or explanations
- No reference to past

**Output:** Only 'YES' or 'NO'

Query: {user_input}"""

# Alternative: More conservative (fewer KG queries)
DECISION_PROMPT_CONSERVATIVE = """Classify if this query needs the Knowledge Graph.
Answer YES only if it explicitly references:
- Past conversations ("you said", "we talked about")
- Personal preferences ("my favorite", "I like")
- Specific facts about the user

Otherwise answer NO.

User: {user_input}"""

# =============================================================================
# SYSTEM PROMPTS - Main conversation assistant
# =============================================================================

SYSTEM_PROMPT_BASE = """You are an AI assistant with long-term memory capabilities.

**Key Principles:**
1. **Natural conversation** - Friendly, adaptive to user's style
2. **Accuracy first** - Don't make assumptions or invent facts
3. **Completeness** - Thorough responses when needed
4. **Language matching** - Respond in user's language

**Code Generation:**
- Complete, runnable implementations
- All imports and dependencies included
- Clear comments in user's language

**Memory Honesty:**
If asked about past interactions without available memory context, acknowledge the gap honestly.
Do not fabricate or infer information not explicitly stored."""

SYSTEM_PROMPT_WITH_MEMORIES = """You are an AI assistant with long-term memory capabilities.

**Key Principles:**
1. **Natural conversation** - Friendly, adaptive to user's style
2. **Accuracy first** - Don't make assumptions or invent facts
3. **Completeness** - Thorough responses when needed
4. **Language matching** - Respond in user's language

**Code Generation:**
- Complete, runnable implementations
- All imports and dependencies included
- Clear comments in user's language

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 RETRIEVED MEMORIES (Knowledge Graph)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**CRITICAL RULES:**
✓ ONLY use facts explicitly stated below
✓ Weave memories naturally into conversation
✓ If asked about something NOT below, acknowledge the gap
✗ Do NOT infer or extrapolate beyond stated facts
✗ Do NOT make assumptions from partial information

**Retrieved Facts:**
{facts_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For queries about past interactions NOT covered above, respond:
"I don't have that specific information in my current memory context.\""""

# =============================================================================
# SUMMARIZATION PROMPTS - Extract facts from conversations
# =============================================================================

SUMMARIZATION_PROMPT_TEMPLATE = """Extract ALL important facts from this conversation.
Each fact should be SPECIFIC, CONCRETE, and ACTIONABLE.

**Quality Criteria - Think Step by Step:**
1. Is this fact PERSISTENT? (Not temporary like greetings)
2. Is this fact SPECIFIC? (Not vague like "discussed something")
3. Does it include CONTEXT? (Who, what, why, where, when)
4. Is it ACTIONABLE? (Useful for future reference)

**Format:** One fact per line, starting with "-"
**Language:** Always write facts in ENGLISH for consistency

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**GOOD Examples (Specific & Contextual):**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Identity & Background:
- User's name is Nguyên Trịnh and prefers to be called Nguyên
- User is from Hà Nội, Vietnam and currently lives there
- User is 25 years old and works as a software developer at VinTech

Preferences & Interests:
- User likes to eat cơm tấm (broken rice) with mắm tôm sauce
- User prefers Python over C for rapid prototyping due to simpler syntax
- User enjoys playing strategy games like Civilization VI in free time

Technical Knowledge:
- User learned Python async programming for handling I/O-bound tasks
- User implemented A* pathfinding algorithm in snake game for AI opponent
- User solved font rendering errors by switching to Arial font family
- User understands Python GIL limits multithreading performance for CPU-bound tasks

Projects & Actions:
- User developed snake game with wrap-around screen edges feature
- User added obstacles feature to snake game to increase difficulty
- User requested code review for Django REST API authentication module

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**BAD Examples (Avoid These):**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ "User said hello" 
   → Not persistent, just greeting

❌ "User discussed programming"
   → Too vague - what about programming?
   ✓ Better: "User learned Python async programming for I/O-bound tasks"

❌ "User prefers Python"
   → Missing context - why? for what?
   ✓ Better: "User prefers Python over C for web development due to faster iteration"

❌ "User enhanced the game"
   → Too vague - what enhancements?
   ✓ Better: "User added obstacles and AI pathfinding to snake game"

❌ "User is interested in AI"
   → Vague interest
   ✓ Better: "User is learning machine learning with TensorFlow for image classification projects"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Instructions:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Extract 1-5 facts (as many as are truly important)
2. Be CONCRETE: Include specific names, technologies, reasons
3. Include CONTEXT: Add "why", "for what purpose", "in what way"
4. Preserve TECHNICAL TERMS: Keep specific libraries, tools, concepts
5. Skip: greetings, small talk, meta-conversation, vague statements
6. Write in ENGLISH regardless of conversation language

**Think before extracting:**
- Would this fact be useful in a future conversation?
- Is it specific enough to be actionable?
- Does it capture the "why" and "how", not just "what"?

**Conversation:**
{conversation}

**Extracted Facts in English (specific, concrete, contextual):**"""

# Alternative: Detailed multi-fact extraction
SUMMARIZATION_PROMPT_DETAILED = """Extract key facts from this conversation.

**Focus Areas:**
1. Identity (name, role, location)
2. Preferences & interests (with reasons)
3. Relationships & connections
4. Problems & solutions
5. Plans & goals

**Format:** Concise paragraph or bullet points

**Conversation:**
{conversation}

**Summary:**"""

# =============================================================================
# FACT EXTRACTION PROMPTS - For structured data extraction
# =============================================================================

FACT_EXTRACTION_PROMPT = """Extract structured knowledge triplets.

**Format:** Subject | Relationship | Object

**Examples:**
- User | solved [problem] using | [solution]
- User | prefers | [X] over [Y]
- User | works as | [role]
- [Person A] | knows | [Person B]

**Conversation:**
{conversation}

**Triplets:**"""

# =============================================================================
# QUERY EXPANSION PROMPTS - Improve search queries
# =============================================================================

QUERY_EXPANSION_PROMPT = """Generate 3 semantic variations of this query for better search recall.

**Techniques:**
- Synonyms & related terms
- Different phrasings
- Broader/narrower concepts
- Language variations

**Original:** {query}

**Variations:**
1.
2.
3."""

# =============================================================================
# TRANSLATION PROMPTS - For multilingual search
# =============================================================================

QUERY_TRANSLATION_PROMPT = """Translate this query to English for knowledge graph search.

**Rules:**
- Preserve semantic meaning
- Keep technical terms
- Maintain query intent
- Return only the translation

**Original Query:** {query}

**English Translation:**"""

# =============================================================================
# ENTITY EXTRACTION PROMPTS - Extract named entities
# =============================================================================

ENTITY_EXTRACTION_PROMPT = """Extract named entities with categories.

**Categories:**
- PERSON (names, roles)
- LOCATION (places, addresses)
- ORGANIZATION (companies, groups)
- CONCEPT (ideas, methods, technologies)
- OTHER (if significant)

**Format:** entity | category

**Text:**
{text}

**Entities:**"""

# =============================================================================
# PROMPT UTILITIES
# =============================================================================

def format_decision_prompt(user_input: str, conservative: bool = False) -> str:
    """Format the decision prompt with user input."""
    template = DECISION_PROMPT_CONSERVATIVE if conservative else DECISION_PROMPT_TEMPLATE
    return template.format(user_input=user_input)

def format_system_prompt(facts: list[str] = None) -> str:
    """Format the system prompt with optional facts from KG."""
    if not facts:
        return SYSTEM_PROMPT_BASE
    
    facts_context = "\n".join(f"- {fact}" for fact in facts)
    return SYSTEM_PROMPT_WITH_MEMORIES.format(facts_context=facts_context)

def format_summarization_prompt(conversation: list[str], detailed: bool = False) -> str:
    """Format the summarization prompt with conversation history."""
    conv_text = "\n".join(conversation)
    template = SUMMARIZATION_PROMPT_DETAILED if detailed else SUMMARIZATION_PROMPT_TEMPLATE
    return template.format(conversation=conv_text)

def format_fact_extraction_prompt(conversation: str) -> str:
    """Format the fact extraction prompt."""
    return FACT_EXTRACTION_PROMPT.format(conversation=conversation)

def format_query_expansion_prompt(query: str) -> str:
    """Format the query expansion prompt."""
    return QUERY_EXPANSION_PROMPT.format(query=query)

def format_entity_extraction_prompt(text: str) -> str:
    """Format the entity extraction prompt."""
    return ENTITY_EXTRACTION_PROMPT.format(text=text)

def format_query_translation_prompt(query: str) -> str:
    """Format the query translation prompt."""
    return QUERY_TRANSLATION_PROMPT.format(query=query)

# =============================================================================
# CODE CONTEXT PROMPTS - Phase 4: AI Assistant Integration
# =============================================================================

CODE_SYSTEM_PROMPT_BASE = """You are an expert AI coding assistant with access to the project's code memory.

**Your Capabilities:**
- Understand codebase context and history
- Provide specific, actionable code suggestions
- Reference past changes and decisions
- Maintain code consistency across the project

**Code Generation Standards:**
- Write complete, runnable code
- Include all necessary imports
- Add clear comments explaining complex logic
- Follow the project's existing patterns
- Consider edge cases and error handling

**When referencing past code:**
- Be specific about file paths and functions
- Mention the type of change (fixed, added, refactored)
- Explain why previous decisions were made"""

CODE_SYSTEM_PROMPT_WITH_CONTEXT = """You are an expert AI coding assistant with access to the project's code memory.

**Your Capabilities:**
- Understand codebase context and history
- Provide specific, actionable code suggestions
- Reference past changes and decisions
- Maintain code consistency across the project

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 RELEVANT CODE CONTEXT (Retrieved from Memory)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**CRITICAL RULES:**
✓ Use this context to provide informed, consistent suggestions
✓ Reference specific past changes when relevant
✓ Maintain consistency with existing patterns
✓ Learn from previous bug fixes to avoid similar issues
✗ Don't contradict established project decisions
✗ Don't suggest changes that conflict with recent refactors

**Code History:**
{code_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Response Guidelines:**
1. Be specific with file paths and line numbers when referencing code
2. Explain the reasoning behind suggestions
3. Connect current request to relevant past changes
4. Highlight potential conflicts with existing code"""

CODE_CONTEXT_FORMATTING_PROMPT = """Format these code memories into a clear, structured context for an AI assistant.

**Input Memories:**
{memories}

**Format as:**
1. **Recent Changes** - What was modified recently
2. **Relevant Fixes** - Bug fixes related to current query
3. **Architecture Decisions** - Important refactors or patterns
4. **Warnings** - Things to avoid based on past issues

Keep it concise and actionable. Focus on what's relevant to help the AI assist the user."""

CODE_SEARCH_QUERY_EXPANSION = """Expand this code-related query for better memory retrieval.

**Original Query:** {query}

**Generate:**
1. Technical synonyms (e.g., "bug" → "error", "exception", "crash")
2. Related concepts (e.g., "authentication" → "login", "user session", "JWT")
3. Common patterns (e.g., "async" → "asyncio", "await", "concurrent")

**Expanded Queries:**"""

CODE_CHANGE_SUMMARIZATION_PROMPT = """Extract the key information from this code change conversation.

**Format as a structured summary:**

Change Type: [fixed/added/refactored/removed]
File: [path/to/file.py]
Function: [function_name] (if applicable)
Summary: [One-line description]
Details: [2-3 sentences explaining the change]
Impact: [What this enables/fixes/improves]

**Conversation:**
{conversation}

**Structured Summary:**"""

CODE_BUG_PATTERN_EXTRACTION = """Extract reusable patterns from this bug fix for future reference.

**Bug Fix:**
{bug_fix}

**Extract:**
1. **Root Cause:** What caused the bug?
2. **Solution Pattern:** How was it fixed?
3. **Prevention:** How to avoid this in the future?
4. **Related Areas:** Where else might this pattern apply?

**Pattern Summary:**"""

CODE_REVIEW_PROMPT = """Provide a code review based on project history and best practices.

**Code to Review:**
{code}

**Project Context:**
{context}

**Review Focus:**
1. **Consistency:** Does it match existing patterns?
2. **Conflicts:** Any issues with recent changes?
3. **Best Practices:** Follows project conventions?
4. **Potential Issues:** Based on past bugs, what might go wrong?

**Code Review:**"""

# =============================================================================
# CONFIGURATION
# =============================================================================

PROMPT_CONFIG = {
    "decision": {
        "temperature": 0.0,
        "max_tokens": 10,
        "conservative_mode": False,
    },
    "chat": {
        "temperature": 0.7,  # Higher for more creative responses
        "max_tokens": 5000,  
    },
    "summarization": {
        "temperature": 0.2,  # Lower for more factual extraction
        "max_tokens": 250,   # Increased to support multiple facts
        "detailed_mode": False,
    },
    "fact_extraction": {
        "temperature": 0.1,
        "max_tokens": 200,
    },
    "translation": {
        "temperature": 0.2,  # Low for accurate translation
        "max_tokens": 100,
    },
    "code_assistant": {
        "temperature": 0.3,  # Low for accurate code suggestions
        "max_tokens": 2000,
    },
    "code_review": {
        "temperature": 0.2,
        "max_tokens": 1000,
    },
    "code_summarization": {
        "temperature": 0.1,  # Very low for factual extraction
        "max_tokens": 300,
    }
}

def get_prompt_config(prompt_type: str) -> dict:
    """Get configuration for a specific prompt type."""
    return PROMPT_CONFIG.get(prompt_type, {})

# =============================================================================
# CODE PROMPT UTILITIES - Phase 4
# =============================================================================

def format_code_system_prompt(code_memories: list[dict] = None) -> str:
    """Format the code assistant system prompt with optional code context."""
    if not code_memories:
        return CODE_SYSTEM_PROMPT_BASE
    
    # Format code memories into readable context
    context_lines = []
    for mem in code_memories:
        file_path = mem.get('file_path', 'unknown')
        change_type = mem.get('change_type') or 'changed'  # Handle None
        summary = mem.get('change_summary', mem.get('text', ''))
        function = mem.get('function_name')
        
        context_line = f"• [{change_type.upper()}] {file_path}"
        if function:
            context_line += f"::{function}()"
        context_line += f" - {summary}"
        context_lines.append(context_line)
    
    code_context = "\n".join(context_lines)
    return CODE_SYSTEM_PROMPT_WITH_CONTEXT.format(code_context=code_context)

def format_code_context_prompt(memories: list[dict]) -> str:
    """Format code memories for context inclusion."""
    memories_text = "\n".join(
        f"- {m.get('text', m.get('summary', ''))}" 
        for m in memories
    )
    return CODE_CONTEXT_FORMATTING_PROMPT.format(memories=memories_text)

def format_code_query_expansion(query: str) -> str:
    """Expand code-related query for better search."""
    return CODE_SEARCH_QUERY_EXPANSION.format(query=query)

def format_code_change_summary(conversation: str) -> str:
    """Extract structured summary from code change conversation."""
    return CODE_CHANGE_SUMMARIZATION_PROMPT.format(conversation=conversation)

def format_code_bug_pattern(bug_fix: str) -> str:
    """Extract reusable pattern from bug fix."""
    return CODE_BUG_PATTERN_EXTRACTION.format(bug_fix=bug_fix)

def format_code_review(code: str, context: str = "") -> str:
    """Format code review prompt with context."""
    return CODE_REVIEW_PROMPT.format(code=code, context=context or "No specific context provided")

# =============================================================================
# CONVERSATION CONTEXT PROMPTS - Phase 1.5: Midterm Memory
# =============================================================================

CONVERSATION_SUMMARY_PROMPT = """Extract a rich, searchable summary from this coding conversation for knowledge graph storage.

**Your goal:** Create a summary that will help future searches find this conversation when relevant.

**Include:**
1. **Main Topic/Action** - What was the primary focus? (e.g., "Fixed bug", "Analyzed system", "Implemented feature")
2. **Technical Details** - Specific files, functions, technologies, algorithms mentioned
3. **Problem & Solution** - If a bug fix, what broke and how it was fixed
4. **Context** - Why this work was done, what it enables
5. **Key Outcomes** - Results, decisions made, lessons learned

**Format Guidelines:**
- Use clear, descriptive language (avoid vague terms like "discussed", "looked at")
- Include technical terminology (file paths, function names, library names)
- Be specific about what changed or was learned
- 3-5 sentences, technical but readable
- Write in English for consistency

**Example Good Summaries:**

"Fixed critical authentication bug in backend/auth/login.py where Redis rate limiter had no TTL, causing permanent user lockouts after 5 failed attempts. Added 15-minute expiration using setex() instead of incr(). Also added clear_rate_limit() admin function and logging for locked accounts. Prevents users from being permanently blocked."

"Analyzed authentication system architecture. Uses JWT tokens with 24-hour expiration and bcrypt password hashing (cost factor 12). Main components: auth/login.py (login endpoint), auth/session.py (session management via Redis), models/user.py (user model). Identified missing features: 2FA support and account lockout policy."

"Implemented Two-Factor Authentication using TOTP (pyotp library). Added User model fields: totp_secret, is_2fa_enabled, recovery_codes. Created three new endpoints: /auth/2fa/setup (generates QR code), /auth/2fa/verify (validates code), /auth/2fa/disable. Updated login flow to check is_2fa_enabled flag and require TOTP code if enabled."

**Conversation:**
{conversation_text}

**Context Files:**
{context_files}

**Tools Used:**
{tools}

**Rich Summary (3-5 sentences, searchable, technical):**"""

CONVERSATION_EPISODE_BODY_FORMATTER = """Format this conversation into a structured episode body optimized for entity extraction.

Use clear sections and technical terminology for better knowledge graph construction.

**Conversation Data:**
Chat ID: {chat_id}
Mode: {chat_mode}
Project: {project_id}

**Messages:**
{messages}

**Context Files:**
{context_files}

**Tools:**
{tools}

**Format into structured episode body with headers and clear sections.**"""

def format_conversation_summary(
    messages: list[dict],
    context_files: list[dict] = None,
    tools: list[dict] = None
) -> str:
    """
    Generate rich conversation summary for Graphiti
    
    Args:
        messages: List of message dicts with role and content_summary
        context_files: List of context file dicts with file_path
        tools: List of tool call dicts with tool_name
    
    Returns:
        Formatted prompt for LLM to generate summary
    """
    # Format conversation text
    conv_lines = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content_summary", "")
        conv_lines.append(f"[{role}]: {content}")
    conversation_text = "\n\n".join(conv_lines)
    
    # Format context files
    if context_files:
        file_lines = [f"- {cf.get('file_path', 'unknown')}" for cf in context_files]
        context_str = "\n".join(file_lines)
    else:
        context_str = "No context files"
    
    # Format tools
    if tools:
        tool_names = list(set([t.get("tool_name", "unknown") for t in tools]))
        tools_str = ", ".join(tool_names)
    else:
        tools_str = "No tools used"
    
    return CONVERSATION_SUMMARY_PROMPT.format(
        conversation_text=conversation_text,
        context_files=context_str,
        tools=tools_str
    )

def format_conversation_episode_body(
    chat_id: str,
    chat_mode: str,
    project_id: str,
    messages: list[dict],
    context_files: list[dict] = None,
    tools: list[dict] = None
) -> str:
    """
    Format conversation into structured episode body
    
    Better structure helps Graphiti extract entities properly
    """
    parts = []
    
    # Header
    parts.append(f"=== CODING CONVERSATION: {chat_id} ===")
    parts.append(f"Mode: {chat_mode} | Project: {project_id}")
    parts.append("")
    
    # Messages with clear structure
    parts.append("=== CONVERSATION ===")
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content_summary", "")
        parts.append(f"\n[{role}]")
        parts.append(content)
    parts.append("")
    
    # Context files
    if context_files and len(context_files) > 0:
        parts.append("=== CONTEXT FILES ===")
        for cf in context_files:
            file_path = cf.get("file_path", "unknown")
            usefulness = cf.get("usefulness", 0.0)
            parts.append(f"- {file_path} (relevance: {usefulness:.2f})")
        parts.append("")
    
    # Tools
    if tools and len(tools) > 0:
        parts.append("=== TOOLS USED ===")
        tool_names = list(set([t.get("tool_name", "unknown") for t in tools]))
        parts.append(f"Tools: {', '.join(tool_names)}")
        parts.append(f"Total calls: {len(tools)}")
        parts.append("")
    
    return "\n".join(parts)
