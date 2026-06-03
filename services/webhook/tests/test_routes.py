"""Tests for the webhook service models and deduplication logic."""

from __future__ import annotations

import os

# Ensure test settings use sqlite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import uuid
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from shared.db.models import PullRequest, PRStatus
from shared.db.session import init_db, create_db_engine, get_session_factory
from services.webhook.main import app

@pytest.fixture(autouse=True)
async def setup_test_db():
    """Setup and teardown in-memory SQLite DB for tests."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:", echo=False)
    await init_db(engine)
    yield
    await engine.dispose()


@pytest.fixture
def test_client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest.fixture
def pr_process_request():
    return {
        "action": "opened",
        "repo_full_name": "owner/repo",
        "pr_number": 123,
        "head_sha": "abc123def456",
        "base_sha": "def789abc012",
        "author": "testuser",
        "installation_id": 12345,
        "merged": False,
    }


@pytest.mark.asyncio
async def test_webhook_health_check(test_client):
    """Health check should return ok."""
    async with test_client as client:
        response = await client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["db"] is True


@pytest.mark.asyncio
@pytest.mark.patch("services.webhook.routes.review_pr.delay")
async def test_process_pr_new_inserts_and_enqueues(mock_delay, test_client, pr_process_request):
    """A new PR should be inserted into DB and enqueued for review."""
    async with test_client as client:
        response = await client.post("/pr/process", json=pr_process_request)
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "pr_id" in data
    
    # Verify DB insertion
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(PullRequest).where(PullRequest.id == uuid.UUID(data["pr_id"]))
        result = await session.execute(stmt)
        pr = result.scalar_one_or_none()
        
        assert pr is not None
        assert pr.repo_full_name == "owner/repo"
        assert pr.status == PRStatus.PENDING
        
    # Verify Celery enqueue
    mock_delay.assert_called_once_with(
        pr_id=data["pr_id"],
        repo="owner/repo",
        pr_number=123,
        head_sha="abc123def456",
        base_sha="def789abc012",
        installation_id=12345,
    )


@pytest.mark.asyncio
@pytest.mark.patch("services.webhook.routes.review_pr.delay")
async def test_process_pr_deduplicates_existing(mock_delay, test_client, pr_process_request):
    """If PR with same repo and head_sha exists and is not failed, it should be skipped."""
    
    # First request
    async with test_client as client:
        res1 = await client.post("/pr/process", json=pr_process_request)
        assert res1.json()["status"] == "queued"
        
    mock_delay.reset_mock()
    
    # Second request with same data
    async with test_client as client:
        res2 = await client.post("/pr/process", json=pr_process_request)
        
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "skipped"
    assert data2["pr_id"] == res1.json()["pr_id"]
    
    # Verify NO new enqueue
    mock_delay.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.patch("services.webhook.routes.review_pr.delay")
async def test_process_pr_retries_failed(mock_delay, test_client, pr_process_request):
    """If PR exists but is failed, it should be retried (status reset to pending and enqueued)."""
    
    # Setup: Insert a failed PR
    factory = get_session_factory()
    failed_id = uuid.uuid4()
    async with factory() as session:
        pr = PullRequest(
            id=failed_id,
            repo_full_name=pr_process_request["repo_full_name"],
            pr_number=pr_process_request["pr_number"],
            head_sha=pr_process_request["head_sha"],
            base_sha=pr_process_request["base_sha"],
            author=pr_process_request["author"],
            installation_id=pr_process_request["installation_id"],
            status=PRStatus.FAILED,
        )
        session.add(pr)
        await session.commit()
        
    # Request to process same PR
    async with test_client as client:
        response = await client.post("/pr/process", json=pr_process_request)
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["pr_id"] == str(failed_id)
    
    # Verify DB status updated
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(PullRequest).where(PullRequest.id == failed_id)
        result = await session.execute(stmt)
        pr = result.scalar_one_or_none()
        assert pr.status == PRStatus.PENDING
        
    # Verify enqueue
    mock_delay.assert_called_once()
