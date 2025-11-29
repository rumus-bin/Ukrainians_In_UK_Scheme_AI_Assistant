# Development Environment Setup

This guide will help you set up the development environment for the Ukrainian Support AI Assistant for Telegram.

## Prerequisites

### Required Software
- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **Python** (version 3.10+) - for local development
- **Git**

### System Requirements
- **RAM**: 8-16GB recommended (for running Ollama with 1-3B parameter models)
- **Storage**: 10GB+ free space (for models and data)
- **OS**: Ubuntu 24.04 (recommended), or any Docker-compatible OS

## Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd ukraine_scheme_ai_assistant
```

### 2. Configure Environment Variables
```bash
cp .env.example .env
```

Edit the `.env` file and add your Telegram bot token:
```bash
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
```

To get a Telegram bot token:
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token provided by BotFather

### 3. Start Services with Docker Compose
```bash
docker-compose up -d
```

This will start:
- **Ollama** (LLM service) on port 11434
- **Qdrant** (vector database) on port 6333
- **Bot application** (Telegram bot)
- **Scraper service** (scheduled data collection)

### 4. Download Ollama Models
After services are running, download the required models:

```bash
# Download the main LLM model (3B parameter version recommended)
docker exec ukraine-bot-ollama ollama pull llama2:3b

# Download the embedding model
docker exec ukraine-bot-ollama ollama pull nomic-embed-text
```

Alternative models you can try:
- `mistral:3b` - Fast and efficient
- `phi:2.7b` - Microsoft's efficient model
- `tinyllama:1.1b` - Smallest option (faster but less capable)

### 5. Verify Services are Running
```bash
# Check all services status
docker-compose ps

# Check Ollama is responding
curl http://localhost:11434/api/tags

# Check Qdrant is responding
curl http://localhost:6333/
```

### 6. View Logs
```bash
# View all logs
docker-compose logs -f

# View bot logs only
docker-compose logs -f bot

# View scraper logs only
docker-compose logs -f scraper
```

## Local Development Setup (Without Docker)

If you prefer to develop locally without Docker:

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
pip install -e ".[dev]"  # Install development dependencies
```

### 3. Install and Run Ollama Locally
```bash
# Download Ollama from https://ollama.ai
# Then pull models:
ollama pull llama2:3b
ollama pull nomic-embed-text
```

### 4. Install and Run Qdrant Locally
```bash
# Using Docker for Qdrant only
docker run -p 6333:6333 -v $(pwd)/data/vectordb:/qdrant/storage qdrant/qdrant
```

### 5. Update .env for Local Development
```bash
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 6. Run the Bot Locally
```bash
python -m src.bot.main
```

## Project Structure

```
ukraine_scheme_ai_assistant/
├── src/
│   ├── agents/          # Multi-agent implementation
│   ├── bot/             # Telegram bot interface
│   ├── rag/             # RAG pipeline
│   ├── scrapers/        # Web scrapers for gov.uk and opora.uk
│   ├── utils/           # Utility functions
│   └── vectorstore/     # Vector database management
├── data/
│   ├── scraped/         # Raw scraped data
│   ├── chunks/          # Processed text chunks
│   └── vectordb/        # Vector database storage
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── docker/              # Dockerfiles
├── logs/                # Application logs
├── .env                 # Environment variables (create from .env.example)
├── docker-compose.yml   # Docker Compose configuration
└── requirements.txt     # Python dependencies
```

## Development Workflow

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_agents.py
```

### Code Formatting and Linting
```bash
# Format code with Black
black src/ tests/

# Check code style with Flake8
flake8 src/ tests/

# Type checking with MyPy
mypy src/
```

### Debugging

#### Enable Debug Mode
Set in `.env`:
```bash
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

#### View Detailed Logs
```bash
# Watch logs in real-time
tail -f logs/bot.log

# Or with Docker
docker-compose logs -f bot
```

## Common Issues and Solutions

### Issue: Ollama models not downloading
**Solution**: Increase Docker memory allocation to at least 8GB in Docker Desktop settings.

### Issue: Bot not responding in Telegram
**Solution**:
1. Verify bot token is correct in `.env`
2. Check bot logs: `docker-compose logs bot`
3. Ensure bot is not already running elsewhere with the same token

### Issue: Vector database connection errors
**Solution**:
1. Check Qdrant is running: `curl http://localhost:6333/`
2. Verify network connectivity between containers
3. Check Docker logs: `docker-compose logs qdrant`

### Issue: Out of memory errors
**Solution**:
1. Use smaller model: `tinyllama:1.1b` instead of `llama2:3b`
2. Reduce `RAG_TOP_K_RESULTS` in `.env`
3. Increase system swap space

### Issue: Slow response times (>7 seconds)
**Solution**:
1. Use quantized models for faster inference
2. Reduce `RAG_CHUNK_SIZE` and `RAG_TOP_K_RESULTS`
3. Ensure Ollama has sufficient resources allocated

## Next Steps

After completing the setup:
1. Review the main [README.md](README.md) for project overview
2. Check the [specs/](specs/) directory for detailed specifications
3. Read agent documentation in `src/agents/README.md` (to be created)
4. Configure scrapers for your specific data sources

## Useful Commands

```bash
# Restart all services
docker-compose restart

# Rebuild after code changes
docker-compose up -d --build

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v

# Access Ollama CLI
docker exec -it ukraine-bot-ollama ollama run llama2:3b

# Access bot container shell
docker exec -it ukraine-bot-app /bin/bash

# View vector database collections
curl http://localhost:6333/collections
```

## Additional Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [LangChain Documentation](https://python.langchain.com/)

## Support

For issues and questions:
1. Check the [GitHub Issues](link-to-issues)
2. Review project documentation in `specs/`
3. Contact project maintainers