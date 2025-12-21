"""Utility functions for date and time operations."""

import requests
from datetime import datetime
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger()


def get_current_datetime_online(fallback_to_local: bool = True) -> datetime:
    """
    Get the current date and time from an online source.

    This function fetches the current time from worldtimeapi.org to ensure
    accuracy regardless of local system time settings.

    Args:
        fallback_to_local: If True, use local system time if online fetch fails

    Returns:
        datetime: Current datetime

    Raises:
        RuntimeError: If online fetch fails and fallback_to_local is False
    """
    try:
        # Use worldtimeapi.org for accurate current time (Europe/London for UK)
        response = requests.get(
            "http://worldtimeapi.org/api/timezone/Europe/London",
            timeout=5
        )
        response.raise_for_status()

        data = response.json()
        datetime_str = data.get('datetime')

        if datetime_str:
            # Parse ISO format datetime
            current_dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            logger.info(f"Retrieved current time from online source: {current_dt.isoformat()}")
            return current_dt
        else:
            raise ValueError("No datetime field in API response")

    except Exception as e:
        logger.warning(f"Failed to get current time from online source: {e}")

        if fallback_to_local:
            logger.info("Falling back to local system time")
            return datetime.now()
        else:
            raise RuntimeError(f"Failed to get current time online: {e}")


def get_current_date_str(format: str = "%Y-%m-%d") -> str:
    """
    Get the current date as a formatted string.

    Args:
        format: Date format string (default: YYYY-MM-DD)

    Returns:
        str: Formatted date string
    """
    try:
        current_dt = get_current_datetime_online()
        return current_dt.strftime(format)
    except Exception as e:
        logger.error(f"Failed to get current date: {e}")
        return datetime.now().strftime(format)


def parse_document_date(date_str: str) -> Optional[datetime]:
    """
    Parse a document date string to datetime object.

    Supports multiple date formats:
    - ISO format: 2024-12-21T10:00:00
    - Date only: 2024-12-21
    - UK format: 21/12/2024

    Args:
        date_str: Date string to parse

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    # Try different date formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",  # ISO with time
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
        "%Y-%m-%d",  # ISO date only
        "%d/%m/%Y",  # UK format
        "%d-%m-%Y",  # UK format with dashes
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.split('+')[0].split('Z')[0], fmt)
        except ValueError:
            continue

    logger.warning(f"Could not parse date string: {date_str}")
    return None


def is_document_outdated(document_date: str, days_threshold: int = 365) -> bool:
    """
    Check if a document is outdated based on its date.

    Args:
        document_date: Document date string
        days_threshold: Number of days before document is considered outdated

    Returns:
        bool: True if document is outdated
    """
    try:
        doc_dt = parse_document_date(document_date)
        if not doc_dt:
            return False

        current_dt = get_current_datetime_online()
        days_old = (current_dt - doc_dt).days

        return days_old > days_threshold

    except Exception as e:
        logger.warning(f"Failed to check if document is outdated: {e}")
        return False


def format_date_for_display(date_str: str, format: str = "%d %B %Y") -> str:
    """
    Format a date string for user-friendly display.

    Args:
        date_str: Date string to format
        format: Output format (default: "21 December 2024")

    Returns:
        str: Formatted date or original string if parsing fails
    """
    try:
        dt = parse_document_date(date_str)
        if dt:
            return dt.strftime(format)
        return date_str
    except Exception:
        return date_str
