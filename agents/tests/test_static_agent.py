"""Tests for the static analysis agent node."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_static_agent_parses_findings(sample_state, mock_openai_client):
    """Static agent should parse GPT JSON response into structured findings."""
    client, make_response = mock_openai_client

    findings_json = json.dumps({
        "findings": [
            {
                "file": "app/main.py",
                "line": 8,
                "severity": "warning",
                "message": "Unused import: os",
                "suggestion": "Remove the unused import"
            },
            {
                "file": "app/main.py",
                "line": 10,
                "severity": "error",
                "message": "subprocess.run with shell=True is dangerous",
                "suggestion": "Use a list of arguments instead"
            }
        ]
    })

    client.chat.completions.create.return_value = make_response(findings_json)

    from agents.static_agent import static_analysis_node
    result = await static_analysis_node(sample_state)

    assert "static_findings" in result
    assert len(result["static_findings"]) == 2
    assert result["static_findings"][0]["agent"] == "static"
    assert result["static_findings"][0]["file_path"] == "app/main.py"
    assert result["static_findings"][0]["severity"] == "warning"
    assert result["static_findings"][1]["severity"] == "error"


@pytest.mark.asyncio
async def test_static_agent_handles_empty_response(sample_state, mock_openai_client):
    """Static agent should return empty findings on empty LLM response."""
    client, make_response = mock_openai_client
    client.chat.completions.create.return_value = make_response('{"findings": []}')

    from agents.static_agent import static_analysis_node
    result = await static_analysis_node(sample_state)

    assert result["static_findings"] == []


@pytest.mark.asyncio
async def test_static_agent_handles_malformed_json(sample_state, mock_openai_client):
    """Static agent should gracefully handle malformed JSON from LLM."""
    client, make_response = mock_openai_client
    client.chat.completions.create.return_value = make_response("not valid json {{{")

    from agents.static_agent import static_analysis_node
    result = await static_analysis_node(sample_state)

    # Should return empty findings, not crash
    assert result["static_findings"] == []


@pytest.mark.asyncio
async def test_static_agent_handles_api_error(sample_state, mock_openai_client):
    """Static agent should handle OpenAI API errors gracefully."""
    client, _ = mock_openai_client
    client.chat.completions.create.side_effect = Exception("API rate limit")

    from agents.static_agent import static_analysis_node
    result = await static_analysis_node(sample_state)

    assert result["static_findings"] == []
