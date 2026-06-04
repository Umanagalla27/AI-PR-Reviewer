import pytest
from agents.state import ReviewState
from agents.static_agent import static_agent
from agents.merger import merger_node
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_static_agent_empty_diff():
    state: ReviewState = {
        "repo": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc",
        "diff": " ",
        "file_hunks": [],
        "style_patterns": [],
        "static_findings": [],
        "security_findings": [],
        "style_findings": [],
        "arch_findings": [],
        "merged_findings": [],
        "langfuse_trace_id": "",
    }

    result = await static_agent(state)
    assert result["static_findings"] == []


@pytest.mark.asyncio
@patch("agents.static_agent.call_llm", new_callable=AsyncMock)
async def test_static_agent_with_findings(mock_call_llm):
    mock_call_llm.return_value = {
        "findings": [
            {
                "file_path": "main.py",
                "line_number": 10,
                "severity": "error",
                "message": "Undefined variable",
                "suggestion": "Define it",
            }
        ]
    }

    state: ReviewState = {
        "repo": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc",
        "diff": "some diff",
        "file_hunks": [],
        "style_patterns": [],
        "static_findings": [],
        "security_findings": [],
        "style_findings": [],
        "arch_findings": [],
        "merged_findings": [],
        "langfuse_trace_id": "",
    }

    result = await static_agent(state)
    findings = result["static_findings"]
    assert len(findings) == 1
    assert findings[0].file_path == "main.py"
    assert findings[0].severity == SeverityLevel.error


def test_merger_node_deduplication():
    f1 = FindingCreate(
        agent="static",
        file_path="main.py",
        line_number=10,
        severity=SeverityLevel.info,
        message="Use single quotes",
        suggestion=None,
    )

    # Duplicate of f1 but higher severity
    f2 = FindingCreate(
        agent="style",
        file_path="main.py",
        line_number=10,
        severity=SeverityLevel.warning,
        message="Use single quotes please",
        suggestion=None,
    )

    # Different finding
    f3 = FindingCreate(
        agent="security",
        file_path="auth.py",
        line_number=5,
        severity=SeverityLevel.error,
        message="Hardcoded secret",
        suggestion=None,
    )

    state: ReviewState = {
        "repo": "owner/repo",
        "pr_number": 1,
        "head_sha": "abc",
        "diff": "some diff",
        "file_hunks": [],
        "style_patterns": [],
        "static_findings": [f1],
        "security_findings": [f3],
        "style_findings": [f2],
        "arch_findings": [],
        "merged_findings": [],
        "langfuse_trace_id": "",
    }

    result = merger_node(state)
    merged = result["merged_findings"]

    assert len(merged) == 2
    # Ensure error is first
    assert merged[0].severity == SeverityLevel.error
    assert merged[0].file_path == "auth.py"

    # Ensure warning replaces info due to deduplication
    assert merged[1].severity == SeverityLevel.warning
    assert merged[1].agent == "style"
