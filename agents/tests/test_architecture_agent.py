"""Tests for the architecture agent node."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_architecture_agent_parses_findings(sample_state, mock_openai_client):
    """Architecture agent should parse design/SOLID findings."""
    client, make_response = mock_openai_client

    findings_json = json.dumps(
        {
            "findings": [
                {
                    "file": "app/main.py",
                    "line": 7,
                    "severity": "warning",
                    "message": "Function handles both command execution and response formatting (SRP violation)",
                    "suggestion": "Separate command execution from response formatting",
                }
            ]
        }
    )

    client.chat.completions.create.return_value = make_response(findings_json)

    from agents.architecture_agent import architecture_agent

    result = await architecture_agent(sample_state)

    assert len(result["arch_findings"]) == 1
    assert result["arch_findings"][0].agent == "architecture"
    assert "SRP" in result["arch_findings"][0].message
