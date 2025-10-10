#!/usr/bin/env python3
"""
OpenAI LLM-based Query Classification for Search Strategy Selection

Uses OpenAI's GPT models to intelligently analyze user queries and determine 
the optimal search strategy for the midterm memory system.

Requires: OPENAI_API_KEY environment variable
"""
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from app.config import llm
from app.graph import get_graphiti

logger = logging.getLogger(__name__)

class SearchStrategy(Enum):
    """Available search strategies"""
    RRF = "rrf"                    # Rich context, general purpose
    NODE_DISTANCE = "node_distance" # Entity-specific, focused
    MMR = "mmr"                    # Diversity, exploration
    CROSS_ENCODER = "cross_encoder" # High precision, accuracy
    NONE = "none"                  # Raw results, fastest

@dataclass
class QueryAnalysis:
    """Result of LLM query analysis"""
    strategy: SearchStrategy
    confidence: float
    reasoning: str
    focal_entity: Optional[str] = None
    query_intent: str = ""
    suggested_queries: List[str] = None

class LLMQueryClassifier:
    """
    OpenAI GPT-powered query classifier for intelligent search strategy selection.
    
    Uses OpenAI's language models to analyze user queries and determine the optimal
    search/reranking strategy based on query intent, specificity, and context.
    
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self.classification_prompt = self._build_classification_prompt()
        self.examples = self._build_examples()
    
    def _build_classification_prompt(self) -> str:
        """Build the LLM prompt for query classification"""
        return """
You are a query classifier for a coding assistant's memory system. 
Analyze the query and select the optimal search strategy.

CRITICAL: Be AGGRESSIVE in detecting keywords! Don't default to RRF unless absolutely necessary.

STRATEGIES (MUST CHECK IN THIS EXACT ORDER):

1. MMR (mmr) - ALWAYS CHECK FIRST for diversity keywords
   STRONG INDICATORS: "different", "various", "alternatives", "compare", "show me all", "multiple ways"
   MANDATORY: If ANY of these words appear → SELECT MMR
   Example: "show me different caching strategies" → MMR (100% confidence)

2. NODE_DISTANCE (node_distance) - CHECK SECOND for specific entities  
   STRONG INDICATORS: File extensions (.py, .js, .ts), function names, "changes to [entity]"
   MANDATORY: If file extension OR specific entity mentioned → SELECT NODE_DISTANCE
   Example: "What changes were made to auth.py?" → NODE_DISTANCE (100% confidence)

3. CROSS_ENCODER (cross_encoder) - CHECK THIRD for precision keywords
   STRONG INDICATORS: "exact", "precise", "generate", "implement exactly", "critical"
   MANDATORY: If ANY precision keyword → SELECT CROSS_ENCODER
   Example: "generate exact JWT validation code" → CROSS_ENCODER (100% confidence)

4. RRF (rrf) - ONLY if NO keywords above detected
   FALLBACK: Use ONLY when no diversity, entity, or precision keywords found
   Example: "How to implement authentication?" → RRF (only if no other keywords)

