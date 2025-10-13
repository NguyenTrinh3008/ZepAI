#!/usr/bin/env python3
"""
Langfuse Tracing Helpers for Test Pipelines

Provides tracing utilities for test scenarios and reranking strategies
"""

import time
import logging
import json
import platform
import sys
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# Global test session tracking
_test_session_id = None
_test_scenarios_completed = 0
_test_queries_executed = 0


def get_system_metadata() -> Dict[str, Any]:
    """Get detailed system metadata for tracing"""
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "architecture": platform.architecture()[0],
        "processor": platform.processor(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "test_environment": "development"
    }


def get_enhanced_metadata(base_data: Dict[str, Any]) -> str:
    """Enhance base data with system metadata and formatting"""
    enhanced_data = {
        **base_data,
        "system_info": get_system_metadata(),
        "session_info": {
            "session_id": _test_session_id,
            "scenarios_completed": _test_scenarios_completed,
            "queries_executed": _test_queries_executed
        }
    }
    return json.dumps(enhanced_data, ensure_ascii=False, indent=2)


def init_test_session(session_name: str) -> str:
    """Initialize a test session with Langfuse tracing"""
    global _test_session_id, _test_scenarios_completed, _test_queries_executed
    
    _test_session_id = f"test_session_{int(time.time())}_{session_name}"
    _test_scenarios_completed = 0
    _test_queries_executed = 0
    
    logger.info(f"🧪 Test session started: {_test_session_id}")
    return _test_session_id


@contextmanager
def trace_test_scenario(scenario_name: str, scenario_type: str = "test"):
    """Context manager to trace a test scenario"""
    from langfuse import observe
    
    @observe(name=f"Test Scenario: {scenario_name}")
    def _trace_scenario():
        global _test_scenarios_completed
        _test_scenarios_completed += 1
        
        logger.info(f"📋 Starting scenario: {scenario_name}")
        
        result_data = {
            "scenario_name": scenario_name,
            "scenario_type": scenario_type,
            "session_id": _test_session_id,
            "scenario_number": _test_scenarios_completed,
            "start_time": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "service": "graphiti-memory-layer",
                "component": "test_tracing",
                "tags": ["test", "scenario", scenario_type]
            }
        }
        
        # Return enhanced metadata as JSON string
        return get_enhanced_metadata(result_data)
    
    try:
        result = _trace_scenario()
        yield result
    except Exception as e:
        logger.error(f"❌ Scenario failed: {scenario_name} - {e}")
        raise
    finally:
        logger.info(f"✅ Scenario completed: {scenario_name}")


@contextmanager
def trace_search_query(query: str, strategy: str = "rrf", expected_results: int = None):
    """Context manager to trace individual search queries"""
    from langfuse import observe
    
    global _test_queries_executed
    _test_queries_executed += 1
    
    @observe(name=f"Search Query #{_test_queries_executed}")
    def _trace_query():
        logger.info(f"🔍 Executing query: '{query[:50]}...' (strategy: {strategy})")
        
        return {
            "query": query,
            "strategy": strategy,
            "query_number": _test_queries_executed,
            "session_id": _test_session_id,
            "expected_results": expected_results
        }
    
    start_time = time.time()
    try:
        result = _trace_query()
        yield result
    except Exception as e:
        logger.error(f"❌ Query failed: {query[:30]}... - {e}")
        raise
    finally:
        duration = time.time() - start_time
        logger.info(f"⏱️ Query completed in {duration:.3f}s")


@contextmanager
def trace_conversation_ingest(conversation_type: str, request_id: str):
    """Context manager to trace conversation ingestion"""
    from langfuse import observe
    
    @observe(name=f"Conversation Ingest: {conversation_type}")
    def _trace_ingest():
        logger.info(f"📥 Ingesting conversation: {conversation_type}")
        
        return {
            "conversation_type": conversation_type,
            "request_id": request_id,
            "session_id": _test_session_id
        }
    
    start_time = time.time()
    try:
        result = _trace_ingest()
        yield result
    except Exception as e:
        logger.error(f"❌ Ingest failed: {conversation_type} - {e}")
        raise
    finally:
        duration = time.time() - start_time
        logger.info(f"⏱️ Ingest completed in {duration:.3f}s")


