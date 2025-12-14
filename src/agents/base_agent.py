"""Base agent class for all specialized agents."""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import ollama

from src.rag.retriever import get_retriever, RetrievalResult
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class AgentResponse:
    """Standardized agent response structure."""
    text: str
    sources: List[Dict[str, Any]]
    agent_name: str
    confidence: float
    processing_time: float
    metadata: Dict[str, Any]


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        name: str,
        model: Optional[str] = None,
        topic_filter: Optional[str] = None
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name
            model: LLM model to use (defaults to settings)
            topic_filter: Optional topic filter for RAG retrieval
        """
        self.name = name
        self.settings = get_settings()
        self.model = model or self.settings.ollama_model_name
        self.topic_filter = topic_filter
        self.retriever = get_retriever()

        logger.info(f"Initialized {self.name} with model {self.model}")

    async def process(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> AgentResponse:
        """
        Process user query and generate response.

        Args:
            query: User query text
            context: Optional additional context

        Returns:
            AgentResponse with generated text and metadata
        """
        start_time = time.time()

        try:
            logger.info(f"{self.name}: Processing query: '{query[:50]}...'")

            # Initialize retriever if needed
            if not self.retriever._connected:
                self.retriever.initialize()

            # Retrieve context from RAG
            retrieval_result = await self._retrieve_context(query)

            if retrieval_result.found_documents == 0:
                logger.warning(f"{self.name}: No documents found for query")
                # Still proceed with generation but note lack of context
            else:
                logger.info(
                    f"{self.name}: Retrieved {retrieval_result.found_documents} documents"
                )

            # Generate response using LLM
            response_text = await self._generate_llm_response(
                query=query,
                context=retrieval_result.context,
                system_prompt=self.get_system_prompt()
            )

            processing_time = time.time() - start_time

            logger.info(
                f"{self.name}: Generated response in {processing_time:.2f}s"
            )

            return AgentResponse(
                text=response_text,
                sources=retrieval_result.sources,
                agent_name=self.name,
                confidence=self._calculate_confidence(retrieval_result),
                processing_time=processing_time,
                metadata={
                    "query": query,
                    "found_documents": retrieval_result.found_documents,
                    "model": self.model
                }
            )

        except Exception as e:
            logger.error(f"{self.name}: Error processing query: {e}")
            processing_time = time.time() - start_time

            # Return error response
            return AgentResponse(
                text=self._get_error_response(),
                sources=[],
                agent_name=self.name,
                confidence=0.0,
                processing_time=processing_time,
                metadata={"error": str(e)}
            )

    async def _retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None
    ) -> RetrievalResult:
        """
        Retrieve relevant context from RAG system.

        Args:
            query: User query
            top_k: Number of documents to retrieve

        Returns:
            RetrievalResult with context and sources
        """
        try:
            return self.retriever.retrieve(
                query=query,
                top_k=top_k or self.settings.rag_top_k_results,
                score_threshold=self.settings.rag_similarity_threshold,
                topic_filter=self.topic_filter
            )
        except Exception as e:
            logger.error(f"{self.name}: RAG retrieval failed: {e}")
            # Return empty result
            from src.rag.retriever import RetrievalResult
            return RetrievalResult(
                context="",
                sources=[],
                query=query,
                found_documents=0
            )

    async def _generate_llm_response(
        self,
        query: str,
        context: str,
        system_prompt: str
    ) -> str:
        """
        Generate response using Ollama LLM.

        Args:
            query: User query
            context: Retrieved context
            system_prompt: System prompt for agent

        Returns:
            Generated response text
        """
        try:
            # Build user prompt with context
            user_prompt = self._build_user_prompt(query, context)

            logger.debug(f"{self.name}: Calling Ollama with model {self.model}")

            # Call Ollama
            client = ollama.Client(host=self.settings.ollama_base_url)

            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={
                    "temperature": self.settings.response_temperature,
                    "num_predict": self.settings.max_response_tokens,
                }
            )

            response_text = response["message"]["content"]

            logger.debug(
                f"{self.name}: LLM generated {len(response_text)} characters"
            )

            return response_text

        except Exception as e:
            logger.error(f"{self.name}: LLM generation failed: {e}")
            raise

    def _build_user_prompt(self, query: str, context: str) -> str:
        """
        Build user prompt with query and context.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Formatted user prompt
        """
        if context:
            return f"""КОНТЕКСТ З ОФІЦІЙНИХ ДЖЕРЕЛ:
{context}

ПИТАННЯ КОРИСТУВАЧА:
{query}

ТВОЯ ВІДПОВІДЬ:"""
        else:
            return f"""У мене немає контексту з бази знань для цього питання.

ПИТАННЯ КОРИСТУВАЧА:
{query}

ТВОЯ ВІДПОВІДЬ (вкажи, що немає інформації в базі, та направ до офіційних джерел):"""

    def _calculate_confidence(self, retrieval_result: RetrievalResult) -> float:
        """
        Calculate confidence score based on retrieval results.

        Args:
            retrieval_result: RAG retrieval result

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if retrieval_result.found_documents == 0:
            return 0.0

        # Use average score from sources if available
        if retrieval_result.sources:
            avg_score = sum(
                s.get("score", 0.0) for s in retrieval_result.sources
            ) / len(retrieval_result.sources)
            return min(avg_score, 1.0)

        # Default to moderate confidence if documents found
        return 0.7

    def get_system_prompt(self) -> str:
        """
        Get complete system prompt for this agent.

        Returns:
            System prompt string
        """
        return self._build_system_prompt()

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """
        Build agent-specific system prompt with safety rules.

        Must be implemented by subclasses.

        Returns:
            System prompt string
        """
        pass

    def _get_error_response(self) -> str:
        """
        Get error response message.

        Returns:
            Error message in Ukrainian
        """
        return (
            "⚠️ Вибачте, сталася помилка при обробці вашого запиту.\n\n"
            "Спробуйте:\n"
            "• Переформулювати питання\n"
            "• Перевірити з'єднання\n"
            "• Звернутися до офіційних джерел:\n"
            "  - gov.uk\n"
            "  - opora.uk\n\n"
            "Якщо проблема повторюється, зверніться до адміністратора."
        )
