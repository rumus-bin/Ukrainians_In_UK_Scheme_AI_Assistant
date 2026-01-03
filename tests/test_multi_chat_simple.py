"""Simplified test for multi-chat notification functionality."""

import asyncio
from datetime import datetime
from src.train_monitor.models import StationConfig, MonitoringMode, NotificationFilter
from src.train_monitor.ukrainian_notifier import UkrainianNotifier


async def test_multi_chat_simple():
    """Test that StationConfig accepts multiple chat IDs."""

    print("=" * 70)
    print("TESTING MULTI-CHAT CONFIGURATION")
    print("=" * 70)

    # Test 1: Create config with multiple chat IDs
    print("\nTEST 1: Multiple chat IDs in StationConfig")
    station_config = StationConfig(
        crs_code="ELY",
        station_name="Ely",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        check_interval_minutes=5,
        time_window_minutes=120,
        max_services=50,
        # Multiple chat IDs
        telegram_chat_ids=[
            "-1001111111111",
            "-1002222222222",
            "-1003333333333",
        ],
        notification_enabled=True,
        filters=NotificationFilter(),
        added_at=datetime.now()
    )

    print(f"✅ Station: {station_config.station_name}")
    print(f"✅ Chat IDs count: {len(station_config.telegram_chat_ids)}")
    for idx, chat_id in enumerate(station_config.telegram_chat_ids, 1):
        print(f"   {idx}. {chat_id}")

    assert len(station_config.telegram_chat_ids) == 3
    assert "-1001111111111" in station_config.telegram_chat_ids
    print("✅ PASSED: Multiple chat IDs configuration works")

    # Test 2: Empty chat IDs list
    print("\nTEST 2: Empty chat IDs list")
    config_empty = StationConfig(
        crs_code="TST",
        station_name="Test",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        telegram_chat_ids=[],  # Empty list
        notification_enabled=True,
        added_at=datetime.now()
    )

    print(f"✅ Chat IDs count: {len(config_empty.telegram_chat_ids)}")
    assert len(config_empty.telegram_chat_ids) == 0
    print("✅ PASSED: Empty chat IDs list works")

    # Test 3: Single chat ID in list
    print("\nTEST 3: Single chat ID in list")
    config_single = StationConfig(
        crs_code="CBG",
        station_name="Cambridge",
        enabled=True,
        monitoring_mode=MonitoringMode.DEPARTURES,
        telegram_chat_ids=["-1009999999999"],  # Single item in list
        notification_enabled=True,
        added_at=datetime.now()
    )

    print(f"✅ Chat IDs count: {len(config_single.telegram_chat_ids)}")
    assert len(config_single.telegram_chat_ids) == 1
    assert config_single.telegram_chat_ids[0] == "-1009999999999"
    print("✅ PASSED: Single chat ID in list works")

    # Test 4: UkrainianNotifier initialization with DRY-RUN
    print("\nTEST 4: UkrainianNotifier with dry_run=True")
    notifier = UkrainianNotifier(dry_run=True)
    print(f"✅ Notifier created: dry_run={notifier.dry_run}")
    assert notifier.dry_run is True
    print("✅ PASSED: Notifier initialization works")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_multi_chat_simple())
