"""
Unit tests for State Manager.

Tests change detection logic with mock data (no API required).
Includes tests for file-based state persistence.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil
import json
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.train_monitor.state_manager import StateManager
from src.train_monitor.models import (
    StationBoard,
    TrainService,
    StationConfig,
    ServiceStatus,
    MonitoringMode,
    NotificationFilter,
    ChangeSeverity,
    ChangeType,
)
from src.utils.logger import setup_logger, get_logger

# Setup logging
setup_logger()
logger = get_logger()


def create_test_service(
    service_id: str = "TEST001",
    origin: str = "Ely",
    destination: str = "Cambridge",
    dest_crs: str = "CBG",
    scheduled_departure: str = "14:30",
    estimated_departure: str = "14:30",
    platform: str = "2",
    delay_minutes: int = 0,
    is_cancelled: bool = False,
    status: ServiceStatus = ServiceStatus.ON_TIME,
    cancellation_reason: str = None,
) -> TrainService:
    """Create a test train service."""
    return TrainService(
        service_id=service_id,
        origin=origin,
        destination=destination,
        destination_crs=dest_crs,
        scheduled_departure=scheduled_departure,
        estimated_departure=estimated_departure,
        platform=platform,
        status=status,
        delay_minutes=delay_minutes,
        is_cancelled=is_cancelled,
        cancellation_reason=cancellation_reason,
    )


def create_test_board(
    crs_code: str = "ELY",
    station_name: str = "Ely",
    services: list = None
) -> StationBoard:
    """Create a test station board."""
    if services is None:
        services = []

    return StationBoard(
        station_crs=crs_code,
        station_name=station_name,
        generated_at=datetime.now(),
        services=services
    )


def create_test_config(
    crs_code: str = "ELY",
    min_delay_minutes: int = 5,
    notify_cancellations: bool = True,
    notify_platform_changes: bool = True,
    destination_filter: list = None
) -> StationConfig:
    """Create a test station configuration."""
    filters = NotificationFilter(
        min_delay_minutes=min_delay_minutes,
        notify_cancellations=notify_cancellations,
        notify_platform_changes=notify_platform_changes,
        destination_filter=destination_filter,
    )

    return StationConfig(
        crs_code=crs_code,
        station_name="Ely",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        check_interval_minutes=5,
        telegram_chat_ids=["-1001234567890"],
        filters=filters,
    )


def test_initial_state():
    """Test that no changes are detected on first update."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Initial State (No Previous Data)")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config()

    # Create initial board
    service = create_test_service()
    board = create_test_board(services=[service])

    # First update should return no changes
    changes = manager.update_and_detect_changes(config, board)

    assert len(changes) == 0, "First update should return no changes"
    assert manager.get_station_count() == 1, "Should track 1 station"
    assert "ELY" in manager.get_tracked_stations(), "Should track ELY station"

    logger.info("✅ Initial state test passed")


def test_new_delay_detection():
    """Test detection of new delay."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: New Delay Detection")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config(min_delay_minutes=5)

    # Initial board - train on time
    service1 = create_test_service(
        service_id="TEST001",
        scheduled_departure="14:30",
        estimated_departure="14:30",
        delay_minutes=0,
        status=ServiceStatus.ON_TIME
    )
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Updated board - train now delayed
    service2 = create_test_service(
        service_id="TEST001",
        scheduled_departure="14:30",
        estimated_departure="14:40",
        delay_minutes=10,
        status=ServiceStatus.DELAYED
    )
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 1, "Should detect 1 change"
    assert changes[0].change_type == ChangeType.DELAY, "Change should be DELAY"
    assert changes[0].service.delay_minutes == 10, "Delay should be 10 minutes"
    assert changes[0].severity == ChangeSeverity.LOW, "10 min delay should be LOW severity (< 15 min)"

    logger.info(f"✅ Detected delay: {changes[0].old_value} → {changes[0].new_value}")
    logger.info("✅ New delay detection test passed")


def test_delay_increase_detection():
    """Test detection of increasing delay."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Delay Increase Detection")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config(min_delay_minutes=5)

    # Initial board - train delayed 5 minutes
    service1 = create_test_service(
        service_id="TEST001",
        delay_minutes=5,
        status=ServiceStatus.DELAYED
    )
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Updated board - delay increased to 20 minutes
    service2 = create_test_service(
        service_id="TEST001",
        delay_minutes=20,
        status=ServiceStatus.DELAYED
    )
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 1, "Should detect 1 change"
    assert changes[0].change_type == ChangeType.DELAY, "Change should be DELAY"
    assert changes[0].old_value == "5", "Old delay should be 5"
    assert changes[0].new_value == "20", "New delay should be 20"
    assert changes[0].severity == ChangeSeverity.MEDIUM, "20 min delay should be MEDIUM severity"

    logger.info(f"✅ Detected delay increase: {changes[0].old_value}min → {changes[0].new_value}min")
    logger.info("✅ Delay increase test passed")


