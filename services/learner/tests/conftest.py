"""Tests for Learner service."""

from __future__ import annotations

import os

# Ensure test settings use sqlite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from shared.db.session import engine
from shared.db.models import Base
from services.learner.main import app

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
def learn_request():
    return {
        "repo_full_name": "owner/repo",
        "pr_number": 123,
        "head_sha": "abc123def456",
        "base_sha": "def789abc012",
        "author": "testuser",
        "installation_id": 12345,
    }

@pytest.fixture
def mock_github_client():
    with patch("services.learner.routes.GitHubClient") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_pr_diff = AsyncMock(return_value="diff content")
        mock_cls.return_value = mock_instance
        yield mock_instance
        
@pytest.fixture
def mock_get_installation_token():
    with patch("services.learner.routes.get_installation_token", new_callable=AsyncMock) as mock:
        mock.return_value = "fake-token"
        yield mock

@pytest.fixture
def mock_openai_response():
    with patch("services.learner.routes.AsyncOpenAI") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value = client
        
        mock_message = MagicMock()
        mock_message.content = '{"patterns": [{"pattern_type": "naming", "description": "use snake case"}]}'
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        client.chat.completions.create = AsyncMock(return_value=mock_response)
        yield client
