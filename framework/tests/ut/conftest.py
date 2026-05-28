"""pytest conftest for ut/ tests: register custom markers."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "delivery: Tests that require delivery-phase state (code changes + git history rewrite).")
