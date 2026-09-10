import logging

import structlog


def configure_logging() -> None:
    """Configure machine-readable logs enriched with request-scoped context."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


log = structlog.get_logger()
