"""Gov.uk specific web scraper."""

from typing import Optional, Dict, Any, List
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseWebScraper, ScrapedContent


class GovUkScraper(BaseWebScraper):
    """Scraper specifically designed for Gov.uk content."""

    def __init__(
        self,
        user_agent: str,
        cache_dir: str,
        base_url: str = "https://www.gov.uk",
        selectors: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize Gov.uk scraper.

        Args:
            user_agent: User agent string
            cache_dir: Cache directory
            base_url: Base URL for Gov.uk (default: https://www.gov.uk)
            selectors: Custom CSS selectors for content extraction
            **kwargs: Additional arguments for BaseWebScraper
        """
        super().__init__(user_agent, cache_dir, **kwargs)

        # Store base URL (can be configured)
        self.base_url = base_url

        # Gov.uk specific selectors
        self.selectors = selectors or {
            'article_container': '.gem-c-govspeak, article, main',
            'title': 'h1, .gem-c-title__text, .govuk-heading-xl',
            'content': '.gem-c-govspeak p, article p, main p, .govuk-body',
            'links': '.gem-c-govspeak a, article a, main a',
            'published': '.gem-c-published-dates, .app-c-published-dates'
        }

    def _parse_content(self, url: str, html: str) -> Optional[ScrapedContent]:
        """
        Parse Gov.uk HTML content with specific selectors.

        Args:
            url: Source URL
            html: HTML content

        Returns:
            ScrapedContent or None
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove unwanted elements specific to Gov.uk
            for tag in soup([
                'script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe',
                'form',  # Forms usually not relevant for content
                '.gem-c-skip-link',  # Skip links
                '.govuk-breadcrumbs',  # Breadcrumbs
                '.gem-c-related-navigation',  # Related navigation
                '.gem-c-feedback',  # Feedback forms
            ]):
                tag.decompose()

            # Find main content container
            article = None
            for selector in self.selectors['article_container'].split(', '):
                article = soup.select_one(selector)
                if article:
                    logger.debug(f"Found article container with selector: {selector}")
                    break

            if not article:
                logger.warning(f"No article container found on {url}")
                # Fallback to main or body
                article = soup.find('main') or soup.find('body') or soup

            # Extract title
            title_text = self._extract_title(article, soup)

            # Extract main content
            content = self._extract_content(article)

            # Validate content length
            if len(content) < 50:
                logger.warning(f"Content too short ({len(content)} chars) from {url}")

            # Extract links
            links = self._extract_links(article, url)

            # Extract publication/update date
            pub_date = self._extract_date(soup)

            # Extract metadata
            metadata = {
                'num_paragraphs': len(article.find_all('p')) if article else 0,
                'num_links': len(links),
                'content_length': len(content),
                'publication_date': pub_date.isoformat() if pub_date else None,
                'source': 'gov.uk',
                'official': True  # Gov.uk is official government source
            }

            return ScrapedContent(
                url=url,
                title=title_text,
                content=content,
                links=links,
                metadata=metadata,
                scraped_at=datetime.now(),
                cached=False
            )

        except Exception as e:
            logger.error(f"Error parsing Gov.uk content from {url}: {e}")
            return None

    def _extract_title(self, article, soup) -> str:
        """Extract title from Gov.uk page."""
        # Try Gov.uk specific selectors first
        for selector in self.selectors['title'].split(', '):
            title = soup.select_one(selector)  # Search whole page for title
            if title:
                title_text = title.get_text(strip=True)
                if title_text:
                    return title_text

        # Fallback to <title> tag and clean it
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove common Gov.uk suffixes
            title_text = title_text.replace(' - GOV.UK', '')
            return title_text

        return "Untitled"

    def _extract_content(self, article) -> str:
        """Extract main text content from Gov.uk article."""
        paragraphs = []

        # Try Gov.uk specific content selectors
        for selector in self.selectors['content'].split(', '):
            elements = article.select(selector)
            if elements:
                paragraphs = elements
                logger.debug(f"Found {len(elements)} paragraphs with selector: {selector}")
                break

        # Fallback to all paragraphs
        if not paragraphs:
            paragraphs = article.find_all('p')

        # Extract text from paragraphs
        content_parts = []
        for p in paragraphs:
            text = p.get_text(strip=True)

            # Filter out very short paragraphs and common Gov.uk boilerplate
            if len(text) < 20:
                continue

            # Skip common boilerplate text
            skip_phrases = [
                'print this page',
                'is this page useful',
                'report a problem',
                'cookies on gov.uk'
            ]
            if any(phrase in text.lower() for phrase in skip_phrases):
                continue

            content_parts.append(text)

        # Also extract list items (Gov.uk uses lots of lists for steps/requirements)
        lists = article.find_all(['ul', 'ol'])
        for lst in lists:
            list_items = []
            for li in lst.find_all('li', recursive=False):
                li_text = li.get_text(strip=True)
                if li_text and len(li_text) > 10:
                    list_items.append(f"• {li_text}")

            if list_items:
                content_parts.append('\n'.join(list_items))

        return '\n\n'.join(content_parts)

    def _extract_links(self, article, base_url: str) -> List[Dict[str, str]]:
        """Extract relevant links from Gov.uk article."""
        links = []
        seen_urls = set()

        # Find all links in article
        for link in article.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            link_href = link['href']

            # Skip empty links
            if not link_text or not link_href:
                continue

            # Convert relative URLs to absolute (Gov.uk uses relative URLs)
            if link_href.startswith('/'):
                link_href = f"https://www.gov.uk{link_href}"

            # Skip duplicates
            if link_href in seen_urls:
                continue

            # Skip navigation/utility links
            skip_patterns = [
                '#', 'javascript:', 'mailto:', 'tel:',
                '/help/', '/contact', '/feedback',
                'facebook.com', 'twitter.com', 'youtube.com'
            ]
            if any(pattern in link_href.lower() for pattern in skip_patterns):
                continue

            # Prioritize gov.uk links
            is_govuk = 'gov.uk' in link_href.lower()

            links.append({
                'text': link_text,
                'href': link_href,
                'is_govuk': is_govuk
            })
            seen_urls.add(link_href)

        # Sort: gov.uk links first
        links.sort(key=lambda x: (not x.get('is_govuk', False), x['text']))

        return links

    def _extract_date(self, soup) -> Optional[datetime]:
        """Extract publication/update date from Gov.uk page."""
        try:
            # Gov.uk uses specific date components
            date_container = soup.select_one(self.selectors['published'])

            if date_container:
                # Look for datetime attribute
                time_elem = date_container.find('time', attrs={'datetime': True})
                if time_elem:
                    date_str = time_elem['datetime']
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

                # Fallback to parsing text
                date_text = date_container.get_text(strip=True)
                if date_text:
                    # Try to extract date from text like "Published 12 March 2024"
                    from dateutil import parser
                    try:
                        return parser.parse(date_text)
                    except Exception:
                        pass

            # Look for any time element with datetime
            for time_elem in soup.find_all('time', attrs={'datetime': True}):
                try:
                    date_str = time_elem['datetime']
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Could not extract date: {e}")

        return None

    def get_page(
        self,
        path: str,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> Optional[ScrapedContent]:
        """
        Get specific Gov.uk page.

        Args:
            path: Page path (e.g., '/housing-for-ukraine')
            use_cache: Whether to use cache
            cache_ttl: Cache TTL override

        Returns:
            ScrapedContent or None
        """
        # Construct full URL using configured base URL
        if path.startswith('http'):
            url = path
        else:
            url = f"{self.base_url}{path}" if path.startswith('/') else f"{self.base_url}/{path}"

        logger.info(f"Fetching Gov.uk page: {url}")

        return self.fetch(url, use_cache=use_cache, cache_ttl=cache_ttl)

    def get_housing_info(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[ScrapedContent]:
        """
        Get housing information from Gov.uk.

        Args:
            topic: Specific housing topic path
            use_cache: Whether to use cache

        Returns:
            ScrapedContent or None
        """
        if topic:
            # If topic is a full path, use it directly
            if topic.startswith('/'):
                path = topic
            else:
                # Common Gov.uk housing paths
                housing_paths = {
                    'ukraine': '/housing-for-ukraine',
                    'council': '/council-housing',
                    'renting': '/private-renting',
                    'benefit': '/housing-benefit',
                    'homeless': '/homelessness'
                }
                path = housing_paths.get(topic.lower(), f'/housing/{topic}')
        else:
            path = '/housing-for-ukraine'  # Default to Ukraine housing scheme

        return self.get_page(path, use_cache=use_cache)

    def get_nhs_info(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[ScrapedContent]:
        """
        Get NHS/healthcare information from Gov.uk.

        Args:
            topic: Specific NHS topic
            use_cache: Whether to use cache

        Returns:
            ScrapedContent or None
        """
        if topic:
            if topic.startswith('/'):
                path = topic
            else:
                nhs_paths = {
                    'gp': '/register-with-a-gp',
                    'services': '/nhs-services',
                    'emergency': '/emergency-medical-treatment'
                }
                path = nhs_paths.get(topic.lower(), f'/nhs/{topic}')
        else:
            path = '/nhs-services'

        return self.get_page(path, use_cache=use_cache)

    def search_ukraine_scheme(
        self,
        query: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[ScrapedContent]:
        """
        Get information about Homes for Ukraine scheme.

        Args:
            query: Optional specific query
            use_cache: Whether to use cache

        Returns:
            ScrapedContent or None
        """
        # Main Ukraine scheme page
        return self.get_page('/housing-for-ukraine', use_cache=use_cache)
