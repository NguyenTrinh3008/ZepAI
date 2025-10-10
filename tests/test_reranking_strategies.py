#!/usr/bin/env python3
"""
Comprehensive test and comparison of different reranking strategies
NOW WITH LLM-POWERED INTELLIGENT STRATEGY SELECTION!

Based on Graphiti documentation:
https://help.getzep.com/graphiti/working-with-data/searching

Features:
- LLM-powered intelligent strategy selection
- Multiple query types (specific, vague, technical, general)
- Performance timing measurements
- Result diversity analysis
- Real-world coding scenarios
- Node distance testing with focal nodes
- Comparison: Manual vs LLM classification
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph import get_graphiti
from app.services.search_service import search_knowledge_graph
from app.config import search as search_config
from app.query_classifier import SmartSearchService, LLMQueryClassifier

PROJECT_ID = "innocody_test_project"

# Test Query Categories
QUERY_CATEGORIES = {
    "specific_technical": [
        "async await database performance optimization",
        "SQL injection security vulnerability fix",
        "React component state management refactoring",
        "Python async def function implementation"
    ],
    "vague_general": [
        "performance issues",
        "database problems", 
        "code improvements",
        "bug fixes"
    ],
    "coding_tasks": [
        "implement user authentication",
        "optimize database queries",
        "refactor legacy code",
        "add error handling"
    ],
    "mixed_keywords": [
        "async database refactor performance",
        "security vulnerability authentication",
        "optimization cache memory",
        "testing deployment monitoring"
    ],
    "diversity_queries": [
        "show me different authentication methods",
        "various caching strategies for performance",
        "compare different database optimization approaches"
    ],
    "precision_queries": [
        "generate exact JWT token validation code",
        "implement precise error handling for critical functions"
    ]
}


async def test_single_strategy_with_timing(
    query: str,
    strategy: str,
    focal_node_uuid: str = None,
    limit: int = 5
) -> Dict:
    """Test a single reranking strategy with performance timing"""
    print(f"\n{'='*80}")
    print(f"Strategy: {strategy.upper()}")
    print(f"{'='*80}")
    
    graphiti = await get_graphiti()
    
    try:
        # Time the search
        start_time = time.time()
        results = await search_knowledge_graph(
            query=query,
            graphiti=graphiti,
            group_id=PROJECT_ID,
            limit=limit,
            rerank_strategy=strategy,
            focal_node_uuid=focal_node_uuid
        )
        end_time = time.time()
        search_time = end_time - start_time
        
        result_count = len(results.get("results", []))
        print(f"Results found: {result_count} (Time: {search_time:.3f}s)")
        
        if result_count > 0:
            print(f"\nTop 3 Results:")
            for i, result in enumerate(results["results"][:3], 1):
                name = result.get("name", "Unknown")
                summary = (result.get("summary") or result.get("text", ""))[:100]
                # Clean Unicode characters for Windows console
                summary = summary.replace('\u2192', '->').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
                score = result.get("score", 0.0)
                print(f"\n{i}. {name}")
                print(f"   Score: {score:.4f}")
                print(f"   Summary: {summary}...")
        else:
            print("No results found")
        
        # Add timing to results
        results["timing"] = {
            "search_time": search_time,
            "strategy": strategy,
            "query": query
        }
        
        return results
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"results": [], "error": str(e), "timing": {"search_time": 0, "strategy": strategy, "query": query}}


def calculate_result_diversity(results_by_strategy: Dict[str, Dict]) -> Dict[str, float]:
    """Calculate diversity metrics between strategies"""
    diversity_metrics = {}
    
    # Get all result names from each strategy
    strategy_results = {}
    for strategy, result_data in results_by_strategy.items():
        if result_data.get("results"):
            strategy_results[strategy] = [r.get("name", "") for r in result_data["results"]]
        else:
            strategy_results[strategy] = []
    
    # Calculate overlap between strategies
    strategies = list(strategy_results.keys())
    for i, strategy1 in enumerate(strategies):
        for strategy2 in strategies[i+1:]:
            results1 = set(strategy_results[strategy1])
            results2 = set(strategy_results[strategy2])
            
            if results1 or results2:
                # Jaccard similarity
                intersection = len(results1.intersection(results2))
                union = len(results1.union(results2))
                similarity = intersection / union if union > 0 else 0
                diversity_metrics[f"{strategy1}_vs_{strategy2}"] = 1 - similarity
    
    return diversity_metrics


def analyze_performance(results_by_strategy: Dict[str, Dict]) -> Dict[str, Any]:
    """Analyze performance metrics across strategies"""
    performance = {
        "timing": {},
        "result_counts": {},
        "avg_scores": {},
        "strategies": []
    }
    
    for strategy, result_data in results_by_strategy.items():
        timing = result_data.get("timing", {})
        results = result_data.get("results", [])
        
        performance["strategies"].append(strategy)
        performance["timing"][strategy] = timing.get("search_time", 0)
        performance["result_counts"][strategy] = len(results)
        
        # Calculate average score
        if results:
            scores = [r.get("score", 0) for r in results]
            performance["avg_scores"][strategy] = sum(scores) / len(scores)
        else:
            performance["avg_scores"][strategy] = 0
    
    return performance


async def test_llm_strategy_selection():
    """NEW: Test LLM-powered intelligent strategy selection"""
    print(f"\n{'='*80}")
    print(f"LLM-POWERED INTELLIGENT STRATEGY SELECTION TEST")
    print(f"{'='*80}")
    print(f"Project: {PROJECT_ID}")
    
    graphiti = await get_graphiti()
    smart_service = SmartSearchService()
    
    llm_results = {}
    llm_performance = defaultdict(list)
    
    # Test each query category with LLM
    for category, queries in QUERY_CATEGORIES.items():
        print(f"\n\n{'='*60}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*60}")
        
        category_results = {}
        
        for query in queries:
            print(f"\n--- Query: '{query}' ---")
            
            # Map category to conversation type for context
            conversation_type_map = {
                "specific_technical": "implementation",
                "vague_general": "debugging",
                "coding_tasks": "implementation",
                "mixed_keywords": "exploration",
                "diversity_queries": "exploration",
                "precision_queries": "implementation"
            }
            
            context = {
                "project_id": PROJECT_ID,
                "conversation_type": conversation_type_map.get(category, "general"),
                "limit": 5
            }
            
            try:
                # Time the LLM-powered search
                start_time = time.time()
                result = await smart_service.smart_search(
                    query=query,
                    graphiti=graphiti,
                    context=context
                )
                end_time = time.time()
                search_time = end_time - start_time
                
                # Extract classification info
                classification = result.get("classification", {})
                selected_strategy = classification.get("strategy", "unknown")
                confidence = classification.get("confidence", 0)
                reasoning = classification.get("reasoning", "No reasoning")
                
                print(f"  LLM Selected: {selected_strategy} (confidence: {confidence:.2f})")
                # Clean Unicode characters for Windows console
                clean_reasoning = reasoning.replace('\u2192', '->').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
                print(f"  Reasoning: {clean_reasoning[:80]}...")
                print(f"  Results: {len(result.get('results', []))} found in {search_time:.3f}s")
                
                # Store results
                category_results[query] = {
                    "strategy": selected_strategy,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "results": result.get("results", []),
                    "search_time": search_time,
                    "result_count": len(result.get("results", []))
                }
                
                # Collect performance data
                llm_performance[selected_strategy].append({
                    "category": category,
                    "query": query,
                    "search_time": search_time,
                    "result_count": len(result.get("results", [])),
                    "confidence": confidence
                })
                
            except Exception as e:
                print(f"  ERROR: {e}")
                category_results[query] = {
                    "error": str(e),
                    "strategy": "error",
                    "search_time": 0,
                    "result_count": 0
                }
            
            await asyncio.sleep(0.2)
        
        llm_results[category] = category_results
    
    # LLM Performance Analysis
    print(f"\n\n{'='*80}")
    print(f"LLM STRATEGY SELECTION ANALYSIS")
    print(f"{'='*80}")
    
    # Strategy distribution
    strategy_counts = defaultdict(int)
    total_queries = 0
    
    for category_data in llm_results.values():
        for query_data in category_data.values():
            if "strategy" in query_data:
                strategy_counts[query_data["strategy"]] += 1
                total_queries += 1
    
    print(f"\nStrategy Distribution:")
    for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_queries * 100) if total_queries > 0 else 0
        print(f"  {strategy:15}: {count:2d} times ({percentage:5.1f}%)")
    
    # Average performance by selected strategy
    print(f"\nPerformance by LLM-Selected Strategy:")
    for strategy, perf_data in llm_performance.items():
        if perf_data:
            avg_time = sum(p["search_time"] for p in perf_data) / len(perf_data)
            avg_results = sum(p["result_count"] for p in perf_data) / len(perf_data)
            avg_confidence = sum(p["confidence"] for p in perf_data) / len(perf_data)
            
            print(f"\n  {strategy.upper()}:")
            print(f"    Used: {len(perf_data)} times")
            print(f"    Avg search time: {avg_time:.3f}s")
            print(f"    Avg results: {avg_results:.1f}")
            print(f"    Avg confidence: {avg_confidence:.2f}")
    
    return llm_results, llm_performance


async def comprehensive_strategy_comparison():
    """Comprehensive comparison across multiple query categories"""
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE RERANKING STRATEGIES ANALYSIS")
    print(f"{'='*80}")
    print(f"Project: {PROJECT_ID}")
    
    # Get available strategies
    strategies = list(search_config.get_available_strategies().keys())
    strategies = [s for s in strategies if s != "node_distance"]  # Skip node_distance for now
    
    print(f"\nTesting strategies: {', '.join(strategies)}")
    print(f"Query categories: {', '.join(QUERY_CATEGORIES.keys())}")
    
    all_results = {}
    performance_summary = defaultdict(list)
    
    # Test each query category
    for category, queries in QUERY_CATEGORIES.items():
        print(f"\n\n{'='*60}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*60}")
        
        category_results = {}
        
        for query in queries:
            print(f"\n--- Query: '{query}' ---")
            
            query_results = {}
            for strategy in strategies:
                result = await test_single_strategy_with_timing(query, strategy, limit=5)
                query_results[strategy] = result
                
                # Collect performance data
                timing = result.get("timing", {})
                performance_summary[strategy].append({
                    "category": category,
                    "query": query,
                    "search_time": timing.get("search_time", 0),
                    "result_count": len(result.get("results", []))
                })
                
                # Small delay between tests
                await asyncio.sleep(0.2)
            
            category_results[query] = query_results
        
        all_results[category] = category_results
    
    # Performance Analysis
    print(f"\n\n{'='*80}")
    print(f"PERFORMANCE ANALYSIS")
    print(f"{'='*80}")
    
    for strategy in strategies:
        strategy_perf = performance_summary[strategy]
        avg_time = sum(p["search_time"] for p in strategy_perf) / len(strategy_perf)
        avg_results = sum(p["result_count"] for p in strategy_perf) / len(strategy_perf)
        
        print(f"\n{strategy.upper()}:")
        print(f"  Average search time: {avg_time:.3f}s")
        print(f"  Average results: {avg_results:.1f}")
    
    # Diversity Analysis
    print(f"\n\n{'='*80}")
    print(f"DIVERSITY ANALYSIS")
    print(f"{'='*80}")
    
    # Analyze diversity for each query
    for category, queries in all_results.items():
        print(f"\n{category.upper()}:")
        for query, query_results in queries.items():
            diversity = calculate_result_diversity(query_results)
            if diversity:
                avg_diversity = sum(diversity.values()) / len(diversity)
                print(f"  '{query}': {avg_diversity:.3f} diversity")
    
    return all_results, performance_summary


async def test_node_distance_comprehensive():
    """Comprehensive testing of node_distance strategy with multiple focal nodes"""
    print(f"\n\n{'='*80}")
    print(f"NODE DISTANCE COMPREHENSIVE TESTING")
    print(f"{'='*80}")
    
    graphiti = await get_graphiti()
    
    # Find multiple focal nodes for testing
    focal_queries = [
        "payment processing",
        "database optimization", 
        "async refactoring",
        "security vulnerability"
    ]
    
    focal_nodes = []
    
    print("Step 1: Finding focal nodes...")
    for query in focal_queries:
        try:
            results = await search_knowledge_graph(
                query=query,
                graphiti=graphiti,
                group_id=PROJECT_ID,
                limit=1,
                rerank_strategy="rrf"
            )
            
            if results.get("results"):
                node = results["results"][0]
                focal_nodes.append({
                    "name": node.get("name", "Unknown"),
                    "uuid": node.get("id"),
                    "source_query": query
                })
                print(f"  Found: {node.get('name', 'Unknown')} (from '{query}')")
        except Exception as e:
            print(f"  Error finding focal node for '{query}': {e}")
    
    if not focal_nodes:
        print("No focal nodes found!")
        return
    
    # Test queries for node distance
    test_queries = [
        "async await performance",
        "database optimization", 
        "security authentication",
        "code refactoring"
    ]
    
    print(f"\nStep 2: Testing node_distance with {len(focal_nodes)} focal nodes...")
    
    for focal_node in focal_nodes:
        print(f"\n--- Focal Node: {focal_node['name']} ---")
        
        for query in test_queries:
            print(f"\nQuery: '{query}'")
            
            # Test RRF vs Node Distance
            rrf_results = await test_single_strategy_with_timing(
                query, "rrf", limit=3
            )
            
            node_dist_results = await test_single_strategy_with_timing(
                query, "node_distance", focal_node["uuid"], limit=3
            )
            
            # Compare results
            rrf_names = [r.get("name", "") for r in rrf_results.get("results", [])]
            nd_names = [r.get("name", "") for r in node_dist_results.get("results", [])]
            
            print(f"  RRF: {rrf_names}")
            print(f"  Node Distance: {nd_names}")
            
            # Check if node_distance found focal node in results
            focal_in_results = focal_node["name"] in nd_names
            print(f"  Focal node in results: {focal_in_results}")
            
            await asyncio.sleep(0.3)


async def save_results_to_json(all_results: Dict, performance_summary: Dict, filename: str = "reranking_analysis.json"):
    """Save comprehensive results to JSON file"""
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project_id": PROJECT_ID,
        "query_categories": QUERY_CATEGORIES,
        "results": all_results,
        "performance_summary": dict(performance_summary)
    }
    
    output_file = Path(__file__).parent / filename
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {output_file}")
    except Exception as e:
        print(f"Error saving results: {e}")


async def generate_recommendations(performance_summary: Dict) -> Dict[str, str]:
    """Generate strategy recommendations based on performance analysis"""
    recommendations = {}
    
    # Calculate averages
    strategy_stats = {}
    for strategy, perf_data in performance_summary.items():
        avg_time = sum(p["search_time"] for p in perf_data) / len(perf_data)
        avg_results = sum(p["result_count"] for p in perf_data) / len(perf_data)
        strategy_stats[strategy] = {
            "avg_time": avg_time,
            "avg_results": avg_results,
            "total_tests": len(perf_data)
        }
    
    # Find fastest strategy
    fastest = min(strategy_stats.items(), key=lambda x: x[1]["avg_time"])
    recommendations["fastest"] = f"Fastest: {fastest[0]} ({fastest[1]['avg_time']:.3f}s avg)"
    
    # Find most consistent (lowest variance in results)
    result_counts = {s: [p["result_count"] for p in perf_data] for s, perf_data in performance_summary.items()}
    variances = {}
    for strategy, counts in result_counts.items():
        if counts:
            mean = sum(counts) / len(counts)
            variance = sum((x - mean) ** 2 for x in counts) / len(counts)
            variances[strategy] = variance
    
    if variances:
        most_consistent = min(variances.items(), key=lambda x: x[1])
        recommendations["most_consistent"] = f"Most consistent: {most_consistent[0]} (variance: {most_consistent[1]:.2f})"
    
    # General recommendations
    recommendations["general"] = [
        "Use RRF for general-purpose searches (fast and reliable)",
        "Use MMR when you need diverse results and can accept slower performance", 
        "Use Cross-Encoder for highest accuracy when speed is not critical",
        "Use Node Distance when you have a specific entity to focus on",
        "Use Episode Mentions for temporal/frequency-based relevance"
    ]
    
    return recommendations


async def compare_all_strategies():
    """Legacy function - redirects to comprehensive comparison"""
    print("Redirecting to comprehensive strategy comparison...")
    return await comprehensive_strategy_comparison()


async def test_with_focal_node():
    """Legacy function - redirects to comprehensive node distance testing"""
    print("Redirecting to comprehensive node distance testing...")
    return await test_node_distance_comprehensive()


async def main():
    """Main test runner with comprehensive options - NOW WITH LLM!"""
    print("=" * 80)
    print("GRAPHITI RERANKING STRATEGIES COMPREHENSIVE TEST")
    print("NOW WITH LLM-POWERED INTELLIGENT STRATEGY SELECTION!")
    print("Based on: https://help.getzep.com/graphiti/working-with-data/searching")
    print("=" * 80)
    
    print("\nAvailable Reranking Strategies:")
    for name, desc in search_config.get_available_strategies().items():
        print(f"  - {name:20} - {desc}")
    
    print("\n\nChoose test mode:")
    print("1. LLM-Powered Intelligent Selection (NEW!)")
    print("2. Manual: Comprehensive analysis (all categories + performance)")
    print("3. Manual: Quick comparison (single query)")
    print("4. Manual: Node distance comprehensive testing")
    print("5. Manual: Single strategy test")
    print("6. Manual: Performance benchmark")
    print("7. Compare: LLM vs Manual Strategies")
    
    # Auto-select option 1 for LLM testing
    choice = "1"
    print(f"\nAuto-selecting choice: {choice}")
    
    if choice == "1":
        # NEW: LLM-Powered intelligent strategy selection
        llm_results, llm_performance = await test_llm_strategy_selection()
        
        # Save LLM results
        await save_results_to_json(
            llm_results, 
            llm_performance, 
            filename="llm_reranking_analysis.json"
        )
        
        print(f"\n\n{'='*80}")
        print(f"LLM STRATEGY SELECTION SUMMARY")
        print(f"{'='*80}")
        print("\nThe LLM intelligently selected search strategies based on:")
        print("  - Query intent (learning, implementation, debugging, exploration)")
        print("  - Query complexity (specific vs vague)")
        print("  - Context (conversation type, current file)")
        print("\nResults saved to: llm_reranking_analysis.json")
        
    elif choice == "2":
        # Comprehensive analysis
        all_results, performance_summary = await comprehensive_strategy_comparison()
        
        # Generate and display recommendations
        recommendations = await generate_recommendations(performance_summary)
        
        print(f"\n\n{'='*80}")
        print(f"STRATEGY RECOMMENDATIONS")
        print(f"{'='*80}")
        
        print(f"\n{recommendations.get('fastest', 'N/A')}")
        print(f"{recommendations.get('most_consistent', 'N/A')}")
        
        print(f"\nGeneral Guidelines:")
        for rec in recommendations.get('general', []):
            print(f"  - {rec}")
        
        # Save results
        await save_results_to_json(all_results, performance_summary)
        
    elif choice == "3":
        # Quick comparison with single query
        query = "async await refactoring database"
        print(f"\nQuick comparison with query: '{query}'")
        
        strategies = list(search_config.get_available_strategies().keys())
        strategies = [s for s in strategies if s != "node_distance"]
        
        results_by_strategy = {}
        for strategy in strategies:
            result = await test_single_strategy_with_timing(query, strategy)
            results_by_strategy[strategy] = result
            await asyncio.sleep(0.2)
        
        # Quick analysis
        diversity = calculate_result_diversity(results_by_strategy)
        performance = analyze_performance(results_by_strategy)
        
        print(f"\nQuick Analysis:")
        print(f"Diversity: {diversity}")
        print(f"Performance: {performance}")
        
    elif choice == "4":
        # Node distance comprehensive testing
        await test_node_distance_comprehensive()
        
    elif choice == "5":
        # Single strategy test
        strategies = list(search_config.get_available_strategies().keys())
        print(f"\nAvailable strategies:")
        for i, s in enumerate(strategies, 1):
            print(f"  {i}. {s}")
        
        # Auto-select RRF for demo
        strategy_choice = "1"
        try:
            strategy = strategies[int(strategy_choice) - 1]
            query = "async await refactoring"
            await test_single_strategy_with_timing(query, strategy)
        except (IndexError, ValueError):
            print("Invalid choice")
            
    elif choice == "6":
        # Performance benchmark
        print("\nPerformance Benchmark...")
        query = "async await refactoring database"
        strategies = list(search_config.get_available_strategies().keys())
        strategies = [s for s in strategies if s != "node_distance"]
        
        benchmark_results = {}
        for strategy in strategies:
            times = []
            for _ in range(3):  # Run 3 times for average
                result = await test_single_strategy_with_timing(query, strategy, limit=5)
                times.append(result.get("timing", {}).get("search_time", 0))
                await asyncio.sleep(0.1)
            
            avg_time = sum(times) / len(times)
            benchmark_results[strategy] = avg_time
            print(f"{strategy}: {avg_time:.3f}s average")
        
        fastest = min(benchmark_results.items(), key=lambda x: x[1])
        print(f"\nFastest: {fastest[0]} ({fastest[1]:.3f}s)")
        
    elif choice == "7":
        # Compare LLM vs Manual
        print(f"\n{'='*80}")
        print(f"LLM vs MANUAL STRATEGY COMPARISON")
        print(f"{'='*80}")
        
        # Run LLM test
        print("\nPhase 1: Running LLM-powered selection...")
        llm_results, llm_performance = await test_llm_strategy_selection()
        
        # Run manual test
        print("\nPhase 2: Running manual all-strategy test...")
        manual_results, manual_performance = await comprehensive_strategy_comparison()
        
        # Compare
        print(f"\n\n{'='*80}")
        print(f"COMPARISON SUMMARY")
        print(f"{'='*80}")
        
        print("\nLLM selected strategies intelligently based on query type")
        print("Manual tested ALL strategies for every query")
        
        # Save both
        await save_results_to_json(llm_results, llm_performance, "llm_reranking_analysis.json")
        await save_results_to_json(manual_results, manual_performance, "manual_reranking_analysis.json")
        
    else:
        print("Invalid choice, running LLM-powered analysis")
        llm_results, llm_performance = await test_llm_strategy_selection()
        await save_results_to_json(llm_results, llm_performance, "llm_reranking_analysis.json")


if __name__ == "__main__":
    asyncio.run(main())

