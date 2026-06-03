import hmac
import hashlib
import json
import httpx
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.config.settings import settings
from shared.observability import logger, RequestIdMiddleware

app = FastAPI(title="Gateway Service")

# Middleware
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

async def forward_webhook(payload: dict):
    """Forward the webhook payload to the webhook service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.WEBHOOK_SERVICE_URL}/pr/process",
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info("webhook_forwarded_successfully", status=response.status_code)
    except Exception as e:
        logger.error("webhook_forward_failed", error=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
        
    raw_body = await request.body()
    
    # Verify HMAC
    secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
    expected_signature = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        logger.warning("webhook_signature_mismatch")
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    if x_github_event != "pull_request":
        logger.info("skipped_non_pr_event", github_event=x_github_event)
        return {"status": "skipped", "reason": "not a pull_request event"}
        
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    action = payload.get("action")
    allowed_actions = ["opened", "synchronize", "reopened", "closed"]
    
    if action not in allowed_actions:
        logger.info("skipped_pr_action", action=action)
        return {"status": "skipped", "reason": f"action {action} not processed"}
        
    if action == "closed" and not payload.get("pull_request", {}).get("merged", False):
        logger.info("skipped_closed_unmerged_pr")
        return {"status": "skipped", "reason": "pr closed but not merged"}
        
    # Valid payload, enqueue forwarding
    background_tasks.add_task(forward_webhook, payload)
    
    return {"status": "accepted"}
