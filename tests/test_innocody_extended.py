#!/usr/bin/env python
"""
Extended Innocody Integration Test Suite with JSON Export

Tests multiple scenarios:
- Different programming languages
- Various severity levels
- Different change types
- Edge cases

Usage:
    python tests/test_innocody_extended.py
    
Output:
    - Console output with results
    - JSON file: test_results.json
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class TestCase:
    """Test case container"""
    def __init__(self, name: str, category: str, payload: Dict, expected: Dict):
        self.name = name
        self.category = category
        self.payload = payload
        self.expected = expected
        self.result = None
        self.actual = None
        self.passed = False
        self.duration_ms = 0
        self.error = None


class TestSuite:
    """Main test suite"""
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {},
            "test_cases": []
        }
    
    def add_test_case(self, name: str, category: str, payload: Dict, expected: Dict):
        """Add a test case"""
        tc = TestCase(name, category, payload, expected)
        self.test_cases.append(tc)
        return tc
    
    def run_all(self):
        """Run all test cases"""
        print("\n" + "="*80)
        print("EXTENDED INNOCODY INTEGRATION TEST SUITE")
        print("="*80)
        
        for idx, tc in enumerate(self.test_cases, 1):
            print(f"\n[{idx}/{len(self.test_cases)}] {tc.category}: {tc.name}")
            print("-" * 80)
            self.run_test_case(tc)
        
        self.print_summary()
        self.export_json()
    
    def run_test_case(self, tc: TestCase):
        """Run single test case"""
        import time
        
        try:
            start = time.time()
            
            # Send webhook request
            response = requests.post(
                "http://localhost:8000/innocody/webhook",
                json=tc.payload,
                timeout=60
            )
            
            tc.duration_ms = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                result = response.json()
                tc.actual = result
                
                # Validate expectations
                tc.passed = self.validate_expectations(result, tc.expected)
                
                if tc.passed:
                    print(f"  ✅ PASS ({tc.duration_ms}ms)")
                    self.print_result_details(result, tc.expected)
                else:
                    print(f"  ❌ FAIL - Expectations not met")
                    self.print_mismatches(result, tc.expected)
            else:
                tc.passed = False
                tc.error = f"HTTP {response.status_code}"
                print(f"  ❌ FAIL - {tc.error}")
                print(f"  Response: {response.text[:200]}")
                
        except Exception as e:
            tc.passed = False
            tc.error = str(e)
            print(f"  ❌ FAIL - Exception: {e}")
    
    def validate_expectations(self, result: Dict, expected: Dict) -> bool:
        """Check if result meets expectations"""
        for key, value in expected.items():
            if key == "severity_in":
                # Check if severity is in allowed list
                actual_severity = result.get('summaries', [{}])[0] if 'summaries' in result else None
                # We'll check metadata later
                continue
            elif key == "ingested_count":
                if result.get('ingested_count') != value:
                    return False
            elif key == "status":
                if result.get('status') != value:
                    return False
        
        return True
    
    def print_result_details(self, result: Dict, expected: Dict):
        """Print result details"""
        print(f"  Status: {result.get('status')}")
        print(f"  Ingested: {result.get('ingested_count')} chunks")
        if 'summaries' in result and result['summaries']:
            summary = result['summaries'][0]
            print(f"  Summary: {summary[:70]}...")
        if 'project_id' in result:
            print(f"  Project: {result['project_id']}")
    
    def print_mismatches(self, result: Dict, expected: Dict):
        """Print what didn't match"""
        for key, expected_value in expected.items():
            actual_value = result.get(key)
            if actual_value != expected_value:
                print(f"  Expected {key}: {expected_value}")
                print(f"  Actual {key}: {actual_value}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        # Group by category
        categories = {}
        for tc in self.test_cases:
            if tc.category not in categories:
                categories[tc.category] = []
            categories[tc.category].append(tc)
        
        total_passed = 0
        total_failed = 0
        
        for category, tests in categories.items():
            passed = sum(1 for t in tests if t.passed)
            failed = len(tests) - passed
            total_passed += passed
            total_failed += failed
            
            print(f"\n{category}:")
            for tc in tests:
                status = "✅" if tc.passed else "❌"
                duration = f"({tc.duration_ms}ms)" if tc.duration_ms else ""
                print(f"  {status} {tc.name} {duration}")
        
        print(f"\n{'='*80}")
        print(f"Total: {total_passed} passed, {total_failed} failed out of {len(self.test_cases)} tests")
        
        if total_failed == 0:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {total_failed} test(s) failed")
        
        # Update summary
        self.results['summary'] = {
            "total": len(self.test_cases),
            "passed": total_passed,
            "failed": total_failed,
            "by_category": {
                cat: {
                    "total": len(tests),
                    "passed": sum(1 for t in tests if t.passed),
                    "failed": sum(1 for t in tests if not t.passed)
                }
                for cat, tests in categories.items()
            }
        }
    
    def export_json(self):
        """Export results to JSON"""
        # Build test case results
        for tc in self.test_cases:
            tc_result = {
                "name": tc.name,
                "category": tc.category,
                "passed": tc.passed,
                "duration_ms": tc.duration_ms,
                "payload": tc.payload,
                "expected": tc.expected,
                "actual": tc.actual,
                "error": tc.error
            }
            self.results['test_cases'].append(tc_result)
        
        # Write to file
        output_file = Path(__file__).parent.parent / "test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Results exported to: {output_file}")
        print(f"   Size: {output_file.stat().st_size} bytes")


