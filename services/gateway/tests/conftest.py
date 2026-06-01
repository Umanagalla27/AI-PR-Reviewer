"""
Test fixtures for Gateway service tests.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")

from services.gateway.main import app


@pytest.fixture
def test_client():
    """Async test client for the gateway app."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest.fixture
def webhook_secret():
    return "test-webhook-secret"


@pytest.fixture
def pr_payload():
    """Sample GitHub PR webhook payload."""
    return {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "head": {"sha": "abc123def456"},
            "base": {"sha": "def789abc012"},
            "user": {"login": "testuser"},
            "merged": False,
        },
        "repository": {
            "full_name": "owner/repo",
        },
        "installation": {
            "id": 12345,
        },
    }


@pytest.fixture
def signed_payload(webhook_secret, pr_payload):
    """Create a signed payload with valid HMAC-SHA256 signature."""
    body = json.dumps(pr_payload).encode("utf-8")
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return body, f"sha256={signature}"
