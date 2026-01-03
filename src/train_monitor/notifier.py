"""
Telegram Notifier for sending notifications about schedule changes.

Supports two modes:
1. PRODUCTION - actual sending to Telegram
2. DRY_RUN (development) - logging only, no actual sending
"""

import httpx
from typing import List, Optional
from abc import ABC, abstractmethod

from src.train_monitor.models import TrainChange, StationConfig, ChangeType, ChangeSeverity
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class BaseNotifier(ABC):
    """Abstract base class for notifiers."""

    @abstractmethod
    async def send_notification(
        self,
        changes: List[TrainChange],
        station_config: StationConfig,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Send notification about changes.

        Args:
            changes: List of changes
            station_config: Station configuration
            chat_id: Chat ID (optional, if provided sends only to this chat,
                     otherwise sends to all station_config.telegram_chat_ids)

        Returns:
            bool: True if successfully sent
        """
        pass


class LogNotifier(BaseNotifier):
    """
    Notifier for development mode - logging only.

    All notifications are written to logs with formatting,
    but not sent to Telegram.
    """

    def __init__(self):
        """Initialize LogNotifier."""
        logger.info("🔧 LogNotifier initialized (DRY-RUN mode)")

    async def send_notification(
        self,
        changes: List[TrainChange],
        station_config: StationConfig,
        chat_id: Optional[str] = None
    ) -> bool:
        """Log notification instead of sending."""
        if not changes:
            return True

        # Format message
        message = self._format_notification(changes, station_config)

        # Log with separators for readability
        logger.info("=" * 70)
        logger.info("📢 [DRY-RUN] TELEGRAM NOTIFICATION (NOT SENT)")
        logger.info(f"📍 Station: {station_config.station_name} ({station_config.crs_code})")
        chat_ids_str = chat_id if chat_id else ", ".join(station_config.telegram_chat_ids)
        logger.info(f"💬 Chat ID(s): {chat_ids_str}")
        logger.info(f"📊 Changes count: {len(changes)}")
        logger.info("-" * 70)
        logger.info("📨 Message content:")
        logger.info("-" * 70)
        # Output each line separately for better readability
        for line in message.split('\n'):
            logger.info(line)
        logger.info("=" * 70)

        return True

    def _format_notification(
        self,
        changes: List[TrainChange],
        station_config: StationConfig
    ) -> str:
        """
        Format notification in Ukrainian language.

        Args:
            changes: List of changes
            station_config: Station configuration

        Returns:
            str: Formatted message
        """
        # Group changes by type
        cancellations = [c for c in changes if c.change_type == ChangeType.CANCELLATION]
        delays = [c for c in changes if c.change_type == ChangeType.DELAY]
        platform_changes = [c for c in changes if c.change_type == ChangeType.PLATFORM_CHANGE]
        new_services = [c for c in changes if c.change_type == ChangeType.NEW_SERVICE]

        # Header
        message_parts = [
            f"🚂 Зміни на станції {station_config.station_name}",
            ""
        ]

        # Cancellations (highest priority)
        if cancellations:
            message_parts.append("❌ СКАСОВАНО")
            for change in cancellations:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Запланований час: {service.scheduled_departure or 'N/A'}",
                ])
                if change.service.cancellation_reason:
                    message_parts.append(f"ℹ️ Причина: {change.service.cancellation_reason}")
                message_parts.append("")

        # Delays
        if delays:
            message_parts.append("⚠️ ЗАТРИМКИ")
            for change in delays:
                service = change.service
                emoji = "🔴" if change.severity == ChangeSeverity.HIGH else "🟡"
                message_parts.extend([
                    f"{emoji} {service.origin} → {service.destination}",
                    f"⏱️ Запланований час: {service.scheduled_departure}",
                    f"🕐 Новий час: {service.estimated_departure} (+{service.delay_minutes} хв)",
                ])
                if service.platform:
                    message_parts.append(f"🛤️ Платформа: {service.platform}")
                message_parts.append("")

        # Platform changes
        if platform_changes:
            message_parts.append("🔄 ЗМІНА ПЛАТФОРМИ")
            for change in platform_changes:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Час відправлення: {service.scheduled_departure}",
                    f"🛤️ Платформа: {change.old_value} → {change.new_value}",
                    ""
                ])

        # New services
        if new_services:
            message_parts.append("🆕 НОВІ РЕЙСИ")
            for change in new_services:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Відправлення: {service.scheduled_departure}",
                    f"🛤️ Платформа: {service.platform or 'TBA'}",
                    ""
                ])

        # Footer with update time
        from datetime import datetime
        message_parts.extend([
            f"📊 Оновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        ])

        return "\n".join(message_parts)


class TelegramNotifier(BaseNotifier):
    """
    Notifier for production - actual sending to Telegram.

    Uses Telegram Bot API to send messages.
    """

    def __init__(self):
        """Initialize TelegramNotifier."""
        self.settings = get_settings()
        self.bot_token = self.settings.telegram_bot_token

        if not self.bot_token or self.bot_token == "your_telegram_bot_token_here":
            logger.warning("⚠️ Telegram bot token not configured!")

        logger.info("✅ TelegramNotifier initialized (PRODUCTION mode)")

    async def send_notification(
        self,
        changes: List[TrainChange],
        station_config: StationConfig,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Send notification to Telegram.

        Args:
            changes: List of changes
            station_config: Station configuration
            chat_id: Chat ID (optional, if provided sends only to this chat,
                     otherwise sends to all station_config.telegram_chat_ids)

        Returns:
            bool: True if successfully sent to all chats
        """
        if not changes:
            return True

        # Format message
        message = self._format_notification(changes, station_config)

        # If specific chat_id provided, send only to that chat
        if chat_id:
            return await self._send_to_chat(chat_id, message, station_config, len(changes))

        # Otherwise send to all configured chats
        if not station_config.telegram_chat_ids:
            logger.error(f"No chat_ids configured for station {station_config.crs_code}")
            return False

        success = True
        for target_chat_id in station_config.telegram_chat_ids:
            result = await self._send_to_chat(target_chat_id, message, station_config, len(changes))
            success = success and result

        return success

    async def _send_to_chat(
        self,
        chat_id: str,
        message: str,
        station_config: StationConfig,
        changes_count: int
    ) -> bool:
        """
        Send a message to a specific chat.

        Args:
            chat_id: Telegram chat ID
            message: Message text
            station_config: Station configuration (for logging)
            changes_count: Number of changes (for logging)

        Returns:
            bool: True if successfully sent
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True
                    }
                )

                if response.status_code == 200:
                    logger.info(
                        f"✅ Notification sent to chat {chat_id} "
                        f"for station {station_config.station_name} ({changes_count} changes)"
                    )
                    return True
                else:
                    logger.error(
                        f"❌ Failed to send notification: HTTP {response.status_code} "
                        f"- {response.text}"
                    )
                    return False

        except Exception as e:
            logger.exception(f"❌ Error sending Telegram notification: {e}")
            return False

    def _format_notification(
        self,
        changes: List[TrainChange],
        station_config: StationConfig
    ) -> str:
        """
        Format notification (same format as LogNotifier).

        Args:
            changes: List of changes
            station_config: Station configuration

        Returns:
            str: Formatted message
        """
        # Use the same formatting logic
        cancellations = [c for c in changes if c.change_type == ChangeType.CANCELLATION]
        delays = [c for c in changes if c.change_type == ChangeType.DELAY]
        platform_changes = [c for c in changes if c.change_type == ChangeType.PLATFORM_CHANGE]
        new_services = [c for c in changes if c.change_type == ChangeType.NEW_SERVICE]

        message_parts = [
            f"🚂 *Зміни на станції {station_config.station_name}*",
            ""
        ]

        if cancellations:
            message_parts.append("❌ *СКАСОВАНО*")
            for change in cancellations:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Запланований час: {service.scheduled_departure or 'N/A'}",
                ])
                if change.service.cancellation_reason:
                    message_parts.append(f"ℹ️ Причина: {change.service.cancellation_reason}")
                message_parts.append("")

        if delays:
            message_parts.append("⚠️ *ЗАТРИМКИ*")
            for change in delays:
                service = change.service
                emoji = "🔴" if change.severity == ChangeSeverity.HIGH else "🟡"
                message_parts.extend([
                    f"{emoji} {service.origin} → {service.destination}",
                    f"⏱️ Запланований час: {service.scheduled_departure}",
                    f"🕐 Новий час: {service.estimated_departure} (+{service.delay_minutes} хв)",
                ])
                if service.platform:
                    message_parts.append(f"🛤️ Платформа: {service.platform}")
                message_parts.append("")

        if platform_changes:
            message_parts.append("🔄 *ЗМІНА ПЛАТФОРМИ*")
            for change in platform_changes:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Час відправлення: {service.scheduled_departure}",
                    f"🛤️ Платформа: {change.old_value} → {change.new_value}",
                    ""
                ])

        if new_services:
            message_parts.append("🆕 *НОВІ РЕЙСИ*")
            for change in new_services:
                service = change.service
                message_parts.extend([
                    f"🚄 {service.origin} → {service.destination}",
                    f"⏱️ Відправлення: {service.scheduled_departure}",
                    f"🛤️ Платформа: {service.platform or 'TBA'}",
                    ""
                ])

        from datetime import datetime
        message_parts.extend([
            f"📊 Оновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        ])

        return "\n".join(message_parts)


def get_notifier(dry_run: bool = True) -> BaseNotifier:
    """
    Factory for creating notifiers.

    Args:
        dry_run: If True - LogNotifier (logs only), else TelegramNotifier

    Returns:
        BaseNotifier: Notifier instance
    """
    if dry_run:
        logger.info("🔧 Creating LogNotifier (DRY-RUN mode for development)")
        return LogNotifier()
    else:
        logger.info("✅ Creating TelegramNotifier (PRODUCTION mode)")
        return TelegramNotifier()


# Singleton for convenience
_notifier_instance: Optional[BaseNotifier] = None


def get_notifier_instance(dry_run: Optional[bool] = None) -> BaseNotifier:
    """
    Get global notifier instance.

    Args:
        dry_run: Mode (None = read from settings)

    Returns:
        BaseNotifier: Notifier instance
    """
    global _notifier_instance

    if _notifier_instance is None:
        # If dry_run not specified, read from settings
        if dry_run is None:
            settings = get_settings()
            dry_run = getattr(settings, 'train_monitor_dry_run', True)

        _notifier_instance = get_notifier(dry_run)

    return _notifier_instance
