"""Data ingestion pipeline for RAG system."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from src.scrapers.govuk_scraper import scrape_govuk
from src.scrapers.opora_scraper import scrape_opora
from src.rag.chunker import DocumentChunker, ChunkingStrategy, TextChunk
from src.rag.document_loader import load_manual_documents
from src.vectorstore.qdrant_client import QdrantVectorStore
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class IngestionStats:
    """Statistics for an ingestion run."""
    run_timestamp: str
    documents_loaded: int
    manual_documents: int
    govuk_documents: int
    opora_documents: int
    chunks_created: int
    chunks_embedded: int
    chunks_stored: int
    errors: int
    duration_seconds: float
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def save(self, path: str):
        """Save stats to JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class DataIngestionPipeline:
    """Pipeline for ingesting data into the RAG system."""

    def __init__(
        self,
        use_manual_docs: Optional[bool] = None,
        scrape_govuk: Optional[bool] = None,
        scrape_opora: Optional[bool] = None,
        recreate_collection: bool = False
    ):
        """
        Initialize the ingestion pipeline.

        Args:
            use_manual_docs: Whether to load manual documents (default: from config)
            scrape_govuk: Whether to scrape gov.uk (default: from config)
            scrape_opora: Whether to scrape opora.uk (default: from config)
            recreate_collection: Whether to recreate the Qdrant collection
        """
        self.settings = get_settings()

        # Use config values if not explicitly set
        self.use_manual_docs = use_manual_docs if use_manual_docs is not None else self.settings.manual_docs_enabled
        self.scrape_govuk_enabled = scrape_govuk if scrape_govuk is not None else self.settings.scraper_govuk_enabled
        self.scrape_opora_enabled = scrape_opora if scrape_opora is not None else self.settings.scraper_opora_enabled
        self.recreate_collection = recreate_collection

        # Initialize components
        self.chunker = DocumentChunker(
            chunk_size=self.settings.rag_chunk_size,
            chunk_overlap=self.settings.rag_chunk_overlap,
            strategy=ChunkingStrategy.SENTENCE
        )
        self.vector_store = QdrantVectorStore()

        # Storage for progress tracking
        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[TextChunk] = []
        self.errors: List[str] = []

    def run(self) -> IngestionStats:
        """
        Run the complete ingestion pipeline.

        Returns:
            IngestionStats with results
        """
        start_time = datetime.now()
        logger.info("=" * 70)
        logger.info("Starting Data Ingestion Pipeline")
        logger.info(f"Timestamp: {start_time.isoformat()}")
        logger.info("=" * 70)

        try:
            # Step 1: Scrape documents
            self._scrape_documents()

            # Step 2: Chunk documents
            self._chunk_documents()

            # Step 3: Initialize vector store
            self._initialize_vector_store()

            # Step 4: Store chunks in vector database
            self._store_chunks()

            # Calculate stats
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            stats = IngestionStats(
                run_timestamp=start_time.isoformat(),
                documents_loaded=len(self.documents),
                manual_documents=sum(1 for d in self.documents if d.get('metadata', {}).get('document_type') == 'manual'),
                govuk_documents=sum(1 for d in self.documents if d.get('metadata', {}).get('source') == 'gov.uk' and d.get('metadata', {}).get('document_type') == 'scraped'),
                opora_documents=sum(1 for d in self.documents if d.get('metadata', {}).get('source') == 'opora.uk' and d.get('metadata', {}).get('document_type') == 'scraped'),
                chunks_created=len(self.chunks),
                chunks_embedded=len(self.chunks),
                chunks_stored=len(self.chunks),
                errors=len(self.errors),
                duration_seconds=duration,
                success=len(self.errors) == 0
            )

            logger.info("=" * 70)
            logger.info("Ingestion Pipeline Completed Successfully")
            logger.info(f"Documents loaded: {stats.documents_loaded}")
            logger.info(f"  - Manual: {stats.manual_documents}")
            logger.info(f"  - Gov.uk: {stats.govuk_documents}")
            logger.info(f"  - Opora.uk: {stats.opora_documents}")
            logger.info(f"Chunks created: {stats.chunks_created}")
            logger.info(f"Chunks stored: {stats.chunks_stored}")
            logger.info(f"Duration: {stats.duration_seconds:.2f} seconds")
            logger.info("=" * 70)

            return stats

        except Exception as e:
            logger.exception(f"Ingestion pipeline failed: {e}")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return IngestionStats(
                run_timestamp=start_time.isoformat(),
                documents_loaded=len(self.documents),
                manual_documents=0,
                govuk_documents=0,
                opora_documents=0,
                chunks_created=len(self.chunks),
                chunks_embedded=0,
                chunks_stored=0,
                errors=len(self.errors) + 1,
                duration_seconds=duration,
                success=False
            )

    def _scrape_documents(self):
        """Step 1: Load documents from sources (manual files or scrapers)."""
        logger.info("Step 1: Loading documents from sources...")

        manual_docs = []
        govuk_docs = []
        opora_docs = []

        # Load manual documents
        if self.use_manual_docs:
            try:
                logger.info("Loading manual documents...")
                manual_docs = load_manual_documents()
                logger.info(f"Loaded {len(manual_docs)} manual documents")
            except Exception as e:
                logger.error(f"Failed to load manual documents: {e}")
                self.errors.append(f"Manual documents loading error: {str(e)}")

        # Scrape gov.uk (only if enabled)
        if self.scrape_govuk_enabled:
            try:
                logger.info("Scraping gov.uk...")
                govuk_docs = scrape_govuk()
                logger.info(f"Scraped {len(govuk_docs)} documents from gov.uk")
            except Exception as e:
                logger.error(f"Failed to scrape gov.uk: {e}")
                self.errors.append(f"gov.uk scraping error: {str(e)}")

        # Scrape opora.uk (only if enabled)
        if self.scrape_opora_enabled:
            try:
                logger.info("Scraping opora.uk...")
                opora_docs = scrape_opora()
                logger.info(f"Scraped {len(opora_docs)} documents from opora.uk")
            except Exception as e:
                logger.error(f"Failed to scrape opora.uk: {e}")
                self.errors.append(f"opora.uk scraping error: {str(e)}")

        # Combine all documents
        self.documents = manual_docs + govuk_docs + opora_docs

        logger.info(f"Total documents loaded: {len(self.documents)}")
        logger.info(f"  - Manual: {len(manual_docs)}")
        logger.info(f"  - Gov.uk: {len(govuk_docs)}")
        logger.info(f"  - Opora.uk: {len(opora_docs)}")

        if len(self.documents) == 0:
            raise ValueError("No documents were loaded. Cannot continue.")

    def _chunk_documents(self):
        """Step 2: Chunk documents into smaller pieces."""
        logger.info("Step 2: Chunking documents...")

        try:
            self.chunks = self.chunker.chunk_documents(self.documents)
            logger.info(f"Created {len(self.chunks)} chunks from {len(self.documents)} documents")

            # Log chunk statistics
            if self.chunks:
                chunk_lengths = [len(chunk.text) for chunk in self.chunks]
                avg_length = sum(chunk_lengths) / len(chunk_lengths)
                min_length = min(chunk_lengths)
                max_length = max(chunk_lengths)

                logger.info(f"Chunk statistics:")
                logger.info(f"  Average length: {avg_length:.0f} characters")
                logger.info(f"  Min length: {min_length} characters")
                logger.info(f"  Max length: {max_length} characters")

        except Exception as e:
            logger.error(f"Failed to chunk documents: {e}")
            self.errors.append(f"Chunking error: {str(e)}")
            raise

    def _initialize_vector_store(self):
        """Step 3: Initialize vector store connection and collection."""
        logger.info("Step 3: Initializing vector store...")

        try:
            # Connect to Qdrant
            if not self.vector_store.connect():
                raise RuntimeError("Failed to connect to Qdrant")

            # Recreate collection if requested
            if self.recreate_collection:
                logger.warning("Recreating vector store collection...")
                try:
                    self.vector_store.delete_collection()
                except Exception as e:
                    logger.warning(f"Could not delete collection (may not exist): {e}")

            # Create collection if it doesn't exist
            # First, get vector size by generating a test embedding
            logger.info("Determining embedding vector size...")
            test_embedding = self.vector_store.get_embedding("test")

            if not test_embedding:
                raise RuntimeError("Failed to generate test embedding")

            vector_size = len(test_embedding)
            logger.info(f"Embedding vector size: {vector_size}")

            # Create collection
            if not self.vector_store.create_collection(vector_size=vector_size):
                # Collection might already exist
                logger.info("Collection already exists or creation not needed")

            # Verify collection
            info = self.vector_store.get_collection_info()
            if info:
                logger.info(f"Vector store ready: {info['name']} ({info['points_count']} existing points)")
            else:
                logger.warning("Could not verify collection info")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            self.errors.append(f"Vector store init error: {str(e)}")
            raise

    def _store_chunks(self):
        """Step 4: Store chunks in vector database."""
        logger.info("Step 4: Storing chunks in vector database...")

        try:
            # Convert chunks to documents format for vector store
            documents_to_store = []

            for chunk in self.chunks:
                doc = {
                    "text": chunk.text,
                    "metadata": chunk.metadata
                }
                documents_to_store.append(doc)

            # Store in batches
            batch_size = 100
            total_stored = 0

            for i in range(0, len(documents_to_store), batch_size):
                batch = documents_to_store[i:i + batch_size]
                logger.info(f"Storing batch {i // batch_size + 1} ({len(batch)} documents)...")

                if self.vector_store.add_documents(batch):
                    total_stored += len(batch)
                    logger.info(f"Stored {total_stored}/{len(documents_to_store)} chunks")
                else:
                    logger.error(f"Failed to store batch {i // batch_size + 1}")
                    self.errors.append(f"Failed to store batch at index {i}")

            logger.info(f"Successfully stored {total_stored} chunks in vector database")

            # Verify final count
            info = self.vector_store.get_collection_info()
            if info:
                logger.info(f"Final collection size: {info['points_count']} points")

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            self.errors.append(f"Storage error: {str(e)}")
            raise

    def save_documents(self, directory: str):
        """
        Save scraped documents to disk for inspection.

        Args:
            directory: Directory to save documents
        """
        output_dir = Path(directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save documents
        docs_file = output_dir / f"documents_{timestamp}.json"
        with open(docs_file, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.documents)} documents to {docs_file}")

        # Save chunks
        chunks_data = [chunk.to_dict() for chunk in self.chunks]
        chunks_file = output_dir / f"chunks_{timestamp}.json"
        with open(chunks_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.chunks)} chunks to {chunks_file}")


