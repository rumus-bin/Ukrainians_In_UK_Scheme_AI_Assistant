#!/usr/bin/env python3
"""
Train Monitor - Main Entry Point

Monitors UK train stations for delays, cancellations, and schedule changes.
Sends notifications to Telegram when changes are detected.

Usage:
    python -m src.train_monitor.monitor [OPTIONS]

Options:
    --dry-run              Run in DRY-RUN mode (log notifications, don't send to Telegram)
    --provider TYPE        Configuration provider type (env, file, database) [default: env]
    --help                 Show this help message

Environment Variables:
    TRAIN_MONITOR_ENABLED       Enable train monitoring (true/false)
    TRAIN_MONITOR_DRY_RUN       DRY-RUN mode (true/false)
    TRAIN_MONITOR_PROVIDER_TYPE Provider type (env/file/database)
    DARWIN_API_KEY              Darwin API key (if using OpenLDBWS)
    TRAIN_MONITOR_STATIONS      Comma-separated station CRS codes

Example:
    # Run with real notifications
    python -m src.train_monitor.monitor

    # Run in DRY-RUN mode (safe for testing)
    python -m src.train_monitor.monitor --dry-run

    # Run in Docker
    docker-compose exec bot python -m src.train_monitor.monitor
"""

import asyncio
import signal
import sys
from typing import Optional
from datetime import datetime

from src.train_monitor.station_manager import StationManager
from src.train_monitor.providers.env_provider import EnvStationProvider
from src.utils.logger import setup_logger, get_logger
from src.utils.config import get_settings

# Initialize logger
setup_logger()
logger = get_logger()

# Global reference to manager for signal handlers
_station_manager: Optional[StationManager] = None


def print_banner():
    """Print startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              🚂 UK TRAIN MONITOR - STATION MANAGER 🚂                ║
║                                                                      ║
║  Monitors UK train stations for delays, cancellations & changes     ║
║  Sends real-time notifications to Telegram                          ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info("Train Monitor starting...")
    logger.info(f"Start time: {datetime.now().isoformat()}")


def print_shutdown_banner():
    """Print shutdown banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                    Train Monitor Shut Down                           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    logger.info(f"Shutdown time: {datetime.now().isoformat()}")


def signal_handler(signum, frame):
    """
    Handle shutdown signals (SIGTERM, SIGINT).

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal: {signal_name}")
    logger.info("Initiating graceful shutdown...")

    if _station_manager and _station_manager.is_running:
        # Create new event loop for shutdown in signal handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_station_manager.stop())
        finally:
            loop.close()

    print_shutdown_banner()
    sys.exit(0)


def parse_args():
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments as dictionary
    """
    args = {
        "dry_run": None,  # None = use settings
        "provider_type": "env",
        "show_help": False,
    }

    for arg in sys.argv[1:]:
        if arg in ["--help", "-h"]:
            args["show_help"] = True
        elif arg == "--dry-run":
            args["dry_run"] = True
        elif arg.startswith("--provider="):
            args["provider_type"] = arg.split("=")[1]

    return args


def print_help():
    """Print help message."""
    print(__doc__)


async def main():
    """Main application entry point."""
    global _station_manager

    # Parse command-line arguments
    args = parse_args()

    if args["show_help"]:
        print_help()
        return 0

    # Print startup banner
    print_banner()

    # Load settings
    settings = get_settings()

    # Check if train monitor is enabled
    if not settings.train_monitor_enabled:
        logger.warning("=" * 70)
        logger.warning("⚠️  TRAIN MONITOR IS DISABLED")
        logger.warning("=" * 70)
        logger.warning("Set TRAIN_MONITOR_ENABLED=true in .env to enable monitoring")
        logger.warning("=" * 70)
        return 1

    # Determine DRY-RUN mode
    dry_run = args["dry_run"]
    if dry_run is None:
        dry_run = settings.train_monitor_dry_run

    # Log configuration
    logger.info("=" * 70)
    logger.info("CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"Enabled: {settings.train_monitor_enabled}")
    logger.info(f"DRY-RUN Mode: {dry_run}")
    logger.info(f"Provider Type: {args['provider_type']}")
    logger.info(f"Darwin API Key: {'✓ Configured' if settings.darwin_api_key else '✗ Not configured'}")
    logger.info("=" * 70)

    if dry_run:
        logger.info("🔧 DRY-RUN MODE ACTIVE")
        logger.info("   Notifications will be logged but NOT sent to Telegram")
        logger.info("   This is safe for testing and development")
        logger.info("=" * 70)

    # Create station configuration provider
    if args["provider_type"] == "env":
        provider = EnvStationProvider()
        logger.info("Using EnvStationProvider (reads from .env file)")
    else:
        logger.error(f"Unsupported provider type: {args['provider_type']}")
        logger.error("Currently supported: env")
        return 1

    # Create station manager
    try:
        _station_manager = StationManager(
            config_provider=provider,
            dry_run=dry_run
        )
        logger.info("✅ Station Manager created successfully")
    except Exception as e:
        logger.exception(f"❌ Failed to create Station Manager: {e}")
        return 1

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("✅ Signal handlers registered (SIGTERM, SIGINT)")

    # Start monitoring
    try:
        logger.info("=" * 70)
        logger.info("STARTING TRAIN MONITORING")
        logger.info("=" * 70)

        await _station_manager.start()

        logger.info("=" * 70)
        logger.info("✅ TRAIN MONITORING ACTIVE")
        logger.info("=" * 70)
        logger.info("Press Ctrl+C to stop monitoring")
        logger.info("=" * 70)

        # Run forever until interrupted
        await _station_manager.run_forever()

    except asyncio.CancelledError:
        logger.info("Monitoring cancelled")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        return 1
    finally:
        # Ensure clean shutdown
        if _station_manager and _station_manager.is_running:
            logger.info("Stopping Station Manager...")
            await _station_manager.stop()
            logger.info("✅ Station Manager stopped")

        print_shutdown_banner()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nTrain Monitor interrupted by user")
        print_shutdown_banner()
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
