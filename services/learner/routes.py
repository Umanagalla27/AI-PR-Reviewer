"""
Learner route handlers — pattern extraction from merged PRs.

Flow:
  1. Look up existing findings for this PR (by repo + pr_number)
  2. Fetch the merged diff from GitHub
  3. Call GPT-4o-mini to extract recurring style patterns
  4. Upsert StylePattern rows: increment frequency if existing, insert if new
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.prompts import LEARNER_SYSTEM_PROMPT, LEARNER_USER_PROMPT
from shared.config.settings import get_settings
from shared.db.models import Finding, PullRequest, StylePattern
from shared.db.session import get_db_session
from shared.github_client.auth import get_installation_token
from shared.github_client.client import GitHubClient
from shared.schemas.pr import LearnMergedPRRequest

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/learn/merged-pr")
async def learn_from_merged_pr(
    request: LearnMergedPRRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Analyze a merged PR to extract style patterns.

    Called by the Gateway when a PR is merged (action="closed", merged=true).
    Extracted patterns are upserted into the style_patterns table.
    """
    settings = get_settings()

    structlog.contextvars.bind_contextvars(
        repo=request.repo_full_name,
        pr_number=request.pr_number,
    )

    logger.info("learning_from_merged_pr")

    # ── Step 1: Fetch existing findings for this PR ─────────────────────────
    # Find the PullRequest record
    pr_stmt = select(PullRequest).where(
        PullRequest.repo_full_name == request.repo_full_name,
        PullRequest.head_sha == request.head_sha,
    )
    pr_result = await db.execute(pr_stmt)
    pr_record = pr_result.scalar_one_or_none()

    findings_data = []
    if pr_record:
        findings_stmt = select(Finding).where(Finding.pr_id == pr_record.id)
        findings_result = await db.execute(findings_stmt)
        findings = findings_result.scalars().all()

        findings_data = [
            {
                "agent": f.agent,
                "file": f.file_path,
                "line": f.line_number,
                "severity": f.severity.value
                if hasattr(f.severity, "value")
                else f.severity,
                "message": f.message,
            }
            for f in findings
        ]

    logger.info("findings_loaded", count=len(findings_data))

    # ── Step 2: Fetch merged diff from GitHub ───────────────────────────────
    try:
        token = await get_installation_token(request.installation_id)
        gh_client = GitHubClient(token)
        diff_text = await gh_client.fetch_pr_diff(
            request.repo_full_name, request.pr_number
        )
    except Exception as exc:
        logger.error("diff_fetch_failed", error=str(exc))
        diff_text = ""

    # ── Step 3: Extract patterns via GPT-4o-mini ────────────────────────────
    patterns: list[Any] = []

    if diff_text or findings_data:
        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            user_prompt = LEARNER_USER_PROMPT.format(
                findings_json=json.dumps(findings_data, indent=2),
                diff=diff_text[:8000],  # Truncate to avoid token limits
            )

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": LEARNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=2048,
            )

            content = response.choices[0].message.content or "[]"
            parsed = json.loads(content)

            if isinstance(parsed, dict):
                patterns = parsed.get("patterns", parsed.get("style_patterns", []))  # type: ignore
            elif isinstance(parsed, list):
                patterns = parsed
            else:
                patterns = []

            logger.info("patterns_extracted", count=len(patterns))

        except Exception as exc:
            logger.error("pattern_extraction_failed", error=str(exc))
            return {"status": "failed", "patterns_upserted": 0}

    # ── Step 4: Upsert StylePattern rows ────────────────────────────────────
    upserted = 0

    for pattern in patterns:
        pattern_type = pattern.get("pattern_type", "").strip()
        description = pattern.get("description", "").strip()

        if not pattern_type or not description:
            continue

        # Check if this pattern already exists
        stmt = select(StylePattern).where(
            StylePattern.repo_full_name == request.repo_full_name,
            StylePattern.pattern_type == pattern_type,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Increment frequency and update description
            existing.frequency = int(existing.frequency) + 1  # type: ignore
            existing.description = description
            existing.last_seen = datetime.now(timezone.utc)  # type: ignore
            logger.debug(
                "pattern_updated",
                pattern_type=pattern_type,
                frequency=existing.frequency,
            )
        else:
            # Insert new pattern
            new_pattern = StylePattern(
                repo_full_name=request.repo_full_name,
                pattern_type=pattern_type,
                description=description,
                frequency=1,
                last_seen=datetime.now(timezone.utc),
            )
            db.add(new_pattern)
            logger.debug("pattern_inserted", pattern_type=pattern_type)

        upserted += 1

    await db.commit()

    logger.info("learning_complete", patterns_upserted=upserted)

    return {"status": "completed", "patterns_upserted": upserted}
