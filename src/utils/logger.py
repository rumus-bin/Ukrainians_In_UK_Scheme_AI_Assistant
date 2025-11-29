"""Logging configuration using loguru."""

import sys
from pathlib import Path
from loguru import logger

from src.utils.config import get_settings


def setup_logger():
    """Configure application logging using loguru.

    Sets up both file and console logging based on configuration.
    """
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Console handler
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=console_format,
        level=settings.log_level,
        colorize=True,
    )

    # File handler
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.log_format == "json":
        file_format = "{message}"
        logger.add(
            log_path,
            format=file_format,
            level=settings.log_level,
            rotation=f"{settings.log_max_size_mb} MB",
            retention=settings.log_backup_count,
            serialize=True,  # JSON output
        )
    else:
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        )
        logger.add(
            log_path,
            format=file_format,
            level=settings.log_level,
            rotation=f"{settings.log_max_size_mb} MB",
            retention=settings.log_backup_count,
        )

    logger.info(f"Logger initialized with level: {settings.log_level}")
    logger.info(f"Logging to file: {log_path}")

    return logger


def get_logger():
    """Get the configured logger instance."""
    return logger