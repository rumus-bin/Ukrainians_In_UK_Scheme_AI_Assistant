"""Configuration management using environment variables and pydantic."""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Configuration
    telegram_bot_token: str
    telegram_bot_username: str = ""

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_name: str = "llama3.2:3b"
    ollama_embedding_model: str = "mxbai-embed-large"

    # Vector Database Configuration
    vector_db_type: Literal["qdrant", "chroma"] = "qdrant"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "ukraine_support_knowledge"

    # RAG Configuration
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k_results: int = 5
    rag_similarity_threshold: float = 0.7

    # Agent Configuration
    orchestrator_model: str = "llama3.2:3b"
    visa_agent_model: str = "llama3.2:3b"
    housing_agent_model: str = "llama3.2:3b"
    work_agent_model: str = "llama3.2:3b"
    fallback_agent_model: str = "llama3.2:3b"

    # Response Configuration
    max_response_tokens: int = 500
    response_temperature: float = 0.3
    response_timeout_seconds: int = 7

    # Language Configuration
    default_output_language: str = "uk"
    supported_input_languages: str = "uk,ru"
    auto_translate_russian: bool = True

    # Scraper Configuration
    scraper_enabled: bool = False  # Disabled by default - use manual documents
    scraper_govuk_enabled: bool = False  # Individual scraper toggle
    scraper_opora_enabled: bool = False  # Individual scraper toggle
    scraper_schedule_enabled: bool = False  # Disable scheduled scraping
    scraper_schedule_cron: str = "0 2 * * 0"
    scraper_user_agent: str = "Mozilla/5.0 (compatible; UkraineSupportBot/1.0)"
    scraper_request_delay_seconds: int = 2
    scraper_max_retries: int = 3

    # Manual Document Ingestion Configuration
    manual_docs_enabled: bool = True  # Use manually created documents
    manual_docs_path: str = "/app/data/manual_docs"  # Path to manual documents
    manual_docs_format: str = "json"  # Format: json, txt, or markdown
    manual_docs_recursive: bool = True  # Search subdirectories

    # Source URLs
    scraper_gov_uk_base: str = "https://www.gov.uk"
    scraper_opora_uk_base: str = "https://www.opora.uk"

    # Logging Configuration
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_file_path: str = "/app/logs/bot.log"
    log_max_size_mb: int = 100
    log_backup_count: int = 5

    # Safety Configuration
    enable_safety_disclaimers: bool = True
    safety_prompt_enabled: bool = True
    block_legal_predictions: bool = True

    # Development/Testing
    debug_mode: bool = False
    test_mode: bool = False
    dry_run: bool = False


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings