#!/usr/bin/env python3
"""
Standalone script to run the data ingestion pipeline.

This script orchestrates:
1. Loading documents from manual files or web scrapers
2. Chunking documents into smaller pieces
3. Generating embeddings via Ollama
4. Storing embeddings in Qdrant vector database

Usage:
    python run_ingestion.py [--recreate] [--no-save]

Options:
    --recreate      Recreate the vector database collection (deletes existing data)
    --no-save       Don't save artifacts to disk

Note: Data sources (manual docs, scrapers) are configured via environment variables.
      See .env.example for available options.
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.rag.ingestion import run_ingestion
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()
logger = get_logger()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run the RAG data ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run ingestion with config defaults (manual docs)
  python run_ingestion.py

  # Recreate database and ingest
  python run_ingestion.py --recreate

  # Ingest without saving artifacts
  python run_ingestion.py --no-save

Note:
  Data sources are configured via environment variables (.env):
  - MANUAL_DOCS_ENABLED=true/false
  - SCRAPER_GOVUK_ENABLED=true/false
  - SCRAPER_OPORA_ENABLED=true/false
        """
    )

    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Recreate the vector database collection (WARNING: deletes existing data)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save artifacts (documents, chunks, stats) to disk'
    )

    args = parser.parse_args()

    # Warn about recreate
    if args.recreate:
        logger.warning("=" * 70)
        logger.warning("WARNING: --recreate flag is set!")
        logger.warning("This will DELETE all existing data in the vector database!")
        logger.warning("=" * 70)

        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Ingestion cancelled by user")
            return 0

    save_artifacts = not args.no_save

    # Get config to show what will be loaded
    from src.utils.config import get_settings
    settings = get_settings()

    # Log configuration
    logger.info("=" * 70)
    logger.info("Data Ingestion Pipeline Configuration")
    logger.info("=" * 70)
    logger.info(f"Manual documents: {settings.manual_docs_enabled}")
    if settings.manual_docs_enabled:
        logger.info(f"  Path: {settings.manual_docs_path}")
        logger.info(f"  Format: {settings.manual_docs_format}")
    logger.info(f"Gov.uk scraper: {settings.scraper_govuk_enabled}")
    logger.info(f"Opora.uk scraper: {settings.scraper_opora_enabled}")
    logger.info(f"Recreate collection: {args.recreate}")
    logger.info(f"Save artifacts: {save_artifacts}")
    logger.info("=" * 70)

    # Check that at least one source is enabled
    if not settings.manual_docs_enabled and not settings.scraper_govuk_enabled and not settings.scraper_opora_enabled:
        logger.error("=" * 70)
        logger.error("ERROR: No data sources are enabled!")
        logger.error("=" * 70)
        logger.error("Please enable at least one source in your .env file:")
        logger.error("  - MANUAL_DOCS_ENABLED=true")
        logger.error("  - SCRAPER_GOVUK_ENABLED=true")
        logger.error("  - SCRAPER_OPORA_ENABLED=true")
        logger.error("=" * 70)
        return 1

    # Run ingestion (uses config settings)
    try:
        stats = run_ingestion(
            use_manual_docs=None,      # Use config setting
            scrape_govuk=None,          # Use config setting
            scrape_opora=None,          # Use config setting
            recreate_collection=args.recreate,
            save_artifacts=save_artifacts
        )

        # Print summary
        print("\n" + "=" * 70)
        print("INGESTION SUMMARY")
        print("=" * 70)
        print(f"Success: {'✓' if stats.success else '✗'}")
        print(f"Documents loaded: {stats.documents_loaded}")
        print(f"  - Manual: {stats.manual_documents}")
        print(f"  - Gov.uk: {stats.govuk_documents}")
        print(f"  - Opora.uk: {stats.opora_documents}")
        print(f"Chunks created: {stats.chunks_created}")
        print(f"Chunks stored: {stats.chunks_stored}")
        print(f"Errors: {stats.errors}")
        print(f"Duration: {stats.duration_seconds:.2f} seconds")
        print("=" * 70)

        if stats.success:
            print("\n✓ Ingestion completed successfully!")
            print("The RAG knowledge base has been updated.")
            return 0
        else:
            print("\n✗ Ingestion completed with errors.")
            print(f"Check logs for details. Error count: {stats.errors}")
            return 1

    except KeyboardInterrupt:
        logger.info("\nIngestion cancelled by user (Ctrl+C)")
        return 130

    except Exception as e:
        logger.exception(f"Fatal error during ingestion: {e}")
        print(f"\n✗ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())