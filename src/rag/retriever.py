"""RAG retrieval and context preparation."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.vectorstore.qdrant_client import get_vector_store
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class RetrievalResult:
    """Result from RAG retrieval."""
    context: str
    sources: List[Dict[str, Any]]
    query: str
    found_documents: int


class RAGRetriever:
    """Handles document retrieval and context preparation for RAG."""

    def __init__(self):
        """Initialize RAG retriever."""
        self.settings = get_settings()
        self.vector_store = get_vector_store()
        self._connected = False

    def initialize(self) -> bool:
        """
        Initialize connection to vector store.

        Returns:
            bool: True if successful
        """
        try:
            if not self._connected:
                logger.info("Initializing RAG retriever...")

                # Connect to vector store
                if not self.vector_store.connect():
                    logger.error("Failed to connect to vector store")
                    return False

                # Check if collection exists
                info = self.vector_store.get_collection_info()

                if info:
                    logger.info(f"Connected to collection: {info['name']} "
                              f"({info['points_count']} documents)")
                    self._connected = True
                    return True
                else:
                    logger.warning("Collection does not exist yet. "
                                 "Retrieval will return empty results until documents are added.")
                    self._connected = True
                    return True

        except Exception as e:
            logger.error(f"Failed to initialize RAG retriever: {e}")
            return False

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        topic_filter: Optional[str] = None
    ) -> RetrievalResult:
        """
        Retrieve relevant documents for a query.

        Args:
            query: User query
            top_k: Number of documents to retrieve (default from settings)
            score_threshold: Minimum similarity score (default from settings)
            topic_filter: Optional filter by topic (visa, housing, work, etc.)

        Returns:
            RetrievalResult with context and sources
        """
        try:
            if not self._connected:
                logger.warning("RAG retriever not initialized, initializing now...")
                if not self.initialize():
                    return self._empty_result(query)

            logger.info(f"Retrieving documents for query: '{query[:50]}...'")

            # Prepare filter conditions
            filter_conditions = {}
            if topic_filter:
                filter_conditions["topic"] = topic_filter

            # Search vector store
            results = self.vector_store.search(
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions if filter_conditions else None
            )

            if not results:
                logger.warning(f"No documents found for query: '{query[:50]}...'")
                return self._empty_result(query)

            # Build context from results
            context = self._build_context(results)

            # Extract sources
            sources = [
                {
                    "text": res["text"][:200] + "...",
                    "score": res["score"],
                    "metadata": res.get("metadata", {})
                }
                for res in results
            ]

            logger.info(f"Retrieved {len(results)} documents, "
                       f"context length: {len(context)} characters")

            return RetrievalResult(
                context=context,
                sources=sources,
                query=query,
                found_documents=len(results)
            )

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return self._empty_result(query)

    def _build_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Build context string from search results.

        Args:
            results: List of search results

        Returns:
            Formatted context string
        """
        context_parts = []

        for idx, result in enumerate(results, 1):
            text = result.get("text", "")
            metadata = result.get("metadata", {})

            # Format with source information including URL
            source_info = ""
            source_name = metadata.get('source', 'Unknown')
            title = metadata.get('title', '')
            url = metadata.get('url', '')

            if title and url:
                source_info = f" - {title}\nДжерело: {source_name}\nПосилання: {url}"
            elif url:
                source_info = f"\nДжерело: {source_name}\nПосилання: {url}"
            elif title:
                source_info = f" - {title}\nДжерело: {source_name}"
            elif source_name:
                source_info = f"\nДжерело: {source_name}"

            context_parts.append(
                f"[Документ {idx}]{source_info}\n{text}\n"
            )

        return "\n".join(context_parts)

    def _empty_result(self, query: str) -> RetrievalResult:
        """
        Create an empty retrieval result.

        Args:
            query: Original query

        Returns:
            Empty RetrievalResult
        """
        return RetrievalResult(
            context="",
            sources=[],
            query=query,
            found_documents=0
        )

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of RAG retriever.

        Returns:
            Dictionary with health status
        """
        try:
            if not self._connected:
                return {
                    "status": "not_initialized",
                    "healthy": False
                }

            info = self.vector_store.get_collection_info()

            if info:
                return {
                    "status": "healthy",
                    "healthy": True,
                    "collection": info["name"],
                    "documents": info["points_count"],
                    "vector_size": info.get("vector_size", "unknown")
                }
            else:
                return {
                    "status": "collection_not_found",
                    "healthy": False
                }

        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "error": str(e)
            }


# Singleton instance
_retriever: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    """Get or create the global RAG retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever