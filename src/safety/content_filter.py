"""Content filtering for spam and inappropriate content."""

import re
from typing import Tuple

from src.utils.logger import get_logger

logger = get_logger()


class ContentFilter:
    """Filters inappropriate or off-topic content."""

    # Patterns that might indicate spam
    SPAM_PATTERNS = [
        r"(buy|cheap|discount|sale|offer).*\$\d+",
        r"click here.*http",
        r"http://bit\.ly",
        r"free money",
        r"win \$",
        r"urgent.*click",
    ]

    # Maximum allowed message length
    MAX_MESSAGE_LENGTH = 4096  # Telegram limit

    # Maximum query length for processing
    MAX_QUERY_LENGTH = 500

    def is_spam(self, text: str) -> bool:
        """
        Check if message is spam.

        Args:
            text: Message text

        Returns:
            True if spam detected
        """
        text_lower = text.lower()

        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text_lower):
                logger.warning(f"Spam pattern detected: {pattern}")
                return True

        return False

    def is_appropriate(self, text: str) -> Tuple[bool, str]:
        """
        Check if content is appropriate.

        Args:
            text: Message text

        Returns:
            Tuple of (is_appropriate, reason)
        """
        # Check spam
        if self.is_spam(text):
            return False, "spam_detected"

        # Check length
        if len(text) > self.MAX_MESSAGE_LENGTH:
            return False, "message_too_long"

        # Check if empty
        if not text or not text.strip():
            return False, "empty_message"

        # All checks passed
        return True, ""

    def validate_query(self, text: str) -> Tuple[bool, str]:
        """
        Validate query for processing.

        Args:
            text: Query text

        Returns:
            Tuple of (is_valid, error_message)
        """
        is_appropriate, reason = self.is_appropriate(text)

        if not is_appropriate:
            if reason == "spam_detected":
                return False, "Spam detected"
            elif reason == "message_too_long":
                return False, f"Message too long (max {self.MAX_MESSAGE_LENGTH} characters)"
            elif reason == "empty_message":
                return False, "Empty message"
            else:
                return False, "Invalid content"

        # Check query length for processing
        if len(text) > self.MAX_QUERY_LENGTH:
            logger.warning(f"Query too long for optimal processing: {len(text)} chars")
            # Still allow, but log warning

        return True, ""


# Singleton instance
_content_filter = None


def get_content_filter() -> ContentFilter:
    """Get or create the global content filter instance."""
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter
