"""Tests for Learner routes."""

from __future__ import annotations

import pytest

from shared.db.models import StylePattern
from shared.db.session import get_session_factory

@pytest.mark.asyncio
async def test_health_check(test_client):
    async with test_client as client:
        response = await client.get("/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_learn_from_merged_pr(
    test_client, 
    learn_request, 
    mock_github_client, 
    mock_get_installation_token, 
    mock_openai_response
):
    """Learning from a PR should extract and upsert patterns."""
    
    async with test_client as client:
        response = await client.post("/learn/merged-pr", json=learn_request)
        
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["patterns_upserted"] == 1
    
    # Verify GitHub diff fetched
    mock_get_installation_token.assert_called_once_with(12345)
    mock_github_client.fetch_pr_diff.assert_called_once_with("owner/repo", 123)
    
    # Verify OpenAI called
    mock_openai_response.chat.completions.create.assert_called_once()
    
    # Verify pattern saved to DB
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(StylePattern)
        result = await session.execute(stmt)
        patterns = result.scalars().all()
        
        assert len(patterns) == 1
        assert patterns[0].repo_full_name == "owner/repo"
        assert patterns[0].pattern_type == "naming"
        assert patterns[0].description == "use snake case"
        assert patterns[0].frequency == 1

@pytest.mark.asyncio
async def test_learn_updates_existing_pattern(
    test_client, 
    learn_request, 
    mock_github_client, 
    mock_get_installation_token, 
    mock_openai_response
):
    """Learning an existing pattern should increment its frequency."""
    
    # Insert existing pattern
    factory = get_session_factory()
    async with factory() as session:
        pattern = StylePattern(
            repo_full_name="owner/repo",
            pattern_type="naming",
            description="old description",
            frequency=1
        )
        session.add(pattern)
        await session.commit()
    
    async with test_client as client:
        response = await client.post("/learn/merged-pr", json=learn_request)
        
    assert response.status_code == 200
    
    # Verify pattern updated in DB
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(StylePattern)
        result = await session.execute(stmt)
        patterns = result.scalars().all()
        
        assert len(patterns) == 1
        assert patterns[0].frequency == 2
        assert patterns[0].description == "use snake case"
