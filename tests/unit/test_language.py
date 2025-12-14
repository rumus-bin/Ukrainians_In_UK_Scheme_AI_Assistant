"""Unit tests for language detection and translation."""

import pytest
from src.language.detector import LanguageDetector


class TestLanguageDetector:
    """Test cases for LanguageDetector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = LanguageDetector()

    def test_detect_ukrainian(self):
        """Test detection of Ukrainian text."""
        ukrainian_texts = [
            "Як продовжити візу?",
            "Де знайти лікаря?",
            "Я хочу отримати допомогу",
            "Дякую за допомогу",
            "Чи можу я подорожувати?"
        ]

        for text in ukrainian_texts:
            lang = self.detector.detect(text)
            assert lang == "uk", f"Expected uk, got {lang} for text: {text}"

    def test_detect_russian(self):
        """Test detection of Russian text."""
        russian_texts = [
            "Как продлить визу?",
            "Где найти врача?",
            "Я хочу получить помощь",
            "Спасибо за помощь",
            "Могу ли я путешествовать?"
        ]

        for text in russian_texts:
            lang = self.detector.detect(text)
            assert lang == "ru", f"Expected ru, got {lang} for text: {text}"

    def test_detect_ukrainian_specific_chars(self):
        """Test detection using Ukrainian-specific characters."""
        # These words contain Ukrainian-specific letters
        ukrainian_specific = [
            "їжа",  # contains ї
            "євро",  # contains є
            "Київ",  # contains ї
            "Україна",  # contains ї
            "ґанок"  # contains ґ
        ]

        for text in ukrainian_specific:
            lang = self.detector.detect(text)
            assert lang == "uk", f"Expected uk, got {lang} for text: {text}"

    def test_detect_russian_specific_chars(self):
        """Test detection using Russian-specific characters."""
        # These words contain Russian-specific letters
        russian_specific = [
            "еда",  # normal Russian word
            "это",  # contains э
            "объект",  # contains ъ
            "ёлка",  # contains ё
            "вы можете"  # contains ы
        ]

        for text in russian_specific:
            lang = self.detector.detect(text)
            assert lang == "ru", f"Expected ru, got {lang} for text: {text}"

    def test_is_ukrainian(self):
        """Test is_ukrainian method."""
        assert self.detector.is_ukrainian("Як справи?")
        assert not self.detector.is_ukrainian("Как дела?")

    def test_is_russian(self):
        """Test is_russian method."""
        assert self.detector.is_russian("Как дела?")
        assert not self.detector.is_russian("Як справи?")

    def test_empty_text(self):
        """Test detection with empty text."""
        assert self.detector.detect("") == "unknown"
        assert self.detector.detect("   ") == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