def test_cancellation_detection():
    """Test detection of train cancellation."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Cancellation Detection")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config()

    # Initial board - train active
    service1 = create_test_service(
        service_id="TEST001",
        is_cancelled=False
    )
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Updated board - train cancelled
    service2 = create_test_service(
        service_id="TEST001",
        is_cancelled=True,
        status=ServiceStatus.CANCELLED,
        cancellation_reason="Staff unavailable"
    )
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 1, "Should detect 1 change"
    assert changes[0].change_type == ChangeType.CANCELLATION, "Change should be CANCELLATION"
    assert changes[0].severity == ChangeSeverity.HIGH, "Cancellation should be HIGH severity"
    assert "Staff unavailable" in changes[0].message, "Should include cancellation reason"

    logger.info(f"✅ Detected cancellation: {changes[0].message}")
    logger.info("✅ Cancellation detection test passed")


def test_platform_change_detection():
    """Test detection of platform change."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Platform Change Detection")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config()

    # Initial board - platform 2
    service1 = create_test_service(
        service_id="TEST001",
        platform="2"
    )
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Updated board - platform changed to 3
    service2 = create_test_service(
        service_id="TEST001",
        platform="3"
    )
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 1, "Should detect 1 change"
    assert changes[0].change_type == ChangeType.PLATFORM_CHANGE, "Change should be PLATFORM_CHANGE"
    assert changes[0].old_value == "2", "Old platform should be 2"
    assert changes[0].new_value == "3", "New platform should be 3"
    assert changes[0].severity == ChangeSeverity.MEDIUM, "Platform change should be MEDIUM severity"

    logger.info(f"✅ Detected platform change: {changes[0].old_value} → {changes[0].new_value}")
    logger.info("✅ Platform change test passed")


def test_min_delay_filter():
    """Test minimum delay filter."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Minimum Delay Filter")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config(min_delay_minutes=10)  # Only notify delays >= 10 min

    # Initial board - on time
    service1 = create_test_service(service_id="TEST001", delay_minutes=0)
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Updated board - 5 minute delay (below threshold)
    service2 = create_test_service(service_id="TEST001", delay_minutes=5)
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 0, "5 min delay should be filtered (threshold is 10)"
    logger.info("✅ 5 min delay correctly filtered")

    # Updated board - 15 minute delay (above threshold)
    service3 = create_test_service(service_id="TEST001", delay_minutes=15)
    board3 = create_test_board(services=[service3])
    changes = manager.update_and_detect_changes(config, board3)

    assert len(changes) == 1, "15 min delay should pass filter (threshold is 10)"
    assert changes[0].service.delay_minutes == 15, "Should report 15 min delay"

    logger.info("✅ 15 min delay correctly passed filter")
    logger.info("✅ Minimum delay filter test passed")


def test_destination_filter():
    """Test destination filter."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Destination Filter")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config(
        destination_filter=["CBG", "KGX"]  # Only Cambridge and Kings Cross
    )

    # Initial state
    service1 = create_test_service(
        service_id="TEST001",
        destination="Cambridge",
        dest_crs="CBG",
        delay_minutes=0
    )
    service2 = create_test_service(
        service_id="TEST002",
        destination="Norwich",
        dest_crs="NRW",
        delay_minutes=0
    )
    board1 = create_test_board(services=[service1, service2])
    manager.update_and_detect_changes(config, board1)

    # Both trains delayed
    service1_delayed = create_test_service(
        service_id="TEST001",
        destination="Cambridge",
        dest_crs="CBG",
        delay_minutes=10
    )
    service2_delayed = create_test_service(
        service_id="TEST002",
        destination="Norwich",
        dest_crs="NRW",
        delay_minutes=10
    )
    board2 = create_test_board(services=[service1_delayed, service2_delayed])
    changes = manager.update_and_detect_changes(config, board2)

    # Only Cambridge delay should be reported (Norwich filtered)
    assert len(changes) == 1, "Should only report 1 change (Cambridge)"
    assert changes[0].service.destination_crs == "CBG", "Should only report Cambridge train"

    logger.info("✅ Norwich train correctly filtered")
    logger.info(f"✅ Cambridge train correctly passed: {changes[0].service.destination}")
    logger.info("✅ Destination filter test passed")


