from agents.state import ReviewState
from agents.utils import call_llm
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel

ARCH_SYSTEM_PROMPT = """You are an Architecture and Design Code Review Agent.
Your task is to analyze the provided diff for architectural anti-patterns.
Focus on:
- SOLID principles violations
- Layering violations (e.g., DB calls in controllers)
- God classes / functions doing too much
- Missing abstractions / hardcoded dependencies
- Circular dependency risks

Respond with a JSON object containing a "findings" array. Each item must have:
- file_path (string)
- line_number (integer or null)
- severity ("error", "warning", "info", "suggestion")
- message (string)
- suggestion (string or null)
"""

async def architecture_agent(state: ReviewState) -> dict:
    """Architecture analysis agent node."""
    diff = state["diff"]
    if not diff.strip():
        return {"arch_findings": []}
        
    user_content = f"Please review this diff for architecture/design issues:\n\n{diff}"
    
    result = await call_llm(
        agent_name="architecture",
        system_prompt=ARCH_SYSTEM_PROMPT,
        user_content=user_content,
        trace_id=state.get("langfuse_trace_id", "")
    )
    
    findings = []
    for item in result.get("findings", []):
        findings.append(
            FindingCreate(
                agent="architecture",
                file_path=item.get("file_path", "unknown"),
                line_number=item.get("line_number"),
                severity=SeverityLevel(item.get("severity", "info")),
                message=item.get("message", "No message provided"),
                suggestion=item.get("suggestion")
            )
        )
        
    return {"arch_findings": findings}
