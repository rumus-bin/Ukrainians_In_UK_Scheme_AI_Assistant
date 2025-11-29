# Ollama Configuration Guide

This project can work with Ollama in two ways:

## Option 1: Use Your Local Ollama (Recommended if you already have it)

**You have Ollama already running locally on port 11434**

This is the **DEFAULT** configuration and what you should use.

### Configuration:

1. **docker-compose.yml**: Keep the Ollama service **commented out** (it already is)

2. **.env file**: Use this configuration:
```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

3. **Verify your local Ollama is running**:
```bash
# Check Ollama is accessible
curl http://localhost:11434/api/tags

# List your models
ollama list
```

4. **Make sure you have the required models**:
```bash
# Download if you don't have them
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

5. **Start only the bot services**:
```bash
docker-compose up -d
```

### How it works:
- The bot and scraper containers will connect to your host machine's Ollama via `host.docker.internal`
- No port conflicts, no duplicate Ollama instances
- Your existing models are used directly
- Less resource usage (one Ollama instance instead of two)

---

## Option 2: Use Containerized Ollama

**You don't have Ollama installed or prefer containerized setup**

### Configuration:

1. **docker-compose.yml**: Uncomment the Ollama service:
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ukraine-bot-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    restart: unless-stopped
    networks:
      - bot-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

2. **docker-compose.yml**: Update bot and scraper dependencies:
```yaml
  bot:
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:          # Uncomment this
        condition: service_healthy

  scraper:
    depends_on:
      - qdrant
      - ollama        # Uncomment this
```

3. **.env file**: Use this configuration:
```bash
OLLAMA_BASE_URL=http://ollama:11434
```

4. **Start all services**:
```bash
docker-compose up -d
```

5. **Download models into the container**:
```bash
docker exec ukraine-bot-ollama ollama pull llama3.2:3b
docker exec ukraine-bot-ollama ollama pull mxbai-embed-large
```

### How it works:
- Ollama runs in its own Docker container
- Models are stored in a Docker volume
- Containers communicate via Docker network
- Completely isolated from host system

---

## Testing Your Configuration

### Test Local Ollama Connection
```bash
# From your host
curl http://localhost:11434/api/tags

# From within bot container
docker exec ukraine-bot-app curl http://host.docker.internal:11434/api/tags
```

### Test Containerized Ollama Connection
```bash
# From bot container
docker exec ukraine-bot-app curl http://ollama:11434/api/tags
```

### View Bot Logs
```bash
# Check if bot successfully connects to Ollama
docker-compose logs bot | grep -i ollama
```

---

## Troubleshooting

### "Connection refused" to host.docker.internal:11434

**Problem**: Bot can't connect to your local Ollama

**Solutions**:
1. Verify Ollama is running: `ollama list`
2. Check it's on port 11434: `lsof -i :11434`
3. On Linux, you may need to configure Ollama to listen on 0.0.0.0:
   ```bash
   # Set environment variable
   export OLLAMA_HOST=0.0.0.0:11434
   # Restart Ollama
   ```
4. Check Docker network configuration allows host access

### "Port 11434 already in use"

**Problem**: You're trying to run containerized Ollama but port is busy

**Solution**: You have local Ollama running. Either:
- Use Option 1 (local Ollama) - recommended
- Stop local Ollama: `pkill ollama` or system-specific command

### Models not found

**Local Ollama**:
```bash
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

**Containerized Ollama**:
```bash
docker exec ukraine-bot-ollama ollama pull llama3.2:3b
docker exec ukraine-bot-ollama ollama pull mxbai-embed-large
```

---

## Current Setup (Default)

The project is currently configured for **Option 1: Local Ollama**

- Ollama service in docker-compose.yml: **COMMENTED OUT** ✅
- .env.example OLLAMA_BASE_URL: `http://host.docker.internal:11434` ✅
- Bot/scraper extra_hosts: Configured with `host-gateway` ✅

**You're ready to use your local Ollama instance!**