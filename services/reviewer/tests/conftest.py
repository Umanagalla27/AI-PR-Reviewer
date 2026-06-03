"""Tests for Reviewer service."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from services.reviewer.main import app

@pytest.fixture
def test_client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )

@pytest.fixture
def review_post_request():
    import uuid
    return {
        "pr_id": str(uuid.uuid4()),
        "repo_full_name": "owner/repo",
        "pr_number": 123,
        "head_sha": "abc123def456",
        "installation_id": 12345,
        "findings": [
            {
                "agent": "static",
                "file_path": "file.py",
                "line_number": 2,
                "severity": "warning",
                "message": "test finding",
                "suggestion": "fix it"
            }
        ]
    }

@pytest.fixture
def mock_github_client():
    with patch("services.reviewer.main.GitHubClient") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.post_review_comment = AsyncMock()
        mock_instance.post_review_summary = AsyncMock()
        mock_instance.add_label = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance
        
@pytest.fixture
def mock_get_installation_token():
    with patch("services.reviewer.main.get_installation_token", new_callable=AsyncMock) as mock:
        mock.return_value = "fake-token"
        yield mock
        
@pytest.fixture
def mock_generate_summary():
    with patch("services.reviewer.main.generate_summary", new_callable=AsyncMock) as mock:
        mock.return_value = "Test summary body"
        yield mock
