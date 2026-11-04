"""Sanitized, request-scoped diagnostics for purchase proposal generation."""
from contextvars import ContextVar
import logging


proposal_correlation_id: ContextVar[str | None] = ContextVar("proposal_correlation_id", default=None)
logger = logging.getLogger("intentra.proposal_diagnostics")


def log(event: str, *, provider_mode: str, stage: str, elapsed_ms: int | None = None,
        error_code: str | None = None, **fields: object) -> None:
    """Log allowlisted metadata only; callers must never pass request or model data."""
    extra: dict[str, object] = {
        "event_name": event,
        "correlation_id": proposal_correlation_id.get(),
        "provider_mode": provider_mode,
        "stage": stage,
    }
    if elapsed_ms is not None:
        extra["elapsed_ms"] = elapsed_ms
    if error_code is not None:
        extra["error_code"] = error_code
    extra.update(fields)
    logger.info(event, extra=extra)
