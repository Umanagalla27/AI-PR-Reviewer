from agents.state import ReviewState
from agents.utils import call_llm
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel
import json

STYLE_SYSTEM_PROMPT = """You are a Code Style and Conventions Review Agent.
Your task is to analyze the provided diff for styling and convention issues.
You must use the provided repository-specific style patterns as reference.
Focus on:
- Adherence to loaded repo StylePatterns
- Naming conventions (functions, classes, variables)
- Docstring presence and format
- Line length, blank lines
- Import ordering

Respond with a JSON object containing a "findings" array. Each item must have:
- file_path (string)
- line_number (integer or null)
- severity ("error", "warning", "info", "suggestion")
- message (string)
- suggestion (string or null)
"""

async def style_agent(state: ReviewState) -> dict:
    """Style and convention analysis agent node."""
    diff = state["diff"]
    if not diff.strip():
        return {"style_findings": []}
        
    patterns = state.get("style_patterns", [])
    patterns_str = json.dumps(patterns, indent=2)
    
    user_content = f"Repo Style Patterns:\n{patterns_str}\n\nPlease review this diff for style issues:\n\n{diff}"
    
    result = await call_llm(
        agent_name="style",
        system_prompt=STYLE_SYSTEM_PROMPT,
        user_content=user_content,
        trace_id=state.get("langfuse_trace_id", "")
    )
    
    findings = []
    for item in result.get("findings", []):
        findings.append(
            FindingCreate(
                agent="style",
                file_path=item.get("file_path", "unknown"),
                line_number=item.get("line_number"),
                severity=SeverityLevel(item.get("severity", "info")),
                message=item.get("message", "No message provided"),
                suggestion=item.get("suggestion")
            )
        )
        
    return {"style_findings": findings}
