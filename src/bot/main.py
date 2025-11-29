"""Main entry point for the Telegram bot application."""

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.utils.config import get_settings
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()
logger = get_logger()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    logger.info(f"Start command received from user {update.effective_user.id}")

    welcome_message = (
        "Вітаю! 👋\n\n"
        "Я AI-асистент для українців у Великій Британії.\n\n"
        "Можу допомогти з питаннями про:\n"
        "📋 Візи та імміграцію\n"
        "🏠 Житло та реєстрацію\n"
        "💼 Роботу та допомогу\n"
        "🏥 NHS та медицину\n\n"
        "⚠️ Важливо: Я не є юристом. Моя інформація базується на офіційних джерелах "
        "(gov.uk та opora.uk), але для юридичних рішень зверніться до спеціаліста.\n\n"
        "Задайте своє питання українською або російською мовою!"
    )

    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    logger.info(f"Help command received from user {update.effective_user.id}")

    help_message = (
        "📖 Як мною користуватися:\n\n"
        "1️⃣ Просто напишіть своє питання українською або російською\n"
        "2️⃣ Я проаналізую запит та дам відповідь на основі офіційних джерел\n"
        "3️⃣ У відповіді будуть посилання на gov.uk або opora.uk\n\n"
        "Приклади питань:\n"
        "• Як продовжити візу Ukraine Permission Extension?\n"
        "• Де зареєструватися у NHS?\n"
        "• Як отримати National Insurance number?\n"
        "• Які мої права як орендаря житла?\n\n"
        "⚠️ Пам'ятайте: Я не можу давати юридичні поради або передбачати "
        "рішення по вашій візі. Для складних випадків звертайтеся до спеціалістів."
    )

    await update.message.reply_text(help_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    message_text = update.message.text

    logger.info(f"Message from {username} (ID: {user_id}): {message_text[:50]}...")

    # TODO: Implement actual agent processing
    # For now, send a placeholder response

    response = (
        "🔄 Обробляю ваш запит...\n\n"
        "⚠️ Увага: Основна функціональність бота ще в розробці.\n\n"
        "Зараз налаштовується:\n"
        "• Підключення до локальної LLM (Ollama)\n"
        "• Векторна база знань з gov.uk та opora.uk\n"
        "• Система агентів для різних типів питань\n\n"
        "Скоро я зможу відповідати на ваші питання! 🚀"
    )

    await update.message.reply_text(response)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    settings = get_settings()

    logger.info("Starting Ukrainian Support AI Assistant Bot...")
    logger.info(f"Bot token configured: {'Yes' if settings.telegram_bot_token else 'No'}")
    logger.info(f"Ollama URL: {settings.ollama_base_url}")
    logger.info(f"Vector DB: {settings.vector_db_type}")

    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN not configured! Please set it in .env file")
        return

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Bot is starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")