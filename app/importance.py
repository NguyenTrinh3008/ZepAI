# app/importance.py
"""
LLM-Only Importance Scoring

Uses OpenAI to score:
1. Conversation facts
2. Code changes

Requires OPENAI_API_KEY in .env file
"""

import os
from openai import OpenAI
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# Prompts
# =============================================================================

CONVERSATION_PROMPT = """Classify this fact's importance category and score.

**Fact:** "{fact}"

**Categories (score):**
- identity (1.0): Personal information like name, age, location, occupation
- preference (0.8): Likes, dislikes, interests, favorites
- knowledge (0.7): Skills learned, topics understood, technical knowledge
- action (0.6): Concrete things done, projects completed
- opinion (0.5): Views, thoughts, beliefs on topics
- question (0.3): Questions asked (usually not persistent)
- greeting (0.1): Greetings, small talk, meta-conversation

**Examples:**

Fact: "User's name is John Smith"
→ identity|1.0

Fact: "User prefers Python over Java for web development"
→ preference|0.8

Fact: "User learned async programming in Python"
→ knowledge|0.7

Fact: "User completed snake game project with AI opponent"
→ action|0.6

Fact: "User said hello"
→ greeting|0.1

**Output format:** category|score

**Your classification:**"""


CODE_PROMPT = """Score this code change's importance.

**Code Change:**
- Type: {change_type}
- File: {file_path}
- Severity: {severity}
- Summary: {summary}

**Categories (score):**
- critical_bug (1.0): Security vulnerabilities, data loss risks, system crashes
- architecture (0.95): Major design decisions, migrations, framework changes
- breaking_change (0.9): API incompatibilities, major refactors affecting users
- major_feature (0.85): Significant new capabilities, major improvements
- bug_fix (0.75): Standard bug fixes, error corrections
- refactor (0.7): Code improvements, optimization, restructuring
- minor_feature (0.6): Small additions, minor improvements
- optimization (0.55): Performance improvements, efficiency gains
- documentation (0.4): Documentation updates, comments
- style (0.2): Formatting, linting, code style changes

**Guidelines:**
- Security issues → critical_bug (1.0)
- Core files (auth, database, API) → higher importance
- Breaking changes → breaking_change (0.9)
- High severity + fix → bug_fix or critical_bug
- Architecture/design changes → architecture (0.95)

**Examples:**

Change: fixed, auth/security.py, critical, "SQL injection vulnerability"
→ critical_bug|1.0

Change: added, api/routes.py, high, "New payment processing endpoint"
→ major_feature|0.85

Change: refactored, utils/helper.py, low, "Code formatting"
→ style|0.2

Change: fixed, api/middleware.py, medium, "Timeout error in requests"
→ bug_fix|0.75

**Output format:** category|score

**Your classification:**"""


# =============================================================================
# Scorer Class
# =============================================================================

class LLMImportanceScorer:
    """LLM-only importance scorer (requires OpenAI API key)"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize LLM scorer
        
        Args:
            api_key: OpenAI API key (optional, uses OPENAI_API_KEY env var)
            model: Model name (default: gpt-4o-mini)
        
        Raises:
            ValueError: If no API key found
        """
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OpenAI API key required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=key)
        self.model = model
    
    # Aliases for backward compatibility
    async def score_fact(self, fact: str) -> Dict[str, float]:
        """Alias for score_conversation"""
        return await self.score_conversation(fact)
    
    async def score_code_memory_llm(self, **kwargs) -> Dict[str, float]:
        """Alias for score_code_change"""
        return await self.score_code_change(**kwargs)
    
    def should_ingest(self, fact: str, threshold: float = 0.3) -> tuple[bool, Dict]:
        """
        Synchronous wrapper to check if fact should be ingested
        
        Args:
            fact: The fact to evaluate
            threshold: Minimum score to ingest (default: 0.3)
            
        Returns:
            (should_ingest: bool, score_info: dict)
        """
        import asyncio
        
        try:
            # Run async score_conversation in sync context
            result = asyncio.run(self.score_conversation(fact))
            score = result['score']
            should_ingest = score >= threshold
            
            return should_ingest, result
        except Exception as e:
            # On error, default to ingesting with neutral score
            return True, {
                "category": "unknown",
                "score": 0.5,
                "reasoning": f"Error: {e}"
            }
    
    async def score_conversation(self, fact: str) -> Dict[str, float]:
        """
        Score a conversation fact using LLM
        
        Args:
            fact: The fact to score
            
        Returns:
            {
                "category": str,
                "score": float (0.0-1.0),
                "reasoning": str
            }
        """
        prompt = CONVERSATION_PROMPT.format(fact=fact)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=50,
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse "category|score"
        if "|" in result:
            category, score_str = result.split("|", 1)
            category = category.strip().lower()
            score = float(score_str.strip())
            
            return {
                "category": category,
                "score": round(score, 3),
                "reasoning": f"LLM: {category}"
            }
        else:
            # Default if parsing fails
            return {
                "category": "opinion",
                "score": 0.5,
                "reasoning": "LLM parse error - default score"
            }
    
    async def score_code_change(self,
                               change_type: str,
                               severity: Optional[str] = None,
                               file_path: Optional[str] = None,
                               summary: Optional[str] = None) -> Dict[str, float]:
        """
        Score a code change using LLM
        
        Args:
            change_type: Type of change (fixed, added, refactored, removed)
            severity: Severity level (critical, high, medium, low)
            file_path: File path
            summary: Change summary text
            
        Returns:
            {
                "category": str,
                "score": float (0.0-1.0),
                "reasoning": str
            }
        """
        prompt = CODE_PROMPT.format(
            change_type=change_type or "unknown",
            file_path=file_path or "unknown",
            severity=severity or "medium",
            summary=summary or "No description"
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=50,
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse "category|score"
        if "|" in result:
            category, score_str = result.split("|", 1)
            category = category.strip().lower()
            score = float(score_str.strip())
            
            return {
                "category": category,
                "score": round(score, 3),
                "reasoning": f"LLM: {category}"
            }
        else:
            # Default if parsing fails
            return {
                "category": "minor_feature",
                "score": 0.6,
                "reasoning": "LLM parse error - default score"
            }


# =============================================================================
# Singleton
# =============================================================================

_scorer = None

def get_scorer(api_key: Optional[str] = None) -> LLMImportanceScorer:
    """Get global LLM scorer instance"""
    global _scorer
    if _scorer is None:
        _scorer = LLMImportanceScorer(api_key=api_key)
    return _scorer


# =============================================================================
# Convenience Functions
# =============================================================================

async def score_fact(fact: str) -> float:
    """Quick function to score a conversation fact"""
    scorer = get_scorer()
    result = await scorer.score_conversation(fact)
    return result["score"]


async def score_code(change_type: str,
                    severity: Optional[str] = None,
                    file_path: Optional[str] = None,
                    summary: Optional[str] = None) -> float:
    """Quick function to score a code change"""
    scorer = get_scorer()
    result = await scorer.score_code_change(
        change_type=change_type,
        severity=severity,
        file_path=file_path,
        summary=summary
    )
    return result["score"]