def trace_llm_classification(query: str, selected_strategy: str, confidence: float, reasoning: str):
    """Trace LLM query classification results"""
    from langfuse import observe
    
    @observe(name="LLM Query Classification")
    def _trace_classification():
        logger.info(f"🤖 LLM classified query as: {selected_strategy} (confidence: {confidence:.2f})")
        
        result_data = {
            "query": query,
            "selected_strategy": selected_strategy,
            "confidence": confidence,
            "reasoning": reasoning,
            "session_id": _test_session_id,
            "classification_time": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "service": "graphiti-memory-layer",
                "component": "llm_classifier",
                "tags": ["llm", "classification", "ai"]
            }
        }
        
        # Return enhanced metadata as JSON string
        return get_enhanced_metadata(result_data)
    
    return _trace_classification()


def trace_performance_metrics(metrics: Dict[str, Any], test_name: str):
    """Trace performance metrics for tests"""
    from langfuse import observe
    
    @observe(name=f"Performance Metrics: {test_name}")
    def _trace_metrics():
        logger.info(f"📊 Performance metrics for {test_name}")
        
        return {
            "test_name": test_name,
            "metrics": metrics,
            "session_id": _test_session_id
        }
    
    _trace_metrics()


def trace_error(error_message: str, context: Dict[str, Any] = None):
    """Trace errors that occur during testing"""
    from langfuse import observe
    
    @observe(name="Test Error")
    def _trace_error():
        logger.error(f"❌ Test error: {error_message}")
        
        return {
            "error_message": error_message,
            "context": context or {},
            "session_id": _test_session_id
        }
    
    _trace_error()


@contextmanager
def trace_conversation_ingest(conversation_type: str, request_id: str):
    """Context manager to trace conversation ingestion with detailed metadata"""
    from langfuse import observe
    
    start_time = time.time()
    
    @observe(name="Conversation Ingest")
    def _trace_ingest():
        logger.info(f"📥 Ingesting conversation: {conversation_type}")
        
        result_data = {
            "conversation_type": conversation_type,
            "request_id": request_id,
            "session_id": _test_session_id,
            "ingest_start_time": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "service": "graphiti-memory-layer",
                "component": "conversation_ingest",
                "tags": ["ingest", "conversation", conversation_type]
            }
        }
        
        return get_enhanced_metadata(result_data)
    
    try:
        result = _trace_ingest()
        yield result
    except Exception as e:
        logger.error(f"❌ Conversation ingest failed: {conversation_type} - {e}")
        raise
    finally:
        duration = time.time() - start_time
        logger.info(f"⏱️ Ingest completed in {duration:.3f}s")


def flush_test_traces():
    """Flush all test traces to Langfuse"""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from app.langfuse_tracer import flush_langfuse
        flush_langfuse()
        logger.info("🚀 Test traces flushed to Langfuse")
    except Exception as e:
        logger.error(f"Failed to flush traces: {e}")


def get_test_session_summary() -> Dict[str, Any]:
    """Get summary of current test session"""
    return {
        "session_id": _test_session_id,
        "scenarios_completed": _test_scenarios_completed,
        "queries_executed": _test_queries_executed
    }


def log_test_summary():
    """Log a summary of the test session"""
    summary = get_test_session_summary()
    logger.info(f"📋 Test Session Summary:")
    logger.info(f"   Session ID: {summary['session_id']}")
    logger.info(f"   Scenarios: {summary['scenarios_completed']}")
    logger.info(f"   Queries: {summary['queries_executed']}")