def test_multiple_changes():
    """Test multiple changes at once."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Multiple Changes Detection")
    logger.info("=" * 70)

    manager = StateManager()
    config = create_test_config(min_delay_minutes=5)

    # Initial board - 3 trains, all on time
    services1 = [
        create_test_service(service_id="TEST001", platform="1", delay_minutes=0),
        create_test_service(service_id="TEST002", platform="2", delay_minutes=0),
        create_test_service(service_id="TEST003", platform="3", delay_minutes=0),
    ]
    board1 = create_test_board(services=services1)
    manager.update_and_detect_changes(config, board1)

    # Updated board - various changes
    services2 = [
        # TEST001: Delayed + platform change
        create_test_service(
            service_id="TEST001",
            platform="4",  # Changed from 1
            delay_minutes=10,  # New delay
            status=ServiceStatus.DELAYED
        ),
        # TEST002: Cancelled
        create_test_service(
            service_id="TEST002",
            platform="2",
            is_cancelled=True,
            status=ServiceStatus.CANCELLED
        ),
        # TEST003: Just delayed
        create_test_service(
            service_id="TEST003",
            platform="3",
            delay_minutes=15,
            status=ServiceStatus.DELAYED
        ),
    ]
    board2 = create_test_board(services=services2)
    changes = manager.update_and_detect_changes(config, board2)

    # Should detect: 2 delays + 1 platform change + 1 cancellation = 4 changes
    assert len(changes) == 4, f"Should detect 4 changes, got {len(changes)}"

    # Count change types
    delays = [c for c in changes if c.change_type == ChangeType.DELAY]
    platforms = [c for c in changes if c.change_type == ChangeType.PLATFORM_CHANGE]
    cancellations = [c for c in changes if c.change_type == ChangeType.CANCELLATION]

    assert len(delays) == 2, "Should detect 2 delays"
    assert len(platforms) == 1, "Should detect 1 platform change"
    assert len(cancellations) == 1, "Should detect 1 cancellation"

    logger.info(f"✅ Detected {len(delays)} delays")
    logger.info(f"✅ Detected {len(platforms)} platform change")
    logger.info(f"✅ Detected {len(cancellations)} cancellation")
    logger.info("✅ Multiple changes test passed")


def test_notification_type_filter():
    """Test notification type filters (cancellations, platform changes)."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Notification Type Filter")
    logger.info("=" * 70)

    manager = StateManager()

    # Config that disables cancellation notifications
    config = create_test_config(
        min_delay_minutes=5,
        notify_cancellations=False,  # Don't notify about cancellations
        notify_platform_changes=True
    )

    # Initial state
    service1 = create_test_service(service_id="TEST001", is_cancelled=False)
    board1 = create_test_board(services=[service1])
    manager.update_and_detect_changes(config, board1)

    # Train cancelled - should be filtered
    service2 = create_test_service(
        service_id="TEST001",
        is_cancelled=True,
        status=ServiceStatus.CANCELLED
    )
    board2 = create_test_board(services=[service2])
    changes = manager.update_and_detect_changes(config, board2)

    assert len(changes) == 0, "Cancellation should be filtered (notify_cancellations=False)"
    logger.info("✅ Cancellation correctly filtered")

    # Now test platform change with filter disabled
    manager2 = StateManager()
    config2 = create_test_config(
        min_delay_minutes=5,
        notify_cancellations=True,
        notify_platform_changes=False  # Don't notify about platform changes
    )

    service3 = create_test_service(service_id="TEST002", platform="1")
    board3 = create_test_board(services=[service3])
    manager2.update_and_detect_changes(config2, board3)

    service4 = create_test_service(service_id="TEST002", platform="2")
    board4 = create_test_board(services=[service4])
    changes2 = manager2.update_and_detect_changes(config2, board4)

    assert len(changes2) == 0, "Platform change should be filtered (notify_platform_changes=False)"
    logger.info("✅ Platform change correctly filtered")
    logger.info("✅ Notification type filter test passed")


