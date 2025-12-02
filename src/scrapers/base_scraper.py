"""Base scraper class with common functionality."""

import time
import requests
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class BaseScraper(ABC):
    """Base class for web scrapers with common functionality."""

    def __init__(self):
        """Initialize the scraper."""
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.settings.scraper_user_agent
        })
        self.delay = self.settings.scraper_request_delay_seconds
        self.max_retries = self.settings.scraper_max_retries

    @abstractmethod
    def get_entry_urls(self) -> List[str]:
        """
        Get list of entry point URLs to scrape.

        Returns:
            List of URLs to scrape
        """
        pass

    @abstractmethod
    def extract_content(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract content from a BeautifulSoup object.

        Args:
            soup: BeautifulSoup parsed HTML
            url: Source URL

        Returns:
            Dictionary with extracted content or None if extraction failed
        """
        pass

    def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching URL: {url} (attempt {attempt + 1}/{self.max_retries})")

                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
                return response.text

            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to fetch {url}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached for {url}")
                    return None

        return None

    def parse_html(self, html: str) -> Optional[BeautifulSoup]:
        """
        Parse HTML content to BeautifulSoup object.

        Args:
            html: HTML string

        Returns:
            BeautifulSoup object or None if parsing failed
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            return soup
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return None

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]  # Remove empty lines

        # Join with single newline
        cleaned = '\n'.join(lines)

        return cleaned.strip()

    def is_valid_url(self, url: str, base_domain: str) -> bool:
        """
        Check if URL is valid and belongs to the base domain.

        Args:
            url: URL to check
            base_domain: Base domain (e.g., 'gov.uk')

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            return base_domain in parsed.netloc
        except Exception:
            return False

    def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single URL.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with scraped content or None if failed
        """
        # Respect rate limit
        time.sleep(self.delay)

        # Fetch HTML
        html = self.fetch_url(url)
        if not html:
            return None

        # Parse HTML
        soup = self.parse_html(html)
        if not soup:
            return None

        # Extract content
        content = self.extract_content(soup, url)

        return content

    def scrape_all(self) -> List[Dict[str, Any]]:
        """
        Scrape all entry URLs.

        Returns:
            List of scraped documents
        """
        logger.info(f"Starting scrape for {self.__class__.__name__}")

        urls = self.get_entry_urls()
        logger.info(f"Found {len(urls)} URLs to scrape")

        documents = []

        for idx, url in enumerate(urls, 1):
            logger.info(f"Scraping URL {idx}/{len(urls)}: {url}")

            try:
                content = self.scrape_url(url)

                if content:
                    documents.append(content)
                    logger.info(f"Successfully scraped {url}")
                else:
                    logger.warning(f"No content extracted from {url}")

            except Exception as e:
                logger.exception(f"Error scraping {url}: {e}")
                continue

        logger.info(f"Scraping complete. Collected {len(documents)} documents")

        return documents

    def extract_links(self, soup: BeautifulSoup, base_url: str, filter_fn=None) -> List[str]:
        """
        Extract links from a page.

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            filter_fn: Optional function to filter links

        Returns:
            List of absolute URLs
        """
        links = []

        for anchor in soup.find_all('a', href=True):
            href = anchor['href']

            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)

            # Apply filter if provided
            if filter_fn and not filter_fn(absolute_url):
                continue

            links.append(absolute_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        return unique_links

    def get_metadata_from_soup(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML.

        Args:
            soup: BeautifulSoup object
            url: Source URL

        Returns:
            Dictionary with metadata
        """
        metadata = {
            "source_url": url,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Try to get title
        title_tag = soup.find('title')
        if title_tag:
            metadata["title"] = self.clean_text(title_tag.get_text())

        # Try to get meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata["description"] = meta_desc['content']

        # Try to get language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata["language"] = html_tag['lang']

        return metadata