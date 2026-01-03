"""
Darwin API client for UK National Rail data.

Supports both nrewebservices and nre-darwin-py libraries.
Provides retry logic and error handling for robust API access.
"""

import asyncio
import httpx
from typing import List, Optional, Literal
from datetime import datetime

from src.train_monitor.models import TrainService, StationBoard, ServiceStatus
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class DarwinAPIError(Exception):
    """Exception raised for Darwin API errors."""
    pass


class DarwinClient:
    """
    Client for accessing Darwin API (UK National Rail).

    Supports SOAP API via nrewebservices library with retry logic
    and error handling.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        wsdl_url: Optional[str] = None,
        library: Optional[Literal["nrewebservices", "nre-darwin-py", "departureboard.io"]] = None
    ):
        """
        Initialize Darwin client.

        Args:
            api_key: Darwin API key (reads from settings if None, not needed for departureboard.io)
            wsdl_url: WSDL URL (reads from settings if None)
            library: Which library/API to use (auto-detects if None)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.darwin_api_key
        self.wsdl_url = wsdl_url or self.settings.darwin_wsdl_url

        # Auto-detect library based on API key availability
        if library is None:
            if self.api_key and self.api_key != "" and self.api_key != "your_darwin_api_key_here":
                library = "nrewebservices"  # Use official API when key is available
                logger.info(f"✅ Darwin API key detected - using official Darwin API (nrewebservices)")
            else:
                library = "departureboard.io"  # Fall back to free proxy
                logger.info("ℹ️ No Darwin API key - falling back to departureboard.io")

        self.library = library
        self._session = None
        self._connected = False

        # departureboard.io doesn't need API key
        if library == "departureboard.io":
            self._connected = True
            logger.info("✅ Darwin client initialized with departureboard.io (no API key required)")
        elif not self.api_key or self.api_key == "" or self.api_key == "your_darwin_api_key_here":
            logger.warning("⚠️ Darwin API key not configured!")
        else:
            logger.info(f"✅ Darwin client initialized with {library} library")

    def _initialize_session(self):
        """Initialize Darwin API session (lazy loading)."""
        if self._session is not None:
            return

        if self.library == "nrewebservices":
            try:
                from nrewebservices.ldbws import Session
                logger.info("Initializing nrewebservices session...")
                logger.info(f"WSDL URL: {self.wsdl_url}")

                # Initialize session (this caches WSDL)
                self._session = Session(
                    wsdl=self.wsdl_url,
                    api_key=self.api_key
                )
                self._connected = True
                logger.info("✅ nrewebservices session initialized successfully")

            except ImportError:
                raise DarwinAPIError(
                    "nrewebservices library not installed. "
                    "Install with: pip install nrewebservices"
                )
            except Exception as e:
                logger.error(f"Failed to initialize nrewebservices: {e}")
                raise DarwinAPIError(f"Failed to initialize Darwin session: {e}")

        elif self.library == "nre-darwin-py":
            try:
                from nre_darwin.webservice import DarwinLdbSession
                logger.info("Initializing nre-darwin-py session...")

                self._session = DarwinLdbSession(
                    wsdl=self.wsdl_url,
                    api_key=self.api_key
                )
                self._connected = True
                logger.info("✅ nre-darwin-py session initialized successfully")

            except ImportError:
                raise DarwinAPIError(
                    "nre-darwin-py library not installed. "
                    "Install with: pip install nre-darwin-py"
                )
            except Exception as e:
                logger.error(f"Failed to initialize nre-darwin-py: {e}")
                raise DarwinAPIError(f"Failed to initialize Darwin session: {e}")
        else:
            raise ValueError(f"Unknown library: {self.library}")

    async def get_departures(
        self,
        station_crs: str,
        time_window: int = 120,
        max_results: int = 50
    ) -> StationBoard:
        """
        Get departure board for a station.

        Args:
            station_crs: 3-letter CRS code (e.g., 'ELY')
            time_window: Time window in minutes (default 120)
            max_results: Maximum number of services to return

        Returns:
            StationBoard: Departure board with services

        Raises:
            DarwinAPIError: If API call fails
        """
        return await self._get_board(
            station_crs=station_crs,
            time_window=time_window,
            max_results=max_results,
            board_type="departures"
        )

    async def get_arrivals(
        self,
        station_crs: str,
        time_window: int = 120,
        max_results: int = 50
    ) -> StationBoard:
        """
        Get arrival board for a station.

        Args:
            station_crs: 3-letter CRS code (e.g., 'ELY')
            time_window: Time window in minutes (default 120)
            max_results: Maximum number of services to return

        Returns:
            StationBoard: Arrival board with services

        Raises:
            DarwinAPIError: If API call fails
        """
        return await self._get_board(
            station_crs=station_crs,
            time_window=time_window,
            max_results=max_results,
            board_type="arrivals"
        )

    async def _get_board(
        self,
        station_crs: str,
        time_window: int,
        max_results: int,
        board_type: Literal["departures", "arrivals"]
    ) -> StationBoard:
        """
        Get station board (internal method with retry logic).

        Args:
            station_crs: Station CRS code
            time_window: Time window in minutes
            max_results: Max number of services
            board_type: Type of board to fetch

        Returns:
            StationBoard: Station board data

        Raises:
            DarwinAPIError: If all retries fail
        """
        # Ensure session is initialized
        if not self._connected:
            self._initialize_session()

        # Retry configuration
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Fetching {board_type} for {station_crs} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

                # Call appropriate method based on library
                if self.library == "departureboard.io":
                    board_data = await self._fetch_departureboard_io(
                        station_crs, time_window, max_results, board_type
                    )
                elif self.library == "nrewebservices":
                    board_data = await self._fetch_nrewebservices(
                        station_crs, time_window, max_results, board_type
                    )
                else:  # nre-darwin-py
                    board_data = await self._fetch_nre_darwin_py(
                        station_crs, time_window, max_results, board_type
                    )

                logger.info(
                    f"✅ Successfully fetched {len(board_data.services)} services "
                    f"for {station_crs}"
                )
                return board_data

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for {station_crs}: {e}"
                )

                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    # All retries failed
                    logger.error(
                        f"❌ Failed to fetch {board_type} for {station_crs} "
                        f"after {max_retries} attempts"
                    )
                    raise DarwinAPIError(
                        f"Failed to fetch {board_type} for {station_crs}: {e}"
                    )

    async def _fetch_departureboard_io(
        self,
        station_crs: str,
        time_window: int,
        max_results: int,
        board_type: str
    ) -> StationBoard:
        """Fetch board using departureboard.io REST API."""
        base_url = "https://api.departureboard.io/api/v1.0"
        endpoint = f"{base_url}/getArrivalsAndDeparturesByCRS/{station_crs.upper()}/"

        logger.debug(f"Fetching from departureboard.io: {endpoint}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(endpoint)

            if response.status_code != 200:
                raise DarwinAPIError(
                    f"departureboard.io returned status {response.status_code}: {response.text}"
                )

            data = response.json()

        # Parse the JSON response
        return self._parse_departureboard_io_response(data, station_crs, board_type, max_results)

    def _parse_departureboard_io_response(
        self,
        data: dict,
        station_crs: str,
        board_type: str,
        max_results: int
    ) -> StationBoard:
        """
        Parse departureboard.io JSON response.

        Args:
            data: JSON response from departureboard.io
            station_crs: Station CRS code
            board_type: Type of board (departures/arrivals)
            max_results: Maximum number of services

        Returns:
            StationBoard: Parsed board
        """
        services = []

        # Get location name
        station_name = data.get('locationName', station_crs)

        # Choose which services to parse based on board_type
        if board_type == "departures":
            raw_services = data.get('departures', {}).get('all', [])
        else:  # arrivals
            raw_services = data.get('arrivals', {}).get('all', [])

        # Limit results
        raw_services = raw_services[:max_results]

        for raw_service in raw_services:
            try:
                service = self._parse_departureboard_io_service(raw_service)
                services.append(service)
            except Exception as e:
                logger.warning(f"Failed to parse service: {e}")
                continue

        return StationBoard(
            station_crs=station_crs.upper(),
            station_name=station_name,
            generated_at=datetime.now(),
            services=services
        )

    def _parse_departureboard_io_service(self, raw: dict) -> TrainService:
        """
        Parse a single service from departureboard.io.

        Args:
            raw: Raw service dict from API

        Returns:
            TrainService: Parsed service
        """
        # Service ID
        service_id = raw.get('serviceIdUrlSafe', raw.get('trainid', 'UNKNOWN'))

        # Origin and destination
        origin = raw.get('origin', {}).get('location', 'Unknown')
        destination = raw.get('destination', {}).get('location', 'Unknown')
        dest_crs = raw.get('destination', {}).get('crs')

        # Times (format: "HH:MM" or special values like "On time", "Delayed", "Cancelled")
        std = raw.get('std')  # Scheduled time of departure
        etd = raw.get('etd')  # Estimated time of departure
        atd = raw.get('atd')  # Actual time of departure

        sta = raw.get('sta')  # Scheduled time of arrival
        eta = raw.get('eta')  # Estimated time of arrival
        ata = raw.get('ata')  # Actual time of arrival

        # Platform
        platform = raw.get('platform')

        # Operator
        operator = raw.get('operator')

        # Status and cancellation
        is_cancelled = raw.get('isCancelled', False)
        cancel_reason = raw.get('cancelReason')

        # Determine status and calculate delay
        status = ServiceStatus.NO_REPORT
        delay_minutes = 0

        if is_cancelled:
            status = ServiceStatus.CANCELLED
        elif etd:
            if etd == "On time":
                status = ServiceStatus.ON_TIME
            elif etd == "Delayed":
                status = ServiceStatus.DELAYED
                delay_minutes = 5  # Default assumption
            elif etd == "Cancelled":
                status = ServiceStatus.CANCELLED
                is_cancelled = True
            else:
                # etd is actual time, calculate delay
                status = ServiceStatus.DELAYED
                delay_minutes = self._calculate_delay(std, etd)

        return TrainService(
            service_id=service_id,
            origin=origin,
            destination=destination,
            destination_crs=dest_crs,
            scheduled_departure=std,
            estimated_departure=etd if etd not in ["On time", "Delayed", "Cancelled"] else std,
            actual_departure=atd,
            scheduled_arrival=sta,
            estimated_arrival=eta if eta not in ["On time", "Delayed", "Cancelled"] else sta,
            actual_arrival=ata,
            platform=platform,
            status=status,
            delay_minutes=delay_minutes,
            operator=operator,
            is_cancelled=is_cancelled,
            cancellation_reason=cancel_reason
        )

    async def _fetch_nrewebservices(
        self,
        station_crs: str,
        time_window: int,
        max_results: int,
        board_type: str
    ) -> StationBoard:
        """Fetch board using nrewebservices library."""
        # Run in thread pool since nrewebservices is synchronous
        loop = asyncio.get_event_loop()

        def _fetch():
            if board_type == "departures":
                return self._session.get_station_board(
                    crs=station_crs.upper(),
                    rows=max_results,
                    time_window=time_window
                )
            else:  # arrivals
                return self._session.get_arrival_board(
                    crs=station_crs.upper(),
                    rows=max_results,
                    time_window=time_window
                )

        raw_board = await loop.run_in_executor(None, _fetch)

        # Convert to our StationBoard model
        return self._parse_nrewebservices_board(raw_board, station_crs)

    async def _fetch_nre_darwin_py(
        self,
        station_crs: str,
        time_window: int,
        max_results: int,
        board_type: str
    ) -> StationBoard:
        """Fetch board using nre-darwin-py library."""
        # Run in thread pool since nre-darwin-py is synchronous
        loop = asyncio.get_event_loop()

        def _fetch():
            if board_type == "departures":
                return self._session.get_station_board(station_crs.upper())
            else:  # arrivals
                return self._session.get_arrival_board(station_crs.upper())

        raw_board = await loop.run_in_executor(None, _fetch)

        # Convert to our StationBoard model
        return self._parse_nre_darwin_py_board(raw_board, station_crs)

    def _parse_nrewebservices_board(self, raw_board, station_crs: str) -> StationBoard:
        """
        Parse nrewebservices board response.

        Args:
            raw_board: Raw board object from nrewebservices
            station_crs: Station CRS code

        Returns:
            StationBoard: Parsed board
        """
        services = []

        if hasattr(raw_board, 'train_services') and raw_board.train_services:
            for raw_service in raw_board.train_services:
                try:
                    service = self._parse_nrewebservices_service(raw_service)
                    services.append(service)
                except Exception as e:
                    logger.warning(f"Failed to parse service: {e}")
                    continue

        station_name = getattr(raw_board, 'location_name', station_crs)

        return StationBoard(
            station_crs=station_crs.upper(),
            station_name=station_name,
            generated_at=datetime.now(),
            services=services
        )

    def _parse_nrewebservices_service(self, raw_service) -> TrainService:
        """Parse a single service from nrewebservices."""
        # Extract service details
        service_id = getattr(raw_service, 'service_id', None) or "UNKNOWN"

        # Origin and destination
        origin = self._extract_location_name(getattr(raw_service, 'origin', None))
        destination = self._extract_location_name(getattr(raw_service, 'destination', None))

        # Get destination CRS if available
        dest_crs = None
        if hasattr(raw_service, 'destination') and raw_service.destination:
            dest_crs = self._extract_location_crs(raw_service.destination)

        # Times
        std = getattr(raw_service, 'std', None)  # Scheduled time of departure
        etd = getattr(raw_service, 'etd', None)  # Estimated time of departure
        atd = getattr(raw_service, 'atd', None)  # Actual time of departure

        sta = getattr(raw_service, 'sta', None)  # Scheduled time of arrival
        eta = getattr(raw_service, 'eta', None)  # Estimated time of arrival
        ata = getattr(raw_service, 'ata', None)  # Actual time of arrival

        # Platform
        platform = getattr(raw_service, 'platform', None)

        # Operator
        operator = getattr(raw_service, 'operator', None)

        # Status and delay calculation
        is_cancelled = getattr(raw_service, 'is_cancelled', False)
        delay_minutes = 0
        status = ServiceStatus.NO_REPORT

        if is_cancelled:
            status = ServiceStatus.CANCELLED
        elif etd and etd != "On time":
            if etd == "Delayed":
                status = ServiceStatus.DELAYED
                # Try to calculate delay (this is approximate)
                delay_minutes = 5  # Default assumption
            elif etd == "Cancelled":
                status = ServiceStatus.CANCELLED
                is_cancelled = True
            else:
                # etd is actual time, calculate delay
                status = ServiceStatus.DELAYED
                delay_minutes = self._calculate_delay(std, etd)
        else:
            status = ServiceStatus.ON_TIME

        # Cancellation reason
        cancel_reason = getattr(raw_service, 'cancel_reason', None)

        return TrainService(
            service_id=service_id,
            origin=origin,
            destination=destination,
            destination_crs=dest_crs,
            scheduled_departure=std,
            estimated_departure=etd if etd not in ["On time", "Delayed", "Cancelled"] else std,
            actual_departure=atd,
            scheduled_arrival=sta,
            estimated_arrival=eta if eta not in ["On time", "Delayed", "Cancelled"] else sta,
            actual_arrival=ata,
            platform=platform,
            status=status,
            delay_minutes=delay_minutes,
            operator=operator,
            is_cancelled=is_cancelled,
            cancellation_reason=cancel_reason
        )

    def _parse_nre_darwin_py_board(self, raw_board, station_crs: str) -> StationBoard:
        """Parse nre-darwin-py board response (similar structure to nrewebservices)."""
        # nre-darwin-py has similar structure, reuse the same parsing logic
        return self._parse_nrewebservices_board(raw_board, station_crs)

    def _extract_location_name(self, location_list) -> str:
        """Extract location name from location list/object."""
        if not location_list:
            return "Unknown"

        # If it's already a string, return it directly
        if isinstance(location_list, str):
            return location_list

        # If it's a list, try to extract from first element
        if isinstance(location_list, list) and len(location_list) > 0:
            location = location_list[0]
            # Check if element is a string
            if isinstance(location, str):
                return location
            # Check for location_name attribute
            if hasattr(location, 'location_name'):
                return location.location_name
            elif hasattr(location, 'locationName'):
                return location.locationName

        # If it's an object with location_name attribute
        elif hasattr(location_list, 'location_name'):
            return location_list.location_name
        elif hasattr(location_list, 'locationName'):
            return location_list.locationName

        return "Unknown"

    def _extract_location_crs(self, location_list) -> Optional[str]:
        """Extract CRS code from location list/object."""
        if not location_list:
            return None

        if isinstance(location_list, list) and len(location_list) > 0:
            location = location_list[0]
            if hasattr(location, 'crs'):
                return location.crs
        elif hasattr(location_list, 'crs'):
            return location_list.crs

        return None

    def _calculate_delay(self, scheduled: Optional[str], estimated: Optional[str]) -> int:
        """
        Calculate delay in minutes.

        Args:
            scheduled: Scheduled time (HH:MM)
            estimated: Estimated time (HH:MM)

        Returns:
            int: Delay in minutes (0 if cannot calculate)
        """
        if not scheduled or not estimated:
            return 0

        try:
            # Parse times
            sched_parts = scheduled.split(':')
            est_parts = estimated.split(':')

            if len(sched_parts) != 2 or len(est_parts) != 2:
                return 0

            sched_minutes = int(sched_parts[0]) * 60 + int(sched_parts[1])
            est_minutes = int(est_parts[0]) * 60 + int(est_parts[1])

            delay = est_minutes - sched_minutes

            # Handle midnight crossing
            if delay < -600:  # If appears to go back more than 10 hours
                delay += 1440  # Add 24 hours

            return max(0, delay)

        except (ValueError, IndexError):
            logger.debug(f"Could not calculate delay from {scheduled} to {estimated}")
            return 0

    def health_check(self) -> dict:
        """
        Check Darwin API connection health.

        Returns:
            dict: Health status
        """
        try:
            if not self._connected:
                self._initialize_session()

            return {
                "healthy": True,
                "connected": self._connected,
                "library": self.library,
                "api_key_configured": bool(self.api_key and self.api_key != "")
            }
        except Exception as e:
            return {
                "healthy": False,
                "connected": False,
                "error": str(e),
                "library": self.library
            }
