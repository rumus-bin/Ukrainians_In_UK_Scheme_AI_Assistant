"""
Test script for Darwin API connection.

Run this to verify your Darwin API key and connection work correctly.

Usage:
    python tests/test_darwin_api.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.train_monitor.darwin_client import DarwinClient, DarwinAPIError
from src.utils.logger import setup_logger, get_logger

# Setup logging
setup_logger()
logger = get_logger()


async def test_darwin_connection():
    """Test Darwin API connection and fetch Ely station data."""
    logger.info("=" * 70)
    logger.info("Darwin API Connection Test")
    logger.info("=" * 70)

    try:
        # Create Darwin client
        logger.info("Creating Darwin client...")
        client = DarwinClient()

        # Check health
        logger.info("Checking API health...")
        health = client.health_check()
        logger.info(f"Health check: {health}")

        if not health.get("api_key_configured"):
            logger.error(
                "❌ Darwin API key not configured!\n"
                "Please set DARWIN_API_KEY in your .env file.\n"
                "Get your API key from: https://www.nationalrail.co.uk/developers/"
            )
            return False

        # Test with Ely station
        logger.info("\n" + "=" * 70)
        logger.info("Fetching departures for Ely station (CRS: ELY)...")
        logger.info("=" * 70)

        board = await client.get_departures(
            station_crs="ELY",
            time_window=120,
            max_results=10
        )

        logger.info(f"\n✅ Successfully fetched station board!")
        logger.info(f"Station: {board.station_name} ({board.station_crs})")
        logger.info(f"Generated at: {board.generated_at}")
        logger.info(f"Number of services: {len(board.services)}")

        # Display services
        if board.services:
            logger.info("\n" + "-" * 70)
            logger.info("DEPARTURES:")
            logger.info("-" * 70)

            for idx, service in enumerate(board.services[:5], 1):  # Show first 5
                logger.info(f"\n{idx}. {service.destination}")
                logger.info(f"   Origin: {service.origin}")
                logger.info(f"   Scheduled: {service.scheduled_departure}")
                logger.info(f"   Estimated: {service.estimated_departure}")
                logger.info(f"   Platform: {service.platform or 'TBA'}")
                logger.info(f"   Status: {service.status}")
                logger.info(f"   Operator: {service.operator or 'Unknown'}")

                if service.is_cancelled:
                    logger.info(f"   ❌ CANCELLED")
                    if service.cancellation_reason:
                        logger.info(f"   Reason: {service.cancellation_reason}")
                elif service.delay_minutes > 0:
                    logger.info(f"   ⚠️ DELAYED by {service.delay_minutes} minutes")

            if len(board.services) > 5:
                logger.info(f"\n... and {len(board.services) - 5} more services")
        else:
            logger.info("\nℹ️ No services found for this time window")

        logger.info("\n" + "=" * 70)
        logger.info("✅ Darwin API test completed successfully!")
        logger.info("=" * 70)
        return True

    except DarwinAPIError as e:
        logger.error(f"\n❌ Darwin API Error: {e}")
        logger.error("\nPossible issues:")
        logger.error("1. Invalid API key")
        logger.error("2. Network connectivity problems")
        logger.error("3. nrewebservices library not installed")
        logger.error("\nTo fix:")
        logger.error("1. Verify your DARWIN_API_KEY in .env")
        logger.error("2. Install library: pip install nrewebservices")
        return False

    except Exception as e:
        logger.exception(f"\n❌ Unexpected error: {e}")
        return False


async def test_multiple_stations():
    """Test fetching data for multiple stations."""
    logger.info("\n" + "=" * 70)
    logger.info("Testing multiple stations...")
    logger.info("=" * 70)

    client = DarwinClient()
    stations = [
        ("ELY", "Ely"),
        ("CBG", "Cambridge"),
        ("KGX", "London Kings Cross")
    ]

    for crs, name in stations:
        try:
            logger.info(f"\nFetching {name} ({crs})...")
            board = await client.get_departures(crs, time_window=60, max_results=3)
            logger.info(f"✅ {name}: {len(board.services)} services found")

        except Exception as e:
            logger.error(f"❌ {name}: Failed - {e}")


async def main():
    """Main test function."""
    logger.info("Starting Darwin API tests...\n")

    # Test basic connection
    success = await test_darwin_connection()

    if success:
        # If basic test passed, try multiple stations
        await test_multiple_stations()

    logger.info("\n" + "=" * 70)
    logger.info("Test suite completed")
    logger.info("=" * 70)

    return success


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
