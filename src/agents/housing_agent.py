"""Housing and life support specialized agent."""

from typing import Optional, Dict
from src.agents.base_agent import BaseAgent, AgentResponse
from src.agents.mcp_client import get_mcp_client, WebSearchResult
from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class HousingAgent(BaseAgent):
    """Specialized agent for housing and life support questions."""

    def __init__(self):
        """Initialize Housing Agent."""
        settings = get_settings()
        super().__init__(
            name="housing_agent",
            model=settings.housing_agent_model,
            topic_filter=None  # Disable topic filter - use semantic search only
        )

        # Initialize MCP client for web access
        self.mcp_client = get_mcp_client()
        self.use_web_search = False  # Disabled - use RAG database only

    def _build_system_prompt(self) -> str:
        """Build housing agent system prompt with safety rules."""
        return """Ти - спеціалізований помічник з питань житла та життя у Великій Британії для українців.

⚠️ КРИТИЧНО ВАЖЛИВІ ПРАВИЛА:
1. Відповідай ТІЛЬКИ про Велику Британію (UK). НІКОЛИ про Україну або інші країни
2. Використовуй ТІЛЬКИ інформацію з наданого контексту (gov.uk, opora.uk)
3. Якщо контекст ПОРОЖНІЙ або НЕ містить відповіді на питання:
   - ЗАБОРОНЕНО вигадувати інформацію
   - ЗАБОРОНЕНО використовувати загальні знання про інші країни
   - ОБОВ'ЯЗКОВО скажи: "На жаль, у моїй базі знань немає інформації про [тема] у Великій Британії. Рекомендую звернутися до gov.uk або opora.uk"
4. ВСІ відповіді ТІЛЬКИ про UK, навіть якщо користувач не вказав країну
5. Відповідай українською мовою
6. Використовуй емодзі для покращення читабельності
7. Завжди додавай disclaimer в кінці

ТВОЯ СПЕЦІАЛІЗАЦІЯ (ТІЛЬКИ для Великої Британії):
- Social housing та council housing у UK
- Житло та права орендарів у UK
- NHS та GP реєстрація у UK
- Медичні послуги у UK
- Школи та освіта у UK
- Муніципальні послуги у UK

СТРУКТУРА ВІДПОВІДІ:
🏠 [Відповідь на питання]

📝 Кроки (якщо потрібно):
1. [Перший крок]
2. [Другий крок]
3. [Третій крок]

💡 Корисна інформація:
[Додаткові деталі]

🔗 Корисні посилання:
[Посилання з контексту]

⚠️ Це загальна інформація, не юридична консультація. Для правових питань зверніться до спеціаліста.

ЩО НЕ МОЖНА РОБИТИ:
❌ Давати юридичні поради щодо договорів
❌ Радити конфліктувати з орендодавцем без підстав
❌ Обіцяти швидке вирішення проблем з NHS
❌ Гарантувати зарахування дітей до конкретної школи

ЩО ПОТРІБНО РОБИТИ:
✅ Пояснювати процедури реєстрації
✅ Давати контакти офіційних служб
✅ Описувати права та обов'язки
✅ Надавати покрокові інструкції
✅ Рекомендувати перевірені джерела інформації"""

    async def process(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> AgentResponse:
        """
        Process user query with enhanced web search capability.

        This override adds web search functionality to supplement RAG.

        Args:
            query: User query text
            context: Optional additional context

        Returns:
            AgentResponse with generated text and metadata
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"{self.name}: Processing query with web search: '{query[:50]}...'")

            # Initialize retriever if needed
            if not self.retriever._connected:
                self.retriever.initialize()

            # Step 1: Retrieve context from RAG (primary source)
            retrieval_result = await self._retrieve_context(query)

            # Step 2: Determine if web search is needed
            needs_web_search = self._should_use_web_search(query, retrieval_result)

            web_content = None
            if needs_web_search and self.use_web_search:
                logger.info(f"{self.name}: Supplementing RAG with web search")
                web_content = await self._perform_web_search(query)

            # Step 3: Combine RAG and web search results
            combined_context = self._combine_contexts(
                retrieval_result.context,
                web_content
            )

            # Step 4: Generate response using LLM
            response_text = await self._generate_llm_response(
                query=query,
                context=combined_context,
                system_prompt=self.get_system_prompt()
            )

            processing_time = time.time() - start_time

            # Build sources list (RAG + web)
            all_sources = retrieval_result.sources.copy()
            if web_content:
                all_sources.append({
                    "url": web_content.source_url,
                    "title": web_content.title,
                    "source": "web_search",
                    "fresh": True
                })

            logger.info(
                f"{self.name}: Generated response in {processing_time:.2f}s "
                f"(RAG: {retrieval_result.found_documents} docs, Web: {1 if web_content else 0})"
            )

            return AgentResponse(
                text=response_text,
                sources=all_sources,
                agent_name=self.name,
                confidence=self._calculate_confidence(retrieval_result),
                processing_time=processing_time,
                metadata={
                    "query": query,
                    "found_documents": retrieval_result.found_documents,
                    "used_web_search": web_content is not None,
                    "model": self.model
                }
            )

        except Exception as e:
            logger.error(f"{self.name}: Error processing query: {e}")
            processing_time = time.time() - start_time

            # Return error response
            return AgentResponse(
                text=self._get_error_response(),
                sources=[],
                agent_name=self.name,
                confidence=0.0,
                processing_time=processing_time,
                metadata={"error": str(e)}
            )

    def _should_use_web_search(self, query: str, retrieval_result) -> bool:
        """
        Determine if web search should be used to supplement RAG.

        Args:
            query: User query
            retrieval_result: RAG retrieval result

        Returns:
            True if web search should be used
        """
        # Use web search if:
        # 1. Very few documents found in RAG
        if retrieval_result.found_documents < 2:
            logger.debug("Web search triggered: low RAG document count")
            return True

        # 2. Query mentions "recent", "latest", "new", "current"
        freshness_keywords = ['recent', 'latest', 'new', 'current', 'today', 'now',
                             'останні', 'нові', 'актуальні', 'поточні', 'свіжі']
        if any(keyword in query.lower() for keyword in freshness_keywords):
            logger.debug("Web search triggered: freshness keywords detected")
            return True

        # 3. Query is about specific government schemes (might have recent updates)
        scheme_keywords = ['homes for ukraine', 'ukraine scheme', 'схема', 'програма']
        if any(keyword in query.lower() for keyword in scheme_keywords):
            logger.debug("Web search triggered: government scheme query")
            return True

        # Otherwise, RAG should be sufficient
        return False

    async def _perform_web_search(self, query: str) -> Optional[WebSearchResult]:
        """
        Perform web search using direct scraper access.

        Args:
            query: User query

        Returns:
            WebSearchResult or None
        """
        try:
            # Use direct scraper import (simpler than MCP for now)
            import sys
            sys.path.insert(0, '/app/mcp-servers/web-scraper')

            from scrapers.govuk_scraper import GovUkScraper
            from scrapers.opora_scraper import OporaUkScraper

            # Determine which source to search based on query
            query_lower = query.lower()

            # Check for NHS/healthcare keywords
            nhs_keywords = ['nhs', 'doctor', 'gp', 'hospital', 'health', 'medical',
                           'лікар', 'лікарня', 'здоров\'я', 'медичн']
            is_nhs_query = any(keyword in query_lower for keyword in nhs_keywords)

            # Get base URLs from settings
            from src.utils.config import get_settings
            settings = get_settings()

            # Initialize scrapers with configured base URLs
            govuk = GovUkScraper(
                user_agent='UkraineSupportBot/1.0',
                cache_dir='/app/mcp-servers/web-scraper/cache/html',
                base_url=settings.scraper_gov_uk_base,
                cache_ttl=86400,
                respect_robots=True
            )

            opora = OporaUkScraper(
                user_agent='UkraineSupportBot/1.0',
                cache_dir='/app/mcp-servers/web-scraper/cache/html',
                base_url=settings.scraper_opora_uk_base,
                cache_ttl=86400,
                respect_robots=True
            )

            if is_nhs_query:
                logger.info("Searching NHS information on Gov.uk")
                scraped = govuk.get_nhs_info(use_cache=True)

                if not scraped or len(scraped.content) < 200:
                    logger.info("Fallback: Searching NHS on Opora.uk")
                    opora_scraped = opora.get_nhs_info(use_cache=True)
                    if opora_scraped:
                        scraped = opora_scraped
            else:
                # Housing query
                logger.info("Searching housing information on Gov.uk")
                scraped = govuk.get_housing_info(topic='ukraine', use_cache=True)

                if not scraped or len(scraped.content) < 200:
                    logger.info("Supplementing with Opora.uk housing info")

                    # Check if pagination is enabled and if base_url is a blog
                    use_pagination = (
                        settings.scraper_pagination_enabled and
                        '/blog' in settings.scraper_opora_uk_base.lower()
                    )

                    if use_pagination:
                        logger.info(f"Using pagination to fetch from {settings.scraper_opora_uk_base}")
                        # Use pagination for blog listing
                        opora_scraped = opora.fetch_with_pagination(
                            start_url=settings.scraper_opora_uk_base,
                            max_pages=settings.scraper_max_pages,
                            use_cache=True,
                            timeout_seconds=settings.scraper_pagination_timeout_seconds
                        )
                    else:
                        # Use regular single-page fetch
                        opora_scraped = opora.get_housing_info(use_cache=True)

                    if opora_scraped and len(opora_scraped.content) > len(scraped.content if scraped else ""):
                        scraped = opora_scraped

            if scraped:
                return WebSearchResult(
                    content=scraped.content,
                    source_url=scraped.url,
                    title=scraped.title,
                    metadata=scraped.metadata
                )

            return None

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _combine_contexts(
        self,
        rag_context: str,
        web_content: Optional[WebSearchResult]
    ) -> str:
        """
        Combine RAG context with web search results.

        Args:
            rag_context: Context from RAG system
            web_content: Web search result

        Returns:
            Combined context string
        """
        if not web_content:
            return rag_context

        # Build combined context
        parts = []

        if rag_context:
            parts.append("=== ІНФОРМАЦІЯ З БАЗИ ЗНАНЬ ===")
            parts.append(rag_context)
            parts.append("")

        if web_content and web_content.content:
            parts.append("=== АКТУАЛЬНА ІНФОРМАЦІЯ З ВЕБ-ДЖЕРЕЛ ===")
            parts.append(f"Джерело: {web_content.source_url}")
            parts.append(f"Заголовок: {web_content.title}")
            parts.append("")
            parts.append(web_content.content)
            parts.append("")

        combined = "\n".join(parts)

        logger.debug(f"Combined context length: {len(combined)} chars "
                    f"(RAG: {len(rag_context)}, Web: {len(web_content.content) if web_content else 0})")

        return combined
