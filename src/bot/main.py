"""Main entry point for the Telegram bot application."""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.bot.handlers import get_bot_handlers
from src.utils.config import get_settings
from src.utils.logger import setup_logger, get_logger

# Initialize logger
setup_logger()
logger = get_logger()


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
    logger.info(f"Model: {settings.ollama_model_name}")

    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN not configured! Please set it in .env file")
        return

    # Initialize bot handlers
    logger.info("Initializing bot handlers...")
    handlers = get_bot_handlers()

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", handlers.handle_start))
    application.add_handler(CommandHandler("help", handlers.handle_help))
    application.add_handler(CommandHandler("health", handlers.handle_health))

    # Add message handler (exclude edited messages to avoid duplicates)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE,
            handlers.handle_message
        )
    )

    # Add error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Bot is starting polling...")
    logger.info("Multi-agent system initialized and ready!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")