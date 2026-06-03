"""Tests for Reviewer routes."""

from __future__ import annotations

import pytest

@pytest.mark.asyncio
async def test_health_check(test_client):
    if True:
        client = test_client
        response = await client.get("/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_post_review_success(
    test_client, 
    review_post_request, 
    mock_github_client, 
    mock_get_installation_token, 
    mock_generate_summary
):
    """Post review should add inline comments, summary, and label."""
    
    if True:
        client = test_client
        response = await client.post("/review/post", json=review_post_request)
        
    assert response.status_code == 200
    assert response.json()["status"] == "posted"
    assert response.json()["inline_comments"] == 1
    
    # Verify GitHub API called
    mock_get_installation_token.assert_called_once_with(12345)
    
    # Verify inline comment posted
    mock_github_client.post_review_comment.assert_called_once()
    kwargs = mock_github_client.post_review_comment.call_args[1]
    assert kwargs["repo"] == "owner/repo"
    assert kwargs["pr_number"] == 123
    assert kwargs["path"] == "file.py"
    assert kwargs["line"] == 2
    assert "test finding" in kwargs["body"]
    
    # Verify summary generated and posted
    mock_generate_summary.assert_called_once()
    mock_github_client.post_review_summary.assert_called_once_with(
        repo="owner/repo",
        pr_number=123,
        body="Test summary body",
        commit_id="abc123def456"
    )
    
    # Verify label added
    mock_github_client.add_label.assert_called_once_with(
        repo="owner/repo",
        pr_number=123,
        label="ai-reviewed"
    )
