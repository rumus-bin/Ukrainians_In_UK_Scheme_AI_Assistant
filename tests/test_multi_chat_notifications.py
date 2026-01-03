"""Test script for multi-chat notification functionality."""

import asyncio
from datetime import datetime
from src.train_monitor.models import StationConfig, MonitoringMode, NotificationFilter, TrainChange, ChangeType, TrainService
from src.train_monitor.ukrainian_notifier import UkrainianNotifier


async def test_multi_chat():
    """Test sending notifications to multiple chats."""

    print("=" * 70)
    print("TESTING MULTI-CHAT NOTIFICATION FUNCTIONALITY")
    print("=" * 70)

    # Create test station config with multiple chat IDs
    station_config = StationConfig(
        crs_code="ELY",
        station_name="Ely",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        check_interval_minutes=5,
        time_window_minutes=120,
        max_services=50,
        # Multiple chat IDs for testing
        telegram_chat_ids=[
            "-1001111111111",  # Group 1
            "-1002222222222",  # Group 2
            "-1003333333333",  # Group 3
        ],
        notification_enabled=True,
        filters=NotificationFilter(
            min_delay_minutes=5,
            notify_cancellations=True,
            notify_platform_changes=True
        ),
        added_at=datetime.now()
    )

    print(f"\n✅ Station: {station_config.station_name} ({station_config.crs_code})")
    print(f"✅ Chat IDs configured: {len(station_config.telegram_chat_ids)}")
    for idx, chat_id in enumerate(station_config.telegram_chat_ids, 1):
        print(f"   {idx}. {chat_id}")

    # Create test change (delayed train)
    now = datetime.now()
    delayed_service = TrainService(
        service_id="TEST123",
        origin="Cambridge",
        destination="London Kings Cross",
        operator="Greater Anglia",
        scheduled_departure=now.strftime("%H:%M"),
        estimated_departure=now.strftime("%H:%M"),
        platform="2"
    )

    test_change = TrainChange(
        service_id="TEST123",
        station_name="Ely",
        change_type=ChangeType.DELAY,
        new_service=delayed_service,
        delay_minutes=15,
        reason="Signal failure"
    )

    print(f"\n📊 Test change: {test_change.change_type.value.upper()}")
    print(f"   Service: {delayed_service.destination}")
    print(f"   Delay: {test_change.delay_minutes} minutes")

    # Test 1: DRY-RUN mode (logs only)
    print("\n" + "=" * 70)
    print("TEST 1: DRY-RUN MODE (should log to all 3 chats)")
    print("=" * 70)

    notifier_dry = UkrainianNotifier(dry_run=True)
    result = await notifier_dry.send_notification(
        changes=[test_change],
        station_config=station_config
    )

    print(f"\n✅ DRY-RUN result: {result}")

    # Test 2: Single chat override
    print("\n" + "=" * 70)
    print("TEST 2: SINGLE CHAT OVERRIDE (should send to only one chat)")
    print("=" * 70)

    result_single = await notifier_dry.send_notification(
        changes=[test_change],
        station_config=station_config,
        chat_id="-1009999999999"  # Override with single chat
    )

    print(f"\n✅ Single chat override result: {result_single}")

    # Test 3: Empty chat IDs
    print("\n" + "=" * 70)
    print("TEST 3: EMPTY CHAT IDs (should log warning)")
    print("=" * 70)

    empty_config = StationConfig(
        crs_code="TEST",
        station_name="Test Station",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        telegram_chat_ids=[],  # Empty list
        notification_enabled=True,
        added_at=datetime.now()
    )

    result_empty = await notifier_dry.send_notification(
        changes=[test_change],
        station_config=empty_config
    )

    print(f"\n✅ Empty chat IDs result: {result_empty}")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_multi_chat())
