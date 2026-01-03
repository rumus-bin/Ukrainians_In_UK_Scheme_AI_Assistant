"""
Ukrainian language notifier for train changes.

Formats train delay/cancellation notifications in Ukrainian language
for Telegram groups.
"""

from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

from src.train_monitor.models import TrainChange, ChangeType
from src.train_monitor.notifier import BaseNotifier
from src.utils.logger import get_logger
from src.utils.config import get_settings

if TYPE_CHECKING:
    from src.train_monitor.models import StationConfig

logger = get_logger()


class UkrainianNotifier(BaseNotifier):
    """
    Notifier that formats messages in Ukrainian language.

    Station names, train operators, and technical terms remain in English.
    """

    def __init__(self, bot_token: str = None, dry_run: bool = False):
        """
        Initialize Ukrainian notifier.

        Args:
            bot_token: Telegram bot token (reads from settings if None)
            dry_run: If True, logs messages instead of sending
        """
        self.settings = get_settings()
        self.bot_token = bot_token or self.settings.telegram_bot_token
        self.dry_run = dry_run

    async def send_notification(
        self,
        changes: List[TrainChange],
        station_config: "StationConfig",
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Send notification about changes (abstract method implementation).

        Args:
            changes: List of changes
            station_config: Station configuration
            chat_id: Chat ID (optional, if provided sends only to this chat)

        Returns:
            True if sent successfully to all chats
        """
        if not changes:
            return True

        # Format message based on single or multiple changes
        if len(changes) == 1:
            message = self._format_change(changes[0])
        else:
            # Multiple changes - use summary format
            message = self.format_daily_summary(
                station_name=station_config.station_name,
                changes=changes
            )

        # If specific chat_id provided, send only to that chat
        if chat_id:
            return await self.notify(chat_id, message)

        # Otherwise send to all configured chats
        if not station_config.telegram_chat_ids:
            logger.warning("No chat IDs configured for station")
            return False

        success = True
        for target_chat_id in station_config.telegram_chat_ids:
            result = await self.notify(target_chat_id, message)
            success = success and result

        return success

    async def notify(self, chat_id: str, message: str) -> bool:
        """
        Send notification to Telegram chat.

        Args:
            chat_id: Telegram chat ID
            message: Message text

        Returns:
            True if sent successfully (or logged in dry-run mode)
        """
        if self.dry_run:
            logger.info("=" * 70)
            logger.info("📢 [DRY-RUN] TELEGRAM NOTIFICATION (NOT SENT)")
            logger.info(f"💬 Chat ID: {chat_id}")
            logger.info("-" * 70)
            logger.info("📨 Message content:")
            logger.info("-" * 70)
            for line in message.split('\n'):
                logger.info(line)
            logger.info("=" * 70)
            return True

        # Send to Telegram in production mode
        if not self.bot_token:
            logger.error("Bot token not configured")
            return False

        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=10.0)
                response.raise_for_status()

            logger.info(f"✅ Message sent to chat {chat_id}")
            return True

        except Exception as e:
            logger.exception(f"Error sending message to chat {chat_id}: {e}")
            return False

    def _format_delay_message(self, change: TrainChange) -> str:
        """Format delay notification in Ukrainian."""
        service = change.new_service

        # Emoji based on delay severity
        emoji = "⏱️" if change.delay_minutes < 15 else "🚨"

        message = f"{emoji} **ЗАТРИМКА ПОЇЗДА** - {change.station_name}\n\n"

        # Route
        if service.origin and service.destination:
            message += f"**Маршрут:** {service.origin} → {service.destination}\n"
        elif service.destination:
            message += f"**Напрямок:** {service.destination}\n"

        # Scheduled time
        if service.scheduled_departure:
            message += f"**Заплановано:** {service.scheduled_departure.strftime('%H:%M')}\n"
        elif service.scheduled_arrival:
            message += f"**Заплановано прибуття:** {service.scheduled_arrival.strftime('%H:%M')}\n"

        # Platform
        if service.platform:
            message += f"**Платформа:** {service.platform}\n"

        message += f"\n⏱️ **ЗАТРИМКА: {change.delay_minutes} хвилин**\n"

        # New expected time
        if service.estimated_departure:
            message += f"**Очікується:** {service.estimated_departure.strftime('%H:%M')}\n"
        elif service.estimated_arrival:
            message += f"**Очікується прибуття:** {service.estimated_arrival.strftime('%H:%M')}\n"

        # Reason if available
        if change.reason:
            message += f"\n💬 **Причина:** {change.reason}\n"

        # Operator
        if service.operator:
            message += f"\n🚂 **Оператор:** {service.operator}\n"

        # Service ID
        if service.service_id:
            message += f"📋 **ID рейсу:** {service.service_id}\n"

        return message

    def _format_cancellation_message(self, change: TrainChange) -> str:
        """Format cancellation notification in Ukrainian."""
        service = change.new_service or change.previous_service

        message = f"❌ **СКАСУВАННЯ ПОЇЗДА** - {change.station_name}\n\n"

        # Route
        if service.origin and service.destination:
            message += f"**Маршрут:** {service.origin} → {service.destination}\n"
        elif service.destination:
            message += f"**Напрямок:** {service.destination}\n"

        # Scheduled time
        if service.scheduled_departure:
            message += f"**Було заплановано:** {service.scheduled_departure.strftime('%H:%M')}\n"
        elif service.scheduled_arrival:
            message += f"**Було заплановано прибуття:** {service.scheduled_arrival.strftime('%H:%M')}\n"

        # Platform
        if service.platform:
            message += f"**Платформа:** {service.platform}\n"

        message += f"\n❌ **ПОЇЗД СКАСОВАНО**\n"

        # Cancellation reason
        if change.reason:
            message += f"\n💬 **Причина скасування:** {change.reason}\n"
        else:
            message += f"\n💬 Причина не вказана\n"

        # Operator
        if service.operator:
            message += f"\n🚂 **Оператор:** {service.operator}\n"

        # Service ID
        if service.service_id:
            message += f"📋 **ID рейсу:** {service.service_id}\n"

        return message

    def _format_platform_change_message(self, change: TrainChange) -> str:
        """Format platform change notification in Ukrainian."""
        service = change.new_service

        message = f"🔄 **ЗМІНА ПЛАТФОРМИ** - {change.station_name}\n\n"

        # Route
        if service.origin and service.destination:
            message += f"**Маршрут:** {service.origin} → {service.destination}\n"
        elif service.destination:
            message += f"**Напрямок:** {service.destination}\n"

        # Scheduled time
        if service.scheduled_departure:
            message += f"**Відправлення:** {service.scheduled_departure.strftime('%H:%M')}\n"
        elif service.scheduled_arrival:
            message += f"**Прибуття:** {service.scheduled_arrival.strftime('%H:%M')}\n"

        # Platform change
        old_platform = change.previous_service.platform if change.previous_service else "невідома"
        new_platform = service.platform or "невідома"

        message += f"\n🔄 **Платформа змінена:**\n"
        message += f"   Було: {old_platform}\n"
        message += f"   Зараз: **{new_platform}**\n"

        # Operator
        if service.operator:
            message += f"\n🚂 **Оператор:** {service.operator}\n"

        # Service ID
        if service.service_id:
            message += f"📋 **ID рейсу:** {service.service_id}\n"

        return message

    def _format_time_change_message(self, change: TrainChange) -> str:
        """Format time change notification in Ukrainian."""
        service = change.new_service
        prev_service = change.previous_service

        message = f"🕐 **ЗМІНА ЧАСУ ВІДПРАВЛЕННЯ** - {change.station_name}\n\n"

        # Route
        if service.origin and service.destination:
            message += f"**Маршрут:** {service.origin} → {service.destination}\n"
        elif service.destination:
            message += f"**Напрямок:** {service.destination}\n"

        # Platform
        if service.platform:
            message += f"**Платформа:** {service.platform}\n"

        # Time change
        if service.scheduled_departure and prev_service and prev_service.scheduled_departure:
            old_time = prev_service.scheduled_departure.strftime('%H:%M')
            new_time = service.scheduled_departure.strftime('%H:%M')
            message += f"\n🕐 **Час змінено:**\n"
            message += f"   Було: {old_time}\n"
            message += f"   Зараз: **{new_time}**\n"

        # Operator
        if service.operator:
            message += f"\n🚂 **Оператор:** {service.operator}\n"

        # Service ID
        if service.service_id:
            message += f"📋 **ID рейсу:** {service.service_id}\n"

        return message

    def _format_change(self, change: TrainChange) -> str:
        """
        Format a single train change in Ukrainian.

        Args:
            change: Train change to format

        Returns:
            Formatted message string
        """
        if change.change_type == ChangeType.DELAY:
            return self._format_delay_message(change)
        elif change.change_type == ChangeType.CANCELLATION:
            return self._format_cancellation_message(change)
        elif change.change_type == ChangeType.PLATFORM_CHANGE:
            return self._format_platform_change_message(change)
        elif change.change_type == ChangeType.TIME_CHANGE:
            return self._format_time_change_message(change)
        else:
            # Fallback to generic message
            service = change.new_service or change.previous_service
            return f"ℹ️ **Зміна для поїзда** - {change.station_name}\n\n{service.destination or 'Unknown'}"

    def format_daily_summary(
        self,
        station_name: str,
        changes: List[TrainChange],
        check_time: datetime = None
    ) -> str:
        """
        Format daily summary message in Ukrainian.

        Args:
            station_name: Name of the station
            changes: List of changes detected
            check_time: Time when check was performed

        Returns:
            Formatted summary message
        """
        if not check_time:
            check_time = datetime.now()

        if not changes:
            message = f"✅ **Щоденний звіт про рух поїздів**\n\n"
            message += f"📍 **Станція:** {station_name}\n"
            message += f"🕐 **Час перевірки:** {check_time.strftime('%H:%M, %d.%m.%Y')}\n\n"
            message += f"✅ **Без змін**\n\n"
            message += f"Всі поїзди йдуть за розкладом. Затримок та скасувань не виявлено."
            return message

        # Group changes by type
        delays = [c for c in changes if c.change_type == ChangeType.DELAY]
        cancellations = [c for c in changes if c.change_type == ChangeType.CANCELLATION]
        platform_changes = [c for c in changes if c.change_type == ChangeType.PLATFORM_CHANGE]

        message = f"📢 **Щоденний звіт про рух поїздів**\n\n"
        message += f"📍 **Станція:** {station_name}\n"
        message += f"🕐 **Час перевірки:** {check_time.strftime('%H:%M, %d.%m.%Y')}\n\n"

        # Summary
        message += f"📊 **Виявлено змін:** {len(changes)}\n"
        if delays:
            message += f"  ⏱️ Затримки: {len(delays)}\n"
        if cancellations:
            message += f"  ❌ Скасування: {len(cancellations)}\n"
        if platform_changes:
            message += f"  🔄 Зміни платформ: {len(platform_changes)}\n"

        message += f"\n{'='*40}\n\n"

        # Detailed changes (limit to prevent too long messages)
        max_details = 10
        for i, change in enumerate(changes[:max_details], 1):
            message += f"**{i}. {change.change_type.value.upper()}**\n"
            message += self._format_change_summary(change)
            message += f"\n{'-'*40}\n\n"

        if len(changes) > max_details:
            message += f"_...та ще {len(changes) - max_details} змін_\n\n"

        message += f"\n🤖 _Повідомлення згенеровано автоматично UK Train Monitor_"

        return message

    def _format_change_summary(self, change: TrainChange) -> str:
        """Format brief change summary for daily report."""
        service = change.new_service or change.previous_service

        summary = ""

        # Route
        if service.destination:
            summary += f"→ {service.destination}\n"

        # Time
        if service.scheduled_departure:
            summary += f"🕐 {service.scheduled_departure.strftime('%H:%M')}\n"

        # Platform
        if service.platform:
            summary += f"Platform {service.platform}\n"

        # Change details
        if change.change_type == ChangeType.DELAY:
            summary += f"⏱️ Затримка: {change.delay_minutes} хв\n"
        elif change.change_type == ChangeType.CANCELLATION:
            summary += f"❌ Скасовано\n"
            if change.reason:
                summary += f"💬 {change.reason}\n"
        elif change.change_type == ChangeType.PLATFORM_CHANGE:
            old_platform = change.previous_service.platform if change.previous_service else "?"
            summary += f"🔄 Платформа: {old_platform} → {service.platform}\n"

        return summary


def get_ukrainian_notifier(dry_run: bool = False) -> UkrainianNotifier:
    """
    Get Ukrainian notifier instance.

    Args:
        dry_run: If True, logs messages instead of sending to Telegram

    Returns:
        UkrainianNotifier instance
    """
    settings = get_settings()

    logger.info(f"🔧 Creating UkrainianNotifier (dry_run={dry_run})")

    return UkrainianNotifier(
        bot_token=settings.telegram_bot_token,
        dry_run=dry_run
    )
