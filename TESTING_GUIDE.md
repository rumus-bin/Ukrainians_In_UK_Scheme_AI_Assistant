# Quick Testing Guide - Ukrainian Support AI Bot

This guide will help you verify that the Telegram bot implementation is working correctly.

---

## Prerequisites

✅ Docker and Docker Compose installed and running
✅ All containers are up (`docker-compose ps`)
✅ Telegram bot token configured in `.env` file
✅ Ollama is running with `llama3.2:3b` model
✅ Qdrant has documents ingested

---

## Quick Start Testing (5 Minutes)

### 1. Start/Restart the Bot

```bash
# Navigate to project directory
cd /home/rumus-bin/Projects/Pet/AI/ukraine_scheme_ai_assistant

# Restart bot with new implementation
docker-compose restart bot

# Watch logs
docker-compose logs -f bot
```

You should see:
```
Starting Ukrainian Support AI Assistant Bot...
Initializing bot handlers...
Initializing specialized agents...
Bot is starting polling...
Multi-agent system initialized and ready!
```

### 2. Run Unit Tests

```bash
# Test orchestrator
docker exec -it ukraine-bot-app pytest tests/unit/test_orchestrator.py -v

# Test language detection
docker exec -it ukraine-bot-app pytest tests/unit/test_language.py -v

# Run all tests
docker exec -it ukraine-bot-app pytest tests/unit/ -v
```

Expected: All tests should PASS ✅

### 3. Test Basic Commands in Telegram

Open your Telegram bot and send:

#### Command: `/start`
**Expected Response:**
```
Вітаю! 👋

Я AI-асистент для українців у Великій Британії.

Можу допомогти з питаннями про:
📋 Візи та імміграцію (UPE, BRP, подорожі)
🏠 Житло та медицину (NHS, GP, школи)
💼 Роботу та допомогу (NI number, benefits)

⚠️ Важливо: Я не є юристом...
```

#### Command: `/health`
**Expected Response:**
```
🔍 Стан системи:

RAG Система:
✅ Векторна база: OK (XXX документів)
✅ Модель: llama3.2:3b
✅ Ollama: Доступний

Агенти:
✅ Orchestrator: Готовий
✅ Visa Agent: Готовий
...
```

---

## Detailed Testing Scenarios (15 Minutes)

### Scenario 1: Visa Question (Ukrainian)

**Send:** `Як продовжити візу UPE?`

**What to Check:**
- ✅ Response received within 7 seconds
- ✅ Response starts with 📋 emoji
- ✅ Response is in Ukrainian
- ✅ Contains a disclaimer about "не юридична консультація"
- ✅ Contains link to gov.uk or opora.uk
- ✅ No prohibited phrases ("ви точно отримаєте")

**Check Logs:**
```bash
docker-compose logs bot | tail -20
```

Should see:
```
INFO: Message from user...
INFO: Detected language: uk
INFO: Routed to: visa
INFO: visa_agent: Processing query...
INFO: Response sent to user in X.XXs (agent: visa_agent)
```

### Scenario 2: Housing Question (Russian)

**Send:** `Где зарегистрироваться в NHS?`

**What to Check:**
- ✅ Bot detects Russian language
- ✅ Bot translates to Ukrainian (check logs)
- ✅ Response is in Ukrainian (not Russian!)
- ✅ Response starts with 🏠 emoji
- ✅ Contains step-by-step instructions
- ✅ Contains disclaimer
- ✅ Contains links

**Check Logs for Translation:**
```bash
docker-compose logs bot | grep -i "translat"
```

### Scenario 3: Work Question

**Send:** `Як отримати National Insurance number?`

**What to Check:**
- ✅ Response starts with 💼 emoji
- ✅ Contains practical steps
- ✅ Routes to work_agent (check logs)
- ✅ Has disclaimer about "не фінансова консультація"

### Scenario 4: Greeting/Off-topic

**Send:** `Привіт!`

**What to Check:**
- ✅ Friendly greeting in Ukrainian
- ✅ Explanation of bot's capabilities
- ✅ Suggestion to ask relevant questions
- ✅ Routes to fallback_agent (check logs)

### Scenario 5: Group Chat Behavior

1. **Add bot to a test group**

2. **Test WITHOUT mention:**
   - Send: `тестове повідомлення`
   - Expected: Bot DOES NOT respond ✅

3. **Test WITH mention:**
   - Send: `@your_bot_name як продовжити UPE?`
   - Expected: Bot responds ✅

4. **Test reply:**
   - Reply to bot's message
   - Expected: Bot responds ✅

---

## Performance Testing

### Test 1: Response Time

```bash
# Monitor response times
docker-compose logs bot | grep "Response sent" | tail -10
```

