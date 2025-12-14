"""Disclaimer templates for different agent types."""

from typing import Dict

# Disclaimer templates for each agent type
DISCLAIMERS: Dict[str, str] = {
    "visa": (
        "\n\n⚠️ Це не юридична консультація. Я не є юристом. "
        "Для вашої конкретної візової ситуації зверніться до імміграційного спеціаліста."
    ),
    "housing": (
        "\n\n⚠️ Це загальна інформація, не юридична консультація. "
        "Для правових питань зверніться до спеціаліста."
    ),
    "work": (
        "\n\n⚠️ Це загальна інформація, не фінансова або юридична консультація. "
        "Для конкретних рішень зверніться до спеціаліста."
    ),
    "general": (
        "\n\n⚠️ Це загальна інформація. "
        "Для юридичних або фінансових рішень зверніться до спеціаліста."
    )
}


def get_disclaimer(agent_type: str) -> str:
    """
    Get appropriate disclaimer for agent type.

    Args:
        agent_type: Type of agent (visa, housing, work, general)

    Returns:
        Disclaimer text
    """
    # Normalize agent type (remove "_agent" suffix if present)
    normalized_type = agent_type.replace("_agent", "")

    # Map common variations
    type_mapping = {
        "visa": "visa",
        "immigration": "visa",
        "housing": "housing",
        "life": "housing",
        "work": "work",
        "benefits": "work",
        "employment": "work",
        "fallback": "general",
        "general": "general"
    }

    agent_key = type_mapping.get(normalized_type, "general")

    return DISCLAIMERS.get(agent_key, DISCLAIMERS["general"])
