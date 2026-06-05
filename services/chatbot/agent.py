import asyncio
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from shared.config.settings import get_settings
from shared.db.models import PullRequest, Finding, StylePattern
from shared.db.session import get_db_context

@tool
def get_recent_prs(repo_full_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch the most recent Pull Requests for a given repository."""
    async def _run():
        async with get_db_context() as db:
            stmt = select(PullRequest).where(
                PullRequest.repo_full_name == repo_full_name
            ).order_by(PullRequest.created_at.desc()).limit(limit)
            result = await db.execute(stmt)
            prs = result.scalars().all()
            return [
                {
                    "pr_number": pr.pr_number,
                    "status": pr.status.value,
                    "author": pr.author,
                    "created_at": pr.created_at.isoformat()
                } for pr in prs
            ]
    return asyncio.run(_run())

@tool
def get_pr_findings(repo_full_name: str, pr_number: int) -> List[Dict[str, Any]]:
    """Fetch all AI review findings for a specific Pull Request."""
    async def _run():
        async with get_db_context() as db:
            # First get the PR
            stmt = select(PullRequest).where(
                PullRequest.repo_full_name == repo_full_name,
                PullRequest.pr_number == pr_number
            ).options(selectinload(PullRequest.findings))
            result = await db.execute(stmt)
            pr = result.scalar_one_or_none()
            
            if not pr:
                return [{"error": f"PR {pr_number} not found in repository {repo_full_name}"}]
                
            return [
                {
                    "file": f.file_path,
                    "line": f.line_number,
                    "severity": f.severity.value,
                    "message": f.message,
                    "suggestion": f.suggestion
                } for f in pr.findings
            ]
    return asyncio.run(_run())

@tool
def get_style_patterns(repo_full_name: str) -> List[Dict[str, Any]]:
    """Fetch the code style patterns the AI has learned for a repository."""
    async def _run():
        async with get_db_context() as db:
            stmt = select(StylePattern).where(
                StylePattern.repo_full_name == repo_full_name
            ).order_by(StylePattern.frequency.desc()).limit(20)
            result = await db.execute(stmt)
            patterns = result.scalars().all()
            return [
                {
                    "pattern_type": p.pattern_type,
                    "description": p.description,
                    "frequency": p.frequency
                } for p in patterns
            ]
    return asyncio.run(_run())

def get_chatbot_agent():
    """Initialize the LangGraph agent with our database tools."""
    settings = get_settings()
    llm_kwargs = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.2,
        "api_key": settings.OPENAI_API_KEY,
    }
    if settings.OPENAI_API_BASE:
        llm_kwargs["base_url"] = settings.OPENAI_API_BASE
        
    llm = ChatOpenAI(**llm_kwargs)
    
    tools = [get_recent_prs, get_pr_findings, get_style_patterns]
    
    system_prompt = "You are the AI-PR-Reviewer Chatbot. You can help users query their database for past pull requests, AI review findings, and learned coding style patterns. Always format your responses clearly in Markdown."
    
    agent_executor = create_react_agent(llm, tools, prompt=system_prompt)
    return agent_executor
