**“Ukrainian Support AI Assistant for Telegram (UK Edition)”**

# 1. **Project Overview**

This project aims to create a **non-commercial AI-driven Telegram assistant** designed to help Ukrainian refugees and immigrants living in the United Kingdom (especially those under the _Homes for Ukraine_ scheme).

The assistant provides:

- Clear and simple guidance on UK visas, UPE, housing, employment, benefits, NHS, schools

- References to reliable sources: **gov.uk** and **opora.uk**

- Answers in **Ukrainian language**

- Safe and responsible behavior (non-legal, non-financial advisory)

- Optimized resource consumption (runs fully locally using small LLM models)


The solution must work **inside a Telegram group**, act as a supportive and simple helper, and rely on RAG (Retrieval Augmented Generation) using a local vector database.

---

# 2. **Target Users**

### Primary users:

Ukrainian refugees, immigrants, and families in the UK who:

- Use Telegram as their main communication tool

- Are not technically skilled

- Need simple explanations and helpful links

- Prefer Ukrainian-language communication


### Secondary users:

- Volunteer group moderators

- Local community leaders

- Social support organizations

- Ukrainians planning relocation to the UK


---

# 3. **User Problems to Solve**

- Lack of understanding of UK visa regulations

- Difficulty finding reliable and structured information

- Overload or misinformation in Telegram chats

- Limited English proficiency

- Confusion regarding bureaucratic steps (GP registration, NI number, benefits, housing rules)


The bot must give **clear, safe, accurate and easy-to-follow** guidance.

---

# 4. **Product Goals**

### Core goals:

- Provide quick, safe, multilingual (UA/RU input → UA output) assistance for Ukrainians in UK.

- Serve as a centralized knowledge assistant inside Telegram.

- Keep infrastructure **very cheap** and self-hosted.

- Maintain reliably updated RAG database from gov.uk & opora.uk.


### Non-goals:

- Provide official legal or immigration consultations.

- Give personalized legal advice.

- Predict visa outcomes or recommend risky legal actions.


---

# 5. **Key Features**

## 5.1 Telegram Group Bot

- Reacts when mentioned (`@botname`) or via keyword prefix.

- Understands Ukrainian & Russian input.

- Always responds in Ukrainian.


## 5.2 Local LLM Engine (Ollama)

- Uses a small, lightweight model (1–3B) for inference.

- Embedding model for vector search.

- Zero paid API usage.


## 5.3 Multi-Agent Architecture

- **Orchestrator agent**

- **Visa & Immigration agent**

- **Housing & Life Support agent**

- **Work & Benefits agent**

- **Fallback General Chat agent**


## 5.4 RAG (Retrieval-Augmented Generation)

- Fetch and scrape gov.uk & opora.uk content.

- Store text chunks in a vector database (Chroma or Qdrant).

- Weekly automated update pipeline.


## 5.5 Safety & Accuracy Layer

- Mandatory disclaimers in every answer.

- No legal statements such as “you will definitely get the visa”.

- Safe-mode override for risky questions.


## 5.6 Simple Explanations

- Short, structured, step-by-step answers.

- Friendly tone.

- Emoji-based section headers (for readability).


---

# 6. **Functional Requirements**

## 6.1 Input Processing

- Detect message language (UA/RU).

- Translate Russian → Ukrainian only if needed.

- Pass user message to orchestrator.


## 6.2 Orchestrator Logic

- Determine which agent should respond based on the topic.

- Choose appropriate retriever (visa / housing / general).

- Ensure that context fits within model limits.


## 6.3 Agent Behavior

### Each agent must:

- Take context chunks from RAG.

- Construct answer using local LLM.

- Include:

    - Short steps

    - Links to gov.uk and opora.uk

    - Disclaimer

    - Friendly tone


## 6.4 System Prompts (high-level)

### Every agent must follow:

1. “You are not a lawyer.”

2. “Use only official sources for facts.”

3. “If unsure — recommend checking gov.uk or consulting specialists.”

4. “Always answer in Ukrainian.”

5. “Target answers for people with low digital skills.”


---

# 7. **Non-Functional Requirements**

## 7.1 Performance

- Response time target: < 7 seconds

- Ollama model size: ideally 1–3B parameters

- Server: Ubuntu 24.04, 8–16GB RAM recommended


## 7.2 Reliability

- Automatic restart via docker-compose

- Logging and fallback messages in case of LLM errors


## 7.3 Security

- No private user data stored

- No external APIs (except Telegram)

- HTTPS proxy (nginx/traefik) optional


## 7.4 Maintainability

- Cron-based weekly scraper update

- Easy-to-rebuild docker-compose stack

- Modular agent design


---

# 8. **Deployment Requirements**

## 8.1 Platform

- Ubuntu 24.04 server

- Docker

- docker-compose


## 8.2 Containers (minimum)

- `bot-api`

- `ollama`

- `vectorstore` (Chroma or Qdrant)

- `reverse-proxy` (optional)


## 8.3 Volumes

- Persistent storage:

    - LLM models

    - Vector database

    - Logs

    - Scraped HTML and processed chunks


---

# 9. **Risks**


|Risk|Mitigation|
|---|---|
|Local LLM gives hallucinated legal info|Strong system prompt + RAG + safety layer|
|gov.uk changes structure|Weekly scraper refresh|
|Server performance insufficient|Use smaller models, quantization|
|Incorrect language detection|Always force Ukrainian output|
|User asks for personal legal help|Provide safe fallback message|

---

# 10. **Acceptance Criteria**

- Bot answers correctly in Ukrainian using official sources.

- Works in Telegram group, politely and consistently.

- All infrastructure runs under docker-compose.

- Local LLM inference works with reasonable speed.

- RAG search returns relevant chunks from gov.uk/opora.

- No hallucinated legal claims in testing scenarios.

- Weekly data refresh works.


---

# 11. **Next Step**

Now that the **PRD is complete**, the next documents to create are:

### ✅ EPICS DOCUMENT

Contains:

- Epics

- Iterations

- Development stages

- Dependencies

- High-level acceptance tests


### ✅ TECHNICAL SPEC DOCUMENTS

One document per epic:

- Architecture

- Docker structure

- Agent design

- RAG pipeline

- Scraper bot spec

- Safety layer design

- Telegram adapter

- Logging & monitoring

- Testing procedures


### ✅ AI-AGENT TASK DOCUMENTS

These are “micro-documents” intended for automated coding agents.  
Each describes:

- Tiny unit of work

- What files to modify

- What classes/functions to create

- How to test it locally

- What constraints apply
