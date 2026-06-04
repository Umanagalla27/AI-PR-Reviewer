"""
Test fixtures for the agents test suite.

Provides mock OpenAI client and sample review state data.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment variables before importing settings
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("GITHUB_APP_ID", "12345")
os.environ.setdefault("GITHUB_APP_PRIVATE_KEY", "test-key")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")


@pytest.fixture
def sample_diff():
    """Sample unified diff for testing."""
    return """diff --git a/app/main.py b/app/main.py
index abc1234..def5678 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,5 +1,10 @@
+import os
+import subprocess
 from fastapi import FastAPI
 
 app = FastAPI()
 
+@app.get("/run")
+def run_command(cmd: str):
+    result = subprocess.run(cmd, shell=True, capture_output=True)
+    password = "admin123"
+    return {"output": result.stdout.decode()}
"""


@pytest.fixture
def sample_state(sample_diff):
    """Sample ReviewState for testing agent nodes."""
    return {
        "repo": "owner/test-repo",
        "pr_number": 42,
        "head_sha": "abc1234567890abcdef1234567890abcdef123456",
        "diff": sample_diff,
        "file_hunks": [],
        "style_patterns": [],
        "static_findings": [],
        "security_findings": [],
        "style_findings": [],
        "arch_findings": [],
        "merged_findings": [],
        "langfuse_trace_id": "test-trace-id",
    }


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""

    def _make_response(content: str):
        mock_message = MagicMock()
        mock_message.content = content

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        return mock_response

    return _make_response


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Patch the OpenAI AsyncClient and Langfuse for testing."""
    with (
        patch("agents.utils.client") as mock_client,
        patch("agents.utils.langfuse") as mock_langfuse,
    ):
        mock_client.chat.completions.create = AsyncMock()
        mock_langfuse.generation = MagicMock()
        yield mock_client, mock_openai_response
