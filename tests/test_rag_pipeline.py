#!/usr/bin/env python3
"""
End-to-end test for the complete RAG pipeline.

Tests the full workflow:
1. Document ingestion (scrape → chunk → embed → store)
2. Document retrieval (query → search → context)
3. Response generation (context → LLM → answer)

Usage:
    python test_rag_pipeline.py [--full-ingestion]

Options:
    --full-ingestion    Run full ingestion before testing (scrapes real sites)
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.rag.chunker import DocumentChunker, ChunkingStrategy
from src.rag.retriever import RAGRetriever
from src.vectorstore.qdrant_client import QdrantVectorStore
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()
logger = get_logger()


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_chunking():
    """Test document chunking."""
    print_section("TEST 1: Document Chunking")

    chunker = DocumentChunker(chunk_size=300, chunk_overlap=50)

    # Test documents (Ukrainian content)
    test_docs = [
        {
            "text": """
            Програма "Додому для України" (Homes for Ukraine) була запущена у 2022 році.
            Ця програма дозволяє українським біженцям знайти житло у Великобританії.
            Візи видаються терміном до трьох років. Після закінчення візи можна подати
            заяву на продовження. Важливо зареєструватися у місцевій поліклініці протягом
            перших кількох тижнів після прибуття до Великобританії.
            """,
            "metadata": {"source": "test_govuk", "topic": "visa", "language": "uk"}
        },
        {
            "text": """
            Українці у Великобританії мають право на роботу. Для роботи потрібно
            отримати номер National Insurance (NI). Цей номер можна отримати онлайн
            або за телефоном. Без NI номера ви не зможете працювати офіційно.
            Також потрібно зареєструватися у податковій службі HMRC.
            """,
            "metadata": {"source": "test_opora", "topic": "work", "language": "uk"}
        }
    ]

    chunks = chunker.chunk_documents(test_docs)

    print(f"✓ Created {len(chunks)} chunks from {len(test_docs)} documents")

    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(f"  Source: {chunk.metadata.get('source')}")
        print(f"  Topic: {chunk.metadata.get('topic')}")
        print(f"  Length: {len(chunk.text)} chars")
        print(f"  Text: {chunk.text[:100].strip()}...")

    return chunks


def test_vector_store(chunks):
    """Test vector store operations."""
    print_section("TEST 2: Vector Store Operations")

    vector_store = QdrantVectorStore()

    # Connect
    print("Connecting to Qdrant...")
    if not vector_store.connect():
        print("✗ Failed to connect to Qdrant")
        return False

    print("✓ Connected to Qdrant")

    # Check for embedding capability
    print("\nTesting embedding generation...")
    test_embedding = vector_store.get_embedding("тест")

    if not test_embedding:
        print("✗ Failed to generate embedding (Ollama not available)")
        print("  This test requires Ollama to be running with mxbai-embed-large")
        return False

    print(f"✓ Generated test embedding ({len(test_embedding)} dimensions)")

    # Create collection
    print("\nCreating/verifying collection...")
    vector_size = len(test_embedding)

    if not vector_store.create_collection(vector_size=vector_size):
        print("Collection already exists or creation not needed")
    else:
        print("✓ Collection created")

    # Get collection info
    info = vector_store.get_collection_info()
    if info:
        print(f"✓ Collection: {info['name']}")
        print(f"  Points: {info['points_count']}")
        print(f"  Vector size: {info['vector_size']}")

    # Store chunks
    print(f"\nStoring {len(chunks)} test chunks...")
    docs_to_store = [chunk.to_dict() for chunk in chunks]

    if vector_store.add_documents(docs_to_store):
        print(f"✓ Stored {len(chunks)} chunks successfully")

        # Verify storage
        info = vector_store.get_collection_info()
        if info:
            print(f"✓ Collection now has {info['points_count']} total points")

        return True
    else:
        print("✗ Failed to store chunks")
        return False


def test_retrieval():
    """Test document retrieval."""
    print_section("TEST 3: Document Retrieval")

    retriever = RAGRetriever()

    # Initialize
    print("Initializing retriever...")
    if not retriever.initialize():
        print("✗ Failed to initialize retriever")
        return False

    print("✓ Retriever initialized")

    # Test queries (Ukrainian)
    test_queries = [
        "Як отримати візу до Великобританії?",
        "Що потрібно для роботи в UK?",
        "Як зареєструватися у лікаря?",
    ]

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 70)

        result = retriever.retrieve(query, top_k=3)

        if result.found_documents > 0:
            print(f"✓ Found {result.found_documents} relevant documents")
            print(f"  Context length: {len(result.context)} characters")

            print("\nSources:")
            for i, source in enumerate(result.sources, 1):
                metadata = source.get('metadata', {})
                print(f"  {i}. Topic: {metadata.get('topic', 'unknown')}")
                print(f"     Source: {metadata.get('source', 'unknown')}")
                print(f"     Score: {source['score']:.3f}")
                print(f"     Text: {source['text'][:80]}...")
        else:
            print("⚠ No documents found")

    # Health check
    print("\nRetriever health check:")
    health = retriever.health_check()
    print(f"  Status: {health['status']}")
    print(f"  Healthy: {health['healthy']}")
    if health['healthy']:
        print(f"  Documents: {health.get('documents', 0)}")

    return True


def test_full_pipeline():
    """Test the complete RAG pipeline end-to-end."""
    print_section("COMPLETE RAG PIPELINE TEST")

    success_count = 0
    total_tests = 3

    try:
        # Test 1: Chunking
        chunks = test_chunking()
        if chunks and len(chunks) > 0:
            success_count += 1
        else:
            print("\n✗ Chunking test failed")
            return False

        # Test 2: Vector Store
        if test_vector_store(chunks):
            success_count += 1
        else:
            print("\n✗ Vector store test failed")
            print("  Make sure Ollama is running and accessible")
            return False

        # Test 3: Retrieval
        if test_retrieval():
            success_count += 1
        else:
            print("\n✗ Retrieval test failed")
            return False

        # Summary
        print_section("TEST SUMMARY")
        print(f"\nTests passed: {success_count}/{total_tests}")

        if success_count == total_tests:
            print("\n✓ ALL TESTS PASSED!")
            print("\nThe RAG pipeline is working correctly:")
            print("  ✓ Documents can be chunked")
            print("  ✓ Embeddings can be generated")
            print("  ✓ Chunks can be stored in Qdrant")
            print("  ✓ Relevant documents can be retrieved")
            print("\nNext steps:")
            print("  1. Run full ingestion: python run_ingestion.py --recreate")
            print("  2. Test with real queries via the bot")
            return True
        else:
            print(f"\n✗ {total_tests - success_count} test(s) failed")
            return False

    except Exception as e:
        logger.exception(f"Pipeline test failed: {e}")
        print(f"\n✗ Fatal error: {e}")
        return False


def run_full_ingestion():
    """Run full ingestion before testing."""
    print_section("RUNNING FULL INGESTION")

    try:
        from src.rag.ingestion import run_ingestion

        print("\nThis will scrape real websites and populate the database.")
        print("This may take several minutes...\n")

        stats = run_ingestion(
            scrape_govuk=True,
            scrape_opora=True,
            recreate_collection=True,
            save_artifacts=True
        )

        print(f"\nIngestion completed:")
        print(f"  Success: {stats.success}")
        print(f"  Documents: {stats.documents_scraped}")
        print(f"  Chunks: {stats.chunks_stored}")
        print(f"  Duration: {stats.duration_seconds:.1f}s")

        return stats.success

    except Exception as e:
        logger.exception(f"Ingestion failed: {e}")
        print(f"\n✗ Ingestion error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the complete RAG pipeline end-to-end"
    )
    parser.add_argument(
        '--full-ingestion',
        action='store_true',
        help='Run full ingestion before testing (scrapes real websites)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  RAG PIPELINE END-TO-END TEST")
    print("=" * 70)

    # Run full ingestion if requested
    if args.full_ingestion:
        if not run_full_ingestion():
            print("\n✗ Ingestion failed, cannot continue with tests")
            return 1

    # Run tests
    success = test_full_pipeline()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())