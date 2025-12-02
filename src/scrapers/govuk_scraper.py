"""Gov.uk scraper for Ukraine support content."""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.logger import get_logger

logger = get_logger()


class GovUkScraper(BaseScraper):
    """Scraper for gov.uk Ukraine-related content."""

    def __init__(self):
        """Initialize gov.uk scraper."""
        super().__init__()
        self.base_url = self.settings.scraper_gov_uk_base

        # Key Ukraine-related pages on gov.uk
        self.ukraine_pages = [
            "/guidance/homes-for-ukraine-scheme-frequently-asked-questions",
            "/guidance/apply-for-a-ukraine-family-scheme-visa",
            "/guidance/support-for-family-members-of-british-nationals-in-ukraine-and-ukrainian-nationals-in-ukraine-and-the-uk",
            "/guidance/homes-for-ukraine-sponsorship-scheme-visa-holders",
            "/government/publications/homes-for-ukraine-sponsor-guidance",
            "/guidance/ukraine-sponsorship-scheme",
            "/guidance/homes-for-ukraine-scheme-visa-holder-guidance",
            "/guidance/homes-for-ukraine-scheme-sponsor-guidance",
            "/apply-to-come-to-the-uk-if-youre-from-ukraine",
            "/government/publications/ukraine-family-scheme-application-form",
            "/guidance/get-help-with-the-cost-of-living",
        ]

    def get_entry_urls(self) -> List[str]:
        """
        Get list of Ukraine-related gov.uk pages to scrape.

        Returns:
            List of full URLs
        """
        urls = [f"{self.base_url}{page}" for page in self.ukraine_pages]

        logger.info(f"Prepared {len(urls)} gov.uk URLs for scraping")
        return urls

    def extract_content(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract content from a gov.uk page.

        Args:
            soup: BeautifulSoup parsed HTML
            url: Source URL

        Returns:
            Dictionary with text, metadata, and topic
        """
        try:
            # Get metadata
            metadata = self.get_metadata_from_soup(soup, url)
            metadata["source"] = "gov.uk"
            metadata["document_type"] = "scraped"

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
        Extract main content from gov.uk page.

        Gov.uk uses specific HTML structure for content.

        Args:
            soup: BeautifulSoup object

        Returns:
            Extracted text
        """
        content_parts = []

        # Method 1: Try to find main content div (common in gov.uk pages)
        main_content = soup.find('div', class_='govuk-grid-column-two-thirds')
        if main_content:
            # Remove navigation and non-content elements
            for element in main_content.find_all(['nav', 'aside', 'footer']):
                element.decompose()

            content_parts.append(main_content.get_text())

        # Method 2: Try article tag
        if not content_parts:
            article = soup.find('article')
            if article:
                content_parts.append(article.get_text())

        # Method 3: Try main content area
        if not content_parts:
            main = soup.find('main')
            if main:
                # Remove scripts, styles, navigation
                for element in main.find_all(['script', 'style', 'nav', 'aside', 'footer']):
                    element.decompose()

                content_parts.append(main.get_text())

        # Method 4: Fallback to body
        if not content_parts:
            body = soup.find('body')
            if body:
                # Remove header, footer, nav
                for element in body.find_all(['header', 'footer', 'nav', 'script', 'style']):
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

        if 'visa' in url_lower or 'family-scheme' in url_lower:
            return 'visa'
        elif 'homes-for-ukraine' in url_lower or 'sponsor' in url_lower:
            return 'housing'
        elif 'cost-of-living' in url_lower or 'support' in url_lower:
            return 'benefits'
        elif 'work' in url_lower or 'employment' in url_lower:
            return 'work'
        else:
            return 'general'

    def scrape_ukraine_homepage(self) -> Optional[List[str]]:
        """
        Scrape the main Ukraine page to find additional relevant links.

        Returns:
            List of discovered URLs or None if failed
        """
        ukraine_home = f"{self.base_url}/guidance/support-for-family-members-of-british-nationals-in-ukraine-and-ukrainian-nationals-in-ukraine-and-the-uk"

        logger.info(f"Scraping Ukraine homepage for additional links: {ukraine_home}")

        html = self.fetch_url(ukraine_home)
        if not html:
            return None

        soup = self.parse_html(html)
        if not soup:
            return None

        # Find all Ukraine-related links
        def is_ukraine_link(url):
            url_lower = url.lower()
            ukraine_keywords = ['ukraine', 'sponsor', 'refugee', 'asylum']
            return any(keyword in url_lower for keyword in ukraine_keywords)

        links = self.extract_links(soup, ukraine_home, filter_fn=is_ukraine_link)

        logger.info(f"Found {len(links)} Ukraine-related links")

        return links


def scrape_govuk() -> List[Dict[str, Any]]:
    """
    Convenience function to scrape gov.uk content.

    Returns:
        List of scraped documents
    """
    scraper = GovUkScraper()
    return scraper.scrape_all()