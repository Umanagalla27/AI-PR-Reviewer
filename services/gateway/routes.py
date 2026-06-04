"""
Gateway route handlers — HMAC validation and webhook forwarding.

Validates GitHub webhook signatures using HMAC-SHA256, filters for
relevant PR events, and forwards cleaned payloads to the Webhook service.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from shared.config.settings import get_settings
from shared.observability.metrics import github_webhooks_received_total

logger = structlog.get_logger(__name__)

router = APIRouter()

# PR actions we process for review
REVIEW_ACTIONS = {"opened", "synchronize", "reopened"}

# PR actions for the learner (merged PRs)
LEARN_ACTIONS = {"closed"}

ALL_ALLOWED_ACTIONS = REVIEW_ACTIONS | LEARN_ACTIONS


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify the HMAC-SHA256 signature of a GitHub webhook payload.

    Uses hmac.compare_digest for constant-time comparison to prevent
    timing attacks.
    """
    if not signature.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


def _extract_pr_payload(body: dict) -> dict:
    """Extract and clean the PR payload from the raw webhook body."""
    pr = body.get("pull_request", {})
    repo = body.get("repository", {})

    return {
        "action": body.get("action", ""),
        "repo_full_name": repo.get("full_name", ""),
        "pr_number": pr.get("number", 0),
        "head_sha": pr.get("head", {}).get("sha", ""),
        "base_sha": pr.get("base", {}).get("sha", ""),
        "author": pr.get("user", {}).get("login", ""),
        "installation_id": body.get("installation", {}).get("id", 0),
        "merged": pr.get("merged", False),
    }


@router.post("/webhook/github")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
    x_github_event: str = Header(default="", alias="X-GitHub-Event"),
):
    """
    Receive and validate a GitHub webhook event.

    1. Validate HMAC-SHA256 signature
    2. Filter for pull_request events with allowed actions
    3. Forward cleaned payload to Webhook or Learner service
    4. Return 200 immediately (GitHub requires response within 10s)
    """
    settings = get_settings()

    # Read raw body for signature verification
    raw_body = await request.body()

    # ── Step 1: Validate signature ──────────────────────────────────────────
    if not _verify_signature(
        raw_body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET
    ):
        # avoid using kwarg name `event` which can collide with structlog internals
        logger.warning("webhook_signature_invalid", github_event=x_github_event)
        github_webhooks_received_total.labels(
            service="gateway", status="invalid_signature"
        ).inc()
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    github_webhooks_received_total.labels(service="gateway", status="received").inc()

    # ── Step 2: Filter event type ───────────────────────────────────────────
    if x_github_event != "pull_request":
        logger.debug("webhook_event_skipped", github_event=x_github_event)
        return {
            "status": "skipped",
            "reason": f"event type '{x_github_event}' not handled",
        }

    # Parse JSON consistently from the raw bytes we already read
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        # Fallback: let FastAPI try to parse (should rarely be necessary)
        body = await request.json()

    action = body.get("action", "")

    if action not in ALL_ALLOWED_ACTIONS:
        logger.debug("webhook_action_skipped", pr_action=action)
        return {"status": "skipped", "reason": f"action '{action}' not handled"}

    # ── Step 3: Extract and forward ─────────────────────────────────────────
    payload = _extract_pr_payload(body)

    structlog.contextvars.bind_contextvars(
        repo=payload["repo_full_name"],
        pr_number=payload["pr_number"],
    )

    logger.info("webhook_event_received", pr_action=action, author=payload["author"])

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if action in REVIEW_ACTIONS:
                # Forward to Webhook service for review processing
                response = await client.post(
                    f"{settings.WEBHOOK_SERVICE_URL}/pr/process",
                    json=payload,
                )
                response.raise_for_status()
                github_webhooks_received_total.labels(
                    service="gateway", status="forwarded_review"
                ).inc()

            elif action in LEARN_ACTIONS and payload.get("merged"):
                # Forward to Learner service for pattern extraction
                response = await client.post(
                    f"{settings.LEARNER_URL}/learn/merged-pr",
                    json=payload,
                )
                response.raise_for_status()
                github_webhooks_received_total.labels(
                    service="gateway", status="forwarded_learn"
                ).inc()
            else:
                logger.debug("webhook_closed_not_merged", pr_action=action)
                return {"status": "skipped", "reason": "PR closed but not merged"}

    except httpx.HTTPError as exc:
        logger.error("webhook_forward_error", error=str(exc))
        # Still return 200 to GitHub — we don't want webhook retries
        # The event data is logged for manual recovery
        github_webhooks_received_total.labels(
            service="gateway", status="forward_error"
        ).inc()
        return {"status": "accepted", "warning": "forwarding failed, event logged"}

    return {"status": "accepted"}
