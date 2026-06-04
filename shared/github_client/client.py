"""
GitHub REST API client with retry logic and rate limit handling.

All API calls retry 3x with exponential backoff on 429/5xx errors
and pause if X-RateLimit-Remaining drops below 10.
"""

from __future__ import annotations

import asyncio
import structlog
import httpx

from shared.observability.metrics import (
    github_api_requests_total,
    github_api_latency_seconds,
)

logger = structlog.get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"
MAX_RETRIES = 3
RATE_LIMIT_THRESHOLD = 10


class GitHubClient:
    """Async GitHub REST API client with automatic retry and rate limit handling."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        headers: dict | None = None,
        json: dict | None = None,
        timeout: float = 30.0,
    ) -> httpx.Response:
        """
        Make an API request with retry logic and rate limit handling.

        Retries up to 3 times with exponential backoff on 429 and 5xx errors.
        Pauses if X-RateLimit-Remaining header indicates < 10 requests remaining.
        """
        url = f"{GITHUB_API_BASE}{endpoint}"
        merged_headers = {**self.headers, **(headers or {})}

        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                with github_api_latency_seconds.labels(endpoint=endpoint).time():
                    async with httpx.AsyncClient() as client:
                        response = await client.request(
                            method,
                            url,
                            headers=merged_headers,
                            json=json,
                            timeout=timeout,
                        )

                # Track metrics
                github_api_requests_total.labels(
                    endpoint=endpoint, status_code=response.status_code
                ).inc()

                # Check rate limits
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) < RATE_LIMIT_THRESHOLD:
                    reset_at = int(response.headers.get("X-RateLimit-Reset", "0"))
                    wait_seconds = max(reset_at - asyncio.get_event_loop().time(), 1)
                    logger.warning(
                        "github_rate_limit_low",
                        remaining=remaining,
                        wait_seconds=wait_seconds,
                    )
                    await asyncio.sleep(min(wait_seconds, 60))

                # Retry on 429 or 5xx
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        backoff = 2**attempt
                        logger.warning(
                            "github_api_retry",
                            status=response.status_code,
                            attempt=attempt + 1,
                            backoff=backoff,
                            endpoint=endpoint,
                        )
                        await asyncio.sleep(backoff)
                        continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    backoff = 2**attempt
                    logger.warning(
                        "github_api_error_retry",
                        error=str(exc),
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

        raise last_exc or RuntimeError("GitHub API request failed after retries")

    async def fetch_pr_diff(self, repo: str, pr_number: int) -> str:
        """Fetch the unified diff for a pull request."""
        response = await self._request(
            "GET",
            f"/repos/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return response.text

    async def post_review_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        path: str,
        line: int,
        commit_id: str,
    ) -> dict:
        """Post an inline review comment on a specific line of a PR."""
        response = await self._request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/comments",
            json={
                "body": body,
                "path": path,
                "line": line,
                "side": "RIGHT",
                "commit_id": commit_id,
            },
        )
        return response.json()

    async def post_review_summary(
        self,
        repo: str,
        pr_number: int,
        body: str,
        commit_id: str,
    ) -> dict:
        """Post an overall PR review summary."""
        response = await self._request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json={
                "commit_id": commit_id,
                "body": body,
                "event": "COMMENT",
            },
        )
        return response.json()

    async def add_label(self, repo: str, pr_number: int, label: str) -> dict:
        """Add a label to a PR (creates the label if it doesn't exist)."""
        response = await self._request(
            "POST",
            f"/repos/{repo}/issues/{pr_number}/labels",
            json={"labels": [label]},
        )
        return response.json()

    async def get_issue_comments(self, repo: str, issue_number: int) -> list[dict]:
        """Get all comments on an issue or PR."""
        response = await self._request(
            "GET",
            f"/repos/{repo}/issues/{issue_number}/comments",
        )
        return response.json()

    async def post_issue_comment(self, repo: str, issue_number: int, body: str) -> dict:
        """Post a general comment to an issue or PR."""
        response = await self._request(
            "POST",
            f"/repos/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return response.json()
