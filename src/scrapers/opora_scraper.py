"""Opora.uk scraper for Ukrainian support content."""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.logger import get_logger

logger = get_logger()


class OporaUkScraper(BaseScraper):
    """Scraper for opora.uk Ukrainian support content."""

    def __init__(self):
        """Initialize opora.uk scraper."""
        super().__init__()
        self.base_url = self.settings.scraper_opora_uk_base

        # Key sections on opora.uk (these may need to be updated based on actual site structure)
        # Opora.uk provides information about life in UK for Ukrainians
        self.opora_pages = [
            "/",  # Homepage
            "/uk",  # Ukrainian version
            "/housing",  # Housing information
            "/work",  # Work and employment
            "/education",  # Education
            "/healthcare",  # Healthcare/NHS
            "/legal",  # Legal support
            "/benefits",  # Benefits and support
            "/visa",  # Visa information
            "/community",  # Community support
        ]

    def get_entry_urls(self) -> List[str]:
        """
        Get list of opora.uk pages to scrape.

        Returns:
            List of full URLs
        """
        urls = [f"{self.base_url}{page}" for page in self.opora_pages]

        logger.info(f"Prepared {len(urls)} opora.uk URLs for scraping")
        return urls

    def extract_content(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract content from an opora.uk page.

        Args:
            soup: BeautifulSoup parsed HTML
            url: Source URL

        Returns:
            Dictionary with text, metadata, and topic
        """
        try:
            # Get metadata
            metadata = self.get_metadata_from_soup(soup, url)
            metadata["source"] = "opora.uk"
            metadata["document_type"] = "scraped"
            metadata["language"] = "uk"  # Content is in Ukrainian

            # Determine topic based on URL
            topic = self._determine_topic(url)
            metadata["topic"] = topic

            # Extract main content
            text = self._extract_main_content(soup)

            if not text:
                logger.warning(f"No content found for {url}")
                return None

            # Clean the text
            cleaned_text = self.clean_text(text)

            if len(cleaned_text) < 100:
                logger.warning(f"Content too short for {url}: {len(cleaned_text)} chars")
                return None

            return {
                "text": cleaned_text,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main content from opora.uk page.

        Note: This is a generic implementation. May need adjustment based on
        actual opora.uk HTML structure.

        Args:
            soup: BeautifulSoup object

        Returns:
            Extracted text
        """
        content_parts = []

        # Method 1: Try common content containers
        content_selectors = [
            {'class': 'content'},
            {'class': 'main-content'},
            {'class': 'article-content'},
            {'class': 'post-content'},
            {'id': 'content'},
            {'id': 'main-content'},
        ]

        for selector in content_selectors:
            content_div = soup.find('div', selector)
            if content_div:
                # Remove navigation and non-content elements
                for element in content_div.find_all(['nav', 'aside', 'footer', 'script', 'style']):
                    element.decompose()

                content_parts.append(content_div.get_text())
                break

        # Method 2: Try article tag
        if not content_parts:
            article = soup.find('article')
            if article:
                for element in article.find_all(['script', 'style', 'nav']):
                    element.decompose()
                content_parts.append(article.get_text())

        # Method 3: Try main tag
        if not content_parts:
            main = soup.find('main')
            if main:
                for element in main.find_all(['script', 'style', 'nav', 'aside', 'footer']):
                    element.decompose()
                content_parts.append(main.get_text())

        # Method 4: Look for Ukrainian text paragraphs (fallback)
        if not content_parts:
            paragraphs = soup.find_all('p')
            # Filter paragraphs that likely contain Ukrainian content
            ukrainian_text = []
            for p in paragraphs:
                text = p.get_text().strip()
                # Ukrainian text detection (presence of Ukrainian-specific letters)
                if any(char in text for char in 'іїєґІЇЄҐ') and len(text) > 50:
                    ukrainian_text.append(text)

            if ukrainian_text:
                content_parts.append('\n\n'.join(ukrainian_text))

        # Method 5: Fallback to body (last resort)
        if not content_parts:
            body = soup.find('body')
            if body:
                for element in body.find_all(['header', 'footer', 'nav', 'script', 'style', 'aside']):
                    element.decompose()
                content_parts.append(body.get_text())

        # Combine all parts
        full_text = '\n\n'.join(content_parts)

        return full_text

    def _determine_topic(self, url: str) -> str:
        """
        Determine topic based on URL.

        Args:
            url: Page URL

        Returns:
            Topic string
        """
        url_lower = url.lower()

        if 'visa' in url_lower or 'імміграц' in url_lower:
            return 'visa'
        elif 'housing' in url_lower or 'житл' in url_lower:
            return 'housing'
        elif 'work' in url_lower or 'робот' in url_lower or 'employment' in url_lower:
            return 'work'
        elif 'benefits' in url_lower or 'допомог' in url_lower:
            return 'benefits'
        elif 'healthcare' in url_lower or 'nhs' in url_lower or 'здоров' in url_lower:
            return 'healthcare'
        elif 'education' in url_lower or 'освіт' in url_lower or 'school' in url_lower:
            return 'education'
        elif 'legal' in url_lower or 'юридич' in url_lower:
            return 'legal'
        else:
            return 'general'

    def discover_additional_pages(self) -> List[str]:
        """
        Discover additional relevant pages from the homepage.

        Returns:
            List of discovered URLs
        """
        logger.info(f"Discovering additional pages from {self.base_url}")

        html = self.fetch_url(self.base_url)
        if not html:
            return []

        soup = self.parse_html(html)
        if not soup:
            return []

        # Extract all internal links
        def is_internal_link(url):
            return self.is_valid_url(url, 'opora.uk')

        links = self.extract_links(soup, self.base_url, filter_fn=is_internal_link)

        # Filter for content pages (exclude admin, login, etc.)
        content_links = []
        exclude_patterns = ['login', 'admin', 'wp-', 'feed', 'comment', 'tag', 'author']

        for link in links:
            if not any(pattern in link.lower() for pattern in exclude_patterns):
                content_links.append(link)

        logger.info(f"Discovered {len(content_links)} additional pages")

        return content_links


def scrape_opora() -> List[Dict[str, Any]]:
    """
    Convenience function to scrape opora.uk content.

    Returns:
        List of scraped documents
    """
    scraper = OporaUkScraper()
    return scraper.scrape_all()