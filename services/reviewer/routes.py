"""
Reviewer route handlers — post inline comments and PR summary to GitHub.

Flow:
  1. Get installation token
  2. Post inline comments for findings with line_number (100ms delay between)
  3. Generate summary via GPT-4o-mini
  4. Post PR review summary
  5. Add "ai-reviewed" label
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, HTTPException

from shared.github_client.auth import get_installation_token
from shared.github_client.client import GitHubClient
from shared.schemas.pr import ReviewPostRequest
from services.reviewer.summary import generate_summary

logger = structlog.get_logger(__name__)

router = APIRouter()

# Severity emoji mapping for formatted comments
SEVERITY_EMOJI = {
    "error": "🔴",
    "warning": "🟡",
    "info": "🔵",
    "suggestion": "💡",
}


def _format_comment(finding: dict) -> str:
    """Format a finding into a GitHub PR comment body."""
    severity = finding.get("severity", "info").upper()
    agent = finding.get("agent", "unknown")
    message = finding.get("message", "")
    suggestion = finding.get("suggestion")
    emoji = SEVERITY_EMOJI.get(finding.get("severity", "info"), "ℹ️")

    comment = f"{emoji} **[{severity}] {agent} agent**\n{message}"
    if suggestion:
        comment += f"\n\n💡 **Suggestion:** {suggestion}"

    return comment


@router.post("/review/post")
async def post_review(request: ReviewPostRequest):
    """
    Post review findings to the GitHub PR.

    Posts inline comments for findings with line numbers,
    generates and posts a review summary, and adds the "ai-reviewed" label.
    """
    structlog.contextvars.bind_contextvars(
        repo=request.repo_full_name,
        pr_number=request.pr_number,
    )

    logger.info("posting_review", findings_count=len(request.findings))

    try:
        # ── Step 1: Get installation token ──────────────────────────────────
        token = await get_installation_token(request.installation_id)
        gh_client = GitHubClient(token)

        # ── Step 2: Post inline comments ────────────────────────────────────
        inline_count = 0
        for finding in request.findings:
            line = finding.line_number
            file_path = finding.file_path

            if line is not None and file_path:
                comment_body = _format_comment(finding.model_dump())

                try:
                    await gh_client.post_review_comment(
                        repo=request.repo_full_name,
                        pr_number=request.pr_number,
                        body=comment_body,
                        path=file_path,
                        line=line,
                        commit_id=request.head_sha,
                    )
                    inline_count += 1

                    # Rate limit: 100ms delay between comments
                    await asyncio.sleep(0.1)

                except Exception as exc:
                    logger.warning(
                        "inline_comment_failed",
                        file=file_path,
                        line=line,
                        error=str(exc),
                    )
                    # Continue posting remaining comments

        logger.info("inline_comments_posted", count=inline_count)

        # ── Step 3: Generate summary ────────────────────────────────────────
        findings_dicts = [f.model_dump() for f in request.findings]
        summary_body = await generate_summary(findings_dicts)

        # ── Step 4: Post PR review summary ──────────────────────────────────
        try:
            await gh_client.post_review_summary(
                repo=request.repo_full_name,
                pr_number=request.pr_number,
                body=summary_body,
                commit_id=request.head_sha,
            )
            logger.info("review_summary_posted")
        except Exception as exc:
            logger.error("review_summary_failed", error=str(exc))

        # ── Step 5: Add label ───────────────────────────────────────────────
        try:
            await gh_client.add_label(
                repo=request.repo_full_name,
                pr_number=request.pr_number,
                label="ai-reviewed",
            )
            logger.info("label_added", label="ai-reviewed")
        except Exception as exc:
            logger.warning("label_add_failed", error=str(exc))

        return {
            "status": "posted",
            "inline_comments": inline_count,
            "total_findings": len(request.findings),
        }

    except Exception as exc:
        logger.error("review_post_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to post review") from exc
