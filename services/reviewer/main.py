import asyncio
import httpx
from fastapi import FastAPI, Request, HTTPException
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.config.settings import settings
from shared.observability import logger, RequestIdMiddleware
from shared.github_client.api import post_inline_comment, post_pr_summary
from shared.github_client.auth import get_installation_token
from openai import AsyncOpenAI

app = FastAPI(title="Reviewer Service")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_summary(findings: list) -> str:
    """Uses GPT-4o-mini to summarize the findings."""
    if not findings:
        return "## AI Code Review Summary\nNo issues found! Great job."
        
    findings_str = "\n".join([f"- [{f.get('severity')}] {f.get('agent')}: {f.get('message')}" for f in findings])
    
    prompt = f"""You are generating a Markdown summary for an AI code review.
Given these findings:
{findings_str}

Produce a markdown summary matching this structure:
## AI Code Review Summary
**N findings** across the PR
### By category: ...
### Critical issues: ...
### Suggestions: ...
"""
    
    response = await openai_client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "system", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

async def add_pr_label(repo: str, pr_number: int, installation_id: int, label: str):
    """Add a label to a PR."""
    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/labels"
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json={"labels": [label]})

@app.get("/health")
async def health():
    return {"status": "ok", "service": "reviewer"}

@app.post("/review/post")
async def post_review(request: Request):
    payload = await request.json()
    repo = payload.get("repo")
    pr_number = payload.get("pr_number")
    head_sha = payload.get("head_sha")
    installation_id = payload.get("installation_id")
    findings = payload.get("findings", [])
    
    # 1. Post inline comments
    for f in findings:
        line = f.get("line_number")
        if line:
            body = f"**[{f.get('severity').upper()}] {f.get('agent')} agent**\n{f.get('message')}"
            if f.get("suggestion"):
                body += f"\n\n💡 {f.get('suggestion')}"
                
            try:
                # We need the file path for inline comment
                path = f.get("file_path")
                await post_inline_comment(repo, pr_number, installation_id, head_sha, path, line, body)
                await asyncio.sleep(0.1) # 100ms delay for rate limit
            except Exception as e:
                logger.warning("failed_to_post_inline_comment", error=str(e), file=path, line=line)
                
    # 2. Generate and post summary
    summary_body = await generate_summary(findings)
    try:
        await post_pr_summary(repo, pr_number, installation_id, head_sha, summary_body)
    except Exception as e:
        logger.error("failed_to_post_summary", error=str(e))
        
    # 3. Add label
    try:
        await add_pr_label(repo, pr_number, installation_id, "ai-reviewed")
    except Exception as e:
        logger.warning("failed_to_add_label", error=str(e))
        
    return {"status": "success"}
