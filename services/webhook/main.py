import httpx
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from starlette_prometheus import metrics, PrometheusMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from shared.config.settings import settings
from shared.observability import logger, RequestIdMiddleware
from shared.db.session import get_db_session
from shared.db.models import PullRequest, PRStatus
# Import celery task (we will create it next)
from workers.celery_app.tasks import review_pr, learn_pr

app = FastAPI(title="Webhook Service")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "webhook"}

@app.post("/pr/process")
async def process_pr(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    action = payload.get("action")
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    
    repo_full_name = repo_data.get("full_name")
    pr_number = pr_data.get("number")
    head_sha = pr_data.get("head", {}).get("sha")
    base_sha = pr_data.get("base", {}).get("sha")
    author = pr_data.get("user", {}).get("login")
    merged = pr_data.get("merged", False)
    # the installation ID for github app token
    installation_id = payload.get("installation", {}).get("id")
    
    if not all([repo_full_name, pr_number, head_sha, base_sha, installation_id]):
        raise HTTPException(status_code=400, detail="Missing required PR fields")

    # Handle PR merge for Learner
    if action == "closed" and merged:
        learn_pr.delay(repo_full_name=repo_full_name, pr_number=pr_number, installation_id=installation_id)
        return {"status": "queued_for_learning"}

    # Proceed with PR Review for opened/synchronize/reopened
    async with get_db_session() as session:
        # Deduplicate
        stmt = select(PullRequest).where(
            PullRequest.repo_full_name == repo_full_name,
            PullRequest.head_sha == head_sha
        )
        result = await session.execute(stmt)
        existing_pr = result.scalar_one_or_none()
        
        if existing_pr:
            if existing_pr.status != PRStatus.failed:
                logger.info("pr_already_processed_or_processing", pr_id=str(existing_pr.id))
                return {"pr_id": str(existing_pr.id), "status": "skipped"}
                
        # Insert new or update failed
        if not existing_pr:
            new_pr = PullRequest(
                id=uuid4(),
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                head_sha=head_sha,
                base_sha=base_sha,
                author=author,
                status=PRStatus.pending
            )
            session.add(new_pr)
            await session.commit()
            pr_id = str(new_pr.id)
        else:
            existing_pr.status = PRStatus.pending
            await session.commit()
            pr_id = str(existing_pr.id)
            
    # Push Celery task
    review_pr.delay(
        pr_id=pr_id,
        repo=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
        installation_id=installation_id
    )
    
    logger.info("pr_queued_for_review", pr_id=pr_id)
    return {"pr_id": pr_id, "status": "queued"}
