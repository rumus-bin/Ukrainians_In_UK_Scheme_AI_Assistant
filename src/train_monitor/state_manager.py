"""
State Manager for tracking train service changes.

Compares current service state with previous state to detect changes
like delays, cancellations, and platform updates.

Supports persistent storage to survive container restarts.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json

from src.train_monitor.models import (
    StationBoard,
    TrainService,
    TrainChange,
    ChangeType,
    ChangeSeverity,
    StationConfig,
    ServiceStatus,
)
from src.utils.logger import get_logger

logger = get_logger()


class StateManager:
    """
    Manages train service state and detects changes.

    Stores previous service states for each station and compares
    with new data to identify delays, cancellations, and other changes.

    Supports persistent storage to survive container restarts.
    """

    # State file expiry threshold - discard if older than this
    STATE_EXPIRY_HOURS = 12

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        enable_persistence: bool = True
    ):
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state files (default: ./data/train_monitor_state)
            enable_persistence: Whether to enable file-based persistence
        """
        # Store previous boards by station CRS code
        # Format: {crs_code: StationBoard}
        self._previous_boards: Dict[str, StationBoard] = {}

        # Store previous services by service ID for quick lookup
        # Format: {crs_code: {service_id: TrainService}}
        self._previous_services: Dict[str, Dict[str, TrainService]] = {}

        # Persistence configuration
        self._enable_persistence = enable_persistence

        if state_dir is None:
            # Default to ./data/train_monitor_state
            self._state_dir = Path(__file__).parent.parent.parent / "data" / "train_monitor_state"
        else:
            self._state_dir = Path(state_dir)

        # Create state directory if persistence enabled
        if self._enable_persistence:
            try:
                self._state_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"State persistence enabled: {self._state_dir}")
            except Exception as e:
                logger.error(f"Failed to create state directory: {e}")
                logger.warning("Continuing without persistence")
                self._enable_persistence = False
        else:
            logger.info("State persistence disabled - using in-memory only")

    def _get_state_file_path(self, crs_code: str) -> Path:
        """
        Get path to state file for a station.

        Args:
            crs_code: Station CRS code

        Returns:
            Path to state file
        """
        return self._state_dir / f"{crs_code}_state.json"

    def save_state_to_disk(self, crs_code: str) -> bool:
        """
        Save state for a station to disk.

        Args:
            crs_code: Station CRS code

        Returns:
            True if saved successfully, False otherwise
        """
        if not self._enable_persistence:
            return False

        board = self._previous_boards.get(crs_code)
        if board is None:
            logger.debug(f"No state to save for {crs_code}")
            return False

        try:
            state_file = self._get_state_file_path(crs_code)

            # Create state object with metadata
            state_data = {
                "crs_code": crs_code,
                "saved_at": datetime.now().isoformat(),
                "board": board.model_dump(mode='json')
            }

            # Write to file atomically (write to temp, then rename)
            temp_file = state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2)

            # Atomic rename
            temp_file.replace(state_file)

            logger.debug(f"Saved state for {crs_code} to {state_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save state for {crs_code}: {e}")
            return False

    def load_state_from_disk(self, crs_code: str) -> bool:
        """
        Load state for a station from disk.

        Args:
            crs_code: Station CRS code

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self._enable_persistence:
            return False

        try:
            state_file = self._get_state_file_path(crs_code)

            if not state_file.exists():
                logger.debug(f"No saved state file for {crs_code}")
                return False

            # Read state file
            with open(state_file, 'r') as f:
                state_data = json.load(f)

            # Check if state is too old
            saved_at = datetime.fromisoformat(state_data['saved_at'])
            age = datetime.now() - saved_at
            max_age = timedelta(hours=self.STATE_EXPIRY_HOURS)

            if age > max_age:
                logger.info(
                    f"State for {crs_code} is too old ({age.total_seconds()/3600:.1f}h), "
                    f"discarding (max age: {self.STATE_EXPIRY_HOURS}h)"
                )
                # Delete old state file
                state_file.unlink(missing_ok=True)
                return False

            # Deserialize board
            board = StationBoard.model_validate(state_data['board'])

            # Store in memory
            self._store_board(crs_code, board)

            logger.info(
                f"Loaded state for {crs_code} from disk "
                f"(age: {age.total_seconds()/3600:.1f}h, "
                f"services: {len(board.services)})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load state for {crs_code}: {e}")
            # Delete corrupted state file
            try:
                state_file = self._get_state_file_path(crs_code)
                if state_file.exists():
                    state_file.unlink()
                    logger.info(f"Deleted corrupted state file: {state_file}")
            except:
                pass
            return False

    def update_and_detect_changes(
        self,
        station_config: StationConfig,
        current_board: StationBoard
    ) -> List[TrainChange]:
        """
        Update state with new board data and detect changes.

        Args:
            station_config: Station configuration with notification filters
            current_board: Current station board from Darwin API

        Returns:
            List of detected changes that match notification filters
        """
        crs_code = station_config.crs_code

        # Get previous board for this station
        previous_board = self._previous_boards.get(crs_code)

        if previous_board is None:
            # First time seeing this station - try loading from disk
            loaded = self.load_state_from_disk(crs_code)
            if loaded:
                # Successfully loaded previous state from disk
                previous_board = self._previous_boards.get(crs_code)
                logger.info(f"Loaded previous state from disk for {crs_code}")
            else:
                # No saved state - this is truly the first check
                logger.info(f"First update for station {crs_code} - storing initial state")
                self._store_board(crs_code, current_board)
                # Save to disk for next restart
                self.save_state_to_disk(crs_code)
                return []

        # Detect all changes
        all_changes = self._detect_changes(
            previous_board,
            current_board,
            station_config
        )

        # Store current board as new previous state
        self._store_board(crs_code, current_board)

        # Save to disk (auto-save after each update)
        self.save_state_to_disk(crs_code)

        # Filter changes based on notification settings
        filtered_changes = self._apply_filters(all_changes, station_config)

        if filtered_changes:
            logger.info(
                f"Detected {len(filtered_changes)} changes for {crs_code} "
                f"(out of {len(all_changes)} total changes)"
            )

        return filtered_changes

    def _store_board(self, crs_code: str, board: StationBoard) -> None:
        """
        Store board state for future comparisons.

        Args:
            crs_code: Station CRS code
            board: Station board to store
        """
        self._previous_boards[crs_code] = board

        # Build service lookup dict
        service_dict = {
            service.service_id: service
            for service in board.services
        }
        self._previous_services[crs_code] = service_dict

    def _detect_changes(
        self,
        previous_board: StationBoard,
        current_board: StationBoard,
        station_config: StationConfig
    ) -> List[TrainChange]:
        """
        Detect all changes between previous and current board.

        Args:
            previous_board: Previous station board
            current_board: Current station board
            station_config: Station configuration

        Returns:
            List of all detected changes
        """
        changes: List[TrainChange] = []
        crs_code = station_config.crs_code

        # Get previous services dict
        previous_services = self._previous_services.get(crs_code, {})

        # Build current services dict
        current_services = {
            service.service_id: service
            for service in current_board.services
        }

        # Check each current service for changes
        for service_id, current_service in current_services.items():
            previous_service = previous_services.get(service_id)

            if previous_service is None:
                # New service appeared - not a change, just new data
                logger.debug(f"New service appeared: {service_id}")
                continue

            # Check for various types of changes
            service_changes = self._detect_service_changes(
                previous_service,
                current_service
            )
            changes.extend(service_changes)

        # Check for removed services (cancellations that disappeared from board)
        for service_id, previous_service in previous_services.items():
            if service_id not in current_services:
                # Service disappeared - might have been cancelled or departed
                logger.debug(f"Service disappeared: {service_id}")
                # We don't report this as it's usually normal (train departed)

        return changes

    def _detect_service_changes(
        self,
        previous: TrainService,
        current: TrainService
    ) -> List[TrainChange]:
        """
        Detect changes for a single service.

        Args:
            previous: Previous service state
            current: Current service state

        Returns:
            List of changes detected for this service
        """
        changes: List[TrainChange] = []

        # Check for cancellation
        if not previous.is_cancelled and current.is_cancelled:
            changes.append(TrainChange(
                change_type=ChangeType.CANCELLATION,
                service_id=current.service_id,
                service=current,
                old_value="Active",
                new_value="Cancelled",
                severity=ChangeSeverity.HIGH,
                timestamp=datetime.now(),
                message=current.cancellation_reason or "Train cancelled"
            ))
            logger.debug(f"Cancellation detected: {current.service_id}")

        # Check for delay (only if not cancelled)
        if not current.is_cancelled:
            # Delay increased
            if current.delay_minutes > previous.delay_minutes:
                changes.append(TrainChange(
                    change_type=ChangeType.DELAY,
                    service_id=current.service_id,
                    service=current,
                    old_value=str(previous.delay_minutes),
                    new_value=str(current.delay_minutes),
                    severity=self._calculate_delay_severity(current.delay_minutes),
                    timestamp=datetime.now(),
                    message=f"Delay increased from {previous.delay_minutes} to {current.delay_minutes} minutes"
                ))
                logger.debug(
                    f"Delay increase detected: {current.service_id} "
                    f"({previous.delay_minutes}min → {current.delay_minutes}min)"
                )

            # New delay appeared
            elif previous.delay_minutes == 0 and current.delay_minutes > 0:
                changes.append(TrainChange(
                    change_type=ChangeType.DELAY,
                    service_id=current.service_id,
                    service=current,
                    old_value="On time",
                    new_value=f"{current.delay_minutes} minutes",
                    severity=self._calculate_delay_severity(current.delay_minutes),
                    timestamp=datetime.now(),
                    message=f"Train delayed by {current.delay_minutes} minutes"
                ))
                logger.debug(f"New delay detected: {current.service_id} ({current.delay_minutes}min)")

        # Check for platform change
        if previous.platform and current.platform:
            if previous.platform != current.platform:
                changes.append(TrainChange(
                    change_type=ChangeType.PLATFORM_CHANGE,
                    service_id=current.service_id,
                    service=current,
                    old_value=previous.platform,
                    new_value=current.platform,
                    severity=ChangeSeverity.MEDIUM,
                    timestamp=datetime.now(),
                    message=f"Platform changed from {previous.platform} to {current.platform}"
                ))
                logger.debug(
                    f"Platform change detected: {current.service_id} "
                    f"({previous.platform} → {current.platform})"
                )

        # Check for time change (scheduled time changed - rare but possible)
        if previous.scheduled_departure and current.scheduled_departure:
            if previous.scheduled_departure != current.scheduled_departure:
                changes.append(TrainChange(
                    change_type=ChangeType.TIME_CHANGE,
                    service_id=current.service_id,
                    service=current,
                    old_value=previous.scheduled_departure,
                    new_value=current.scheduled_departure,
                    severity=ChangeSeverity.HIGH,
                    timestamp=datetime.now(),
                    message=f"Scheduled time changed from {previous.scheduled_departure} to {current.scheduled_departure}"
                ))
                logger.debug(
                    f"Time change detected: {current.service_id} "
                    f"({previous.scheduled_departure} → {current.scheduled_departure})"
                )

        return changes

    def _calculate_delay_severity(self, delay_minutes: int) -> ChangeSeverity:
        """
        Calculate severity based on delay duration.

        According to model definition:
        - LOW: < 15 minutes
        - MEDIUM: 15-30 minutes
        - HIGH: > 30 minutes

        Args:
            delay_minutes: Delay in minutes

        Returns:
            Change severity level
        """
        if delay_minutes > 30:
            return ChangeSeverity.HIGH
        elif delay_minutes >= 15:
            return ChangeSeverity.MEDIUM
        else:
            return ChangeSeverity.LOW

    def _apply_filters(
        self,
        changes: List[TrainChange],
        station_config: StationConfig
    ) -> List[TrainChange]:
        """
        Apply notification filters to changes.

        Args:
            changes: All detected changes
            station_config: Station configuration with filters

        Returns:
            Filtered list of changes that should trigger notifications
        """
        if not changes:
            return []

        filters = station_config.filters
        filtered = []

        for change in changes:
            # Check if this change type should be notified
            if not self._should_notify_change_type(change, filters):
                logger.debug(f"Change filtered by type: {change.change_type}")
                continue

            # Check minimum delay threshold
            if change.change_type == ChangeType.DELAY:
                if change.service.delay_minutes < filters.min_delay_minutes:
                    logger.debug(
                        f"Delay filtered by threshold: "
                        f"{change.service.delay_minutes}min < {filters.min_delay_minutes}min"
                    )
                    continue

            # Check destination filter
            if filters.destination_filter:
                if change.service.destination_crs not in filters.destination_filter:
                    logger.debug(
                        f"Change filtered by destination: "
                        f"{change.service.destination_crs} not in {filters.destination_filter}"
                    )
                    continue

            # All filters passed
            filtered.append(change)

        return filtered

    def _should_notify_change_type(
        self,
        change: TrainChange,
        filters
    ) -> bool:
        """
        Check if change type should trigger notification.

        Args:
            change: Train change to check
            filters: Notification filters

        Returns:
            True if this change type should be notified
        """
        if change.change_type == ChangeType.CANCELLATION:
            return filters.notify_cancellations
        elif change.change_type == ChangeType.PLATFORM_CHANGE:
            return filters.notify_platform_changes
        elif change.change_type == ChangeType.DELAY:
            return True  # Delays always checked (but filtered by threshold)
        elif change.change_type == ChangeType.TIME_CHANGE:
            return True  # Time changes are important
        else:
            return True  # Other changes default to notify

    def clear_station_state(self, crs_code: str) -> None:
        """
        Clear stored state for a station (both memory and disk).

        Args:
            crs_code: Station CRS code
        """
        # Clear from memory
        self._previous_boards.pop(crs_code, None)
        self._previous_services.pop(crs_code, None)

        # Delete state file from disk
        if self._enable_persistence:
            try:
                state_file = self._get_state_file_path(crs_code)
                if state_file.exists():
                    state_file.unlink()
                    logger.info(f"Deleted state file for {crs_code}")
            except Exception as e:
                logger.error(f"Failed to delete state file for {crs_code}: {e}")

        logger.info(f"Cleared state for station {crs_code}")

    def clear_all_state(self) -> None:
        """Clear all stored state (both memory and disk)."""
        # Get list of stations before clearing
        stations = list(self._previous_boards.keys())

        # Clear from memory
        self._previous_boards.clear()
        self._previous_services.clear()

        # Delete all state files from disk
        if self._enable_persistence:
            for crs_code in stations:
                try:
                    state_file = self._get_state_file_path(crs_code)
                    if state_file.exists():
                        state_file.unlink()
                        logger.debug(f"Deleted state file for {crs_code}")
                except Exception as e:
                    logger.error(f"Failed to delete state file for {crs_code}: {e}")

        logger.info(f"Cleared all state ({len(stations)} station(s))")

    def get_station_count(self) -> int:
        """
        Get number of stations being tracked.

        Returns:
            Number of stations with stored state
        """
        return len(self._previous_boards)

    def get_tracked_stations(self) -> List[str]:
        """
        Get list of station CRS codes being tracked.

        Returns:
            List of station CRS codes
        """
        return list(self._previous_boards.keys())
