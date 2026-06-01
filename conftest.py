"""
Shared test fixtures for service tests.

Provides test configuration, mock clients, and database fixtures.
"""

from __future__ import annotations

import os

# Set test environment BEFORE any imports that load settings
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["GITHUB_APP_ID"] = "12345"
os.environ["GITHUB_APP_PRIVATE_KEY"] = "test-private-key"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["WEBHOOK_SERVICE_URL"] = "http://localhost:8001"
os.environ["ORCHESTRATOR_URL"] = "http://localhost:8002"
os.environ["REVIEWER_URL"] = "http://localhost:8003"
os.environ["LEARNER_URL"] = "http://localhost:8004"
