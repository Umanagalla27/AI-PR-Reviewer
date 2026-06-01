from agents.state import ReviewState
from agents.utils import call_llm
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel

SECURITY_SYSTEM_PROMPT = """You are a Security Code Review Agent.
Your task is to analyze the provided diff for OWASP Top 10 vulnerabilities.
Focus on:
- A01 Broken Access Control
- A02 Cryptographic Failures (hardcoded secrets, weak algorithms)
- A03 Injection (SQL, command, path traversal)
- A05 Security Misconfiguration
- A07 Auth failures
- A09 Logging failures (sensitive data in logs)

Respond with a JSON object containing a "findings" array. Each item must have:
- file_path (string)
- line_number (integer or null)
- severity ("error", "warning", "info", "suggestion")
- owasp_category (string)
- message (string)
- suggestion (string or null)
"""

async def security_agent(state: ReviewState) -> dict:
    """Security analysis agent node."""
    diff = state["diff"]
    if not diff.strip():
        return {"security_findings": []}
        
    user_content = f"Please review this diff for security issues:\n\n{diff}"
    
    result = await call_llm(
        agent_name="security",
        system_prompt=SECURITY_SYSTEM_PROMPT,
        user_content=user_content,
        trace_id=state.get("langfuse_trace_id", "")
    )
    
    findings = []
    for item in result.get("findings", []):
        owasp = item.get("owasp_category", "")
        msg = item.get("message", "No message provided")
        if owasp:
            msg = f"[{owasp}] {msg}"
            
        findings.append(
            FindingCreate(
                agent="security",
                file_path=item.get("file_path", "unknown"),
                line_number=item.get("line_number"),
                severity=SeverityLevel(item.get("severity", "warning")),
                message=msg,
                suggestion=item.get("suggestion")
            )
        )
        
    return {"security_findings": findings}
