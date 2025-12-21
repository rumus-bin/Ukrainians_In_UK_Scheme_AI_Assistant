"""Opora.uk specific web scraper."""

from typing import Optional, Dict, Any, List
from datetime import datetime
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseWebScraper, ScrapedContent


class OporaUkScraper(BaseWebScraper):
    """Scraper specifically designed for Opora.uk content."""

    def __init__(
        self,
        user_agent: str,
        cache_dir: str,
        base_url: str = "https://opora.uk",
        selectors: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize Opora.uk scraper.

        Args:
            user_agent: User agent string
            cache_dir: Cache directory
            base_url: Base URL for Opora.uk (default: https://opora.uk)
            selectors: Custom CSS selectors for content extraction
            **kwargs: Additional arguments for BaseWebScraper
        """
        super().__init__(user_agent, cache_dir, **kwargs)

        # Store base URL (can be configured)
        self.base_url = base_url

        # Default selectors for Opora.uk
        self.selectors = selectors or {
            'article_container': 'article, .article-content, .post-content, .entry-content',
            'title': 'h1, .article-title, .entry-title, .post-title',
            'content': 'article p, .article-content p, .post-content p, .entry-content p',
            'links': 'article a, .article-content a, .post-content a',
            'date': 'time, .published-date, .article-date, .entry-date'
        }

    def _parse_content(self, url: str, html: str) -> Optional[ScrapedContent]:
        """
        Parse Opora.uk HTML content with specific selectors.

        Args:
            url: Source URL
            html: HTML content

        Returns:
            ScrapedContent or None
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove unwanted tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                tag.decompose()

            # Find article container
            article = None
            for selector in self.selectors['article_container'].split(', '):
                article = soup.select_one(selector)
                if article:
                    logger.debug(f"Found article container with selector: {selector}")
                    break

            if not article:
                logger.warning(f"No article container found on {url}")
                # Fallback to entire body
                article = soup.find('body') or soup

            # Extract title
            title_text = self._extract_title(article, soup)

            # Extract main content
            content = self._extract_content(article)

            # Validate content length
            if len(content) < 50:
                logger.warning(f"Content too short ({len(content)} chars) from {url}")
                # Don't return None, just log warning - some pages might be legitimately short

            # Extract links
            links = self._extract_links(article, url)

            # Extract publication date if available
            pub_date = self._extract_date(article)

            # Extract metadata
            metadata = {
                'num_paragraphs': len(article.find_all('p')) if article else 0,
                'num_links': len(links),
                'content_length': len(content),
                'publication_date': pub_date.isoformat() if pub_date else None,
                'source': 'opora.uk'
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
            logger.error(f"Error parsing Opora.uk content from {url}: {e}")
            return None

    def _extract_title(self, article, soup) -> str:
        """Extract title from article or page."""
        for selector in self.selectors['title'].split(', '):
            title = article.select_one(selector) or soup.select_one(selector)
            if title:
                title_text = title.get_text(strip=True)
                if title_text:
                    return title_text

        # Fallback to <title> tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)

        return "Untitled"

    def _extract_content(self, article) -> str:
        """Extract main text content from article."""
        paragraphs = []

        # Try structured content selectors first
        for selector in self.selectors['content'].split(', '):
            elements = article.select(selector)
            if elements:
                paragraphs = elements
                break

        # Fallback to all paragraphs in article
        if not paragraphs:
            paragraphs = article.find_all('p')

        # Extract text from paragraphs
        content_parts = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 20:  # Filter out very short paragraphs
                content_parts.append(text)

        return '\n\n'.join(content_parts)

    def _extract_links(self, article, base_url: str) -> List[Dict[str, str]]:
        """Extract relevant links from article."""
        links = []
        seen_urls = set()

        # Find all links in article
        for link in article.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            link_href = link['href']

            # Skip empty links
            if not link_text or not link_href:
                continue

            # Convert relative URLs to absolute
            if link_href.startswith('/'):
                from urllib.parse import urlparse
                parsed_base = urlparse(base_url)
                link_href = f"{parsed_base.scheme}://{parsed_base.netloc}{link_href}"

            # Skip duplicates
            if link_href in seen_urls:
                continue

            # Skip navigation/social media links
            skip_patterns = ['#', 'javascript:', 'mailto:', 'tel:', 'facebook.com', 'twitter.com', 'instagram.com']
            if any(pattern in link_href.lower() for pattern in skip_patterns):
                continue

            links.append({
                'text': link_text,
                'href': link_href
            })
            seen_urls.add(link_href)

        return links

    def _extract_date(self, article) -> Optional[datetime]:
        """Extract publication date from article."""
        try:
            for selector in self.selectors['date'].split(', '):
                date_elem = article.select_one(selector)
                if date_elem:
                    # Try to get datetime attribute first
                    if date_elem.has_attr('datetime'):
                        date_str = date_elem['datetime']
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))

                    # Try to parse text content
                    date_text = date_elem.get_text(strip=True)
                    if date_text:
                        # Try common date formats
                        # This is basic - you might want to add more sophisticated parsing
                        from dateutil import parser
                        try:
                            return parser.parse(date_text)
                        except Exception:
                            pass

        except Exception as e:
            logger.debug(f"Could not extract date: {e}")

        return None

    def search_section(
        self,
        section_path: str,
        query: Optional[str] = None,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> Optional[ScrapedContent]:
        """
        Search specific section of Opora.uk.

        Args:
            section_path: Section path (e.g., '/housing', '/housing/tenant-rights')
            query: Optional search query (for future search functionality)
            use_cache: Whether to use cache
            cache_ttl: Cache TTL override

        Returns:
            ScrapedContent or None
        """
        # Construct full URL using configured base URL
        url = f"{self.base_url}{section_path}"

        logger.info(f"Searching Opora.uk section: {url}")

        # Fetch and parse
        content = self.fetch(url, use_cache=use_cache, cache_ttl=cache_ttl)

        if content and query:
            # If query provided, could filter content here
            # For now, just return full content
            # Future: implement keyword highlighting or filtering
            pass

        return content

    def get_housing_info(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[ScrapedContent]:
        """
        Get housing information from Opora.uk.

        Args:
            topic: Specific housing topic (e.g., 'tenant-rights', 'social-housing')
            use_cache: Whether to use cache

        Returns:
            ScrapedContent or None
        """
        if topic:
            section_path = f"/housing/{topic}"
        else:
            section_path = "/housing"

        return self.search_section(section_path, use_cache=use_cache)

    def get_nhs_info(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[ScrapedContent]:
        """
        Get NHS/healthcare information from Opora.uk.

        Args:
            topic: Specific NHS topic (e.g., 'gp-registration')
            use_cache: Whether to use cache

        Returns:
            ScrapedContent or None
        """
        if topic:
            section_path = f"/nhs/{topic}"
        else:
            section_path = "/nhs"

        return self.search_section(section_path, use_cache=use_cache)

    def _find_next_page_link(self, content: ScrapedContent) -> Optional[str]:
        """
        Find the "Next page" link from scraped content.

        Args:
            content: ScrapedContent from current page

        Returns:
            URL of next page or None if no next page found
        """
        try:
            # Look through extracted links for pagination indicators
            for link in content.links:
                link_text = link['text'].lower()
                link_href = link['href']

                # Common pagination text patterns (Ukrainian, Russian, English)
                next_patterns = [
                    'наступна', 'далі', 'next', 'следующая',
                    '→', '»', 'newer', 'новіші'
                ]

                # Check if link text indicates "next page"
                if any(pattern in link_text for pattern in next_patterns):
                    logger.debug(f"Found next page link: {link_href} (text: '{link['text']}')")
                    return link_href

                # Check for numbered pagination (e.g., page=2, /page/2/)
                if 'page' in link_href.lower():
                    # Simple heuristic: if URL contains "page" and is different from current URL
                    if link_href != content.url:
                        logger.debug(f"Found potential next page (numbered): {link_href}")
                        return link_href

            logger.debug("No next page link found")
            return None

        except Exception as e:
            logger.error(f"Error finding next page link: {e}")
            return None

    def fetch_with_pagination(
        self,
        start_url: str,
        max_pages: int = 5,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
        timeout_seconds: int = 30
    ) -> Optional[ScrapedContent]:
        """
        Fetch multiple pages following pagination links.

        Args:
            start_url: Starting URL
            max_pages: Maximum number of pages to fetch
            use_cache: Whether to use cache
            cache_ttl: Cache TTL override
            timeout_seconds: Total timeout for all page fetches

        Returns:
            Aggregated ScrapedContent from all pages or None
        """
        start_time = time.time()
        all_pages: List[ScrapedContent] = []
        current_url = start_url
        seen_urls = set()

        logger.info(f"Starting paginated fetch from {start_url} (max {max_pages} pages)")

        for page_num in range(1, max_pages + 1):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning(f"Pagination timeout after {elapsed:.1f}s (fetched {page_num - 1} pages)")
                break

            # Avoid infinite loops
            if current_url in seen_urls:
                logger.warning(f"Detected loop: {current_url} already visited")
                break

            seen_urls.add(current_url)

            # Fetch current page
            logger.info(f"Fetching page {page_num}/{max_pages}: {current_url}")
            page_content = self.fetch(current_url, use_cache=use_cache, cache_ttl=cache_ttl)

            if not page_content:
                logger.warning(f"Failed to fetch page {page_num}: {current_url}")
                break

            all_pages.append(page_content)

            # Find next page link
            if page_num < max_pages:
                next_url = self._find_next_page_link(page_content)

                if not next_url:
                    logger.info(f"No more pages found after page {page_num}")
                    break

                # Convert relative URL to absolute
                if not next_url.startswith('http'):
                    next_url = urljoin(self.base_url, next_url)

                current_url = next_url
            else:
                logger.info(f"Reached max pages limit: {max_pages}")

        if not all_pages:
            logger.error("No pages successfully fetched")
            return None

        # Aggregate all pages into single content
        logger.info(f"Aggregating {len(all_pages)} pages into single content")
        aggregated = self._aggregate_pages(all_pages, start_url)

        return aggregated

    def _aggregate_pages(
        self,
        pages: List[ScrapedContent],
        original_url: str
    ) -> ScrapedContent:
        """
        Aggregate multiple pages into single ScrapedContent.

        Args:
            pages: List of ScrapedContent from individual pages
            original_url: Original starting URL

        Returns:
            Aggregated ScrapedContent
        """
        if not pages:
            raise ValueError("No pages to aggregate")

        if len(pages) == 1:
            # Single page, just return it
            return pages[0]

        # Use first page's title as main title
        title = pages[0].title

        # Combine all content with page separators
        content_parts = []
        for i, page in enumerate(pages, 1):
            if i > 1:
                content_parts.append(f"\n\n--- Page {i} ---\n")
            content_parts.append(page.content)

        combined_content = '\n'.join(content_parts)

        # Combine all links (deduplicate)
        all_links = []
        seen_link_urls = set()
        for page in pages:
            for link in page.links:
                link_url = link['href']
                if link_url not in seen_link_urls:
                    all_links.append(link)
                    seen_link_urls.add(link_url)

        # Aggregate metadata
        metadata = {
            'num_pages': len(pages),
            'page_urls': [p.url for p in pages],
            'total_paragraphs': sum(p.metadata.get('num_paragraphs', 0) for p in pages),
            'total_links': len(all_links),
            'content_length': len(combined_content),
            'source': 'opora.uk',
            'paginated': True
        }

        # Add publication dates if available
        pub_dates = [
            p.metadata.get('publication_date')
            for p in pages
            if p.metadata.get('publication_date')
        ]
        if pub_dates:
            metadata['first_publication_date'] = pub_dates[0]
            metadata['latest_publication_date'] = pub_dates[-1]

        return ScrapedContent(
            url=original_url,
            title=f"{title} (Pages 1-{len(pages)})",
            content=combined_content,
            links=all_links,
            metadata=metadata,
            scraped_at=datetime.now(),
            cached=False
        )
