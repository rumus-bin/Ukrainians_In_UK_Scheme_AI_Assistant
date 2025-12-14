"""Translation from Russian to Ukrainian using Ollama."""

import ollama

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class Translator:
    """Translates Russian text to Ukrainian using LLM."""

    def __init__(self):
        """Initialize translator."""
        self.settings = get_settings()
        self.model = self.settings.ollama_model_name

    async def translate_ru_to_ua(self, text: str) -> str:
        """
        Translate Russian text to Ukrainian.

        Args:
            text: Russian text

        Returns:
            Ukrainian translation
        """
        if not text or not text.strip():
            return text

        try:
            logger.info(f"Translating Russian text: '{text[:50]}...'")

            translation_prompt = f"""Переклади наступний текст з російської мови на українську.

ВАЖЛИВО:
- Переклад має бути природним та зрозумілим
- Зберігай сенс та тон оригіналу
- Не додавай нічого від себе
- Відповідь має містити ТІЛЬКИ переклад, без пояснень

Текст для перекладу:
{text}

Переклад українською:"""

            client = ollama.Client(host=self.settings.ollama_base_url)

            response = client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ти - професійний перекладач з російської на українську. Надавай тільки переклад без пояснень."
                    },
                    {
                        "role": "user",
                        "content": translation_prompt
                    }
                ],
                options={
                    "temperature": 0.3,  # Lower temperature for more consistent translation
                    "num_predict": len(text) * 3,  # Allow enough tokens for translation
                }
            )

            translated_text = response["message"]["content"].strip()

            logger.info(f"Translation completed: '{translated_text[:50]}...'")

            return translated_text

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Return original text if translation fails
            logger.warning("Returning original text due to translation failure")
            return text


# Singleton instance
_translator = None


def get_translator() -> Translator:
    """Get or create the global translator instance."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
