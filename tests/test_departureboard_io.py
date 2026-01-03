"""
Test script for departureboard.io API integration.

This script tests the free departureboard.io REST API (no registration required).

Usage:
    python tests/test_departureboard_io.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.train_monitor.darwin_client import DarwinClient, DarwinAPIError
from src.train_monitor.notifier import get_notifier
from src.train_monitor.models import (
    StationConfig,
    MonitoringMode,
    TrainChange,
    ChangeType,
    ChangeSeverity,
)
from src.utils.logger import setup_logger, get_logger

# Setup logging
setup_logger()
logger = get_logger()


async def test_departureboard_io_basic():
    """Test basic departureboard.io API connection."""
    logger.info("=" * 70)
    logger.info("departureboard.io API Test")
    logger.info("=" * 70)

    try:
        # Create Darwin client with departureboard.io
        logger.info("Creating Darwin client (departureboard.io)...")
        client = DarwinClient(library="departureboard.io")

        # Check health
        logger.info("Checking API health...")
        health = client.health_check()
        logger.info(f"Health check: {health}")

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

            for idx, service in enumerate(board.services[:10], 1):
                logger.info(f"\n{idx}. {service.destination}")
                logger.info(f"   Service ID: {service.service_id}")
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
                else:
                    logger.info(f"   ✅ ON TIME")

            if len(board.services) > 10:
                logger.info(f"\n... and {len(board.services) - 10} more services")
        else:
            logger.info("\nℹ️ No services found for this time window")

        logger.info("\n" + "=" * 70)
        logger.info("✅ departureboard.io test completed successfully!")
        logger.info("=" * 70)
        return board

    except DarwinAPIError as e:
        logger.error(f"\n❌ Darwin API Error: {e}")
        logger.error("\nPossible issues:")
        logger.error("1. Network connectivity problems")
        logger.error("2. departureboard.io service down")
        logger.error("3. Invalid station code")
        return None

    except Exception as e:
        logger.exception(f"\n❌ Unexpected error: {e}")
        return None


async def test_dry_run_notification():
    """Test DRY-RUN notification with departureboard.io data."""
    logger.info("\n" + "=" * 70)
    logger.info("Testing DRY-RUN Notification System")
    logger.info("=" * 70)

    try:
        # Fetch real data
        client = DarwinClient(library="departureboard.io")
        board = await client.get_departures("ELY", time_window=120, max_results=5)

        if not board or not board.services:
            logger.warning("No services found - cannot test notifications")
            return

        # Create station config
        station_config = StationConfig(
            crs_code="ELY",
            station_name="Ely",
            enabled=True,
            monitoring_mode=MonitoringMode.DEPARTURES,
            check_interval_minutes=5,
            telegram_chat_id="-1001234567890",  # Dummy chat ID
        )

        # Simulate some changes from the real data
        changes = []
        for service in board.services[:3]:  # Use first 3 services
            if service.delay_minutes > 0:
                # Real delay found
                change = TrainChange(
                    change_type=ChangeType.DELAY,
                    service_id=service.service_id,
                    service=service,
                    old_value=service.scheduled_departure,
                    new_value=service.estimated_departure or service.scheduled_departure,
                    severity=ChangeSeverity.MEDIUM if service.delay_minutes >= 10 else ChangeSeverity.LOW,
                )
                changes.append(change)

        if not changes:
            # If no real delays, simulate one for testing
            logger.info("\nNo delays found in real data. Simulating a delay for testing...")
            if board.services:
                service = board.services[0]
                change = TrainChange(
                    change_type=ChangeType.DELAY,
                    service_id=service.service_id,
                    service=service,
                    old_value=service.scheduled_departure,
                    new_value="(simulated delay)",
                    severity=ChangeSeverity.MEDIUM,
                )
                changes.append(change)

        # Get notifier in DRY-RUN mode
        logger.info("\nCreating notifier in DRY-RUN mode...")
        notifier = get_notifier(dry_run=True)

        # Send notification (will only log, not send to Telegram)
        logger.info("\nSending notification (DRY-RUN)...\n")
        await notifier.send_notification(changes, station_config)

        logger.info("\n" + "=" * 70)
        logger.info("✅ DRY-RUN notification test completed!")
        logger.info("=" * 70)

    except Exception as e:
        logger.exception(f"\n❌ Error in notification test: {e}")


async def test_multiple_stations():
    """Test fetching data for multiple stations using departureboard.io."""
    logger.info("\n" + "=" * 70)
    logger.info("Testing Multiple Stations")
    logger.info("=" * 70)

    client = DarwinClient(library="departureboard.io")
    stations = [
        ("ELY", "Ely"),
        ("CBG", "Cambridge"),
        ("KGX", "London Kings Cross"),
        ("NRW", "Norwich"),
    ]

    results = {}
    for crs, name in stations:
        try:
            logger.info(f"\nFetching {name} ({crs})...")
            board = await client.get_departures(crs, time_window=60, max_results=3)

            if board and board.services:
                results[crs] = len(board.services)
                logger.info(f"✅ {name}: {len(board.services)} services found")

                # Show first service
                first = board.services[0]
                logger.info(f"   Example: {first.origin} → {first.destination} at {first.scheduled_departure}")
            else:
                results[crs] = 0
                logger.info(f"⚠️ {name}: No services found")

        except Exception as e:
            logger.error(f"❌ {name}: Failed - {e}")
            results[crs] = -1

    # Summary
    logger.info("\n" + "-" * 70)
    logger.info("Summary:")
    logger.info("-" * 70)
    for crs, name in stations:
        count = results.get(crs, -1)
        if count > 0:
            logger.info(f"✅ {name} ({crs}): {count} services")
        elif count == 0:
            logger.info(f"⚠️ {name} ({crs}): No services")
        else:
            logger.info(f"❌ {name} ({crs}): Error")


async def main():
    """Main test function."""
    logger.info("Starting departureboard.io integration tests...\n")

    # Test 1: Basic API connection
    board = await test_departureboard_io_basic()

    if board:
        # Test 2: DRY-RUN notification system
        await test_dry_run_notification()

        # Test 3: Multiple stations
        await test_multiple_stations()

    logger.info("\n" + "=" * 70)
    logger.info("All tests completed")
    logger.info("=" * 70)

    return board is not None


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
