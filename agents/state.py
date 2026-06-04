from typing import TypedDict, List, Dict, Any
from shared.schemas.finding import FindingCreate


class ReviewState(TypedDict):
    repo: str
    pr_number: int
    head_sha: str
    diff: str
    file_hunks: List[Dict[str, Any]]
    style_patterns: List[Dict[str, Any]]

    # Findings from each agent
    static_findings: List[FindingCreate]
    security_findings: List[FindingCreate]
    style_findings: List[FindingCreate]
    arch_findings: List[FindingCreate]

    # Final merged findings
    merged_findings: List[FindingCreate]

    # Langfuse tracing
    langfuse_trace_id: str
