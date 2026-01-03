"""
Daily Train Monitor - performs scheduled checks once per day.

Checks train schedules once daily at configured time (default 7:00 AM)
and sends Ukrainian language summary to Telegram.
"""

import asyncio
import signal
import sys
from datetime import datetime, time
from typing import Optional
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.train_monitor.darwin_client import DarwinClient
from src.train_monitor.state_manager import StateManager
from src.train_monitor.providers.base import StationConfigProvider
from src.train_monitor.providers.env_provider import EnvStationProvider
from src.train_monitor.ukrainian_notifier import get_ukrainian_notifier
from src.train_monitor.models import StationConfig, MonitoringMode
from src.utils.logger import setup_logger, get_logger
from src.utils.config import get_settings

# Setup logging
setup_logger()
logger = get_logger()

# Global state for graceful shutdown
_scheduler: Optional[AsyncIOScheduler] = None
_shutdown_event = asyncio.Event()


class DailyTrainMonitor:
    """
    Daily train monitor that performs scheduled checks.

    Checks stations once per day and sends summary notifications.
    """

    def __init__(
        self,
        config_provider: StationConfigProvider,
        check_time: time = time(hour=7, minute=0),
        dry_run: bool = False
    ):
        """
        Initialize daily monitor.

        Args:
            config_provider: Provider for station configurations
            check_time: Time of day to perform checks (default 7:00 AM)
            dry_run: If True, logs notifications instead of sending
        """
        self.config_provider = config_provider
        self.check_time = check_time
        self.dry_run = dry_run

        self.darwin_client = DarwinClient()
        self.state_manager = StateManager()
        self.notifier = get_ukrainian_notifier(dry_run=dry_run)

        logger.info(
            f"DailyTrainMonitor initialized "
            f"(check_time={check_time.strftime('%H:%M')}, dry_run={dry_run})"
        )

    async def perform_daily_check(self):
        """
        Perform daily check for all enabled stations.

        Fetches current train data, detects changes, and sends summary.
        """
        logger.info("=" * 70)
        logger.info("Starting daily train check")
        logger.info(f"Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)

        try:
            # Get all enabled stations
            stations = await self.config_provider.get_stations()
            enabled_stations = [s for s in stations if s.enabled]

            if not enabled_stations:
                logger.warning("No enabled stations found")
                return

            logger.info(f"Checking {len(enabled_stations)} station(s)")

            # Check each station
            for station in enabled_stations:
                await self._check_station(station)

            logger.info("=" * 70)
            logger.info("Daily check completed successfully")
            logger.info("=" * 70)

        except Exception as e:
            logger.exception(f"Error during daily check: {e}")

    async def _check_station(self, station_config: StationConfig):
        """
        Check a single station for changes.

        Args:
            station_config: Station configuration
        """
        logger.info(f"\nChecking station: {station_config.station_name} ({station_config.crs_code})")

        try:
            # Get departure/arrival board
            if station_config.monitoring_mode == MonitoringMode.DEPARTURES:
                board = await self.darwin_client.get_departures(
                    station_crs=station_config.crs_code,
                    time_window=station_config.time_window_minutes,
                    max_results=station_config.max_services
                )
            elif station_config.monitoring_mode == MonitoringMode.ARRIVALS:
                board = await self.darwin_client.get_arrivals(
                    station_crs=station_config.crs_code,
                    time_window=station_config.time_window_minutes,
                    max_results=station_config.max_services
                )
            else:  # BOTH
                # Get departures for daily summary
                board = await self.darwin_client.get_departures(
                    station_crs=station_config.crs_code,
                    time_window=station_config.time_window_minutes,
                    max_results=station_config.max_services
                )

            if not board or not board.services:
                logger.info(f"No services found for {station_config.station_name}")
                logger.info("No notification sent - no services available")
                return

            logger.info(f"Found {len(board.services)} service(s)")

            # Detect changes
            changes = self.state_manager.update_and_detect_changes(station_config, board)

            if changes:
                logger.info(f"Detected {len(changes)} change(s):")
                for change in changes:
                    logger.info(f"  - {change.change_type.value}: {change.summary()}")

                # Send notification ONLY when changes are detected
                if station_config.notification_enabled and station_config.telegram_chat_ids:
                    message = self.notifier.format_daily_summary(
                        station_name=station_config.station_name,
                        changes=changes,
                        check_time=datetime.now()
                    )
                    # Send to all configured chats
                    for chat_id in station_config.telegram_chat_ids:
                        await self.notifier.notify(chat_id, message)
                        logger.info(f"✅ Summary sent to chat {chat_id}")
                    logger.info(f"✅ Notifications sent to {len(station_config.telegram_chat_ids)} chat(s)")
                else:
                    if not station_config.notification_enabled:
                        logger.info("Notifications disabled for this station - changes not sent")
                    else:
                        logger.info("No chat IDs configured - changes not sent")
            else:
                logger.info("No changes detected - all services on time")
                logger.info("No notification sent - everything is on schedule")

        except Exception as e:
            logger.exception(f"Error checking station {station_config.crs_code}: {e}")

    async def check_now(self):
        """
        Perform immediate check (for testing).

        Ignores scheduled time and checks immediately.
        """
        logger.info("=" * 70)
        logger.info("MANUAL CHECK REQUESTED")
        logger.info("=" * 70)
        await self.perform_daily_check()


async def scheduled_check():
    """Wrapper for scheduled check execution."""
    global _daily_monitor
    if _daily_monitor:
        await _daily_monitor.perform_daily_check()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    signal_name = signal.Signals(signum).name
    logger.info(f"\n{'='*70}")
    logger.info(f"Received signal: {signal_name}")
    logger.info(f"{'='*70}")
    logger.info("Initiating graceful shutdown...")

    # Stop scheduler
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler stopped")

    # Set shutdown event
    _shutdown_event.set()


def print_banner():
    """Print startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║           🚂 UK TRAIN MONITOR - DAILY SCHEDULER 🚂                   ║
║                                                                      ║
║  Щоденна перевірка розкладу поїздів                                  ║
║  Daily train schedule check with Ukrainian notifications            ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info("Daily Train Monitor starting...")
    logger.info(f"Start time: {datetime.now().isoformat()}")


async def main():
    """Main entry point for daily monitor."""
    global _scheduler, _daily_monitor

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="UK Train Monitor - Daily Scheduler")
    parser.add_argument(
        "--check-now",
        action="store_true",
        help="Perform immediate check and exit (for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log notifications instead of sending to Telegram"
    )
    parser.add_argument(
        "--time",
        type=str,
        default="07:00",
        help="Check time(s) in HH:MM format. Multiple times separated by comma (e.g., 07:00,09:00,12:00)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["env", "file", "database"],
        default="env",
        help="Configuration provider type"
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Parse check time(s) - support multiple times separated by comma
    check_times = []
    try:
        time_strings = [t.strip() for t in args.time.split(',')]
        for time_str in time_strings:
            hour, minute = map(int, time_str.split(':'))
            check_times.append(time(hour=hour, minute=minute))
    except ValueError:
        logger.error(f"Invalid time format: {args.time}. Use HH:MM or HH:MM,HH:MM,...")
        return 1

    # Use first time for backward compatibility with single-time config
    check_time = check_times[0]

    # Configuration
    settings = get_settings()
    dry_run = args.dry_run or settings.train_monitor_dry_run

    logger.info("=" * 70)
    logger.info("CONFIGURATION")
    logger.info("=" * 70)
    if len(check_times) == 1:
        logger.info(f"Check Time: {check_times[0].strftime('%H:%M')}")
    else:
        times_str = ", ".join([t.strftime('%H:%M') for t in check_times])
        logger.info(f"Check Times: {times_str} ({len(check_times)} times per day)")
    logger.info(f"DRY-RUN Mode: {dry_run}")
    logger.info(f"Provider Type: {args.provider}")
    logger.info(f"Darwin API Key: {'✓ Configured' if settings.darwin_api_key else '✗ Not set'}")
    logger.info("=" * 70)

    if dry_run:
        logger.info("🔧 DRY-RUN MODE ACTIVE")
        logger.info("   Notifications will be logged but NOT sent to Telegram")
        logger.info("   This is safe for testing and development")
        logger.info("=" * 70)

    # Create configuration provider
    if args.provider == "env":
        logger.info("Using EnvStationProvider (reads from .env file)")
        config_provider = EnvStationProvider()
    else:
        logger.error(f"Provider {args.provider} not yet implemented")
        return 1

    # Create daily monitor
    _daily_monitor = DailyTrainMonitor(
        config_provider=config_provider,
        check_time=check_time,
        dry_run=dry_run
    )

    logger.info("✅ Daily Monitor created successfully")

    # Check now mode (for testing)
    if args.check_now:
        logger.info("=" * 70)
        logger.info("IMMEDIATE CHECK MODE")
        logger.info("=" * 70)
        await _daily_monitor.check_now()
        logger.info("=" * 70)
        logger.info("✅ Check completed - exiting")
        logger.info("=" * 70)
        return 0

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("✅ Signal handlers registered (SIGTERM, SIGINT)")

    # Create and start scheduler
    logger.info("=" * 70)
    logger.info("STARTING SCHEDULER")
    logger.info("=" * 70)

    _scheduler = AsyncIOScheduler()

    # Add job for each check time
    for idx, check_time_item in enumerate(check_times):
        job_id = f'daily_train_check_{idx+1}'
        job_name = f'Daily Train Check ({check_time_item.strftime("%H:%M")})'

        _scheduler.add_job(
            scheduled_check,
            trigger=CronTrigger(hour=check_time_item.hour, minute=check_time_item.minute),
            id=job_id,
            name=job_name,
            replace_existing=True
        )
        logger.info(f"📅 Job {idx+1}: {check_time_item.strftime('%H:%M')} daily")

    _scheduler.start()

    logger.info(f"✅ Scheduler started with {len(check_times)} check(s) per day")
    logger.info("=" * 70)
    logger.info("✅ DAILY MONITOR ACTIVE")
    logger.info("=" * 70)
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Wait for shutdown signal
    try:
        await _shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")

    # Graceful shutdown
    logger.info("\n" + "=" * 70)
    logger.info("SHUTTING DOWN")
    logger.info("=" * 70)

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("✅ Scheduler shutdown complete")

    logger.info("=" * 70)
    logger.info("👋 Daily Train Monitor stopped")
    logger.info(f"Shutdown time: {datetime.now().isoformat()}")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nShutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
