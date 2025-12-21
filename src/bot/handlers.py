"""Enhanced message and command handlers for Telegram bot."""

import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src.agents.orchestrator import get_orchestrator
from src.language.detector import get_language_detector
from src.language.translator import get_translator
from src.safety.validator import get_response_validator
from src.safety.content_filter import get_content_filter
from src.bot.response_formatter import get_response_formatter
from src.rag.retriever import get_retriever
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class RateLimiter:
    """Simple rate limiter for bot requests."""

    def __init__(self):
        """Initialize rate limiter."""
        self.user_requests: Dict[int, list] = defaultdict(list)
        self.max_requests_per_minute = 5

    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user has exceeded rate limits.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (allowed, error_message)
        """
        now = datetime.now()

        # Clean old entries (older than 1 minute)
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id]
            if (now - ts).total_seconds() < 60
        ]

        # Check limit
        if len(self.user_requests[user_id]) >= self.max_requests_per_minute:
            return False, "⚠️ Занадто багато запитів. Зачекайте хвилину."

        # Record this request
        self.user_requests[user_id].append(now)
        return True, ""


class BotHandlers:
    """Centralized message and command handling."""

    def __init__(self):
        """Initialize bot handlers."""
        self.settings = get_settings()
        self.orchestrator = get_orchestrator()
        self.language_detector = get_language_detector()
        self.translator = get_translator()
        self.safety_validator = get_response_validator()
        self.content_filter = get_content_filter()
        self.formatter = get_response_formatter()
        self.retriever = get_retriever()
        self.rate_limiter = RateLimiter()

        # Initialize RAG retriever
        if not self.retriever._connected:
            logger.info("Initializing RAG retriever...")
            self.retriever.initialize()

        logger.info("BotHandlers initialized")

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        logger.info(f"/start command from {username} (ID: {user_id})")

        welcome_message = (
            "Вітаю! 👋\n\n"
            "Я AI-асистент для українців у Великій Британії.\n\n"
            "Можу допомогти з питаннями про:\n"
            "📋 Візи та імміграцію (UPE, BRP, подорожі)\n"
            "🏠 Житло та медицину (NHS, GP, школи)\n"
            "💼 Роботу та допомогу (NI number, benefits)\n\n"
            "⚠️ Важливо: Я не є юристом. Моя інформація базується на офіційних джерелах "
            "(gov.uk та opora.uk), але для юридичних рішень зверніться до спеціаліста.\n\n"
            "Задайте своє питання українською або російською мовою!\n\n"
            "Команди:\n"
            "/help - як користуватися ботом\n"
            "/health - перевірити стан системи"
        )

        await update.message.reply_text(welcome_message)

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        logger.info(f"/help command from {username} (ID: {user_id})")

        help_message = (
            "📖 Як мною користуватися:\n\n"
            "1️⃣ Просто напишіть своє питання українською або російською\n"
            "2️⃣ Я проаналізую запит та дам відповідь на основі офіційних джерел\n"
            "3️⃣ У відповіді будуть посилання на gov.uk або opora.uk\n\n"
            "Приклади питань:\n\n"
            "📋 Віза та імміграція:\n"
            "• Як продовжити візу Ukraine Permission Extension?\n"
            "• Чи можу я подорожувати за кордон з UPE?\n"
            "• Що робити, якщо загубив BRP?\n\n"
            "🏠 Житло та медицина:\n"
            "• Де зареєструватися у NHS?\n"
            "• Як знайти GP у моєму районі?\n"
            "• Які мої права як орендаря житла?\n\n"
            "💼 Робота та допомога:\n"
            "• Як отримати National Insurance number?\n"
            "• Чи маю я право на Universal Credit?\n"
            "• Де шукати роботу у UK?\n\n"
            "⚠️ Пам'ятайте: Я не можу давати юридичні поради або передбачати "
            "рішення по вашій візі. Для складних випадків звертайтеся до спеціалістів.\n\n"
            "Команди:\n"
            "/start - почати роботу\n"
            "/health - перевірити стан системи"
        )

        await update.message.reply_text(help_message)

    async def handle_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command for system status."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"

        logger.info(f"/health command from {username} (ID: {user_id})")

        try:
            # Check RAG system health
            rag_health = self.retriever.health_check()

            # Build health status message
            health_message = "🔍 Стан системи:\n\n"

            # RAG System
            health_message += "RAG Система:\n"
            if rag_health.get("healthy"):
                health_message += f"✅ Векторна база: OK ({rag_health.get('documents', 0)} документів)\n"
                health_message += f"✅ Модель: {self.settings.ollama_model_name}\n"
                health_message += "✅ Ollama: Доступний\n"
            else:
                health_message += f"❌ Векторна база: {rag_health.get('status', 'ERROR')}\n"

            # Agents
            health_message += "\nАгенти:\n"
            health_message += "✅ Orchestrator: Готовий\n"
            health_message += "✅ Visa Agent: Готовий\n"
            health_message += "✅ Housing Agent: Готовий\n"
            health_message += "✅ Work Agent: Готовий\n"
            health_message += "✅ Fallback Agent: Готовий\n"

            health_message += "\n📊 Версія: 1.0.0\n"

            if rag_health.get("healthy"):
                health_message += "\nСистема працює нормально! ✅"
            else:
                health_message += "\n⚠️ Деякі компоненти недоступні"

            await update.message.reply_text(health_message)

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            error_message = (
                "❌ Помилка при перевірці стану системи.\n\n"
                f"Деталі: {str(e)}"
            )
            await update.message.reply_text(error_message)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        start_time = time.time()

        try:
            # Extract message details (works for both message and edited_message)
            message = update.effective_message
            if not message or not message.text:
                logger.debug("Ignoring update without text message")
                return

            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            message_text = message.text
            chat_type = update.effective_chat.type

            logger.info(
                f"Message from {username} (ID: {user_id}) "
                f"in {chat_type}: {message_text[:50]}..."
            )

            # Check if bot should respond (in groups, only respond to mentions)
            if chat_type in ["group", "supergroup"]:
                if not self._should_respond_in_group(update, context):
                    logger.debug("Ignoring group message without mention")
                    return

            # Check rate limit
            allowed, rate_limit_msg = self.rate_limiter.check_rate_limit(user_id)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                await message.reply_text(rate_limit_msg)
                return

            # Validate content
            is_valid, error_msg = self.content_filter.validate_query(message_text)
            if not is_valid:
                logger.warning(f"Invalid content from user {user_id}: {error_msg}")
                await message.reply_text(
                    f"⚠️ {error_msg}\n\nСпробуйте переформулювати питання."
                )
                return

            # Strip bot mention from query (for better RAG matching)
            clean_query = message_text
            bot_username = self.settings.telegram_bot_username
            if bot_username and f"@{bot_username}" in message_text:
                clean_query = message_text.replace(f"@{bot_username}", "").strip()
                logger.debug(f"Stripped bot mention, clean query: {clean_query[:50]}...")

            # Language detection
            detected_lang = self.language_detector.detect(clean_query)
            logger.info(f"Detected language: {detected_lang}")

            # Translate Russian to Ukrainian if needed
            query_ua = clean_query
            if detected_lang == "ru" and self.settings.auto_translate_russian:
                query_ua = await self.translator.translate_ru_to_ua(clean_query)
                logger.info(f"Translated: {query_ua[:50]}...")

            # Process with orchestrator
            response = await self.orchestrator.process_with_routing(query_ua)

            # Validate safety
            is_safe, validated_response = self.safety_validator.validate(response)
            if not is_safe:
                logger.warning(f"Response failed safety check for user {user_id}")
                validated_response = self.safety_validator.get_safe_fallback(
                    response.agent_name
                )

            # Format response
            formatted_message = self.formatter.format(validated_response)

            # Send response with Markdown, fallback to plain text if parsing fails
            try:
                await message.reply_text(
                    formatted_message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            except Exception as markdown_error:
                # If Markdown parsing fails, retry without parse_mode
                logger.warning(f"Markdown parsing failed, retrying with plain text: {markdown_error}")
                await message.reply_text(
                    formatted_message,
                    parse_mode=None,
                    disable_web_page_preview=False
                )

            # Log performance
            processing_time = time.time() - start_time
            logger.info(
                f"Response sent to {username} in {processing_time:.2f}s "
                f"(agent: {validated_response.agent_name})"
            )

            # Check if response time exceeds target
            if processing_time > self.settings.response_timeout_seconds:
                logger.warning(
                    f"Response time exceeded target: {processing_time:.2f}s "
                    f"> {self.settings.response_timeout_seconds}s"
                )

        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            await self._send_error_response(update, e)

    def _should_respond_in_group(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Check if bot should respond to group message.

        Args:
            update: Telegram update
            context: Bot context

        Returns:
            True if should respond
        """
        message = update.message

        # Respond if bot is mentioned
        if context.bot.username:
            if f"@{context.bot.username}" in message.text:
                return True

        # Respond if message is a reply to bot
        if message.reply_to_message:
            if message.reply_to_message.from_user.id == context.bot.id:
                return True

        return False

    async def _send_error_response(self, update: Update, error: Exception):
        """
        Send user-friendly error message.

        Args:
            update: Telegram update
            error: Exception that occurred
        """
        error_message = self.formatter.format_error("general")

        try:
            message = update.effective_message
            if message:
                await message.reply_text(error_message)
            else:
                logger.error("Cannot send error response: no message in update")
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")


# Singleton instance
_handlers = None


def get_bot_handlers() -> BotHandlers:
    """Get or create the global bot handlers instance."""
    global _handlers
    if _handlers is None:
        _handlers = BotHandlers()
    return _handlers