def run_ingestion(
    use_manual_docs: Optional[bool] = None,
    scrape_govuk: Optional[bool] = None,
    scrape_opora: Optional[bool] = None,
    recreate_collection: bool = False,
    save_artifacts: bool = True
) -> IngestionStats:
    """
    Convenience function to run the ingestion pipeline.

    Args:
        use_manual_docs: Whether to load manual documents (default: from config)
        scrape_govuk: Whether to scrape gov.uk (default: from config)
        scrape_opora: Whether to scrape opora.uk (default: from config)
        recreate_collection: Whether to recreate the vector database
        save_artifacts: Whether to save documents and chunks to disk

    Returns:
        IngestionStats with results
    """
    pipeline = DataIngestionPipeline(
        use_manual_docs=use_manual_docs,
        scrape_govuk=scrape_govuk,
        scrape_opora=scrape_opora,
        recreate_collection=recreate_collection
    )

    stats = pipeline.run()

    # Save artifacts if requested
    if save_artifacts:
        try:
            pipeline.save_documents("/app/data/ingestion")

            # Save stats
            stats_dir = Path("/app/data/ingestion")
            stats_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stats_file = stats_dir / f"stats_{timestamp}.json"
            stats.save(str(stats_file))

            logger.info(f"Saved ingestion stats to {stats_file}")

        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")

    return stats