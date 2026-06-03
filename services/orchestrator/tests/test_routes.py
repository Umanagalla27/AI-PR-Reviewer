"""Tests for Orchestrator routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from shared.db.models import StylePattern, Finding
from shared.db.session import async_session_factory


@pytest.mark.asyncio
async def test_health_check(test_client):
    if True:
        client = test_client
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("services.orchestrator.routes.httpx.AsyncClient")
async def test_start_review_success(
    mock_httpx_cls, 
    test_client, 
    review_start_request, 
    mock_github_client, 
    mock_get_installation_token, 
    mock_review_graph
):
    """Start review should fetch diff, run graph, save findings, and post to reviewer."""
    
    # Setup mock for httpx POST to reviewer service
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_httpx_cls.return_value = mock_client
    
    # Add a style pattern to the DB to test loading
    factory = async_session_factory
    async with factory() as session:
        pattern = StylePattern(
            repo_full_name="owner/repo",
            pattern_type="test",
            description="test description"
        )
        session.add(pattern)
        await session.commit()
    
    # Run request
    if True:
        client = test_client
        response = await client.post("/review/start", json=review_start_request)
        
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["findings_count"] == 1
    
    # Verify GitHub API called
    mock_get_installation_token.assert_called_once_with(12345)
    mock_github_client.fetch_pr_diff.assert_called_once_with("owner/repo", 123)
    
    # Verify graph invoked
    mock_review_graph.ainvoke.assert_called_once()
    call_args = mock_review_graph.ainvoke.call_args[0][0]
    assert call_args["repo"] == "owner/repo"
    assert len(call_args["style_patterns"]) == 1
    assert call_args["style_patterns"][0]["description"] == "test description"
    
    # Verify findings saved to DB
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(Finding)
        result = await session.execute(stmt)
        findings = result.scalars().all()
        assert len(findings) == 1
        assert findings[0].message == "test finding"
        
    # Verify POST to reviewer service
    mock_client.post.assert_called_once()
    post_args = mock_client.post.call_args
    assert "http://localhost:8003/review/post" in post_args[0][0]
    payload = post_args[1]["json"]
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["message"] == "test finding"
