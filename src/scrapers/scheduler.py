"""Scheduler for periodic web scraping tasks."""

import time
import schedule
from datetime import datetime

from src.utils.config import get_settings
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()
logger = get_logger()


def run_scraping_job():
    """Execute the data ingestion job (manual docs or scrapers)."""
    logger.info("=" * 60)
    logger.info("Starting scheduled data ingestion job")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    try:
        # Import ingestion pipeline
        from src.rag.ingestion import run_ingestion

        # Run the complete ingestion pipeline
        # This will use config settings to determine sources:
        # - Manual documents (if enabled)
        # - Web scrapers (if enabled)
        # Then: load → chunk → embed → store
        stats = run_ingestion(
            # Use config settings for all sources
            use_manual_docs=None,  # From config
            scrape_govuk=None,     # From config
            scrape_opora=None,     # From config
            recreate_collection=False,  # Don't recreate on scheduled runs
            save_artifacts=True
        )

        if stats.success:
            logger.info("Ingestion job completed successfully")
            logger.info(f"Documents loaded: {stats.documents_loaded}")
            logger.info(f"  - Manual: {stats.manual_documents}")
            logger.info(f"  - Gov.uk: {stats.govuk_documents}")
            logger.info(f"  - Opora.uk: {stats.opora_documents}")
            logger.info(f"Chunks created: {stats.chunks_created}")
            logger.info(f"Chunks stored: {stats.chunks_stored}")
        else:
            logger.error(f"Ingestion job completed with errors: {stats.errors}")

        return stats

    except Exception as e:
        logger.exception(f"Data ingestion job failed: {e}")
        return None

    finally:
        logger.info("=" * 60)


def main():
    """Main scheduler loop."""
    settings = get_settings()

    logger.info("Starting data ingestion scheduler service...")
    logger.info(f"Scheduler enabled: {settings.scraper_schedule_enabled}")
    logger.info(f"Manual docs enabled: {settings.manual_docs_enabled}")
    logger.info(f"Gov.uk scraper enabled: {settings.scraper_govuk_enabled}")
    logger.info(f"Opora.uk scraper enabled: {settings.scraper_opora_enabled}")
    logger.info(f"Schedule (cron): {settings.scraper_schedule_cron}")

    if not settings.scraper_schedule_enabled:
        logger.warning("Scheduler is disabled in configuration. Service will idle.")
        logger.info("To enable scheduled ingestion, set SCRAPER_SCHEDULE_ENABLED=true")
        while True:
            time.sleep(3600)  # Sleep for 1 hour
        return

    # Parse cron schedule (simplified - weekly on Sunday at 2 AM)
    # For production, use a proper cron parser or APScheduler
    logger.info("Scheduling weekly data ingestion job for Sundays at 2:00 AM")

    schedule.every().sunday.at("02:00").do(run_scraping_job)

    # Run immediately on startup for testing
    if settings.debug_mode:
        logger.info("Debug mode: Running data ingestion job immediately")
        run_scraping_job()

    # Scheduler loop
    logger.info("Scheduler is running. Waiting for scheduled jobs...")

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

            # Log heartbeat every hour
            if datetime.now().minute == 0:
                logger.info(f"Scheduler heartbeat: {datetime.now().isoformat()}")

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.exception(f"Scheduler error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()