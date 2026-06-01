"""
Langfuse tracing integration for LLM observability.

Provides helpers to create traces and generations for the LangGraph
review pipeline, tracking model usage, latency, and cost.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Lazy import to avoid ImportError when langfuse isn't configured
_langfuse_client = None


@lru_cache(maxsize=1)
def get_langfuse():
    """
    Get or create the Langfuse client singleton.

    Returns None if Langfuse credentials are not configured,
    allowing the system to run without tracing.
    """
    global _langfuse_client

    try:
        from langfuse import Langfuse
        from shared.config.settings import get_settings

        settings = get_settings()

        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            logger.info("langfuse_not_configured", msg="Langfuse tracing disabled")
            return None

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("langfuse_initialized", host=settings.langfuse_host)
        return _langfuse_client

    except Exception as exc:
        logger.warning("langfuse_init_error", error=str(exc))
        return None


def create_trace(
    name: str,
    metadata: dict[str, Any] | None = None,
    trace_id: str | None = None,
):
    """
    Create a Langfuse trace for a PR review run.

    Returns a trace object, or a no-op stub if Langfuse isn't configured.
    """
    client = get_langfuse()
    if client is None:
        return _NoOpTrace()

    kwargs: dict[str, Any] = {"name": name}
    if metadata:
        kwargs["metadata"] = metadata
    if trace_id:
        kwargs["id"] = trace_id

    return client.trace(**kwargs)


def create_generation(
    trace,
    name: str,
    model: str,
    input_data: Any,
    output_data: Any,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
):
    """
    Log an LLM generation within a trace.

    Tracks the model, prompt, response, and token usage.
    """
    if isinstance(trace, _NoOpTrace):
        return _NoOpGeneration()

    kwargs: dict[str, Any] = {
        "name": name,
        "model": model,
        "input": input_data,
        "output": output_data,
    }
    if usage:
        kwargs["usage"] = usage
    if metadata:
        kwargs["metadata"] = metadata

    return trace.generation(**kwargs)


class _NoOpTrace:
    """Stub trace object when Langfuse is not configured."""

    def generation(self, **kwargs):
        return _NoOpGeneration()

    def span(self, **kwargs):
        return self

    def end(self, **kwargs):
        pass


class _NoOpGeneration:
    """Stub generation object when Langfuse is not configured."""

    def end(self, **kwargs):
        pass
