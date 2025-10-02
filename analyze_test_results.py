#!/usr/bin/env python
"""
Analyze test results from JSON output

Usage:
    python analyze_test_results.py
    python analyze_test_results.py --verbose
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


def load_results() -> Dict:
    """Load test results from JSON"""
    results_file = Path("test_results.json")
    
    if not results_file.exists():
        print(f"❌ Error: {results_file} not found")
        print("💡 Run tests first: python tests/test_innocody_extended.py")
        sys.exit(1)
    
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_summary(results: Dict):
    """Print high-level summary"""
    summary = results['summary']
    
    print("\n" + "="*80)
    print("TEST RESULTS ANALYSIS")
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


def print_performance_stats(results: Dict):
    """Print performance statistics"""
    test_cases = results['test_cases']
    
    durations = [tc['duration_ms'] for tc in test_cases if tc['duration_ms'] > 0]
    
    if not durations:
        return
    
    print(f"\n⏱️  Performance Stats:")
    print(f"   Average: {sum(durations)/len(durations):.0f}ms")
    print(f"   Min: {min(durations)}ms")
    print(f"   Max: {max(durations)}ms")
    print(f"   Total: {sum(durations)/1000:.1f}s")


def print_failures(results: Dict):
    """Print failed test details"""
    failed_tests = [tc for tc in results['test_cases'] if not tc['passed']]
    
    if not failed_tests:
        print("\n✨ No failures!")
        return
    
    print(f"\n❌ Failed Tests ({len(failed_tests)}):")
    print("-" * 80)
    
    for tc in failed_tests:
        print(f"\n   Test: {tc['name']}")
        print(f"   Category: {tc['category']}")
        
        if tc['error']:
            print(f"   Error: {tc['error']}")
        
        if tc['expected'] and tc['actual']:
            print(f"   Expected: {tc['expected']}")
            print(f"   Actual: {tc['actual']}")


def print_severity_distribution(results: Dict):
    """Analyze severity distribution from summaries"""
    print(f"\n🎯 Severity Distribution (from LLM summaries):")
    
    # This would require parsing summaries or metadata
    # For now, show file type distribution
    file_types = defaultdict(int)
    
    for tc in results['test_cases']:
        if tc['payload'].get('chunks'):
            file_name = tc['payload']['chunks'][0].get('file_name', '')
            if '.' in file_name:
                ext = file_name.split('.')[-1]
                file_types[ext] += 1
    
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   .{ext}: {count} tests")


def print_language_distribution(results: Dict):
    """Show language distribution"""
    print(f"\n🌍 Language Distribution:")
    
    languages = defaultdict(int)
    
    for tc in results['test_cases']:
        if tc['payload'].get('chunks'):
            file_name = tc['payload']['chunks'][0].get('file_name', '')
            
            # Map extensions to languages
            ext_to_lang = {
                'py': 'Python',
                'js': 'JavaScript',
                'ts': 'TypeScript',
                'tsx': 'TypeScript/React',
                'go': 'Go',
                'rs': 'Rust',
                'java': 'Java',
                'sql': 'SQL',
                'md': 'Markdown'
            }
            
            if '.' in file_name:
                ext = file_name.split('.')[-1]
                lang = ext_to_lang.get(ext, f'Other ({ext})')
                languages[lang] += 1
    
    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
        print(f"   {lang}: {count} tests")


def print_change_size_stats(results: Dict):
    """Analyze change size distribution"""
    print(f"\n📏 Change Size Stats:")
    
    small = 0  # < 10 lines
    medium = 0  # 10-50 lines
    large = 0  # > 50 lines
    
    for tc in results['test_cases']:
        if tc['payload'].get('chunks'):
            chunk = tc['payload']['chunks'][0]
            lines_add = len(chunk.get('lines_add', '').splitlines())
            lines_remove = len(chunk.get('lines_remove', '').splitlines())
            total = lines_add + lines_remove
            
            if total < 10:
                small += 1
            elif total < 50:
                medium += 1
            else:
                large += 1
    
    total = small + medium + large
    if total > 0:
        print(f"   Small (<10 lines): {small} ({small/total*100:.0f}%)")
        print(f"   Medium (10-50 lines): {medium} ({medium/total*100:.0f}%)")
        print(f"   Large (>50 lines): {large} ({large/total*100:.0f}%)")


def export_summary_csv(results: Dict):
    """Export summary to CSV"""
    import csv
    
    csv_file = Path("test_results_summary.csv")
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Category', 'Test Name', 'Status', 'Duration (ms)', 'File', 'Language'])
        
        for tc in results['test_cases']:
            status = 'PASS' if tc['passed'] else 'FAIL'
            file_name = ''
            language = ''
            
            if tc['payload'].get('chunks'):
                file_name = tc['payload']['chunks'][0].get('file_name', '')
                if '.' in file_name:
                    ext = file_name.split('.')[-1]
                    lang_map = {
                        'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
                        'go': 'Go', 'rs': 'Rust', 'java': 'Java'
                    }
                    language = lang_map.get(ext, ext)
            
            writer.writerow([
                tc['category'],
                tc['name'],
                status,
                tc['duration_ms'],
                file_name,
                language
            ])
    
    print(f"\n📊 CSV exported to: {csv_file}")


def print_verbose_details(results: Dict):
    """Print detailed test information"""
    print(f"\n📋 Detailed Test Results:")
    print("="*80)
    
    for idx, tc in enumerate(results['test_cases'], 1):
        status_emoji = "✅" if tc['passed'] else "❌"
        
        print(f"\n[{idx}] {status_emoji} {tc['name']}")
        print(f"    Category: {tc['category']}")
        print(f"    Duration: {tc['duration_ms']}ms")
        
        if tc['payload'].get('chunks'):
            chunk = tc['payload']['chunks'][0]
            print(f"    File: {chunk.get('file_name')}")
            print(f"    Action: {chunk.get('file_action')}")
            
            lines_add = len(chunk.get('lines_add', '').splitlines())
            lines_remove = len(chunk.get('lines_remove', '').splitlines())
            print(f"    Changes: +{lines_add} -{lines_remove}")
        
        if tc['actual']:
            actual = tc['actual']
            if 'summaries' in actual and actual['summaries']:
                summary = actual['summaries'][0]
                print(f"    Summary: {summary[:60]}...")


def main():
    """Main entry point"""
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    # Load results
    results = load_results()
    
    # Print timestamp
    print(f"\n🕐 Test Run: {results['timestamp']}")
    
    # Print analysis
    print_summary(results)
    print_performance_stats(results)
    print_language_distribution(results)
    print_severity_distribution(results)
    print_change_size_stats(results)
    print_failures(results)
    
    # Export CSV
    export_summary_csv(results)
    
    # Verbose mode
    if verbose:
        print_verbose_details(results)
    
    # Final message
    print("\n" + "="*80)
    if results['summary']['failed'] == 0:
        print("🎉 All tests passed successfully!")
    else:
        print(f"⚠️  {results['summary']['failed']} test(s) need attention")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
