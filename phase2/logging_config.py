"""
phase2/logging_config.py
Unified structlog configuration for Agent-X.
Call configure_logging() once at pipeline entry point.
"""

import structlog


def configure_logging() -> None:
    """Configure structlog with JSON output and ISO timestamps."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


if __name__ == "__main__":
    configure_logging()
    log = structlog.get_logger()
    log.info("logging_config.smoke_test", status="ok")
    print("logging_config smoke test passed")
