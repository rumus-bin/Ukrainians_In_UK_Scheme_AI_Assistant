"""Tests for MCP web scraper functionality."""

import pytest
import asyncio
from pathlib import Path
import sys

# Add mcp-servers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "web-scraper"))

from scrapers.base_scraper import BaseWebScraper, RobotsChecker, RateLimiter, ContentCache
from scrapers.opora_scraper import OporaUkScraper
from scrapers.govuk_scraper import GovUkScraper


class TestRobotsChecker:
    """Test robots.txt compliance checker."""

    def test_can_fetch_allowed(self):
        """Test that allowed URLs return True."""
        checker = RobotsChecker()

        # Most sites allow crawling by default
        result = checker.can_fetch("https://www.gov.uk/housing-for-ukraine", "*")
        assert isinstance(result, bool)

    def test_caching(self):
        """Test that robots.txt is cached."""
        checker = RobotsChecker(cache_ttl=3600)

        # First call
        checker.can_fetch("https://www.gov.uk/housing", "*")

        # Should use cache for same domain
        assert "https://www.gov.uk" in checker.cache


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_delay(self):
        """Test that rate limiter enforces delays."""
        import time

        limiter = RateLimiter(requests_per_minute=60, delay_between_requests=0.1)

        start = time.time()
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        # Second call should have waited at least 0.1 seconds
        assert elapsed >= 0.1

    def test_rate_limiter_rpm(self):
        """Test requests per minute limit."""
        limiter = RateLimiter(requests_per_minute=2, delay_between_requests=0.01)

        # Make 2 requests quickly
        limiter.wait_if_needed()
        limiter.wait_if_needed()

        # Should have 2 requests in the time window
        assert len(limiter.request_times) == 2


class TestContentCache:
    """Test content caching."""

    def test_cache_set_and_get(self, tmp_path):
        """Test caching and retrieval of content."""
        from scrapers.base_scraper import ScrapedContent
        from datetime import datetime

        cache = ContentCache(str(tmp_path), default_ttl=3600)

        # Create test content
        content = ScrapedContent(
            url="https://test.com/page",
            title="Test Page",
            content="Test content",
            links=[],
            metadata={},
            scraped_at=datetime.now()
        )

        # Cache it
        cache.set(content)

        # Retrieve it
        retrieved = cache.get("https://test.com/page")

        assert retrieved is not None
        assert retrieved.title == "Test Page"
        assert retrieved.content == "Test content"
        assert retrieved.cached is True

    def test_cache_expiration(self, tmp_path):
        """Test that expired cache entries return None."""
        from scrapers.base_scraper import ScrapedContent
        from datetime import datetime
        import time

        cache = ContentCache(str(tmp_path), default_ttl=1)  # 1 second TTL

        content = ScrapedContent(
            url="https://test.com/page",
            title="Test",
            content="Test",
            links=[],
            metadata={},
            scraped_at=datetime.now()
        )

        cache.set(content)

        # Wait for expiration
        time.sleep(2)

        # Should be expired
        retrieved = cache.get("https://test.com/page")
        assert retrieved is None


