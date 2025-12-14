"""Unit tests for orchestrator agent."""

import pytest
from src.agents.orchestrator import OrchestratorAgent


class TestOrchestratorAgent:
    """Test cases for OrchestratorAgent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = OrchestratorAgent()

    def test_keyword_classify_visa(self):
        """Test keyword classification for visa queries."""
        queries = [
            "Як продовжити УПЕ візу?",
            "Чи можу я подорожувати з BRP?",
            "Питання про імміграцію",
            "Де отримати дозвіл на проживання?"
        ]

        for query in queries:
            intent = self.orchestrator._keyword_classify(query)
            assert intent == "visa", f"Expected visa, got {intent} for query: {query}"

    def test_keyword_classify_housing(self):
        """Test keyword classification for housing queries."""
        queries = [
            "Де зареєструватися у NHS?",
            "Як знайти GP у моєму районі?",
            "Питання про житло та оренду",
            "Як записати дитину до школи?"
        ]

        for query in queries:
            intent = self.orchestrator._keyword_classify(query)
            assert intent == "housing", f"Expected housing, got {intent} for query: {query}"

    def test_keyword_classify_work(self):
        """Test keyword classification for work queries."""
        queries = [
            "Як отримати NI number?",
            "Де подати на Universal Credit?",
            "Питання про роботу та зарплату",
            "Які у мене права як працівника?"
        ]

        for query in queries:
            intent = self.orchestrator._keyword_classify(query)
            assert intent == "work", f"Expected work, got {intent} for query: {query}"

    def test_keyword_classify_uncertain(self):
        """Test keyword classification for uncertain queries."""
        queries = [
            "Привіт!",
            "Як справи?",
            "Що нового?"
        ]

        for query in queries:
            intent = self.orchestrator._keyword_classify(query)
            assert intent == "uncertain", f"Expected uncertain, got {intent} for query: {query}"

    def test_get_agent(self):
        """Test agent retrieval."""
        # Test valid agent types
        visa_agent = self.orchestrator.get_agent("visa")
        assert visa_agent is not None
        assert visa_agent.name == "visa_agent"

        housing_agent = self.orchestrator.get_agent("housing")
        assert housing_agent is not None
        assert housing_agent.name == "housing_agent"

        work_agent = self.orchestrator.get_agent("work")
        assert work_agent is not None
        assert work_agent.name == "work_agent"

        general_agent = self.orchestrator.get_agent("general")
        assert general_agent is not None
        assert general_agent.name == "fallback_agent"

    def test_get_agent_unknown_type(self):
        """Test agent retrieval with unknown type."""
        agent = self.orchestrator.get_agent("unknown_type")
        assert agent is not None
        # Should return fallback agent
        assert agent.name == "fallback_agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
