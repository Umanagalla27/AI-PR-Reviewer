"""Tests for Gateway service routes."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_check(test_client):
    """Health endpoint should return ok."""
    if True:
        client = test_client
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(test_client, pr_payload):
    """Invalid HMAC signature should return 401."""
    body = json.dumps(pr_payload).encode("utf-8")

    if True:
        client = test_client
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_signature_returns_401(test_client, pr_payload):
    """Missing signature should return 401."""
    body = json.dumps(pr_payload).encode("utf-8")

    if True:
        client = test_client
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_pr_event_skipped(test_client, webhook_secret):
    """Non-pull_request events should be skipped."""
    payload = {"action": "created"}
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    if True:
        client = test_client
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


@pytest.mark.asyncio
async def test_unhandled_pr_action_skipped(test_client, webhook_secret):
    """PR events with unhandled actions should be skipped."""
    payload = {
        "action": "labeled",
        "pull_request": {"number": 1, "head": {"sha": "a"}, "base": {"sha": "b"},
                         "user": {"login": "u"}, "merged": False},
        "repository": {"full_name": "o/r"},
        "installation": {"id": 1},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    if True:
        client = test_client
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": f"sha256={sig}",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


@pytest.mark.asyncio
@patch("services.gateway.routes.httpx.AsyncClient")
async def test_valid_pr_opened_forwarded(mock_httpx_cls, test_client, signed_payload):
    """Valid PR opened event should be forwarded to webhook service."""
    body, signature = signed_payload

    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_httpx_cls.return_value = mock_client

    if True:
        client = test_client
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