def test_state_persistence_save_load():
    """Test saving and loading state from disk."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: State Persistence - Save & Load")
    logger.info("=" * 70)

    # Create temporary directory for state files
    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Using temp directory: {temp_dir}")

    try:
        # Create manager with persistence enabled
        manager = StateManager(state_dir=temp_dir, enable_persistence=True)
        config = create_test_config()

        # Create a board with a delayed train
        service = create_test_service(
            service_id="TEST001",
            delay_minutes=15,
            platform="3",
            status=ServiceStatus.DELAYED
        )
        board = create_test_board(services=[service])

        # First update - stores state
        changes = manager.update_and_detect_changes(config, board)
        assert len(changes) == 0, "First update should return no changes"

        # Verify state file was created
        state_file = temp_dir / "ELY_state.json"
        assert state_file.exists(), "State file should be created"
        logger.info(f"✅ State file created: {state_file}")

        # Read and verify state file contents
        with open(state_file, 'r') as f:
            state_data = json.load(f)

        assert state_data['crs_code'] == 'ELY', "CRS code should be saved"
        assert 'saved_at' in state_data, "Timestamp should be saved"
        assert len(state_data['board']['services']) == 1, "Should save 1 service"
        assert state_data['board']['services'][0]['delay_minutes'] == 15, "Should save delay"
        logger.info("✅ State file contains correct data")

        # Create new manager and load state
        manager2 = StateManager(state_dir=temp_dir, enable_persistence=True)

        # Create updated board (delay increased)
        service2 = create_test_service(
            service_id="TEST001",
            delay_minutes=25,  # Increased from 15
            platform="3",
            status=ServiceStatus.DELAYED
        )
        board2 = create_test_board(services=[service2])

        # This should load previous state and detect the change
        changes = manager2.update_and_detect_changes(config, board2)

        assert len(changes) == 1, "Should detect 1 change (delay increase)"
        assert changes[0].change_type == ChangeType.DELAY, "Should detect delay change"
        assert changes[0].old_value == "15", "Old delay should be 15"
        assert changes[0].new_value == "25", "New delay should be 25"

        logger.info("✅ State loaded from disk and changes detected")
        logger.info("✅ State persistence save & load test passed")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temp directory: {temp_dir}")


def test_state_expiry():
    """Test that old state files are discarded."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: State Expiry")
    logger.info("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Using temp directory: {temp_dir}")

    try:
        # Create manager
        manager = StateManager(state_dir=temp_dir, enable_persistence=True)
        config = create_test_config()

        # Create and save a state file
        service = create_test_service(delay_minutes=10)
        board = create_test_board(services=[service])
        manager.update_and_detect_changes(config, board)

        state_file = temp_dir / "ELY_state.json"
        assert state_file.exists(), "State file should exist"

        # Manually modify the timestamp to make it old (13 hours ago)
        with open(state_file, 'r') as f:
            state_data = json.load(f)

        old_timestamp = datetime.now() - timedelta(hours=13)
        state_data['saved_at'] = old_timestamp.isoformat()

        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        logger.info(f"Modified state timestamp to {old_timestamp.isoformat()}")

        # Create new manager - should discard old state
        manager2 = StateManager(state_dir=temp_dir, enable_persistence=True)

        # Try to load - should fail due to expiry
        loaded = manager2.load_state_from_disk("ELY")
        assert not loaded, "Old state should not be loaded (expired)"

        # State file should be deleted
        assert not state_file.exists(), "Expired state file should be deleted"

        logger.info("✅ Old state file correctly discarded and deleted")
        logger.info("✅ State expiry test passed")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temp directory: {temp_dir}")


