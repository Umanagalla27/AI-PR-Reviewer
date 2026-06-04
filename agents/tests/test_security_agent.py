"""Tests for the security agent node."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_security_agent_parses_findings(sample_state, mock_openai_client):
    """Security agent should parse findings with OWASP categories."""
    client, make_response = mock_openai_client

    findings_json = json.dumps(
        {
            "findings": [
                {
                    "file": "app/main.py",
                    "line": 8,
                    "severity": "error",
                    "message": "Command injection vulnerability",
                    "suggestion": "Use shlex.quote or pass arguments as a list",
                    "owasp_category": "A03: Injection",
                },
                {
                    "file": "app/main.py",
                    "line": 9,
                    "severity": "error",
                    "message": "Hardcoded password detected",
                    "suggestion": "Use environment variables for secrets",
                    "owasp_category": "A02: Cryptographic Failures",
                },
            ]
        }
    )

    client.chat.completions.create.return_value = make_response(findings_json)

    from agents.security_agent import security_agent

    result = await security_agent(sample_state)

    assert len(result["security_findings"]) == 2
    assert result["security_findings"][0].agent == "security"
    # OWASP category should be prepended to the message
    assert "A03: Injection" in result["security_findings"][0].message
    assert "A02: Cryptographic Failures" in result["security_findings"][1].message


@pytest.mark.asyncio
async def test_security_agent_handles_no_vulnerabilities(
    sample_state, mock_openai_client
):
    """Security agent should return empty list when no vulnerabilities found."""
    client, make_response = mock_openai_client
    client.chat.completions.create.return_value = make_response('{"findings": []}')

    from agents.security_agent import security_agent

    result = await security_agent(sample_state)

    assert result["security_findings"] == []
