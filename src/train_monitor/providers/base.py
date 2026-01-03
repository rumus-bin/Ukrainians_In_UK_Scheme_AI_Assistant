"""Base station configuration provider interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.train_monitor.models import StationConfig


class StationConfigProvider(ABC):
    """Abstract provider for station configuration."""

    @abstractmethod
    async def get_stations(self) -> List[StationConfig]:
        """
        Get list of all stations for monitoring.

        Returns:
            List[StationConfig]: List of station configurations
        """
        pass

    @abstractmethod
    async def get_station(self, crs_code: str) -> Optional[StationConfig]:
        """
        Get configuration for a specific station.

        Args:
            crs_code: CRS code of the station

        Returns:
            Optional[StationConfig]: Configuration or None if not found
        """
        pass

    @abstractmethod
    async def add_station(self, config: StationConfig) -> bool:
        """
        Add new station (optional, not all providers support this).

        Args:
            config: Station configuration

        Returns:
            bool: True if successfully added
        """
        pass

    @abstractmethod
    async def update_station(self, crs_code: str, config: StationConfig) -> bool:
        """
        Update station configuration.

        Args:
            crs_code: CRS code of the station
            config: New configuration

        Returns:
            bool: True if successfully updated
        """
        pass

    @abstractmethod
    async def remove_station(self, crs_code: str) -> bool:
        """
        Remove station from monitoring.

        Args:
            crs_code: CRS code of the station

        Returns:
            bool: True if successfully removed
        """
        pass

    @abstractmethod
    async def reload(self) -> None:
        """Reload configuration from source."""
        pass