def test_persistence_disabled():
    """Test that manager works with persistence disabled."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Persistence Disabled")
    logger.info("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create manager with persistence disabled
        manager = StateManager(state_dir=temp_dir, enable_persistence=False)
        config = create_test_config()

        # Create and update state
        service = create_test_service(delay_minutes=10)
        board = create_test_board(services=[service])
        manager.update_and_detect_changes(config, board)

        # State file should NOT be created
        state_file = temp_dir / "ELY_state.json"
        assert not state_file.exists(), "State file should not be created when persistence disabled"

        logger.info("✅ No state file created (persistence disabled)")
        logger.info("✅ Persistence disabled test passed")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_clear_state_deletes_files():
    """Test that clear_station_state deletes state files."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Clear State Deletes Files")
    logger.info("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())

    try:
        manager = StateManager(state_dir=temp_dir, enable_persistence=True)
        config = create_test_config()

        # Create state
        service = create_test_service()
        board = create_test_board(services=[service])
        manager.update_and_detect_changes(config, board)

        state_file = temp_dir / "ELY_state.json"
        assert state_file.exists(), "State file should exist"

        # Clear state
        manager.clear_station_state("ELY")

        # State file should be deleted
        assert not state_file.exists(), "State file should be deleted"
        assert manager.get_station_count() == 0, "Should track 0 stations"

        logger.info("✅ State file deleted on clear")
        logger.info("✅ Clear state deletes files test passed")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_container_restart_simulation():
    """Test complete container restart scenario."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Container Restart Simulation")
    logger.info("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Using temp directory: {temp_dir}")

    try:
        # === BEFORE RESTART: Evening check ===
        logger.info("\n--- BEFORE RESTART (22:00 Evening Check) ---")
        manager1 = StateManager(state_dir=temp_dir, enable_persistence=True)
        config = create_test_config()

        # Evening check - some trains on time, some delayed
        services_evening = [
            create_test_service(
                service_id="TRAIN_001",
                destination="Cambridge",
                dest_crs="CBG",
                scheduled_departure="22:30",
                delay_minutes=5,
                platform="1"
            ),
            create_test_service(
                service_id="TRAIN_002",
                destination="London Kings Cross",
                dest_crs="KGX",
                scheduled_departure="22:45",
                delay_minutes=0,
                platform="2"
            ),
        ]
        board_evening = create_test_board(services=services_evening)
        changes = manager1.update_and_detect_changes(config, board_evening)

        logger.info(f"Evening check: {len(services_evening)} trains, no changes (first check)")
        assert len(changes) == 0, "First evening check should report no changes"

        # Verify state saved
        state_file = temp_dir / "ELY_state.json"
        assert state_file.exists(), "State should be saved"

        # === SIMULATE SHUTDOWN ===
        logger.info("\n--- SIMULATING CONTAINER SHUTDOWN ---")
        logger.info("Container stopped (manager1 destroyed)")
        del manager1

        # === AFTER RESTART: Morning check ===
        logger.info("\n--- AFTER RESTART (07:00 Morning Check) ---")
        manager2 = StateManager(state_dir=temp_dir, enable_persistence=True)

        # Morning check - TRAIN_001 delay increased, TRAIN_002 cancelled
        services_morning = [
            create_test_service(
                service_id="TRAIN_001",
                destination="Cambridge",
                dest_crs="CBG",
                scheduled_departure="07:15",
                delay_minutes=15,  # Increased from 5
                platform="1",
                status=ServiceStatus.DELAYED
            ),
            create_test_service(
                service_id="TRAIN_002",
                destination="London Kings Cross",
                dest_crs="KGX",
                scheduled_departure="07:30",
                delay_minutes=0,
                platform="2",
                is_cancelled=True,  # Now cancelled!
                status=ServiceStatus.CANCELLED,
                cancellation_reason="Staff shortage"
            ),
        ]
        board_morning = create_test_board(services=services_morning)

        # This should load previous state and detect changes
        changes = manager2.update_and_detect_changes(config, board_morning)

        logger.info(f"Morning check detected {len(changes)} changes")

        # Should detect: delay increase + time change for TRAIN_001, cancellation + time change for TRAIN_002
        assert len(changes) == 4, f"Should detect 4 changes (2 trains × 2 changes each), got {len(changes)}"

        delays = [c for c in changes if c.change_type == ChangeType.DELAY]
        cancellations = [c for c in changes if c.change_type == ChangeType.CANCELLATION]
        time_changes = [c for c in changes if c.change_type == ChangeType.TIME_CHANGE]

        assert len(delays) == 1, "Should detect 1 delay increase"
        assert len(cancellations) == 1, "Should detect 1 cancellation"
        assert len(time_changes) == 2, "Should detect 2 time changes (one per train)"

        # Verify delay change
        delay_change = delays[0]
        assert delay_change.service_id == "TRAIN_001", "Delay should be for TRAIN_001"
        assert delay_change.old_value == "5", "Old delay should be 5"
        assert delay_change.new_value == "15", "New delay should be 15"

        # Verify cancellation
        cancel_change = cancellations[0]
        assert cancel_change.service_id == "TRAIN_002", "Cancellation should be for TRAIN_002"
        assert "Staff shortage" in cancel_change.message, "Should include cancellation reason"

        # Verify time changes (evening → morning schedule)
        train1_time_change = [c for c in time_changes if c.service_id == "TRAIN_001"][0]
        assert train1_time_change.old_value == "22:30", "Old time should be 22:30"
        assert train1_time_change.new_value == "07:15", "New time should be 07:15"

        logger.info("✅ State survived container restart")
        logger.info("✅ Overnight changes detected on first morning check")
        logger.info("✅ Container restart simulation test passed")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temp directory: {temp_dir}")


def run_all_tests():
    """Run all State Manager tests."""
    logger.info("\n" + "=" * 70)
    logger.info("STATE MANAGER TEST SUITE")
    logger.info("=" * 70)

    tests = [
        ("Initial State", test_initial_state),
        ("New Delay Detection", test_new_delay_detection),
        ("Delay Increase Detection", test_delay_increase_detection),
        ("Cancellation Detection", test_cancellation_detection),
        ("Platform Change Detection", test_platform_change_detection),
        ("Min Delay Filter", test_min_delay_filter),
        ("Destination Filter", test_destination_filter),
        ("Multiple Changes", test_multiple_changes),
        ("Notification Type Filter", test_notification_type_filter),
        # Persistence tests
        ("State Persistence - Save & Load", test_state_persistence_save_load),
        ("State Expiry", test_state_expiry),
        ("Persistence Disabled", test_persistence_disabled),
        ("Clear State Deletes Files", test_clear_state_deletes_files),
        ("Container Restart Simulation", test_container_restart_simulation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            logger.error(f"\n❌ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            logger.exception(f"\n❌ {test_name} ERROR: {e}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total tests: {len(tests)}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")

    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED! 🎉")
    else:
        logger.error(f"\n⚠️ {failed} test(s) failed")

    logger.info("=" * 70)

    return failed == 0


if __name__ == "__main__":
    import sys

    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
