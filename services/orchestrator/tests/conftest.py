"""Tests for Orchestrator service."""

from __future__ import annotations

import os

# Ensure test settings use sqlite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from shared.db.session import engine
from shared.db.models import Base
from services.orchestrator.main import app

@pytest.fixture(autouse=True)
async def setup_test_db():
    """Setup and teardown in-memory SQLite DB for tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def test_client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest.fixture
def review_start_request():
    import uuid
    return {
        "pr_id": str(uuid.uuid4()),
        "repo_full_name": "owner/repo",
        "pr_number": 123,
        "head_sha": "abc123def456",
        "base_sha": "def789abc012",
        "installation_id": 12345,
    }


@pytest.fixture
def mock_github_client():
    with patch("services.orchestrator.routes.GitHubClient") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_pr_diff = AsyncMock(return_value="""diff --git a/file.py b/file.py
+++ b/file.py
@@ -1,1 +1,2 @@
-old
+new
""")
        mock_cls.return_value = mock_instance
        yield mock_instance
        
@pytest.fixture
def mock_get_installation_token():
    with patch("services.orchestrator.routes.get_installation_token", new_callable=AsyncMock) as mock:
        mock.return_value = "fake-token"
        yield mock
        
@pytest.fixture
def mock_review_graph():
    with patch("services.orchestrator.routes.review_graph") as mock:
        mock.ainvoke = AsyncMock(return_value={
            "merged_findings": [
                {
                    "agent": "static",
                    "file_path": "file.py",
                    "line_number": 2,
                    "severity": "warning",
                    "message": "test finding",
                    "suggestion": "fix it"
                }
            ]
        })
        yield mock
