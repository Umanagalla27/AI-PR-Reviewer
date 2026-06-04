from agents.state import ReviewState
from agents.utils import call_llm
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel

STATIC_SYSTEM_PROMPT = """You are a Static Analysis Code Review Agent.
Your task is to analyze the provided diff and identify static analysis issues.
Focus on:
- Undefined variables, unused imports
- Complexity (cyclomatic, nesting depth)
- Null/None dereference risks
- Type errors and mismatches
- Deprecated API usage

Respond with a JSON object containing a "findings" array. Each item must have:
- file_path (string)
- line_number (integer or null)
- severity ("error", "warning", "info", "suggestion")
- message (string)
- suggestion (string or null)
"""


async def static_agent(state: ReviewState) -> dict:
    """Static analysis agent node."""
    diff = state["diff"]
    if not diff.strip():
        return {"static_findings": []}

    user_content = f"Please review this diff for static analysis issues:\n\n{diff}"

    result = await call_llm(
        agent_name="static",
        system_prompt=STATIC_SYSTEM_PROMPT,
        user_content=user_content,
        trace_id=state.get("langfuse_trace_id", ""),
    )

    findings = []
    for item in result.get("findings", []):
        findings.append(
            FindingCreate(
                agent="static",
                file_path=item.get("file_path", "unknown"),
                line_number=item.get("line_number"),
                severity=SeverityLevel(item.get("severity", "info")),
                message=item.get("message", "No message provided"),
                suggestion=item.get("suggestion"),
            )
        )

    return {"static_findings": findings}
