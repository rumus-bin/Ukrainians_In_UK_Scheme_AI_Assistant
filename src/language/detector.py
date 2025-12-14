"""Language detection for user messages."""

from typing import Literal
import re

from src.utils.logger import get_logger

logger = get_logger()


class LanguageDetector:
    """Detects language of user messages (Ukrainian or Russian)."""

    # Ukrainian-specific characters that don't exist in Russian
    UKRAINIAN_CHARS = set("ґєії")

    # Russian-specific characters that don't exist in Ukrainian
    RUSSIAN_CHARS = set("ыэъё")

    # Common Ukrainian words
    UKRAINIAN_WORDS = {
        "як", "що", "де", "коли", "чому", "який", "яка", "які",
        "ви", "ти", "він", "вона", "вони", "ми", "я",
        "дякую", "будь ласка", "вітаю", "привіт",
        "може", "можу", "треба", "потрібно",
        "допоможіть", "допомогти", "зробити", "отримати"
    }

    # Common Russian words
    RUSSIAN_WORDS = {
        "как", "что", "где", "когда", "почему", "который", "которая", "которые",
        "вы", "ты", "он", "она", "они", "мы", "я",
        "спасибо", "пожалуйста", "привет",
        "может", "могу", "нужно", "надо",
        "помогите", "помочь", "сделать", "получить"
    }

    def detect(self, text: str) -> Literal["uk", "ru", "unknown"]:
        """
        Detect language of text.

        Args:
            text: Input text

        Returns:
            "uk" for Ukrainian, "ru" for Russian, "unknown" if unclear
        """
        if not text or not text.strip():
            return "unknown"

        text_lower = text.lower()

        # Method 1: Check for unique characters
        has_ukrainian_chars = any(char in text_lower for char in self.UKRAINIAN_CHARS)
        has_russian_chars = any(char in text_lower for char in self.RUSSIAN_CHARS)

        if has_ukrainian_chars and not has_russian_chars:
            logger.debug("Detected Ukrainian by characters")
            return "uk"

        if has_russian_chars and not has_ukrainian_chars:
            logger.debug("Detected Russian by characters")
            return "ru"

        # Method 2: Check for common words
        words = re.findall(r'\b\w+\b', text_lower)

        ukrainian_score = sum(1 for word in words if word in self.UKRAINIAN_WORDS)
        russian_score = sum(1 for word in words if word in self.RUSSIAN_WORDS)

        logger.debug(f"Word scores - Ukrainian: {ukrainian_score}, Russian: {russian_score}")

        if ukrainian_score > russian_score:
            logger.debug("Detected Ukrainian by words")
            return "uk"

        if russian_score > ukrainian_score:
            logger.debug("Detected Russian by words")
            return "ru"

        # Method 3: Check Cyrillic ratio (if mostly Cyrillic, assume Ukrainian by default)
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        total_letters = sum(1 for char in text if char.isalpha())

        if total_letters > 0:
            cyrillic_ratio = cyrillic_count / total_letters

            if cyrillic_ratio > 0.5:
                # Default to Ukrainian for ambiguous Cyrillic text
                logger.debug("Defaulting to Ukrainian for Cyrillic text")
                return "uk"

        logger.debug("Could not determine language")
        return "unknown"

    def is_ukrainian(self, text: str) -> bool:
        """
        Check if text is in Ukrainian.

        Args:
            text: Input text

        Returns:
            True if Ukrainian
        """
        return self.detect(text) == "uk"

    def is_russian(self, text: str) -> bool:
        """
        Check if text is in Russian.

        Args:
            text: Input text

        Returns:
            True if Russian
        """
        return self.detect(text) == "ru"


# Singleton instance
_detector = None


def get_language_detector() -> LanguageDetector:
    """Get or create the global language detector instance."""
    global _detector
    if _detector is None:
        _detector = LanguageDetector()
    return _detector
