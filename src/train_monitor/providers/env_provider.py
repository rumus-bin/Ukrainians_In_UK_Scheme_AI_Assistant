"""Environment variables station configuration provider."""

import os
from typing import List, Optional
from datetime import datetime

from src.train_monitor.providers.base import StationConfigProvider
from src.train_monitor.models import StationConfig, MonitoringMode, NotificationFilter
from src.utils.logger import get_logger

logger = get_logger()


class EnvStationProvider(StationConfigProvider):
    """
    Provider for reading station configuration from environment variables.

    Supports multiple stations via separators.

    .env format:
    TRAIN_MONITOR_STATIONS=ELY,CBG,KGX
    TRAIN_MONITOR_ELY_NAME=Ely
    TRAIN_MONITOR_ELY_ENABLED=true
    TRAIN_MONITOR_ELY_CHECK_INTERVAL=5
    TRAIN_MONITOR_ELY_CHAT_IDS=-1001234567890,-1009876543210  # Multiple chats (comma-separated)
    # OR single chat (backward compatible):
    # TRAIN_MONITOR_ELY_CHAT_ID=-1001234567890
    ...
    """

    def __init__(self):
        """Initialize provider."""
        self._stations_cache: Optional[List[StationConfig]] = None

    async def get_stations(self) -> List[StationConfig]:
        """Get list of all stations from .env."""
        if self._stations_cache is not None:
            return self._stations_cache

        # Get list of CRS codes
        stations_str = os.getenv("TRAIN_MONITOR_STATIONS", "ELY")
        crs_codes = [code.strip().upper() for code in stations_str.split(",")]

        stations = []
        for crs in crs_codes:
            config = await self._parse_station_config(crs)
            if config:
                stations.append(config)

        self._stations_cache = stations
        logger.info(
            f"Loaded {len(stations)} stations from environment: "
            f"{[s.crs_code for s in stations]}"
        )
        return stations

    async def get_station(self, crs_code: str) -> Optional[StationConfig]:
        """Get configuration for specific station."""
        stations = await self.get_stations()
        for station in stations:
            if station.crs_code.upper() == crs_code.upper():
                return station
        return None

    async def _parse_station_config(self, crs: str) -> Optional[StationConfig]:
        """
        Parse station configuration from environment variables.

        Args:
            crs: CRS code of the station

        Returns:
            Optional[StationConfig]: Configuration or None on error
        """
        prefix = f"TRAIN_MONITOR_{crs}_"

        try:
            # Core parameters
            station_name = os.getenv(f"{prefix}NAME", crs)
            enabled = os.getenv(f"{prefix}ENABLED", "true").lower() == "true"

            # Monitoring mode
            mode_str = os.getenv(f"{prefix}MODE", "departures").lower()
            try:
                monitoring_mode = MonitoringMode(mode_str)
            except ValueError:
                logger.warning(
                    f"Invalid monitoring mode '{mode_str}' for station {crs}, "
                    f"using default 'departures'"
                )
                monitoring_mode = MonitoringMode.DEPARTURES

            # Intervals
            check_interval = int(os.getenv(f"{prefix}CHECK_INTERVAL", "5"))
            time_window = int(os.getenv(f"{prefix}TIME_WINDOW", "120"))

            # Telegram - support both CHAT_ID (single) and CHAT_IDS (multiple, comma-separated)
            chat_ids_str = os.getenv(f"{prefix}CHAT_IDS") or os.getenv(f"{prefix}CHAT_ID")
            chat_ids = []
            if chat_ids_str:
                # Parse comma-separated list of chat IDs
                chat_ids = [chat_id.strip() for chat_id in chat_ids_str.split(",") if chat_id.strip()]
            notification_enabled = os.getenv(f"{prefix}NOTIFICATIONS", "true").lower() == "true"

            # Filters
            min_delay = int(os.getenv(f"{prefix}MIN_DELAY", "5"))
            notify_cancellations = os.getenv(f"{prefix}NOTIFY_CANCELLATIONS", "true").lower() == "true"
            notify_platform_changes = os.getenv(f"{prefix}NOTIFY_PLATFORM", "true").lower() == "true"
            notify_new_services = os.getenv(f"{prefix}NOTIFY_NEW", "false").lower() == "true"

            # Destination filter
            destinations_str = os.getenv(f"{prefix}DESTINATIONS")
            destination_filter = None
            if destinations_str:
                destination_filter = [d.strip().upper() for d in destinations_str.split(",")]

            # Time window
            time_start = os.getenv(f"{prefix}TIME_START")
            time_end = os.getenv(f"{prefix}TIME_END")

            # Metadata
            description = os.getenv(f"{prefix}DESCRIPTION")
            tags_str = os.getenv(f"{prefix}TAGS", "")
            tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]

            # Create configuration
            config = StationConfig(
                crs_code=crs,
                station_name=station_name,
                enabled=enabled,
                monitoring_mode=monitoring_mode,
                check_interval_minutes=check_interval,
                time_window_minutes=time_window,
                telegram_chat_ids=chat_ids,
                notification_enabled=notification_enabled,
                filters=NotificationFilter(
                    min_delay_minutes=min_delay,
                    notify_cancellations=notify_cancellations,
                    notify_platform_changes=notify_platform_changes,
                    notify_new_services=notify_new_services,
                    destination_filter=destination_filter,
                    time_range_start=time_start,
                    time_range_end=time_end
                ),
                description=description,
                added_at=datetime.now(),
                tags=tags
            )

            logger.debug(f"Parsed config for station {crs}: {config}")
            return config

        except Exception as e:
            logger.error(f"Error parsing config for station {crs}: {e}")
            return None

    async def add_station(self, config: StationConfig) -> bool:
        """EnvProvider does not support adding stations."""
        logger.warning("EnvStationProvider does not support adding stations")
        return False

    async def update_station(self, crs_code: str, config: StationConfig) -> bool:
        """EnvProvider does not support updating stations."""
        logger.warning("EnvStationProvider does not support updating stations")
        return False

    async def remove_station(self, crs_code: str) -> bool:
        """EnvProvider does not support removing stations."""
        logger.warning("EnvStationProvider does not support removing stations")
        return False

    async def reload(self) -> None:
        """Reload configuration from .env."""
        self._stations_cache = None
        logger.info("Station configuration reloaded from environment")
