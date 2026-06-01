"""Tests for the style agent node."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_style_agent_with_patterns(sample_state, mock_openai_client):
    """Style agent should incorporate loaded patterns into its review."""
    client, make_response = mock_openai_client

    # Add style patterns to state
    sample_state["style_patterns"] = [
        {
            "pattern_type": "naming_convention",
            "description": "Use snake_case for function names",
            "frequency": 10,
        },
    ]

    findings_json = json.dumps({
        "findings": [
            {
                "file": "app/main.py",
                "line": 7,
                "severity": "suggestion",
                "message": "Function name should use snake_case",
                "suggestion": "Rename 'runCommand' to 'run_command'"
            }
        ]
    })

    client.chat.completions.create.return_value = make_response(findings_json)

    from agents.style_agent import style_review_node
    result = await style_review_node(sample_state)

    assert len(result["style_findings"]) == 1
    assert result["style_findings"][0]["agent"] == "style"


@pytest.mark.asyncio
async def test_style_agent_without_patterns(sample_state, mock_openai_client):
    """Style agent should work without learned patterns."""
    client, make_response = mock_openai_client
    sample_state["style_patterns"] = []

    client.chat.completions.create.return_value = make_response('{"findings": []}')

    from agents.style_agent import style_review_node
    result = await style_review_node(sample_state)

    assert result["style_findings"] == []
