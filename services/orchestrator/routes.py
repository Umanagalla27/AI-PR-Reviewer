"""
Orchestrator route handlers — diff fetching, pattern loading, LangGraph invocation.

Flow:
  1. Authenticate with GitHub App → get installation token
  2. Fetch PR diff via GitHub API
  3. Parse diff into file hunks
  4. Load repo-specific StylePatterns from DB
  5. Build ReviewState and invoke LangGraph graph
  6. Save findings to DB
  7. POST to Reviewer service with findings
"""

from __future__ import annotations

import uuid

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import review_graph
from shared.config.settings import get_settings
from shared.db.models import Finding, SeverityLevel as Severity, StylePattern
from shared.db.session import get_db_session
from shared.github_client.auth import get_installation_token
from shared.github_client.client import GitHubClient
from shared.github_client.diff_parser import parse_unified_diff
from shared.observability.tracing import create_trace
from shared.schemas.pr import ReviewStartRequest

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/review/start")
async def start_review(
    request: ReviewStartRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Start a full PR review using the LangGraph multi-agent pipeline.

    This endpoint is called by the Celery worker task.
    """
    settings = get_settings()

    structlog.contextvars.bind_contextvars(
        repo=request.repo_full_name,
        pr_number=request.pr_number,
        pr_id=str(request.pr_id),
    )

    logger.info("review_starting")

    try:
        # ── Step 1: Authenticate with GitHub ────────────────────────────────
        token = await get_installation_token(request.installation_id)
        gh_client = GitHubClient(token)

        # ── Step 2: Fetch PR diff ───────────────────────────────────────────
        diff_text = await gh_client.fetch_pr_diff(
            request.repo_full_name, request.pr_number
        )
        logger.info("diff_fetched", diff_size=len(diff_text))

        # ── Step 3: Parse diff into file hunks ──────────────────────────────
        file_hunks = parse_unified_diff(diff_text)
        logger.info("diff_parsed", hunk_count=len(file_hunks))

        # ── Step 4: Load style patterns from DB ────────────────────────────
        stmt = select(StylePattern).where(
            StylePattern.repo_full_name == request.repo_full_name
        )
        result = await db.execute(stmt)
        style_patterns = result.scalars().all()

        patterns_data = [
            {
                "pattern_type": p.pattern_type,
                "description": p.description,
                "frequency": p.frequency,
            }
            for p in style_patterns
        ]
        logger.info("patterns_loaded", count=len(patterns_data))

        # ── Step 5: Build ReviewState and invoke graph ──────────────────────
        trace_id = str(uuid.uuid4())
        trace = create_trace(
            name="pr_review",
            metadata={
                "repo": request.repo_full_name,
                "pr_number": request.pr_number,
            },
            trace_id=trace_id,
        )

        initial_state = {
            "repo": request.repo_full_name,
            "pr_number": request.pr_number,
            "head_sha": request.head_sha,
            "diff": diff_text,
            "file_hunks": [h.to_dict() for h in file_hunks],
            "style_patterns": patterns_data,
            "static_findings": [],
            "security_findings": [],
            "style_findings": [],
            "arch_findings": [],
            "merged_findings": [],
            "langfuse_trace_id": trace_id,
        }

        # Run the LangGraph pipeline
        result_state = await review_graph.ainvoke(initial_state)
        merged_findings = result_state.get("merged_findings", [])

        logger.info("graph_complete", findings_count=len(merged_findings))

        # ── Step 6: Save findings to DB ─────────────────────────────────────
        for f in merged_findings:
            severity_value = f.get("severity", "info")
            try:
                severity_enum = Severity(severity_value)
            except ValueError:
                severity_enum = Severity.INFO

            finding = Finding(
                id=uuid.uuid4(),
                pr_id=request.pr_id,
                agent=f.get("agent", "unknown"),
                file_path=f.get("file_path", ""),
                line_number=f.get("line_number"),
                severity=severity_enum,
                message=f.get("message", ""),
                suggestion=f.get("suggestion"),
            )
            db.add(finding)

        await db.commit()
        logger.info("findings_saved", count=len(merged_findings))

        # ── Step 7: POST to Reviewer service ────────────────────────────────
        findings_payload = [
            {
                "agent": f.get("agent", "unknown"),
                "file": f.get("file_path", ""),
                "line": f.get("line_number"),
                "severity": f.get("severity", "info"),
                "message": f.get("message", ""),
                "suggestion": f.get("suggestion"),
            }
            for f in merged_findings
        ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.REVIEWER_URL}/review/post",
                json={
                    "pr_id": str(request.pr_id),
                    "repo_full_name": request.repo_full_name,
                    "pr_number": request.pr_number,
                    "head_sha": request.head_sha,
                    "installation_id": request.installation_id,
                    "findings": findings_payload,
                },
            )
            response.raise_for_status()

        logger.info("review_posted_to_reviewer")

        # End Langfuse trace
        if hasattr(trace, "end"):
            trace.end()

        return {
            "status": "completed",
            "findings_count": len(merged_findings),
        }

    except Exception as exc:
        logger.error("review_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Review failed") from exc
