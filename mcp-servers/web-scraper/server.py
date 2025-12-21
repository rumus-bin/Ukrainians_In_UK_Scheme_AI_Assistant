"""MCP Server for web scraping predefined Ukrainian support resources."""

import asyncio
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from loguru import logger

from scrapers.opora_scraper import OporaUkScraper
from scrapers.govuk_scraper import GovUkScraper


class WebScraperMCPServer:
    """MCP Server for web scraping functionality."""

    def __init__(self, config_path: str):
        """
        Initialize MCP server.

        Args:
            config_path: Path to sources.yml configuration file
        """
        self.server = Server("web-scraper")
        self.config_path = Path(config_path)
        self.config = self._load_config()

        # Initialize scrapers
        scraping_config = self.config.get('scraping', {})
        user_agent = scraping_config.get('user_agent', 'UkraineSupportBot/1.0')
        cache_dir = scraping_config.get('cache', {}).get('directory', '/app/cache/html')
        cache_ttl = scraping_config.get('cache', {}).get('default_ttl', 86400)

        self.opora_scraper = OporaUkScraper(
            user_agent=user_agent,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            rate_limit_rpm=scraping_config.get('rate_limit', {}).get('requests_per_minute', 10),
            delay_between_requests=scraping_config.get('rate_limit', {}).get('delay_between_requests', 2.0),
            timeout=tuple(scraping_config.get('timeout', {}).values()),
            max_retries=scraping_config.get('retries', {}).get('max_attempts', 3),
            respect_robots=self.config.get('robots', {}).get('enabled', True)
        )

        self.govuk_scraper = GovUkScraper(
            user_agent=user_agent,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            rate_limit_rpm=scraping_config.get('rate_limit', {}).get('requests_per_minute', 10),
            delay_between_requests=scraping_config.get('rate_limit', {}).get('delay_between_requests', 2.0),
            timeout=tuple(scraping_config.get('timeout', {}).values()),
            max_retries=scraping_config.get('retries', {}).get('max_attempts', 3),
            respect_robots=self.config.get('robots', {}).get('enabled', True)
        )

        logger.info("WebScraperMCPServer initialized")

        # Register handlers
        self._register_handlers()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _register_handlers(self):
        """Register MCP tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_opora_housing",
                    description=(
                        "Search housing information on Opora.uk. "
                        "Returns articles and guidance about housing, tenant rights, "
                        "social housing, and Homes for Ukraine scheme."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": (
                                    "Specific housing topic (optional). Examples: "
                                    "'tenant-rights', 'social-housing', 'homes-for-ukraine'"
                                ),
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                    },
                ),
                Tool(
                    name="search_opora_nhs",
                    description=(
                        "Search NHS and healthcare information on Opora.uk. "
                        "Returns articles about GP registration, NHS services, and emergency care."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": (
                                    "Specific NHS topic (optional). Examples: "
                                    "'gp-registration', 'emergency-services'"
                                ),
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                    },
                ),
                Tool(
                    name="get_govuk_housing",
                    description=(
                        "Get official housing information from Gov.uk. "
                        "Returns official UK government guidance on housing, including "
                        "Homes for Ukraine scheme, council housing, private renting, and housing benefits."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": (
                                    "Specific housing topic (optional). Examples: "
                                    "'ukraine', 'council', 'renting', 'benefit'"
                                ),
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                    },
                ),
                Tool(
                    name="get_govuk_nhs",
                    description=(
                        "Get official NHS information from Gov.uk. "
                        "Returns official UK government guidance on NHS services and GP registration."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": (
                                    "Specific NHS topic (optional). Examples: "
                                    "'gp', 'services', 'emergency'"
                                ),
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                    },
                ),
                Tool(
                    name="get_govuk_ukraine_scheme",
                    description=(
                        "Get information about the official Homes for Ukraine scheme from Gov.uk. "
                        "Returns the most up-to-date official government information about "
                        "the Ukrainian refugee housing scheme."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                    },
                ),
                Tool(
                    name="get_opora_page",
                    description=(
                        "Get any page from Opora.uk by section path. "
                        "Use this for custom searches on Opora.uk when specific tools don't match."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "section_path": {
                                "type": "string",
                                "description": "Section path (e.g., '/housing', '/nhs/gp-registration')",
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                        "required": ["section_path"],
                    },
                ),
                Tool(
                    name="get_govuk_page",
                    description=(
                        "Get any page from Gov.uk by path. "
                        "Use this for custom searches on Gov.uk when specific tools don't match."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Page path (e.g., '/housing-for-ukraine', '/council-housing')",
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Whether to use cached content (default: true)",
                                "default": True
                            }
                        },
                        "required": ["path"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                # Opora.uk tools
                if name == "search_opora_housing":
                    result = await asyncio.to_thread(
                        self.opora_scraper.get_housing_info,
                        topic=arguments.get("topic"),
                        use_cache=arguments.get("use_cache", True)
                    )

                elif name == "search_opora_nhs":
                    result = await asyncio.to_thread(
                        self.opora_scraper.get_nhs_info,
                        topic=arguments.get("topic"),
                        use_cache=arguments.get("use_cache", True)
                    )

                elif name == "get_opora_page":
                    result = await asyncio.to_thread(
                        self.opora_scraper.search_section,
                        section_path=arguments["section_path"],
                        use_cache=arguments.get("use_cache", True)
                    )

                # Gov.uk tools
                elif name == "get_govuk_housing":
                    result = await asyncio.to_thread(
                        self.govuk_scraper.get_housing_info,
                        topic=arguments.get("topic"),
                        use_cache=arguments.get("use_cache", True)
                    )

                elif name == "get_govuk_nhs":
                    result = await asyncio.to_thread(
                        self.govuk_scraper.get_nhs_info,
                        topic=arguments.get("topic"),
                        use_cache=arguments.get("use_cache", True)
                    )

                elif name == "get_govuk_ukraine_scheme":
                    result = await asyncio.to_thread(
                        self.govuk_scraper.search_ukraine_scheme,
                        use_cache=arguments.get("use_cache", True)
                    )

                elif name == "get_govuk_page":
                    result = await asyncio.to_thread(
                        self.govuk_scraper.get_page,
                        path=arguments["path"],
                        use_cache=arguments.get("use_cache", True)
                    )

                else:
                    raise ValueError(f"Unknown tool: {name}")

                # Format response
                if result:
                    response_text = self._format_scraped_content(result)
                    return [TextContent(type="text", text=response_text)]
                else:
                    return [TextContent(
                        type="text",
                        text=f"Failed to fetch content. Please try again or check the URL."
                    )]

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]

    def _format_scraped_content(self, content) -> str:
        """
        Format scraped content for agent consumption.

        Args:
            content: ScrapedContent object

        Returns:
            Formatted string
        """
        parts = []

        # Header
        parts.append(f"# {content.title}")
        parts.append(f"**Source:** {content.url}")
        parts.append(f"**Scraped:** {content.scraped_at.strftime('%Y-%m-%d %H:%M UTC')}")

        if content.cached:
            parts.append("**Status:** Cached content")

        if content.metadata.get('publication_date'):
            parts.append(f"**Published:** {content.metadata['publication_date']}")

        parts.append("")  # Blank line

        # Main content
        parts.append("## Content")
        parts.append(content.content)
        parts.append("")

        # Links (if any)
        if content.links:
            parts.append("## Relevant Links")
            for link in content.links[:10]:  # Limit to first 10 links
                parts.append(f"- [{link['text']}]({link['href']})")
            parts.append("")

        # Metadata
        parts.append("## Metadata")
        parts.append(f"- Content length: {content.metadata.get('content_length', 0)} characters")
        parts.append(f"- Number of links: {content.metadata.get('num_links', 0)}")
        if content.metadata.get('official'):
            parts.append("- **Official UK Government Source**")

        return "\n".join(parts)

    async def run(self):
        """Run the MCP server."""
        logger.info("Starting MCP web scraper server...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point."""
    import sys

    # Setup logging
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # Determine config path
    config_path = Path(__file__).parent / "config" / "sources.yml"

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    # Create and run server
    server = WebScraperMCPServer(str(config_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
