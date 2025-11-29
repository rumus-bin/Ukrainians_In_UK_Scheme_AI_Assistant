# Quick Start Guide

Get the Ukrainian Support AI Assistant bot running in 5 minutes!

## Prerequisites Check

```bash
# Check Docker is installed
docker --version

# Check Docker Compose is installed
docker-compose --version

# Check Ollama is running (you should already have this)
ollama list
```

If Docker is not installed, visit [Docker Installation Guide](https://docs.docker.com/get-docker/)

> **Important**: This quickstart assumes you already have **Ollama running locally** on port 11434. If not, see [OLLAMA_CONFIG.md](OLLAMA_CONFIG.md) for containerized setup.

## 1. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Telegram bot token
nano .env  # or use your preferred editor
```

**Get a Telegram Bot Token:**
1. Open Telegram
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow instructions
5. Copy the token to `.env`

## 2. Start Services

```bash
# Start all services in background
docker-compose up -d

# Check services are running
docker-compose ps
```

Expected output (with local Ollama):
```
NAME                   STATUS
ukraine-bot-app        Up
ukraine-bot-qdrant     Up (healthy)
ukraine-bot-scraper    Up
```

## 3. Verify/Download AI Models

**If you already have Ollama running locally** (default configuration):

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check if you have the required models
ollama list

# Download models if needed
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

**If using containerized Ollama** (see OLLAMA_CONFIG.md):

```bash
# Download the main language model (3B parameters, ~2GB)
docker exec ukraine-bot-ollama ollama pull llama3.2:3b

# Download the embedding model (~670MB)
docker exec ukraine-bot-ollama ollama pull mxbai-embed-large
```

This may take 5-10 minutes depending on your internet connection.

> **Note**: By default, the project is configured to use your **local Ollama** instance. See [OLLAMA_CONFIG.md](OLLAMA_CONFIG.md) for details.

## 4. Test the Bot

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. You should see a welcome message in Ukrainian!

## 5. View Logs

```bash
# View all logs
docker-compose logs -f

# View just bot logs
docker-compose logs -f bot
```

## Troubleshooting

### Bot doesn't respond
```bash
# Check bot logs for errors
docker-compose logs bot --tail=50

# Verify token is correct
grep TELEGRAM_BOT_TOKEN .env

# Verify Ollama connection
docker exec ukraine-bot-app curl http://host.docker.internal:11434/api/tags
```

### Out of memory errors
```bash
# Use a smaller model
docker exec ukraine-bot-ollama ollama pull tinyllama:1.1b

# Update .env
OLLAMA_MODEL_NAME=tinyllama:1.1b
```

### Services won't start
```bash
# Stop all services
docker-compose down

# Remove old containers and volumes
docker-compose down -v

# Restart
docker-compose up -d
```

## Next Steps

- Read [SETUP.md](SETUP.md) for detailed development setup
- Configure scrapers to collect data from gov.uk and opora.uk
- Implement agent logic for answering questions
- Add RAG pipeline for knowledge retrieval

## Useful Commands

```bash
# Stop services
docker-compose stop

# Restart services
docker-compose restart

# View service status
docker-compose ps

# Remove everything
docker-compose down -v
```

For more information, see the full [README.md](README.md)