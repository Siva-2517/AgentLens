"""Structured operational logging and secret redaction filter (Phase 20C).

Provides:
- Standardized operational log records with correlation ID, timestamp, component, and level.
- Logging filter that redacts API keys, JWTs, database URLs, and Redis passwords on all log outputs,
  including exception tracebacks and formatted message arguments.
- ContextVar storage for request correlation IDs.
"""

import contextvars
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.redaction import mask_sensitive_text

# ContextVar for propagating correlation/request ID across async task boundaries
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)


def get_correlation_id() -> str:
    """Retrieve current async context correlation ID."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current async context."""
    correlation_id_ctx.set(correlation_id)


class RedactingFilter(logging.Filter):
    """Logging filter that ensures sensitive tokens and credentials never reach log sinks."""

    def filter(self, record: logging.LogRecord) -> bool:
        # 1. Redact message string
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_text(record.msg)
        elif record.msg is not None:
            record.msg = mask_sensitive_text(str(record.msg))

        # 2. Redact tuple/dict arguments if formatted later
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_text(a) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: mask_sensitive_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }

        # 3. Redact exception text if pre-rendered
        if record.exc_text:
            record.exc_text = mask_sensitive_text(record.exc_text)

        # 4. Attach correlation ID to record for formatters
        if not hasattr(record, "correlation_id") or record.correlation_id == "-":
            record.correlation_id = get_correlation_id()

        return True


class StructuredJsonFormatter(logging.Formatter):
    """Structured JSON formatter for production operational monitoring."""

    def __init__(self, service_name: str = "agentlens-api"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Ensure redacting filter logic ran
        message = record.getMessage()
        masked_message = mask_sensitive_text(message)

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "component": record.name,
            "correlation_id": getattr(record, "correlation_id", get_correlation_id()),
            "message": masked_message,
        }

        if record.exc_info:
            exc_str = "".join(traceback.format_exception(*record.exc_info))
            log_data["exception"] = mask_sensitive_text(exc_str)
        elif record.exc_text:
            log_data["exception"] = mask_sensitive_text(record.exc_text)

        return json.dumps(log_data)


def configure_logging(service_name: str = "agentlens-api", json_format: Optional[bool] = None) -> None:
    """Configure root and application loggers with redaction and structured formatting."""
    is_prod = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
    use_json = json_format if json_format is not None else is_prod

    root_logger = logging.getLogger()
    redactor = RedactingFilter()

    # Add redactor filter to all existing handlers
    for handler in root_logger.handlers:
        handler.addFilter(redactor)
        if use_json:
            handler.setFormatter(StructuredJsonFormatter(service_name=service_name))

    # Also attach redactor to app logger hierarchy
    app_logger = logging.getLogger("app")
    app_logger.addFilter(redactor)
