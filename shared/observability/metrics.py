"""
Prometheus metrics definitions for the AI PR Review pipeline.

All metrics are defined centrally here and imported by individual services.
Each service exposes these at /metrics via starlette-prometheus middleware.
"""

from prometheus_client import Counter, Gauge, Histogram

# ─── Counters ────────────────────────────────────────────────────────────────

github_webhooks_received_total = Counter(
    "github_webhooks_received_total",
    "Total GitHub webhook events received",
    ["service", "status"],
)

pr_reviews_started_total = Counter(
    "pr_reviews_started_total",
    "Total PR reviews started",
    ["repo"],
)

pr_reviews_completed_total = Counter(
    "pr_reviews_completed_total",
    "Total PR reviews completed",
    ["repo", "status"],
)

agent_calls_total = Counter(
    "agent_calls_total",
    "Total AI agent invocations",
    ["agent", "status"],
)

github_api_requests_total = Counter(
    "github_api_requests_total",
    "Total GitHub API requests",
    ["endpoint", "status_code"],
)

# ─── Histograms ──────────────────────────────────────────────────────────────

pr_review_duration_seconds = Histogram(
    "pr_review_duration_seconds",
    "Duration of complete PR review pipeline",
    ["repo"],
    buckets=[5, 10, 30, 60, 120, 300, 600],
)

agent_latency_seconds = Histogram(
    "agent_latency_seconds",
    "Latency of individual AI agent calls",
    ["agent"],
    buckets=[1, 2, 5, 10, 30, 60],
)

github_api_latency_seconds = Histogram(
    "github_api_latency_seconds",
    "Latency of GitHub API requests",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10],
)

# ─── Gauges ──────────────────────────────────────────────────────────────────

celery_queue_depth = Gauge(
    "celery_queue_depth",
    "Number of tasks waiting in the Celery queue",
)

active_reviews_count = Gauge(
    "active_reviews_count",
    "Number of reviews currently in progress",
)
