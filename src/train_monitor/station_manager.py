"""
Station Manager for orchestrating multi-station train monitoring.

Manages parallel monitoring of multiple stations, coordinating
Darwin API client, State Manager, and Notifier for each station.
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime

from src.train_monitor.darwin_client import DarwinClient, DarwinAPIError
from src.train_monitor.state_manager import StateManager
from src.train_monitor.notifier import BaseNotifier, get_notifier
from src.train_monitor.models import StationConfig, MonitoringMode
from src.train_monitor.providers.base import StationConfigProvider
from src.utils.logger import get_logger
from src.utils.config import get_settings

logger = get_logger()


class StationMonitoringTask:
    """
    Monitoring task for a single station.

    Manages periodic checks for one station, tracking state
    and sending notifications when changes occur.
    """

    def __init__(
        self,
        station_config: StationConfig,
        darwin_client: DarwinClient,
        state_manager: StateManager,
        notifier: BaseNotifier,
    ):
        """
        Initialize station monitoring task.

        Args:
            station_config: Station configuration
            darwin_client: Darwin API client (shared)
            state_manager: State manager (shared)
            notifier: Notifier for sending alerts (shared)
        """
        self.config = station_config
        self.darwin_client = darwin_client
        self.state_manager = state_manager
        self.notifier = notifier

        self.task: Optional[asyncio.Task] = None
        self.is_running = False
        self.last_check: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.check_count = 0
        self.error_count = 0

    async def start(self):
        """Start monitoring task for this station."""
        if self.is_running:
            logger.warning(f"Station {self.config.crs_code} monitoring already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            f"Started monitoring for {self.config.station_name} ({self.config.crs_code}) "
            f"- check interval: {self.config.check_interval_minutes} minutes"
        )

    async def stop(self):
        """Stop monitoring task for this station."""
        if not self.is_running:
            return

        self.is_running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info(f"Stopped monitoring for {self.config.station_name} ({self.config.crs_code})")

    async def _monitoring_loop(self):
        """Main monitoring loop for this station."""
        logger.info(f"Monitoring loop started for {self.config.crs_code}")

        while self.is_running:
            try:
                await self._perform_check()
                self.last_error = None

            except DarwinAPIError as e:
                self.error_count += 1
                self.last_error = str(e)
                logger.error(
                    f"Darwin API error for {self.config.crs_code}: {e} "
                    f"(error count: {self.error_count})"
                )

            except Exception as e:
                self.error_count += 1
                self.last_error = str(e)
                logger.exception(
                    f"Unexpected error in monitoring loop for {self.config.crs_code}: {e}"
                )

            # Wait for next check
            if self.is_running:
                await asyncio.sleep(self.config.check_interval_minutes * 60)

    async def _perform_check(self):
        """Perform a single monitoring check."""
        self.check_count += 1
        self.last_check = datetime.now()

        logger.debug(
            f"Performing check #{self.check_count} for {self.config.crs_code} "
            f"(mode: {self.config.monitoring_mode})"
        )

        # Fetch current board from Darwin API
        if self.config.monitoring_mode == MonitoringMode.DEPARTURES:
            current_board = await self.darwin_client.get_departures(
                station_crs=self.config.crs_code,
                time_window=self.config.time_window_minutes,
                max_results=self.config.max_services
            )
        elif self.config.monitoring_mode == MonitoringMode.ARRIVALS:
            current_board = await self.darwin_client.get_arrivals(
                station_crs=self.config.crs_code,
                time_window=self.config.time_window_minutes,
                max_results=self.config.max_services
            )
        else:  # BOTH - fetch both departures and arrivals (TODO: implement)
            # For now, just fetch departures
            logger.warning(f"BOTH mode not fully implemented, using DEPARTURES only")
            current_board = await self.darwin_client.get_departures(
                station_crs=self.config.crs_code,
                time_window=self.config.time_window_minutes,
                max_results=self.config.max_services
            )

        logger.debug(
            f"Fetched board for {self.config.crs_code}: "
            f"{len(current_board.services)} services"
        )

        # Detect changes using state manager
        changes = self.state_manager.update_and_detect_changes(
            station_config=self.config,
            current_board=current_board
        )

        # Send notifications if changes detected
        if changes and self.config.notification_enabled:
            logger.info(
                f"Detected {len(changes)} changes for {self.config.crs_code}, "
                f"sending notification"
            )

            try:
                await self.notifier.send_notification(
                    changes=changes,
                    station_config=self.config
                )
            except Exception as e:
                logger.error(f"Failed to send notification for {self.config.crs_code}: {e}")

    def get_health_status(self) -> Dict:
        """
        Get health status for this station.

        Returns:
            Health status dictionary
        """
        return {
            "crs_code": self.config.crs_code,
            "station_name": self.config.station_name,
            "is_running": self.is_running,
            "enabled": self.config.enabled,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_count": self.check_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "check_interval_minutes": self.config.check_interval_minutes,
        }


class StationManager:
    """
    Manages monitoring for multiple train stations.

    Orchestrates Darwin API client, State Manager, and Notifier
    to monitor multiple stations in parallel.
    """

    def __init__(
        self,
        config_provider: StationConfigProvider,
        dry_run: Optional[bool] = None
    ):
        """
        Initialize station manager.

        Args:
            config_provider: Provider for station configurations
            dry_run: Override DRY_RUN mode (None = use settings)
        """
        self.config_provider = config_provider
        self.settings = get_settings()

        # Use provided dry_run or fall back to settings
        if dry_run is None:
            dry_run = self.settings.train_monitor_dry_run

        # Initialize shared components
        self.darwin_client = DarwinClient()
        self.state_manager = StateManager()
        self.notifier = get_notifier(dry_run=dry_run)

        # Track monitoring tasks by CRS code
        self.tasks: Dict[str, StationMonitoringTask] = {}

        # Manager state
        self.is_running = False
        self.start_time: Optional[datetime] = None

        logger.info(
            f"StationManager initialized (dry_run={dry_run}, "
            f"provider={type(config_provider).__name__})"
        )

    async def start(self):
        """
        Start monitoring all enabled stations.

        Loads station configurations and starts monitoring tasks.
        """
        if self.is_running:
            logger.warning("StationManager already running")
            return

        self.is_running = True
        self.start_time = datetime.now()

        logger.info("=" * 70)
        logger.info("Starting Train Monitor - Station Manager")
        logger.info("=" * 70)

        # Load station configurations
        stations = await self.config_provider.get_stations()
        enabled_stations = [s for s in stations if s.enabled]

        logger.info(f"Loaded {len(stations)} station(s), {len(enabled_stations)} enabled")

        if not enabled_stations:
            logger.warning("No enabled stations found!")
            return

        # Create and start monitoring tasks
        for station_config in enabled_stations:
            await self._start_station_monitoring(station_config)

        logger.info("=" * 70)
        logger.info(f"All {len(self.tasks)} station monitoring tasks started")
        logger.info("=" * 70)

    async def stop(self):
        """
        Stop all monitoring tasks gracefully.

        Waits for all tasks to complete before returning.
        """
        if not self.is_running:
            return

        logger.info("=" * 70)
        logger.info("Stopping Train Monitor - Station Manager")
        logger.info("=" * 70)

        self.is_running = False

        # Stop all monitoring tasks
        stop_tasks = [task.stop() for task in self.tasks.values()]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self.tasks.clear()

        logger.info("All station monitoring tasks stopped")
        logger.info("=" * 70)

    async def reload_config(self):
        """
        Reload station configurations and restart tasks.

        Useful for updating monitoring without full restart.
        """
        logger.info("Reloading station configurations...")

        # Load new configurations
        new_stations = await self.config_provider.get_stations()
        new_stations_map = {s.crs_code: s for s in new_stations if s.enabled}

        current_crs_codes = set(self.tasks.keys())
        new_crs_codes = set(new_stations_map.keys())

        # Find stations to stop (removed or disabled)
        to_stop = current_crs_codes - new_crs_codes
        for crs_code in to_stop:
            logger.info(f"Stopping removed/disabled station: {crs_code}")
            await self._stop_station_monitoring(crs_code)

        # Find stations to start (new or re-enabled)
        to_start = new_crs_codes - current_crs_codes
        for crs_code in to_start:
            logger.info(f"Starting new/enabled station: {crs_code}")
            await self._start_station_monitoring(new_stations_map[crs_code])

        # Update configurations for existing stations
        to_update = current_crs_codes & new_crs_codes
        for crs_code in to_update:
            old_config = self.tasks[crs_code].config
            new_config = new_stations_map[crs_code]

            # Check if configuration changed
            if self._config_changed(old_config, new_config):
                logger.info(f"Restarting station with updated config: {crs_code}")
                await self._stop_station_monitoring(crs_code)
                await self._start_station_monitoring(new_config)
            else:
                logger.debug(f"No config changes for station: {crs_code}")

        logger.info(
            f"Config reload complete: "
            f"{len(to_stop)} stopped, {len(to_start)} started, "
            f"{len(to_update)} checked for updates"
        )

    async def _start_station_monitoring(self, station_config: StationConfig):
        """
        Start monitoring task for a single station.

        Args:
            station_config: Station configuration
        """
        task = StationMonitoringTask(
            station_config=station_config,
            darwin_client=self.darwin_client,
            state_manager=self.state_manager,
            notifier=self.notifier
        )

        await task.start()
        self.tasks[station_config.crs_code] = task

    async def _stop_station_monitoring(self, crs_code: str):
        """
        Stop monitoring task for a single station.

        Args:
            crs_code: Station CRS code
        """
        task = self.tasks.pop(crs_code, None)
        if task:
            await task.stop()
            # Clear state for this station
            self.state_manager.clear_station_state(crs_code)

    def _config_changed(self, old: StationConfig, new: StationConfig) -> bool:
        """
        Check if station configuration changed.

        Args:
            old: Old configuration
            new: New configuration

        Returns:
            True if configuration changed
        """
        # Compare relevant fields
        return (
            old.check_interval_minutes != new.check_interval_minutes
            or old.monitoring_mode != new.monitoring_mode
            or old.time_window_minutes != new.time_window_minutes
            or old.max_services != new.max_services
            or old.notification_enabled != new.notification_enabled
            or old.telegram_chat_ids != new.telegram_chat_ids
            or old.filters != new.filters
        )

    def get_health_status(self) -> Dict:
        """
        Get health status for all stations.

        Returns:
            Overall health status with per-station details
        """
        station_statuses = [
            task.get_health_status()
            for task in self.tasks.values()
        ]

        # Calculate overall statistics
        total_checks = sum(s["check_count"] for s in station_statuses)
        total_errors = sum(s["error_count"] for s in station_statuses)
        running_count = sum(1 for s in station_statuses if s["is_running"])

        return {
            "manager_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "total_stations": len(self.tasks),
            "running_stations": running_count,
            "total_checks": total_checks,
            "total_errors": total_errors,
            "stations": station_statuses,
        }

    def get_station_status(self, crs_code: str) -> Optional[Dict]:
        """
        Get health status for a specific station.

        Args:
            crs_code: Station CRS code

        Returns:
            Station health status or None if not found
        """
        task = self.tasks.get(crs_code)
        return task.get_health_status() if task else None

    async def run_forever(self):
        """
        Run station manager indefinitely.

        Useful for running as standalone service.
        """
        await self.start()

        try:
            # Keep running until interrupted
            while self.is_running:
                await asyncio.sleep(60)  # Sleep in chunks to allow interruption

        except asyncio.CancelledError:
            logger.info("Station manager interrupted")

        finally:
            await self.stop()
