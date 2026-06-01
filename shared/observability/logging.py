"""
Structured JSON logging via structlog.

Provides consistent, machine-parseable logs with context binding
for service name, request ID, repo, and PR number.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(service_name: str, log_level: str = "INFO") -> None:
    """
    Configure structlog for structured JSON logging.

    Call once at service startup. All subsequent structlog.get_logger()
    calls will produce JSON-formatted output with bound context.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Bind service name to all logs
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger, optionally bound to a module name."""
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    return logger