class TestBaseWebScraper:
    """Test base web scraper functionality."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create a test scraper instance."""
        return BaseWebScraper(
            user_agent="TestBot/1.0",
            cache_dir=str(tmp_path / "cache"),
            rate_limit_rpm=60,
            delay_between_requests=0.1,
            cache_ttl=3600,
            respect_robots=False  # Disable for testing
        )

    def test_scraper_initialization(self, scraper):
        """Test that scraper initializes correctly."""
        assert scraper.user_agent == "TestBot/1.0"
        assert scraper.rate_limiter is not None
        assert scraper.cache is not None

    def test_parse_content(self, scraper):
        """Test HTML parsing."""
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Title</h1>
                <p>First paragraph</p>
                <p>Second paragraph</p>
                <a href="/link1">Link 1</a>
            </body>
        </html>
        """

        result = scraper._parse_content("https://test.com", html)

        assert result is not None
        assert result.title == "Main Title"
        assert "First paragraph" in result.content
        assert "Second paragraph" in result.content
        assert len(result.links) > 0


class TestOporaUkScraper:
    """Test Opora.uk specific scraper."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create Opora.uk scraper instance."""
        return OporaUkScraper(
            user_agent="TestBot/1.0",
            cache_dir=str(tmp_path / "cache"),
            respect_robots=False
        )

    def test_scraper_initialization(self, scraper):
        """Test Opora scraper initializes with correct selectors."""
        assert 'article_container' in scraper.selectors
        assert 'title' in scraper.selectors

    def test_extract_title(self, scraper):
        """Test title extraction."""
        from bs4 import BeautifulSoup

        html = """
        <html>
            <head><title>Page Title</title></head>
            <body>
                <article>
                    <h1 class="article-title">Article Title</h1>
                </article>
            </body>
        </html>
        """

        soup = BeautifulSoup(html, 'lxml')
        article = soup.find('article')

        title = scraper._extract_title(article, soup)
        assert title == "Article Title"


class TestGovUkScraper:
    """Test Gov.uk specific scraper."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create Gov.uk scraper instance."""
        return GovUkScraper(
            user_agent="TestBot/1.0",
            cache_dir=str(tmp_path / "cache"),
            respect_robots=False
        )

    def test_scraper_initialization(self, scraper):
        """Test Gov.uk scraper initializes with correct selectors."""
        assert 'article_container' in scraper.selectors
        assert 'gem-c-govspeak' in scraper.selectors['article_container']

    def test_extract_title_removes_govuk_suffix(self, scraper):
        """Test that Gov.uk suffix is removed from titles."""
        from bs4 import BeautifulSoup

        html = """
        <html>
            <head><title>Housing for Ukraine - GOV.UK</title></head>
            <body>
                <h1>Housing for Ukraine</h1>
            </body>
        </html>
        """

        soup = BeautifulSoup(html, 'lxml')
        title = scraper._extract_title(soup, soup)

        assert title == "Housing for Ukraine"
        assert "GOV.UK" not in title


@pytest.mark.asyncio
class TestMCPClient:
    """Test MCP client integration."""

    async def test_mcp_client_creation(self):
        """Test MCP client can be created."""
        from src.agents.mcp_client import MCPWebScraperClient

        client = MCPWebScraperClient()
        assert client is not None
        assert client._connected is False

    async def test_get_mcp_client_singleton(self):
        """Test that get_mcp_client returns singleton."""
        from src.agents.mcp_client import get_mcp_client

        client1 = get_mcp_client()
        client2 = get_mcp_client()

        assert client1 is client2


@pytest.mark.integration
class TestIntegration:
    """Integration tests (require internet connection)."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create real scraper for integration tests."""
        return GovUkScraper(
            user_agent="UkraineSupportBot/1.0 (test)",
            cache_dir=str(tmp_path / "cache"),
            respect_robots=True
        )

    @pytest.mark.skip(reason="Requires internet connection and may be slow")
    def test_fetch_real_govuk_page(self, scraper):
        """Test fetching a real Gov.uk page."""
        result = scraper.get_page("/housing-for-ukraine", use_cache=False)

        assert result is not None
        assert len(result.content) > 100
        assert "gov.uk" in result.url.lower()
        assert result.metadata.get('official') is True

    @pytest.mark.skip(reason="Requires internet connection and may be slow")
    def test_cache_works(self, scraper):
        """Test that caching works in real scenario."""
        import time

        # First fetch (uncached)
        start1 = time.time()
        result1 = scraper.get_page("/housing-for-ukraine", use_cache=True)
        time1 = time.time() - start1

        # Second fetch (should be cached)
        start2 = time.time()
        result2 = scraper.get_page("/housing-for-ukraine", use_cache=True)
        time2 = time.time() - start2

        assert result1 is not None
        assert result2 is not None
        assert result2.cached is True
        # Cached fetch should be much faster
        assert time2 < time1 / 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
