import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from starlette_prometheus import metrics, PrometheusMiddleware
from sqlalchemy import select
from uuid import UUID

from shared.config.settings import settings
from shared.observability import logger, RequestIdMiddleware
from shared.github_client.api import get_pr_diff
from shared.db.session import get_db_session
from shared.db.models import StylePattern, Finding

from agents.graph import review_graph
from agents.state import ReviewState

app = FastAPI(title="Orchestrator Service")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}

async def run_review_workflow(pr_id: str, repo: str, pr_number: int, head_sha: str, base_sha: str, installation_id: int):
    try:
        # 1. Fetch Diff
        diff = await get_pr_diff(repo, pr_number, installation_id)
        
        # 2. Load patterns
        async with get_db_session() as session:
            stmt = select(StylePattern).where(StylePattern.repo_full_name == repo)
            result = await session.execute(stmt)
            patterns_db = result.scalars().all()
            style_patterns = [{"pattern_type": p.pattern_type, "description": p.description} for p in patterns_db]
            
        # 3. Build State and run LangGraph
        state: ReviewState = {
            "repo": repo,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "diff": diff,
            "file_hunks": [], # Basic implementation, LLM usually parses raw diff fine
            "style_patterns": style_patterns,
            "static_findings": [],
            "security_findings": [],
            "style_findings": [],
            "arch_findings": [],
            "merged_findings": [],
            "langfuse_trace_id": f"{repo}-{pr_number}-{head_sha}"
        }
        
        logger.info("invoking_langgraph", pr_id=pr_id)
        final_state = await review_graph.ainvoke(state)
        merged_findings = final_state.get("merged_findings", [])
        
        # 4. Save findings to DB
        async with get_db_session() as session:
            db_findings = []
            for f in merged_findings:
                db_f = Finding(
                    pr_id=UUID(pr_id),
                    agent=f.agent,
                    file_path=f.file_path,
                    line_number=f.line_number,
                    severity=f.severity,
                    message=f.message,
                    suggestion=f.suggestion
                )
                session.add(db_f)
                db_findings.append(db_f)
            await session.commit()
            
        # 5. POST to Reviewer Service
        reviewer_payload = {
            "pr_id": pr_id,
            "repo": repo,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "installation_id": installation_id,
            "findings": [f.model_dump() for f in merged_findings]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{settings.REVIEWER_URL}/review/post", json=reviewer_payload)
            response.raise_for_status()
            
        logger.info("orchestration_completed", pr_id=pr_id)
    except Exception as e:
        logger.exception("orchestration_failed", pr_id=pr_id, error=str(e))
        raise

@app.post("/review/start")
async def start_review(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    pr_id = payload.get("pr_id")
    repo = payload.get("repo")
    pr_number = payload.get("pr_number")
    head_sha = payload.get("head_sha")
    base_sha = payload.get("base_sha")
    installation_id = payload.get("installation_id")
    
    if not all([pr_id, repo, pr_number, head_sha, installation_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")
        
    # Process asynchronously to free up Celery worker faster, or just block?
    # Actually, Celery is waiting for this to finish to mark it completed.
    # So we should block here and await run_review_workflow if celery expects synchronous completion.
    # The prompt says: "POST to Orchestrator... On success -> update status = completed."
    # So yes, we await it directly.
    await run_review_workflow(pr_id, repo, pr_number, head_sha, base_sha, installation_id)
    
    return {"status": "success"}
