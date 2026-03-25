import logging
import os


def configure_logging() -> None:
    """Configura logging central una sola vez para toda la app."""
    if logging.getLogger().handlers:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def log_operation(
    logger: logging.Logger,
    operation: str,
    success: bool,
    error_code: str | None = None,
    details: str | None = None,
) -> None:
    """Registra resultado de operación con contexto estándar."""
    status = "success" if success else "failure"
    parts = [f"operation={operation}", f"status={status}"]
    if error_code:
        parts.append(f"error_code={error_code}")
    if details:
        parts.append(f"details={details}")

    message = " | ".join(parts)
    if success:
        logger.info(message)
    else:
        logger.error(message)