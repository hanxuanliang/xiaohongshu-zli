"""Integration smoke tests — require a valid login session.

These tests are marked with @pytest.mark.integration and are SKIPPED
by default. Run them explicitly with:

    uv run pytest tests/ -v -m integration

They verify end-to-end CLI functionality against the real
Xiaohongshu website.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

# Skip all tests in this module unless --run-integration is passed
pytestmark = pytest.mark.integration


def _run_xhs(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run an xhs CLI command and return the result."""
    cmd = [sys.executable, "-m", "xhs_cli.cli"] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=None,
    )


class TestIntegrationStatus:
    def test_status(self):
        result = _run_xhs("status")
        assert result.returncode == 0
        assert "Logged in" in result.stdout

    def test_whoami_json(self):
        result = _run_xhs("whoami", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)


class TestIntegrationSearch:
    def test_search(self):
        result = _run_xhs("search", "咖啡")
        assert result.returncode == 0

    def test_search_json(self):
        result = _run_xhs("search", "咖啡", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestIntegrationFeed:
    def test_feed(self):
        result = _run_xhs("feed")
        assert result.returncode == 0

    def test_feed_json(self):
        result = _run_xhs("feed", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestIntegrationFavorites:
    def test_favorites(self):
        result = _run_xhs("favorites", "--max", "3")
        assert result.returncode == 0
