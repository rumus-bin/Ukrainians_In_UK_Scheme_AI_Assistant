"""Response formatting for Telegram messages."""

from typing import List
import re

from src.agents.base_agent import AgentResponse
from src.utils.logger import get_logger

logger = get_logger()


class ResponseFormatter:
    """Formats agent responses for Telegram display."""

    # Maximum message length for Telegram
    MAX_MESSAGE_LENGTH = 4096

    # Maximum length before splitting (leave room for formatting)
    SPLIT_THRESHOLD = 3800

    def format(self, response: AgentResponse) -> str:
        """
        Format agent response for Telegram.

        Args:
            response: AgentResponse to format

        Returns:
            Formatted message string
        """
        try:
            formatted_text = response.text

            # Ensure proper emoji formatting (add spaces if needed)
            formatted_text = self._format_emojis(formatted_text)

            # Ensure proper line breaks
            formatted_text = self._format_line_breaks(formatted_text)

            # Add source attribution if not already present
            if response.sources and not self._has_source_links(formatted_text):
                formatted_text += self._format_sources(response.sources)

            # Check length and split if needed
            if len(formatted_text) > self.SPLIT_THRESHOLD:
                logger.warning(f"Response too long ({len(formatted_text)} chars), truncating")
                formatted_text = self._truncate_message(formatted_text)

            return formatted_text

        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            # Return original text if formatting fails
            return response.text

    def _format_emojis(self, text: str) -> str:
        """
        Ensure emojis have proper spacing.

        Args:
            text: Text with emojis

        Returns:
            Formatted text
        """
        # Add space after emoji if not present (for readability)
        # Pattern: emoji followed by letter without space
        text = re.sub(r'([😀-🙏💀-🛔])([А-Яа-яA-Za-z])', r'\1 \2', text)

        return text

    def _format_line_breaks(self, text: str) -> str:
        """
        Ensure proper line breaks for readability.

        Args:
            text: Text to format

        Returns:
            Formatted text
        """
        # Replace multiple newlines with max 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Ensure sections have proper spacing
        # Pattern: emoji section header without preceding newline
        text = re.sub(r'([^\n])([📋🏠💼🔗⚠️💡📝📞])', r'\1\n\n\2', text)

        return text

    def _has_source_links(self, text: str) -> bool:
        """
        Check if text already has source links section.

        Args:
            text: Text to check

        Returns:
            True if source links present
        """
        return bool(re.search(r'🔗.*(?:джерел|посилан)', text, re.IGNORECASE))

    def _format_sources(self, sources: List[dict]) -> str:
        """
        Format sources as attribution section.

        Args:
            sources: List of source dictionaries

        Returns:
            Formatted sources text
        """
        if not sources:
            return ""

        source_text = "\n\n🔗 Джерела:\n"

        # Extract unique URLs from sources
        urls = set()

        for source in sources:
            metadata = source.get("metadata", {})
            url = metadata.get("url", "")

            if url and url not in urls:
                urls.add(url)
                title = metadata.get("title", "")
                source_name = metadata.get("source", "")

                if title:
                    source_text += f"• {title}: {url}\n"
                elif source_name:
                    source_text += f"• {source_name}: {url}\n"
                else:
                    source_text += f"• {url}\n"

        # If no URLs found, don't add sources section
        if len(urls) == 0:
            return ""

        return source_text

    def _truncate_message(self, text: str) -> str:
        """
        Truncate message to fit Telegram limits.

        Args:
            text: Text to truncate

        Returns:
            Truncated text
        """
        if len(text) <= self.SPLIT_THRESHOLD:
            return text

        # Find a good break point (end of sentence or paragraph)
        truncate_point = self.SPLIT_THRESHOLD

        # Try to find last sentence break before limit
        last_period = text.rfind('.', 0, self.SPLIT_THRESHOLD)
        last_newline = text.rfind('\n', 0, self.SPLIT_THRESHOLD)

        break_point = max(last_period, last_newline)

        if break_point > self.SPLIT_THRESHOLD * 0.8:  # At least 80% of limit
            truncate_point = break_point + 1

        truncated = text[:truncate_point]

        # Add continuation notice
        truncated += "\n\n...(повідомлення скорочено через обмеження довжини)"

        return truncated

    def format_error(self, error_type: str = "general") -> str:
        """
        Format error message.

        Args:
            error_type: Type of error

        Returns:
            Formatted error message
        """
        error_messages = {
            "ollama_unavailable": (
                "⚠️ Система тимчасово недоступна.\n\n"
                "Спробуйте пізніше або зверніться до /help"
            ),
            "rag_failure": (
                "⚠️ Не вдалося знайти інформацію з бази знань.\n\n"
                "Спробуйте переформулювати питання або відвідайте:\n"
                "• gov.uk\n"
                "• opora.uk"
            ),
            "timeout": (
                "⚠️ Обробка запиту займає довше, ніж очікувалося.\n\n"
                "Спробуйте:\n"
                "• Зробити питання коротшим\n"
                "• Спробувати пізніше"
            ),
            "general": (
                "⚠️ Вибачте, сталася помилка.\n\n"
                "Використайте /help або зверніться до адміністратора."
            )
        }

        return error_messages.get(error_type, error_messages["general"])


# Singleton instance
_formatter = None


def get_response_formatter() -> ResponseFormatter:
    """Get or create the global response formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = ResponseFormatter()
    return _formatter