DETECTION RULES:
- SCAN query word-by-word for keywords
- If diversity keyword found → MMR (don't consider others)
- If entity keyword found → NODE_DISTANCE (don't consider others)  
- If precision keyword found → CROSS_ENCODER (don't consider others)
- ONLY use RRF if NO keywords detected

RESPONSE FORMAT (JSON only):
{
  "strategy": "strategy_name",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "focal_entity": "entity_name_or_null",
  "query_intent": "intent_description",
  "suggested_queries": ["alt1", "alt2"]
}

EXAMPLES:
"""
    
    def _build_examples(self) -> List[Dict]:
        """Build example queries and their classifications"""
        return [
            # MMR Examples (Diversity - HIGHEST PRIORITY)
            {
                "query": "show me different caching strategies",
                "expected": {
                    "strategy": "mmr",
                    "confidence": 1.0,
                    "reasoning": "MANDATORY: Diversity keyword 'different' detected → MMR",
                    "focal_entity": None,
                    "query_intent": "exploration",
                    "suggested_queries": ["caching alternatives", "various cache methods"]
                }
            },
            {
                "query": "various authentication methods",
                "expected": {
                    "strategy": "mmr",
                    "confidence": 1.0,
                    "reasoning": "MANDATORY: Diversity keyword 'various' detected → MMR",
                    "focal_entity": None,
                    "query_intent": "exploration",
                    "suggested_queries": ["auth alternatives", "different auth methods"]
                }
            },
            
            # NODE_DISTANCE Examples (Entity-specific - SECOND PRIORITY)
            {
                "query": "What changes were made to auth.py?",
                "expected": {
                    "strategy": "node_distance",
                    "confidence": 1.0,
                    "reasoning": "MANDATORY: File extension '.py' detected → NODE_DISTANCE",
                    "focal_entity": "auth.py",
                    "query_intent": "file_history",
                    "suggested_queries": ["auth.py modifications", "authentication file changes"]
                }
            },
            {
                "query": "Show me getUserData function",
                "expected": {
                    "strategy": "node_distance",
                    "confidence": 1.0,
                    "reasoning": "MANDATORY: Specific function name 'getUserData' detected → NODE_DISTANCE",
                    "focal_entity": "getUserData",
                    "query_intent": "function_lookup",
                    "suggested_queries": ["getUserData function", "user data retrieval"]
                }
            },
            
            # CROSS_ENCODER Examples (Precision - THIRD PRIORITY)
            {
                "query": "generate exact JWT validation code",
                "expected": {
                    "strategy": "cross_encoder",
                    "confidence": 1.0,
                    "reasoning": "MANDATORY: Precision keywords 'exact' and 'generate' detected → CROSS_ENCODER",
                    "focal_entity": "JWT",
                    "query_intent": "code_generation",
                    "suggested_queries": ["JWT validation code", "token verification"]
                }
            },
            
            # RRF Examples (General - ONLY WHEN NO KEYWORDS)
            {
                "query": "How to implement authentication?",
                "expected": {
                    "strategy": "rrf",
                    "confidence": 0.9,
                    "reasoning": "FALLBACK: No diversity, entity, or precision keywords detected → RRF",
                    "focal_entity": None,
                    "query_intent": "implementation_guidance",
                    "suggested_queries": ["authentication patterns", "auth implementation"]
                }
            }
        ]
    
    async def classify_query(self, query: str, context: Optional[Dict] = None) -> QueryAnalysis:
        """
        Classify a user query and determine optimal search strategy
        
        Args:
            query: User's search query
            context: Additional context (current file, conversation history, etc.)
            
        Returns:
            QueryAnalysis with strategy recommendation
        """
        try:
            # Build context-aware prompt
            full_prompt = self._build_full_prompt(query, context)
            
            # Get LLM classification
            response = await self._get_llm_classification(full_prompt)
            
            # Parse and validate response
            analysis = self._parse_llm_response(response, query)
            
            return analysis
            
        except Exception as e:
            # Fallback to RRF on error
            return QueryAnalysis(
                strategy=SearchStrategy.RRF,
                confidence=0.5,
                reasoning=f"Fallback due to classification error: {str(e)}",
                query_intent="general",
                suggested_queries=[]
            )
    
    def _build_full_prompt(self, query: str, context: Optional[Dict] = None) -> str:
        """Build complete prompt with query and context"""
        prompt = self.classification_prompt
        
        # Add examples
        for example in self.examples:
            prompt += f'\nQuery: "{example["query"]}"\n'
            prompt += f'Expected: {json.dumps(example["expected"], indent=2)}\n'
        
        # Add current query
        prompt += f'\n\nCURRENT QUERY TO CLASSIFY:\n'
        prompt += f'Query: "{query}"\n'
        
        # Add context if available
        if context:
            prompt += f'\nCONTEXT:\n'
            if context.get("current_file"):
                prompt += f'- Current file: {context["current_file"]}\n'
            if context.get("conversation_type"):
                prompt += f'- Conversation type: {context["conversation_type"]}\n'
            if context.get("recent_queries"):
                prompt += f'- Recent queries: {context["recent_queries"][:3]}\n'
        
        prompt += '\nProvide your analysis in JSON format:\n'
        
        return prompt
    
    async def _get_llm_classification(self, prompt: str) -> str:
        """Get real LLM classification response from OpenAI"""
        import os
        
        # Check if OpenAI API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key or api_key == "your_key_here":
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.\n"
                "Get your API key from: https://platform.openai.com/api-keys"
            )
        
        # Use real OpenAI LLM
        logger.info("🤖 Using OpenAI LLM for query classification")
        response = await self._call_openai_llm(prompt, api_key)
        return response
    
    async def _call_openai_llm(self, prompt: str, api_key: str) -> str:
        """Call OpenAI API for LLM classification"""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=api_key)
            
            # Get model from config
            model_name = llm.MODEL_NAME if hasattr(llm, 'MODEL_NAME') else "gpt-4o-mini"
            
            logger.debug(f"🔄 Calling OpenAI {model_name} for query classification...")
            
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert query classifier for a coding assistant's memory system. "
                                   "Analyze queries and recommend optimal search strategies. "
                                   "Respond ONLY with valid JSON, no additional text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent classification
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            result = response.choices[0].message.content
            logger.debug(f"✅ OpenAI response received: {len(result)} chars")
            
            return result
            
        except ImportError:
            logger.error("❌ openai package not installed. Run: pip install openai")
            raise
        except Exception as e:
            logger.error(f"❌ OpenAI API call failed: {e}")
            raise
    
    def _parse_llm_response(self, response: str, original_query: str) -> QueryAnalysis:
        """Parse LLM response into QueryAnalysis object"""
        try:
            # Clean response (remove markdown, extra text)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            data = json.loads(response)
            
            # Validate strategy
            try:
                strategy = SearchStrategy(data["strategy"])
            except ValueError:
                strategy = SearchStrategy.RRF  # Default fallback
            
            return QueryAnalysis(
                strategy=strategy,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "No reasoning provided"),
                focal_entity=data.get("focal_entity"),
                query_intent=data.get("query_intent", "unknown"),
                suggested_queries=data.get("suggested_queries", [])
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback parsing
            return QueryAnalysis(
                strategy=SearchStrategy.RRF,
                confidence=0.3,
                reasoning=f"Failed to parse LLM response: {str(e)}",
                query_intent="unknown",
                suggested_queries=[]
            )


class SmartSearchService:
    """
    Enhanced search service with OpenAI GPT-powered intelligent strategy selection.
    
    Automatically analyzes queries using OpenAI's language models to determine
    the optimal search and reranking strategy for each request.
    
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self):
        self.classifier = LLMQueryClassifier()
    
    async def smart_search(
        self, 
        query: str, 
        graphiti,
        context: Optional[Dict] = None,
        force_strategy: Optional[SearchStrategy] = None
    ) -> Dict:
        """
        Perform intelligent search with OpenAI GPT-selected strategy.
        
        Args:
            query: User search query
            graphiti: Graphiti instance
            context: Additional context for LLM classification (project_id, current_file, etc.)
            force_strategy: Override LLM classification with manual strategy
            
        Returns:
            Enhanced search results with classification metadata
            
        Raises:
            ValueError: If OPENAI_API_KEY is not set and no force_strategy provided
        """
        # Classify query if not forced
        if force_strategy:
            analysis = QueryAnalysis(
                strategy=force_strategy,
                confidence=1.0,
                reasoning="Strategy forced by user",
                query_intent="forced"
            )
        else:
            analysis = await self.classifier.classify_query(query, context)
        
        # Perform search with selected strategy
        results = await self._execute_search(
            query=query,
            graphiti=graphiti,
            analysis=analysis,
            context=context
        )
        
        # Enhance results with classification info
        results["classification"] = {
            "strategy": analysis.strategy.value,
            "confidence": analysis.confidence,
            "reasoning": analysis.reasoning,
            "query_intent": analysis.query_intent,
            "focal_entity": analysis.focal_entity,
            "suggested_queries": analysis.suggested_queries
        }
        
        return results
    
    async def _execute_search(
        self, 
        query: str, 
        graphiti, 
        analysis: QueryAnalysis,
        context: Optional[Dict] = None
    ) -> Dict:
        """Execute search with classified strategy"""
        from app.services.search_service import search_knowledge_graph
        
        # Prepare search parameters
        search_params = {
            "query": query,
            "graphiti": graphiti,
            "group_id": context.get("project_id") if context else "innocody_test_project",
            "rerank_strategy": analysis.strategy.value,
            "limit": context.get("limit", 10)
        }
        
        # Add focal node for node_distance
        if analysis.strategy == SearchStrategy.NODE_DISTANCE and analysis.focal_entity:
            focal_uuid = await self._get_entity_uuid(analysis.focal_entity, graphiti)
            if focal_uuid:
                search_params["focal_node_uuid"] = focal_uuid
        
        # Execute search
        return await search_knowledge_graph(**search_params)
    
    async def _get_entity_uuid(self, entity_name: str, graphiti) -> Optional[str]:
        """Get UUID for focal entity"""
        try:
            # Search for entity in graph
            results = await graphiti.search(entity_name, limit=1)
            if results:
                return results[0].get("source_node_uuid") or results[0].get("uuid")
        except Exception:
            pass
        return None


# Convenience function
async def classify_and_search(
    query: str, 
    graphiti,
    context: Optional[Dict] = None
) -> Dict:
    """
    Convenience function for OpenAI GPT-powered smart search.
    
    Automatically classifies query and executes optimal search strategy.
    Requires OPENAI_API_KEY environment variable.
    """
    service = SmartSearchService()
    return await service.smart_search(query, graphiti, context)
