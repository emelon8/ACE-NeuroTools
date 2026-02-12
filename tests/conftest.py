"""
Shared fixtures and configuration for integration tests.

Sets PROJECT_REPO to the example_project to avoid requiring a .env file
during testing.
"""

import os
from pathlib import Path

# Set PROJECT_REPO to the example project for all tests
# This must happen before any imports from src2.shared.paths
EXAMPLE_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "example_project"
os.environ.setdefault("PROJECT_REPO", str(EXAMPLE_PROJECT))
