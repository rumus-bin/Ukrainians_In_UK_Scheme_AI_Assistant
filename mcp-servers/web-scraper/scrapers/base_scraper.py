"""Base web scraper with safety features (robots.txt, rate limiting, caching)."""

import time
import hashlib
import urllib.robotparser
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

import requests
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class ScrapedContent:
    """Scraped content container."""
    url: str
    title: str
    content: str
    links: List[Dict[str, str]]
    metadata: Dict[str, Any]
    scraped_at: datetime
    cached: bool = False


class RobotsChecker:
    """Check robots.txt compliance."""

    def __init__(self, cache_ttl: int = 86400):
        """
        Initialize robots.txt checker.

        Args:
            cache_ttl: Cache TTL in seconds (default: 24 hours)
        """
        self.cache: Dict[str, tuple[urllib.robotparser.RobotFileParser, datetime]] = {}
        self.cache_ttl = timedelta(seconds=cache_ttl)

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check
            user_agent: User agent string

        Returns:
            True if allowed to fetch, False otherwise
        """
        try:
            # Extract base URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = f"{base_url}/robots.txt"

            # Check cache
            now = datetime.now()
            if base_url in self.cache:
                rp, cached_at = self.cache[base_url]
                if now - cached_at < self.cache_ttl:
                    return rp.can_fetch(user_agent, url)

            # Fetch and parse robots.txt
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)

            try:
                rp.read()
                self.cache[base_url] = (rp, now)
                return rp.can_fetch(user_agent, url)
            except Exception as e:
                logger.warning(f"Could not fetch robots.txt for {base_url}: {e}")
                # If can't fetch robots.txt, assume allowed
                return True

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # On error, assume allowed
            return True


class RateLimiter:
    """Rate limiter for web requests."""

    def __init__(self, requests_per_minute: int = 10, delay_between_requests: float = 2.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            delay_between_requests: Minimum delay between requests in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.delay = delay_between_requests
        self.last_request_time: Optional[float] = None
        self.request_times: List[float] = []

    def wait_if_needed(self):
        """Wait if necessary to comply with rate limits."""
        now = time.time()

        # Enforce minimum delay between requests
        if self.last_request_time:
            time_since_last = now - self.last_request_time
            if time_since_last < self.delay:
                sleep_time = self.delay - time_since_last
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                now = time.time()

        # Enforce requests per minute limit
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.requests_per_minute:
            # Wait until oldest request is 60s old
            oldest = self.request_times[0]
            sleep_time = 60 - (now - oldest)
            if sleep_time > 0:
                logger.debug(f"RPM limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                now = time.time()

        self.request_times.append(now)
        self.last_request_time = now


class ContentCache:
    """File-based cache for scraped content."""

    def __init__(self, cache_dir: str, default_ttl: int = 86400):
        """
        Initialize content cache.

        Args:
            cache_dir: Directory for cache storage
            default_ttl: Default TTL in seconds (default: 24 hours)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, url: str, ttl: Optional[int] = None) -> Optional[ScrapedContent]:
        """
        Get cached content if available and not expired.

        Args:
            url: URL to get from cache
            ttl: TTL in seconds (uses default if not specified)

        Returns:
            ScrapedContent if cached and fresh, None otherwise
        """
        try:
            cache_key = self._get_cache_key(url)
            cache_path = self._get_cache_path(cache_key)

            if not cache_path.exists():
                return None

            # Check if expired
            ttl = ttl or self.default_ttl
            file_age = time.time() - cache_path.stat().st_mtime
            if file_age > ttl:
                logger.debug(f"Cache expired for {url} (age: {file_age:.0f}s)")
                return None

            # Load from cache
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Cache hit for {url}")

            return ScrapedContent(
                url=data['url'],
                title=data['title'],
                content=data['content'],
                links=data['links'],
                metadata=data['metadata'],
                scraped_at=datetime.fromisoformat(data['scraped_at']),
                cached=True
            )

        except Exception as e:
            logger.error(f"Error reading cache for {url}: {e}")
            return None

    def set(self, content: ScrapedContent):
        """
        Store content in cache.

        Args:
            content: Content to cache
        """
        try:
            cache_key = self._get_cache_key(content.url)
            cache_path = self._get_cache_path(cache_key)

            data = {
                'url': content.url,
                'title': content.title,
                'content': content.content,
                'links': content.links,
                'metadata': content.metadata,
                'scraped_at': content.scraped_at.isoformat()
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Cached content for {content.url}")

        except Exception as e:
            logger.error(f"Error writing cache for {content.url}: {e}")

    def clear_expired(self, ttl: Optional[int] = None):
        """
        Clear expired cache entries.

        Args:
            ttl: TTL in seconds (uses default if not specified)
        """
        ttl = ttl or self.default_ttl
        now = time.time()
        cleared = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                file_age = now - cache_file.stat().st_mtime
                if file_age > ttl:
                    cache_file.unlink()
                    cleared += 1
            except Exception as e:
                logger.error(f"Error clearing cache file {cache_file}: {e}")

        if cleared > 0:
            logger.info(f"Cleared {cleared} expired cache entries")


class BaseWebScraper:
    """Base web scraper with safety features."""

    def __init__(
        self,
        user_agent: str,
        cache_dir: str,
        rate_limit_rpm: int = 10,
        delay_between_requests: float = 2.0,
        cache_ttl: int = 86400,
        timeout: tuple = (10, 30),
        max_retries: int = 3,
        respect_robots: bool = True
    ):
        """
        Initialize base web scraper.

        Args:
            user_agent: User agent string
            cache_dir: Cache directory path
            rate_limit_rpm: Requests per minute limit
            delay_between_requests: Minimum delay between requests
            cache_ttl: Cache TTL in seconds
            timeout: (connect_timeout, read_timeout) in seconds
            max_retries: Maximum retry attempts
            respect_robots: Whether to respect robots.txt
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.respect_robots = respect_robots

        # Initialize components
        self.rate_limiter = RateLimiter(rate_limit_rpm, delay_between_requests)
        self.cache = ContentCache(cache_dir, cache_ttl)
        self.robots_checker = RobotsChecker() if respect_robots else None

        # Session setup
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'uk,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        logger.info("BaseWebScraper initialized")

    def fetch(
        self,
        url: str,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> Optional[ScrapedContent]:
        """
        Fetch and parse content from URL.

        Args:
            url: URL to fetch
            use_cache: Whether to use cache
            cache_ttl: Cache TTL override

        Returns:
            ScrapedContent or None if failed
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(url, ttl=cache_ttl)
            if cached:
                return cached

        # Check robots.txt
        if self.robots_checker and not self.robots_checker.can_fetch(url, self.user_agent):
            logger.warning(f"robots.txt disallows fetching {url}")
            return None

        # Rate limit
        self.rate_limiter.wait_if_needed()

        # Fetch with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Fetching {url} (attempt {attempt}/{self.max_retries})")

                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()

                # Parse content
                content = self._parse_content(url, response.text)

                if content:
                    # Cache if enabled
                    if use_cache:
                        self.cache.set(content)

                    return content
                else:
                    logger.warning(f"Failed to parse content from {url}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt} failed for {url}: {e}")

                if attempt < self.max_retries:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {self.max_retries} attempts failed for {url}")
                    return None

        return None

    def _parse_content(self, url: str, html: str) -> Optional[ScrapedContent]:
        """
        Parse HTML content (to be implemented by subclasses).

        Args:
            url: Source URL
            html: HTML content

        Returns:
            ScrapedContent or None
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove unwanted tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            # Extract basic content
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else "Untitled"

            # Extract all paragraphs
            paragraphs = soup.find_all('p')
            content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                link_text = link.get_text(strip=True)
                link_href = link['href']
                if link_text and link_href:
                    links.append({
                        'text': link_text,
                        'href': link_href
                    })

            return ScrapedContent(
                url=url,
                title=title_text,
                content=content,
                links=links,
                metadata={
                    'num_paragraphs': len(paragraphs),
                    'num_links': len(links),
                    'content_length': len(content)
                },
                scraped_at=datetime.now(),
                cached=False
            )

        except Exception as e:
            logger.error(f"Error parsing content from {url}: {e}")
            return None

    def clear_cache(self):
        """Clear expired cache entries."""
        self.cache.clear_expired()