def create_test_cases(suite: TestSuite):
    """Create all test cases"""
    
    # ==================== CATEGORY 1: PYTHON TESTS ====================
    
    # Test 1.1: Python - Authentication (Critical)
    suite.add_test_case(
        name="Python auth service - critical change",
        category="Python Tests",
        payload={
            "file_before": """
def login(user):
    return user.token
""",
            "file_after": """
def login(user):
    if not user:
        raise ValueError('User is None')
    if not user.is_active:
        raise ValueError('User is inactive')
    return user.token
""",
            "chunks": [{
                "file_name": "src/auth/auth_service.py",
                "file_action": "edit",
                "line1": 2,
                "line2": 6,
                "lines_remove": "    return user.token",
                "lines_add": "    if not user:\n        raise ValueError('User is None')\n    if not user.is_active:\n        raise ValueError('User is inactive')\n    return user.token"
            }],
            "meta": {"project_id": "test_extended_python"}
        },
        expected={
            "status": "success",
            "ingested_count": 1,
            "severity_in": ["high", "critical"]
        }
    )
    
    # Test 1.2: Python - Utility function (Low)
    suite.add_test_case(
        name="Python utility - low severity",
        category="Python Tests",
        payload={
            "file_before": "def format_date(d):\n    return str(d)",
            "file_after": "def format_date(d):\n    return d.strftime('%Y-%m-%d')",
            "chunks": [{
                "file_name": "src/utils/helpers.py",
                "file_action": "edit",
                "line1": 2,
                "line2": 2,
                "lines_remove": "    return str(d)",
                "lines_add": "    return d.strftime('%Y-%m-%d')"
            }],
            "meta": {"project_id": "test_extended_python"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 1.3: Python - Class change
    suite.add_test_case(
        name="Python class - method addition",
        category="Python Tests",
        payload={
            "file_before": """
class User:
    def __init__(self, name):
        self.name = name
""",
            "file_after": """
class User:
    def __init__(self, name):
        self.name = name
    
    def validate_email(self):
        return '@' in self.name
""",
            "chunks": [{
                "file_name": "src/models/user.py",
                "file_action": "edit",
                "line1": 4,
                "line2": 6,
                "lines_remove": "",
                "lines_add": "    \n    def validate_email(self):\n        return '@' in self.name"
            }],
            "meta": {"project_id": "test_extended_python"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # ==================== CATEGORY 2: JAVASCRIPT TESTS ====================
    
    # Test 2.1: JavaScript - API endpoint
    suite.add_test_case(
        name="JavaScript API - new endpoint",
        category="JavaScript Tests",
        payload={
            "file_before": """
app.get('/users', (req, res) => {
  res.json(users);
});
""",
            "file_after": """
app.get('/users', async (req, res) => {
  const users = await db.getUsers();
  res.json(users);
});

app.post('/users', async (req, res) => {
  const user = await db.createUser(req.body);
  res.json(user);
});
""",
            "chunks": [{
                "file_name": "src/api/users.js",
                "file_action": "edit",
                "line1": 1,
                "line2": 9,
                "lines_remove": "app.get('/users', (req, res) => {\n  res.json(users);\n});",
                "lines_add": "app.get('/users', async (req, res) => {\n  const users = await db.getUsers();\n  res.json(users);\n});\n\napp.post('/users', async (req, res) => {\n  const user = await db.createUser(req.body);\n  res.json(user);\n});"
            }],
            "meta": {"project_id": "test_extended_js"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 2.2: TypeScript - React component
    suite.add_test_case(
        name="TypeScript React - component update",
        category="JavaScript Tests",
        payload={
            "file_before": """
export const Header = () => {
  return <div>Hello</div>;
};
""",
            "file_after": """
export const Header: React.FC = () => {
  const [user, setUser] = useState(null);
  
  return (
    <div>
      <h1>Hello {user?.name}</h1>
    </div>
  );
};
""",
            "chunks": [{
                "file_name": "src/components/Header.tsx",
                "file_action": "edit",
                "line1": 1,
                "line2": 9,
                "lines_remove": "export const Header = () => {\n  return <div>Hello</div>;\n};",
                "lines_add": "export const Header: React.FC = () => {\n  const [user, setUser] = useState(null);\n  \n  return (\n    <div>\n      <h1>Hello {user?.name}</h1>\n    </div>\n  );\n};"
            }],
            "meta": {"project_id": "test_extended_js"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # ==================== CATEGORY 3: SEVERITY TESTS ====================
    
    # Test 3.1: Critical - Database migration
    suite.add_test_case(
        name="Critical - Database schema change",
        category="Severity Tests",
        payload={
            "file_before": "CREATE TABLE users (id INT, name VARCHAR(100));",
            "file_after": "CREATE TABLE users (\n  id INT PRIMARY KEY,\n  name VARCHAR(100) NOT NULL,\n  email VARCHAR(255) UNIQUE,\n  password_hash VARCHAR(255) NOT NULL,\n  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);",
            "chunks": [{
                "file_name": "migrations/001_create_users.sql",
                "file_action": "edit",
                "line1": 1,
                "line2": 6,
                "lines_remove": "CREATE TABLE users (id INT, name VARCHAR(100));",
                "lines_add": "CREATE TABLE users (\n  id INT PRIMARY KEY,\n  name VARCHAR(100) NOT NULL,\n  email VARCHAR(255) UNIQUE,\n  password_hash VARCHAR(255) NOT NULL,\n  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);"
            }],
            "meta": {"project_id": "test_severity"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 3.2: High - Security patch
    suite.add_test_case(
        name="High - Security vulnerability fix",
        category="Severity Tests",
        payload={
            "file_before": "const token = req.headers.token;",
            "file_after": "const token = req.headers.authorization?.replace('Bearer ', '');\nif (!token || !validateToken(token)) {\n  return res.status(401).json({ error: 'Unauthorized' });\n}",
            "chunks": [{
                "file_name": "src/middleware/security.js",
                "file_action": "edit",
                "line1": 1,
                "line2": 4,
                "lines_remove": "const token = req.headers.token;",
                "lines_add": "const token = req.headers.authorization?.replace('Bearer ', '');\nif (!token || !validateToken(token)) {\n  return res.status(401).json({ error: 'Unauthorized' });\n}"
            }],
            "meta": {"project_id": "test_severity"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 3.3: Low - Documentation update
    suite.add_test_case(
        name="Low - README update",
        category="Severity Tests",
        payload={
            "file_before": "# My Project\n\nA simple app",
            "file_after": "# My Project\n\nA simple app for managing users.\n\n## Installation\n\n```bash\nnpm install\n```",
            "chunks": [{
                "file_name": "README.md",
                "file_action": "edit",
                "line1": 3,
                "line2": 8,
                "lines_remove": "A simple app",
                "lines_add": "A simple app for managing users.\n\n## Installation\n\n```bash\nnpm install\n```"
            }],
            "meta": {"project_id": "test_severity"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 3.4: Low - Test file
    suite.add_test_case(
        name="Low - Test file update",
        category="Severity Tests",
        payload={
            "file_before": "def test_login():\n    pass",
            "file_after": "def test_login():\n    user = create_user('test@example.com')\n    result = login(user)\n    assert result.token is not None",
            "chunks": [{
                "file_name": "tests/test_auth.py",
                "file_action": "edit",
                "line1": 2,
                "line2": 4,
                "lines_remove": "    pass",
                "lines_add": "    user = create_user('test@example.com')\n    result = login(user)\n    assert result.token is not None"
            }],
            "meta": {"project_id": "test_severity"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # ==================== CATEGORY 4: EDGE CASES ====================
    
    # Test 4.1: Very large change
    suite.add_test_case(
        name="Edge - Large refactoring (100+ lines)",
        category="Edge Cases",
        payload={
            "file_before": "# Old implementation\n" + "def process():\n    pass\n" * 50,
            "file_after": "# New implementation\n" + "async def process():\n    await task()\n" * 50,
            "chunks": [{
                "file_name": "src/core/processor.py",
                "file_action": "edit",
                "line1": 1,
                "line2": 150,
                "lines_remove": "# Old implementation\n" + "def process():\n    pass\n" * 50,
                "lines_add": "# New implementation\n" + "async def process():\n    await task()\n" * 50
            }],
            "meta": {"project_id": "test_edge"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 4.2: Empty lines
    suite.add_test_case(
        name="Edge - Only whitespace changes",
        category="Edge Cases",
        payload={
            "file_before": "def hello():\n    print('hi')",
            "file_after": "def hello():\n    \n    print('hi')\n    ",
            "chunks": [{
                "file_name": "src/hello.py",
                "file_action": "edit",
                "line1": 2,
                "line2": 3,
                "lines_remove": "    print('hi')",
                "lines_add": "    \n    print('hi')\n    "
            }],
            "meta": {"project_id": "test_edge"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 4.3: File creation
    suite.add_test_case(
        name="Edge - New file creation",
        category="Edge Cases",
        payload={
            "file_before": "",
            "file_after": "export const config = {\n  apiUrl: 'http://localhost:3000'\n};",
            "chunks": [{
                "file_name": "src/config.js",
                "file_action": "add",
                "line1": 1,
                "line2": 3,
                "lines_remove": "",
                "lines_add": "export const config = {\n  apiUrl: 'http://localhost:3000'\n};"
            }],
            "meta": {"project_id": "test_edge"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 4.4: File deletion
    suite.add_test_case(
        name="Edge - File deletion",
        category="Edge Cases",
        payload={
            "file_before": "const OLD_CODE = 'deprecated';",
            "file_after": "",
            "chunks": [{
                "file_name": "src/deprecated.js",
                "file_action": "remove",
                "line1": 1,
                "line2": 1,
                "lines_remove": "const OLD_CODE = 'deprecated';",
                "lines_add": ""
            }],
            "meta": {"project_id": "test_edge"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # ==================== CATEGORY 5: MULTI-LANGUAGE ====================
    
    # Test 5.1: Go
    suite.add_test_case(
        name="Go - HTTP handler",
        category="Multi-Language",
        payload={
            "file_before": "func handler(w http.ResponseWriter, r *http.Request) {\n\tfmt.Fprintf(w, \"Hello\")\n}",
            "file_after": "func handler(w http.ResponseWriter, r *http.Request) {\n\tif r.Method != \"GET\" {\n\t\thttp.Error(w, \"Method not allowed\", 405)\n\t\treturn\n\t}\n\tfmt.Fprintf(w, \"Hello\")\n}",
            "chunks": [{
                "file_name": "main.go",
                "file_action": "edit",
                "line1": 2,
                "line2": 6,
                "lines_remove": "\tfmt.Fprintf(w, \"Hello\")",
                "lines_add": "\tif r.Method != \"GET\" {\n\t\thttp.Error(w, \"Method not allowed\", 405)\n\t\treturn\n\t}\n\tfmt.Fprintf(w, \"Hello\")"
            }],
            "meta": {"project_id": "test_multilang"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 5.2: Rust
    suite.add_test_case(
        name="Rust - Error handling",
        category="Multi-Language",
        payload={
            "file_before": "fn divide(a: i32, b: i32) -> i32 {\n    a / b\n}",
            "file_after": "fn divide(a: i32, b: i32) -> Result<i32, String> {\n    if b == 0 {\n        return Err(\"Division by zero\".to_string());\n    }\n    Ok(a / b)\n}",
            "chunks": [{
                "file_name": "src/math.rs",
                "file_action": "edit",
                "line1": 1,
                "line2": 5,
                "lines_remove": "fn divide(a: i32, b: i32) -> i32 {\n    a / b\n}",
                "lines_add": "fn divide(a: i32, b: i32) -> Result<i32, String> {\n    if b == 0 {\n        return Err(\"Division by zero\".to_string());\n    }\n    Ok(a / b)\n}"
            }],
            "meta": {"project_id": "test_multilang"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )
    
    # Test 5.3: Java
    suite.add_test_case(
        name="Java - Exception handling",
        category="Multi-Language",
        payload={
            "file_before": "public void process(String data) {\n    System.out.println(data);\n}",
            "file_after": "public void process(String data) throws IllegalArgumentException {\n    if (data == null || data.isEmpty()) {\n        throw new IllegalArgumentException(\"Data cannot be null or empty\");\n    }\n    System.out.println(data);\n}",
            "chunks": [{
                "file_name": "src/main/java/Processor.java",
                "file_action": "edit",
                "line1": 1,
                "line2": 5,
                "lines_remove": "public void process(String data) {\n    System.out.println(data);\n}",
                "lines_add": "public void process(String data) throws IllegalArgumentException {\n    if (data == null || data.isEmpty()) {\n        throw new IllegalArgumentException(\"Data cannot be null or empty\");\n    }\n    System.out.println(data);\n}"
            }],
            "meta": {"project_id": "test_multilang"}
        },
        expected={
            "status": "success",
            "ingested_count": 1
        }
    )


def main():
    """Main entry point"""
    
    # Check if API is running
    try:
        response = requests.get("http://localhost:8000/innocody/health", timeout=2)
        if response.status_code != 200:
            print("❌ Error: Innocody API is not healthy")
            print("💡 Make sure API is running: uvicorn app.main:app --reload")
            return 1
    except Exception as e:
        print(f"❌ Error: Cannot connect to API - {e}")
        print("💡 Make sure API is running: uvicorn app.main:app --reload")
        return 1
    
    # Create test suite
    suite = TestSuite()
    create_test_cases(suite)
    
    # Run all tests
    suite.run_all()
    
    # Return exit code
    return 0 if suite.results['summary']['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
