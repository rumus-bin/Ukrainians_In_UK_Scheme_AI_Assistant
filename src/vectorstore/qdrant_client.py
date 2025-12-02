"""Qdrant vector database client implementation."""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
from qdrant_client.http import models
import ollama

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class QdrantVectorStore:
    """Qdrant vector store for RAG functionality."""

    def __init__(self):
        """Initialize Qdrant client and configuration."""
        self.settings = get_settings()
        self.client: Optional[QdrantClient] = None
        self.collection_name = self.settings.qdrant_collection_name
        self.embedding_model = self.settings.ollama_embedding_model
        self.ollama_base_url = self.settings.ollama_base_url
        self._vector_size: Optional[int] = None

        # Configure ollama client with custom host
        self.ollama_client = ollama.Client(host=self.ollama_base_url)

    def connect(self) -> bool:
        """
        Connect to Qdrant database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to Qdrant at {self.settings.qdrant_host}:{self.settings.qdrant_port}")

            self.client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port,
                timeout=10
            )

            # Test connection
            collections = self.client.get_collections()
            logger.info(f"Successfully connected to Qdrant. Found {len(collections.collections)} collections.")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False

    def create_collection(self, vector_size: int = 1024) -> bool:
        """
        Create collection if it doesn't exist.

        Args:
            vector_size: Dimension of embedding vectors (default 1024 for mxbai-embed-large)

        Returns:
            bool: True if collection created or exists, False otherwise
        """
        try:
            if not self.client:
                raise RuntimeError("Qdrant client not connected")

            # Check if collection exists
            collections = self.client.get_collections()
            collection_exists = any(
                col.name == self.collection_name
                for col in collections.collections
            )

            if collection_exists:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return True

            # Create collection
            logger.info(f"Creating collection '{self.collection_name}' with vector size {vector_size}")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )

            logger.info(f"Successfully created collection '{self.collection_name}'")
            self._vector_size = vector_size

            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using Ollama.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        try:
            logger.debug(f"Generating embedding for text (length: {len(text)})")

            # Use ollama library to generate embeddings
            response = self.ollama_client.embeddings(
                model=self.embedding_model,
                prompt=text
            )

            embedding = response.get("embedding")

            if embedding:
                logger.debug(f"Successfully generated embedding (size: {len(embedding)})")

                # Cache vector size
                if not self._vector_size:
                    self._vector_size = len(embedding)

                return embedding
            else:
                logger.error("No embedding returned from Ollama")
                return None

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> bool:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents with 'text' and 'metadata' fields
            batch_size: Number of documents to process at once

        Returns:
            bool: True if all documents added successfully
        """
        try:
            if not self.client:
                raise RuntimeError("Qdrant client not connected")

            logger.info(f"Adding {len(documents)} documents to collection '{self.collection_name}'")

            points = []

            for idx, doc in enumerate(documents):
                text = doc.get("text", "")
                metadata = doc.get("metadata", {})

                if not text:
                    logger.warning(f"Document {idx} has no text, skipping")
                    continue

                # Generate embedding
                embedding = self.get_embedding(text)

                if not embedding:
                    logger.warning(f"Failed to generate embedding for document {idx}, skipping")
                    continue

                # Create point
                point = PointStruct(
                    id=idx,
                    vector=embedding,
                    payload={
                        "text": text,
                        **metadata
                    }
                )

                points.append(point)

                # Upload in batches
                if len(points) >= batch_size:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                    logger.info(f"Uploaded batch of {len(points)} points")
                    points = []

            # Upload remaining points
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Uploaded final batch of {len(points)} points")

            logger.info(f"Successfully added all documents to collection")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query: Query text
            top_k: Number of results to return (default from settings)
            score_threshold: Minimum similarity score (default from settings)
            filter_conditions: Optional metadata filters

        Returns:
            List of search results with text, metadata, and score
        """
        try:
            if not self.client:
                raise RuntimeError("Qdrant client not connected")

            # Use settings defaults if not provided
            top_k = top_k or self.settings.rag_top_k_results
            score_threshold = score_threshold or self.settings.rag_similarity_threshold

            logger.info(f"Searching for: '{query[:50]}...' (top_k={top_k}, threshold={score_threshold})")

            # Generate query embedding
            query_embedding = self.get_embedding(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Prepare filter if provided
            search_filter = None
            if filter_conditions:
                # Convert filter conditions to Qdrant filter format
                # This is a simplified implementation
                search_filter = Filter(
                    must=[
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                        for key, value in filter_conditions.items()
                    ]
                )

            # Perform search
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=search_filter
            ).points

            # Format results
            results = []
            for result in search_results:
                results.append({
                    "text": result.payload.get("text", ""),
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k != "text"
                    },
                    "score": result.score,
                    "id": result.id
                })

            logger.info(f"Found {len(results)} results")

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the collection.

        Returns:
            Dictionary with collection statistics or None if failed
        """
        try:
            if not self.client:
                raise RuntimeError("Qdrant client not connected")

            info = self.client.get_collection(collection_name=self.collection_name)

            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "status": info.status
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None

    def delete_collection(self) -> bool:
        """
        Delete the collection.

        Returns:
            bool: True if successful
        """
        try:
            if not self.client:
                raise RuntimeError("Qdrant client not connected")

            logger.warning(f"Deleting collection '{self.collection_name}'")
            self.client.delete_collection(collection_name=self.collection_name)
            logger.info(f"Successfully deleted collection '{self.collection_name}'")

            return True

        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False


# Singleton instance
_vector_store: Optional[QdrantVectorStore] = None


def get_vector_store() -> QdrantVectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore()
    return _vector_store