"""Response validation for safety and compliance."""

from typing import Tuple, List

from src.agents.base_agent import AgentResponse
from src.safety.disclaimers import get_disclaimer
from src.language.detector import get_language_detector
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class ResponseValidator:
    """Validates agent responses for safety and compliance."""

    # Required disclaimer keywords (at least one must be present)
    REQUIRED_DISCLAIMER_KEYWORDS = [
        "не юридична консультація",
        "не є юристом",
        "зверніться до спеціаліста",
        "це загальна інформація",
        "не фінансова консультація"
    ]

    # Prohibited phrases that indicate illegal legal predictions
    PROHIBITED_PHRASES = [
        "ви точно отримаєте",
        "вам гарантовано",
        "100% схвалення",
        "визначено отримаєте візу",
        "гарантую",
        "точно схвалять",
        "обов'язково отримаєте",
        "без сумніву отримаєте"
    ]

    def __init__(self):
        """Initialize response validator."""
        self.settings = get_settings()
        self.language_detector = get_language_detector()

    def validate(self, response: AgentResponse) -> Tuple[bool, AgentResponse]:
        """
        Validate response for safety compliance.

        Args:
            response: Agent response to validate

        Returns:
            Tuple of (is_valid, validated_response)
        """
        try:
            text = response.text.lower()
            is_valid = True

            # Check 1: Must be in Ukrainian (or at least Cyrillic)
            if not self._is_ukrainian_text(response.text):
                logger.warning(f"{response.agent_name}: Response not in Ukrainian")
                # Don't fail, but log warning
                # is_valid = False  # Commented out to allow Russian/mixed responses

            # Check 2: Must have disclaimer (or add it)
            has_disclaimer = any(
                keyword in text
                for keyword in self.REQUIRED_DISCLAIMER_KEYWORDS
            )

            if not has_disclaimer and self.settings.enable_safety_disclaimers:
                # Add appropriate disclaimer
                disclaimer = get_disclaimer(response.agent_name)
                response.text += disclaimer
                logger.info(f"{response.agent_name}: Added missing disclaimer")

            # Check 3: Must not have prohibited legal predictions
            has_prohibited = any(
                phrase in text
                for phrase in self.PROHIBITED_PHRASES
            )

            if has_prohibited and self.settings.block_legal_predictions:
                logger.error(
                    f"{response.agent_name}: Response contains prohibited legal prediction"
                )
                is_valid = False
                return False, self.get_safe_fallback(response.agent_name)

            # Check 4: Log if no sources (warning only)
            if not response.sources or len(response.sources) == 0:
                logger.warning(f"{response.agent_name}: Response has no sources")
                # Still valid, just log it

            logger.info(f"{response.agent_name}: Response validation passed")
            return is_valid, response

        except Exception as e:
            logger.error(f"Response validation error: {e}")
            return False, self.get_safe_fallback(response.agent_name)

    def _is_ukrainian_text(self, text: str) -> bool:
        """
        Check if text is primarily Ukrainian.

        Args:
            text: Text to check

        Returns:
            True if Ukrainian or Cyrillic
        """
        # Use language detector
        detected = self.language_detector.detect(text)

        # Accept both Ukrainian and Russian (since we support both input languages)
        # Also accept unknown if it's mostly Cyrillic
        if detected in ["uk", "ru"]:
            return True

        # Check if mostly Cyrillic as fallback
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        total_letters = sum(1 for char in text if char.isalpha())

        if total_letters > 0 and (cyrillic_count / total_letters) > 0.5:
            return True

        return False

    def get_safe_fallback(self, agent_name: str = "safety_fallback") -> AgentResponse:
        """
        Get safe fallback response for validation failures.

        Args:
            agent_name: Name of agent that failed

        Returns:
            Safe fallback AgentResponse
        """
        return AgentResponse(
            text=(
                "⚠️ Вибачте, я не можу надати відповідь на це питання.\n\n"
                "Рекомендую звернутися до:\n"
                "• Офіційних джерел: gov.uk, opora.uk\n"
                "• Імміграційного спеціаліста (для візових питань)\n"
                "• Служби підтримки вашої місцевої ради\n\n"
                "Спробуйте переформулювати питання або скористайтеся командою /help\n\n"
                "⚠️ Це загальна інформація, не юридична консультація."
            ),
            sources=[],
            agent_name=agent_name,
            confidence=0.0,
            processing_time=0.0,
            metadata={"reason": "safety_validation_failed"}
        )


# Singleton instance
_validator = None


def get_response_validator() -> ResponseValidator:
    """Get or create the global response validator instance."""
    global _validator
    if _validator is None:
        _validator = ResponseValidator()
    return _validator