✅ Target: Most responses < 5 seconds
⚠️  Acceptable: Up to 7 seconds
❌ Issue if: > 7 seconds consistently

### Test 2: Rate Limiting

Send 6 messages quickly:
```
1. Як продовжити візу?
2. Де знайти GP?
3. Як отримати NI?
4. Привіт
5. Дякую
6. Ще питання
```

After message 5 or 6:
```
⚠️ Занадто багато запитів. Зачекайте хвилину.
```

---

## Error Testing

### Test 1: Ollama Down

```bash
# Stop Ollama
docker stop ollama

# Send message to bot
# Expected: Error message with instructions

# Restart Ollama
docker start ollama
```

### Test 2: Invalid Input

Send very long message (> 4096 characters)
- Expected: Error message about message length

---

## Debugging

### View Logs
```bash
# All logs
docker-compose logs bot

# Follow logs
docker-compose logs -f bot

# Recent errors
docker-compose logs bot | grep -i error | tail -20

# Recent warnings
docker-compose logs bot | grep -i warning | tail -20

# Performance issues
docker-compose logs bot | grep "exceeded" | tail -10
```

### Check Container Status
```bash
docker-compose ps
docker stats ukraine-bot-app
```

### Shell Access
```bash
docker exec -it ukraine-bot-app /bin/bash
```

---

## Common Issues and Solutions

### Issue: Bot not responding

**Check 1:** Is bot running?
```bash
docker-compose ps
```

**Check 2:** Are there errors in logs?
```bash
docker-compose logs bot | grep -i error | tail -20
```

**Check 3:** Is Telegram token configured?
```bash
docker exec -it ukraine-bot-app python -c "from src.utils.config import get_settings; print(get_settings().telegram_bot_token[:10])"
```

**Solution:** Restart bot
```bash
docker-compose restart bot
```

### Issue: "Ollama unavailable" errors

**Check:** Is Ollama running?
```bash
docker ps | grep ollama
```

**Solution:** Start Ollama
```bash
docker start ollama
```

### Issue: "No documents found" in responses

**Check:** Is Qdrant populated?
```bash
docker exec -it ukraine-bot-app python -c "
from src.rag.retriever import get_retriever
r = get_retriever()
r.initialize()
print(r.health_check())
"
```

**Solution:** Run ingestion
```bash
docker exec -it ukraine-bot-app python run_ingestion.py
```

### Issue: Responses in wrong language

**Check logs for language detection:**
```bash
docker-compose logs bot | grep "Detected language"
```

**If detection is wrong:** This is a language detector issue. Check the input text.

**If translation failed:** Check logs for translation errors
```bash
docker-compose logs bot | grep -i "translation failed"
```

### Issue: Slow responses (> 7s)

**Check what's slow:**
```bash
docker-compose logs bot | grep "exceeded target"
```

**Possible causes:**
1. Ollama model too large → Use smaller model
2. Too many documents retrieved → Reduce `rag_top_k_results` in `.env`
3. Network latency → Check Qdrant connection

---

## Success Criteria

Your implementation is working correctly if:

✅ **Commands:**
- `/start` shows welcome message
- `/help` shows usage instructions
- `/health` shows system status

✅ **Routing:**
- Visa questions → Visa Agent
- Housing questions → Housing Agent
- Work questions → Work Agent
- Greetings → Fallback Agent

✅ **Language:**
- Ukrainian input processed correctly
- Russian input translated to Ukrainian
- All responses in Ukrainian

✅ **Safety:**
- All responses have disclaimers
- No prohibited phrases
- Source links included

✅ **Performance:**
- Response time < 7 seconds
- Rate limiting works
- Error handling works

✅ **Group Chat:**
- Responds to mentions
- Ignores non-mentions
- Responds to replies

---

## Next Steps After Testing

1. ✅ **If all tests pass:**
   - Add bot to small test group
   - Invite 2-3 trusted users
   - Collect feedback on response quality
   - Monitor logs for issues

2. ⚠️ **If some tests fail:**
   - Check the specific section in this guide
   - Review logs for error details
   - Fix issues and retest
   - Document issues in [specs/work_log](specs/work_log/)

3. 📝 **Always:**
   - Keep logs for analysis
   - Note any slow queries
   - Document user feedback
   - Track common questions

---

## Support

For detailed implementation information, see:
- [Implementation Report](specs/work_log/telegram_bot_implementation_report.md)
- [Technical Specification](ai_docs/telegram_bot_integration_spec.md)
- [Project README](README.md)

For issues or questions:
- Check logs: `docker-compose logs bot`
- Review architecture in implementation report
- Test individual components with unit tests

---

**Happy Testing! 🚀**

