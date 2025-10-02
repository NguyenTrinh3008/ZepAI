#!/usr/bin/env python
"""
Analyze search test results

Usage:
    python analyze_search_results.py
    python analyze_search_results.py --verbose
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def load_results():
    """Load search test results"""
    results_file = Path("search_test_results.json")
    
    if not results_file.exists():
        print(f"❌ Error: {results_file} not found")
        print("💡 Run search tests first: python tests/test_search_capabilities.py")
        sys.exit(1)
    
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_summary(results):
    """Print summary"""
    summary = results['summary']
    
    print("\n" + "="*80)
    print("SEARCH TEST RESULTS ANALYSIS")
    print("="*80)
    
    print(f"\n📊 Overall Results:")
    print(f"   Total tests: {summary['total']}")
    print(f"   ✅ Passed: {summary['passed']}")
    print(f"   ❌ Failed: {summary['failed']}")
    
    if summary['total'] > 0:
        pass_rate = (summary['passed'] / summary['total']) * 100
        print(f"   📈 Pass rate: {pass_rate:.1f}%")
    
    print(f"\n📁 By Category:")
    for category, stats in summary['by_category'].items():
        pass_rate = (stats['passed'] / stats['total']) * 100 if stats['total'] > 0 else 0
        status = "✅" if stats['failed'] == 0 else "⚠️"
        print(f"   {status} {category}: {stats['passed']}/{stats['total']} ({pass_rate:.0f}%)")


def print_search_performance(results):
    """Print search performance stats"""
    test_cases = results['test_cases']
    
    durations = [tc['duration_ms'] for tc in test_cases if tc['duration_ms'] > 0]
    
    if not durations:
        return
    
    print(f"\n⏱️  Search Performance:")
    print(f"   Average: {sum(durations)/len(durations):.0f}ms")
    print(f"   Min: {min(durations)}ms")
    print(f"   Max: {max(durations)}ms")
    print(f"   P95: {sorted(durations)[int(len(durations)*0.95)]}ms")
    
    # Performance categories
    fast = sum(1 for d in durations if d < 100)
    medium = sum(1 for d in durations if 100 <= d < 500)
    slow = sum(1 for d in durations if d >= 500)
    
    print(f"\n   Distribution:")
    print(f"   ⚡ Fast (<100ms): {fast} tests")
    print(f"   🔄 Medium (100-500ms): {medium} tests")
    print(f"   🐌 Slow (>500ms): {slow} tests")


def print_metadata_quality(results):
    """Analyze metadata completeness"""
    test_cases = results['test_cases']
    
    # Get tests that check metadata
    metadata_tests = [tc for tc in test_cases if tc['metadata_score'] > 0]
    
    if not metadata_tests:
        return
    
    print(f"\n🎯 Metadata Quality:")
    avg_score = sum(tc['metadata_score'] for tc in metadata_tests) / len(metadata_tests)
    print(f"   Average completeness: {avg_score*100:.1f}%")
    
    excellent = sum(1 for tc in metadata_tests if tc['metadata_score'] >= 0.9)
    good = sum(1 for tc in metadata_tests if 0.7 <= tc['metadata_score'] < 0.9)
    poor = sum(1 for tc in metadata_tests if tc['metadata_score'] < 0.7)
    
    print(f"\n   Distribution:")
    print(f"   ✨ Excellent (>90%): {excellent} tests")
    print(f"   ✅ Good (70-90%): {good} tests")
    print(f"   ⚠️  Poor (<70%): {poor} tests")


def print_search_accuracy(results):
    """Analyze search result accuracy"""
    test_cases = results['test_cases']
    
    print(f"\n🔍 Search Accuracy:")
    
    # Filter by category
    by_category = defaultdict(list)
    for tc in test_cases:
        by_category[tc['category']].append(tc)
    
    for category, tests in sorted(by_category.items()):
        passed = sum(1 for t in tests if t['passed'])
        total = len(tests)
        accuracy = (passed / total * 100) if total > 0 else 0
        
        status = "✅" if accuracy == 100 else "⚠️" if accuracy >= 80 else "❌"
        print(f"   {status} {category}: {accuracy:.0f}% ({passed}/{total})")


def print_result_counts(results):
    """Analyze result counts"""
    test_cases = results['test_cases']
    
    print(f"\n📊 Result Counts:")
    
    total_results = sum(tc['actual_count'] for tc in test_cases)
    avg_results = total_results / len(test_cases) if test_cases else 0
    
    print(f"   Total results returned: {total_results}")
    print(f"   Average per query: {avg_results:.1f}")
    
    # Distribution
    no_results = sum(1 for tc in test_cases if tc['actual_count'] == 0)
    few_results = sum(1 for tc in test_cases if 1 <= tc['actual_count'] <= 3)
    many_results = sum(1 for tc in test_cases if tc['actual_count'] > 3)
    
    print(f"\n   Distribution:")
    print(f"   ❌ No results: {no_results} queries")
    print(f"   ✅ Few results (1-3): {few_results} queries")
    print(f"   📚 Many results (>3): {many_results} queries")


def print_failures(results):
    """Print failed tests"""
    failed_tests = [tc for tc in results['test_cases'] if not tc['passed']]
    
    if not failed_tests:
        print("\n✨ No failures!")
        return
    
    print(f"\n❌ Failed Tests ({len(failed_tests)}):")
    print("-" * 80)
    
    for tc in failed_tests:
        print(f"\n   Test: {tc['name']}")
        print(f"   Category: {tc['category']}")
        print(f"   Query: {tc['query']}")
        print(f"   Expected: {tc['expectations']}")
        print(f"   Actual count: {tc['actual_count']}")
        
        if tc['error']:
            print(f"   Error: {tc['error']}")


def print_filter_effectiveness(results):
    """Analyze filter effectiveness"""
    test_cases = results['test_cases']
    
    print(f"\n🎛️  Filter Effectiveness:")
    
    # Project isolation
    project_tests = [tc for tc in test_cases if 'Project Isolation' in tc['category']]
    project_passed = sum(1 for tc in project_tests if tc['passed'])
    print(f"   Project Isolation: {project_passed}/{len(project_tests)} passed")
    
    # File filtering
    file_tests = [tc for tc in test_cases if 'File Filtering' in tc['category']]
    file_passed = sum(1 for tc in file_tests if tc['passed'])
    print(f"   File Filtering: {file_passed}/{len(file_tests)} passed")
    
    # Time filtering
    time_tests = [tc for tc in test_cases if 'Time Filtering' in tc['category']]
    time_passed = sum(1 for tc in time_tests if tc['passed'])
    print(f"   Time Filtering: {time_passed}/{len(time_tests)} passed")
    
    # Combined filters
    combined_tests = [tc for tc in test_cases if 'Combined' in tc['category']]
    combined_passed = sum(1 for tc in combined_tests if tc['passed'])
    print(f"   Combined Filters: {combined_passed}/{len(combined_tests)} passed")


def export_csv(results):
    """Export to CSV"""
    import csv
    
    csv_file = Path("search_test_results.csv")
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Category', 'Test Name', 'Status', 'Duration (ms)',
            'Results Found', 'Metadata Score', 'Query'
        ])
        
        for tc in results['test_cases']:
            status = 'PASS' if tc['passed'] else 'FAIL'
            query_str = tc['query'].get('query', '')
            
            writer.writerow([
                tc['category'],
                tc['name'],
                status,
                tc['duration_ms'],
                tc['actual_count'],
                f"{tc['metadata_score']*100:.0f}%",
                query_str[:50]
            ])
    
    print(f"\n📊 CSV exported to: {csv_file}")


def print_verbose(results):
    """Print verbose details"""
    print(f"\n📋 Detailed Results:")
    print("="*80)
    
    for idx, tc in enumerate(results['test_cases'], 1):
        status = "✅" if tc['passed'] else "❌"
        
        print(f"\n[{idx}] {status} {tc['name']}")
        print(f"    Category: {tc['category']}")
        print(f"    Duration: {tc['duration_ms']}ms")
        print(f"    Query: {tc['query']}")
        print(f"    Results found: {tc['actual_count']}")
        
        if tc['metadata_score'] > 0:
            print(f"    Metadata score: {tc['metadata_score']*100:.0f}%")
        
        if tc['result'] and tc['result'].get('results'):
            print(f"    Top result: {tc['result']['results'][0].get('text', '')[:60]}...")


def main():
    """Main entry point"""
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    # Load results
    results = load_results()
    
    # Print timestamp
    print(f"\n🕐 Test Run: {results['timestamp']}")
    
    # Print analysis
    print_summary(results)
    print_search_performance(results)
    print_metadata_quality(results)
    print_search_accuracy(results)
    print_result_counts(results)
    print_filter_effectiveness(results)
    print_failures(results)
    
    # Export CSV
    export_csv(results)
    
    # Verbose mode
    if verbose:
        print_verbose(results)
    
    # Final message
    print("\n" + "="*80)
    if results['summary']['failed'] == 0:
        print("🎉 All search tests passed!")
    else:
        print(f"⚠️  {results['summary']['failed']} search test(s) need attention")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
