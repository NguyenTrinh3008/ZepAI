# tests/conftest.py
"""
Pytest configuration for test suite
"""

import sys
from pathlib import Path

# Add parent directory to Python path so tests can import app module
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
