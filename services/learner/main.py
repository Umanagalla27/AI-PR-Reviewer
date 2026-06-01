import json
from fastapi import FastAPI, Request, HTTPException
from starlette_prometheus import metrics, PrometheusMiddleware
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from shared.config.settings import settings
from shared.observability import logger, RequestIdMiddleware
from shared.github_client.api import get_pr_diff
from shared.db.session import get_db_session
from shared.db.models import PullRequest, Finding, StylePattern
from openai import AsyncOpenAI
import uuid

app = FastAPI(title="Learner Service")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "learner"}

async def extract_patterns(diff: str, findings: list) -> list:
    if not diff.strip() or not findings:
        return []
        
    findings_str = json.dumps([{"agent": f.agent, "message": f.message, "severity": f.severity} for f in findings])
    
    prompt = f"""You are a Code Style Extraction Agent.
Given these review findings and the accepted diff, what recurring code style patterns does this repo follow or violate?
Extract structured patterns.

Review Findings:
{findings_str}

Diff:
{diff}

Respond with a JSON array of objects, each containing:
- pattern_type (string, e.g. "naming_convention", "error_handling")
- description (string)
"""
    
    try:
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data.get("patterns", data.get("findings", [])) # Handle potential key names
    except Exception as e:
        logger.error("failed_to_extract_patterns", error=str(e))
        return []

@app.post("/learn/merged-pr")
async def learn_merged_pr(request: Request):
    payload = await request.json()
    repo = payload.get("repo_full_name")
    pr_number = payload.get("pr_number")
    installation_id = payload.get("installation_id")
    
    if not all([repo, pr_number, installation_id]):
        raise HTTPException(status_code=400, detail="Missing fields")
        
    async with get_db_session() as session:
        # 1. Fetch Findings
        stmt = select(PullRequest).options(selectinload(PullRequest.findings)).where(
            PullRequest.repo_full_name == repo,
            PullRequest.pr_number == pr_number
        ).order_by(PullRequest.created_at.desc())
        
        result = await session.execute(stmt)
        pr = result.scalars().first()
        
        if not pr:
            logger.warning("pr_not_found_for_learning", repo=repo, pr_number=pr_number)
            return {"status": "skipped", "reason": "PR not found in DB"}
            
        findings = pr.findings
        
        # 2. Fetch Diff
        try:
            diff = await get_pr_diff(repo, pr_number, installation_id)
        except Exception as e:
            logger.error("failed_to_fetch_diff", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to fetch diff")
            
        # 3. Extract Patterns
        patterns = await extract_patterns(diff, findings)
        
        # 4. Upsert Patterns
        for pat in patterns:
            ptype = pat.get("pattern_type")
            desc = pat.get("description")
            if not ptype or not desc:
                continue
                
            # Check if exists
            stmt_pat = select(StylePattern).where(
                StylePattern.repo_full_name == repo,
                StylePattern.pattern_type == ptype
            )
            res_pat = await session.execute(stmt_pat)
            existing = res_pat.scalar_one_or_none()
            
            if existing:
                existing.frequency += 1
                existing.description = desc # update with latest description
            else:
                new_pat = StylePattern(
                    id=uuid.uuid4(),
                    repo_full_name=repo,
                    pattern_type=ptype,
                    description=desc,
                    frequency=1
                )
                session.add(new_pat)
                
        await session.commit()
        
    return {"status": "success", "patterns_extracted": len(patterns)}
