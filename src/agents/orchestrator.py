"""Orchestrator agent for routing queries to specialized agents."""

from typing import Dict, List, Optional

import ollama

from src.agents.base_agent import BaseAgent, AgentResponse
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class OrchestratorAgent:
    """Routes queries to specialized agents based on intent classification."""

    # Intent categories with Ukrainian and Russian keywords
    INTENT_CATEGORIES = {
        "visa": [
            # Ukrainian
            "віз", "дозвіл", "upe", "brp", "подорож", "імігр", "поїздк",
            "виїзд", "в'їзд", "прикордон", "паспорт", "документ",
            # Russian
            "виз", "разреш", "поездк", "въезд", "выезд", "границ", "паспорт"
        ],
        "housing": [
            # Ukrainian
            "житл", "оренд", "nhs", "gp", "школ", "лікар", "медиц",
            "квартир", "будин", "реєстр", "дит", "освіт", "лікарн",
            # Russian
            "жиль", "аренд", "квартир", "врач", "школ", "медиц",
            "больниц", "регистр"
        ],
        "work": [
            # Ukrainian
            "робот", "зарплат", "ni number", "national insurance",
            "benefits", "допомог", "працевлашт", "податк", "universal credit",
            "заробіт", "вакансі", "роботодав",
            # Russian
            "работ", "зарплат", "пособ", "помощ", "налог", "вакансии"
        ]
    }

    def __init__(self):
        """Initialize orchestrator."""
        self.settings = get_settings()
        self.model = self.settings.orchestrator_model
        self._agents = None  # Lazy initialization

        logger.info("Initialized OrchestratorAgent")

    async def route(self, query: str) -> str:
        """
        Determine which agent should handle this query.

        Args:
            query: User query

        Returns:
            Agent type: "visa", "housing", "work", or "general"
        """
        logger.info(f"Routing query: '{query[:50]}...'")

        # Stage 1: Fast keyword-based classification
        keyword_intent = self._keyword_classify(query)

        if keyword_intent != "uncertain":
            logger.info(f"Keyword classification: {keyword_intent}")
            return keyword_intent

        # Stage 2: LLM-based classification for uncertain cases
        logger.info("Using LLM classification for uncertain query")
        llm_intent = await self._llm_classify(query)

        logger.info(f"LLM classification: {llm_intent}")
        return llm_intent

    def _keyword_classify(self, query: str) -> str:
        """
        Fast keyword-based classification.

        Args:
            query: User query

        Returns:
            Intent category or "uncertain"
        """
        query_lower = query.lower()
        scores = {}

        for category, keywords in self.INTENT_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[category] = score

        max_score = max(scores.values())

        # Threshold for confidence (need at least 1 keyword match)
        if max_score >= 1:
            # Get category with highest score
            best_category = max(scores, key=scores.get)
            logger.debug(f"Keyword scores: {scores}, selected: {best_category}")
            return best_category

        return "uncertain"

    async def _llm_classify(self, query: str) -> str:
        """
        LLM-based classification for uncertain cases.

        Args:
            query: User query

        Returns:
            Intent category: "visa", "housing", "work", or "general"
        """
        try:
            classification_prompt = """Класифікуй питання користувача в ОДНУ з категорій:

- visa: питання про візи, дозволи на проживання (UPE, BRP), подорожі, імміграцію, кордон, паспорти
- housing: питання про житло, оренду, NHS, GP, лікарів, школи, медицину, освіту, реєстрацію
- work: питання про роботу, зарплату, NI number, benefits, фінансову допомогу, працевлаштування, податки
- general: привітання, подяки, загальні питання, що не стосуються трьох категорій вище

ВАЖЛИВО: Відповідь має бути ТІЛЬКИ ОДНЕ СЛОВО - назва категорії (visa, housing, work, або general).

Питання: {query}

Категорія:"""

            client = ollama.Client(host=self.settings.ollama_base_url)

            response = client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ти класифікатор питань. Відповідай тільки одним словом: visa, housing, work, або general."
                    },
                    {
                        "role": "user",
                        "content": classification_prompt.format(query=query)
                    }
                ],
                options={
                    "temperature": 0.1,  # Low temperature for consistent classification
                    "num_predict": 10,  # Only need one word
                }
            )

            intent = response["message"]["content"].strip().lower()

            # Validate and normalize intent
            valid_intents = ["visa", "housing", "work", "general"]

            for valid_intent in valid_intents:
                if valid_intent in intent:
                    return valid_intent

            # Default to general if unclear
            logger.warning(f"Unclear LLM classification: '{intent}', defaulting to general")
            return "general"

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # Fallback to general
            return "general"

    def get_agent(self, agent_type: str) -> BaseAgent:
        """
        Get the appropriate specialized agent.

        Args:
            agent_type: Type of agent (visa, housing, work, general)

        Returns:
            BaseAgent instance
        """
        # Lazy initialization of agents
        if self._agents is None:
            self._initialize_agents()

        # Return appropriate agent
        agent = self._agents.get(agent_type)

        if agent is None:
            logger.warning(f"Unknown agent type: {agent_type}, using fallback")
            return self._agents["general"]

        return agent

    def _initialize_agents(self):
        """Initialize all specialized agents."""
        logger.info("Initializing specialized agents...")

        # Import here to avoid circular imports
        from src.agents.visa_agent import VisaAgent
        from src.agents.housing_agent import HousingAgent
        from src.agents.work_agent import WorkAgent
        from src.agents.fallback_agent import FallbackAgent

        self._agents = {
            "visa": VisaAgent(),
            "housing": HousingAgent(),
            "work": WorkAgent(),
            "general": FallbackAgent()
        }

        logger.info("All agents initialized")

    async def process_with_routing(self, query: str) -> AgentResponse:
        """
        Route query and process with appropriate agent.

        Args:
            query: User query

        Returns:
            AgentResponse from specialized agent
        """
        # Determine routing
        agent_type = await self.route(query)

        # Get appropriate agent
        agent = self.get_agent(agent_type)

        # Process with agent
        response = await agent.process(query)

        return response


# Singleton instance
_orchestrator: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
