"""
Webhook route handlers — PR parsing, deduplication, and Celery task enqueuing.

Logic:
  1. Parse PR payload fields
  2. Deduplicate: check DB for (repo_full_name, head_sha) — skip if already exists and not failed
  3. Insert new PullRequest row with status="pending"
  4. Enqueue Celery task: review_pr
  5. Return {pr_id, status: "queued"}
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import PRStatus, PullRequest
from shared.db.session import get_db_session
from shared.schemas.pr import PRProcessRequest, PRProcessResponse
from workers.celery_app.tasks import review_pr

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/pr/process", response_model=PRProcessResponse)
async def process_pr(
    request: PRProcessRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Process a validated PR webhook event.

    Deduplicates by (repo_full_name, head_sha) and enqueues a Celery
    review task for new or previously-failed PRs.
    """
    structlog.contextvars.bind_contextvars(
        repo=request.repo_full_name,
        pr_number=request.pr_number,
    )

    # ── Step 1: Deduplicate ─────────────────────────────────────────────────
    stmt = select(PullRequest).where(
        PullRequest.repo_full_name == request.repo_full_name,
        PullRequest.head_sha == request.head_sha,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing and existing.status != PRStatus.failed:
        logger.info(
            "pr_deduplicated",
            pr_id=str(existing.id),
            status=existing.status.value,
        )
        return PRProcessResponse(pr_id=existing.id, status="skipped")

    # ── Step 2: Insert new PullRequest ──────────────────────────────────────
    pr_id = uuid.uuid4()

    if existing and existing.status == PRStatus.failed:
        # Reuse existing row, reset status
        existing.status = PRStatus.pending
        existing.updated_at = datetime.now(timezone.utc)
        pr_id = existing.id
        logger.info("pr_retry_after_failure", pr_id=str(pr_id))
    else:
        pr = PullRequest(
            id=pr_id,
            repo_full_name=request.repo_full_name,
            pr_number=request.pr_number,
            head_sha=request.head_sha,
            base_sha=request.base_sha,
            author=request.author,
            installation_id=request.installation_id,
            status=PRStatus.pending,
        )
        db.add(pr)

    await db.commit()

    logger.info("pr_inserted", pr_id=str(pr_id), status="pending")

    # ── Step 3: Enqueue Celery task ─────────────────────────────────────────
    try:
        review_pr.delay(
            pr_id=str(pr_id),
            repo=request.repo_full_name,
            pr_number=request.pr_number,
            head_sha=request.head_sha,
            base_sha=request.base_sha,
            installation_id=request.installation_id,
        )
        logger.info("celery_task_enqueued", pr_id=str(pr_id))

    except Exception as exc:
        logger.error("celery_enqueue_error", error=str(exc), pr_id=str(pr_id))
        # Don't fail the request — the PR is persisted and can be retried
        return PRProcessResponse(pr_id=pr_id, status="queued_with_warning")

    return PRProcessResponse(pr_id=pr_id, status="queued")
