"""MCP Client for connecting agents to MCP web scraper server."""

import asyncio
import subprocess
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from loguru import logger


@dataclass
class WebSearchResult:
    """Web search result from MCP server."""
    content: str
    source_url: str
    title: str
    metadata: Dict[str, Any]


class MCPWebScraperClient:
    """Client for MCP web scraper server."""

    def __init__(self, server_command: Optional[List[str]] = None):
        """
        Initialize MCP client.

        Args:
            server_command: Command to start MCP server (defaults to containerized server)
        """
        self.server_command = server_command or [
            "docker", "exec", "-i", "ukraine-bot-mcp-scraper",
            "python", "/app/mcp-servers/web-scraper/server.py"
        ]
        self.session: Optional[ClientSession] = None
        self.server_process: Optional[subprocess.Popen] = None
        self._connected = False

        logger.info("MCPWebScraperClient initialized")

    async def connect(self):
        """Connect to MCP server."""
        if self._connected:
            logger.debug("Already connected to MCP server")
            return

        try:
            logger.info("Connecting to MCP web scraper server...")

            # Start server and create session
            server_params = {
                "command": self.server_command[0],
                "args": self.server_command[1:],
            }

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    self._connected = True

                    # Initialize session
                    await session.initialize()

                    logger.info("Connected to MCP web scraper server")

                    # List available tools
                    tools = await session.list_tools()
                    logger.info(f"Available tools: {[t.name for t in tools.tools]}")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Disconnect from MCP server."""
        if not self._connected:
            return

        try:
            self.session = None
            self._connected = False
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server: {e}")

    async def search_opora_housing(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[WebSearchResult]:
        """
        Search housing information on Opora.uk.

        Args:
            topic: Specific housing topic (e.g., 'tenant-rights', 'social-housing')
            use_cache: Whether to use cached content

        Returns:
            WebSearchResult or None
        """
        return await self._call_tool(
            "search_opora_housing",
            {"topic": topic, "use_cache": use_cache}
        )

    async def search_opora_nhs(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[WebSearchResult]:
        """
        Search NHS information on Opora.uk.

        Args:
            topic: Specific NHS topic (e.g., 'gp-registration')
            use_cache: Whether to use cached content

        Returns:
            WebSearchResult or None
        """
        return await self._call_tool(
            "search_opora_nhs",
            {"topic": topic, "use_cache": use_cache}
        )

    async def get_govuk_housing(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[WebSearchResult]:
        """
        Get housing information from Gov.uk.

        Args:
            topic: Specific housing topic (e.g., 'ukraine', 'council', 'renting')
            use_cache: Whether to use cached content

        Returns:
            WebSearchResult or None
        """
        return await self._call_tool(
            "get_govuk_housing",
            {"topic": topic, "use_cache": use_cache}
        )

    async def get_govuk_nhs(
        self,
        topic: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[WebSearchResult]:
        """
        Get NHS information from Gov.uk.

        Args:
            topic: Specific NHS topic (e.g., 'gp', 'services')
            use_cache: Whether to use cached content

        Returns:
            WebSearchResult or None
        """
        return await self._call_tool(
            "get_govuk_nhs",
            {"topic": topic, "use_cache": use_cache}
        )

    async def get_govuk_ukraine_scheme(
        self,
        use_cache: bool = True
    ) -> Optional[WebSearchResult]:
        """
        Get Homes for Ukraine scheme information from Gov.uk.

        Args:
            use_cache: Whether to use cached content

        Returns:
            WebSearchResult or None
        """
        return await self._call_tool(
            "get_govuk_ukraine_scheme",
            {"use_cache": use_cache}
        )

    async def _call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Optional[WebSearchResult]:
        """
        Call MCP tool.

        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments

        Returns:
            WebSearchResult or None
        """
        try:
            # Create a new connection for each request
            # This is a simplified approach - for production, you might want to maintain a persistent connection
            server_params = StdioServerParameters(
                command=self.server_command[0],
                args=self.server_command[1:],
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize
                    await session.initialize()

                    logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")

                    # Call tool
                    result = await session.call_tool(tool_name, arguments)

                    if result and result.content:
                        # Extract text content
                        content_text = ""
                        for content in result.content:
                            if hasattr(content, 'text'):
                                content_text += content.text

                        # Parse the formatted content
                        return self._parse_result(content_text)

                    logger.warning(f"No result from tool {tool_name}")
                    return None

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return None

    def _parse_result(self, content: str) -> WebSearchResult:
        """
        Parse formatted result from MCP server.

        Args:
            content: Formatted content string

        Returns:
            WebSearchResult
        """
        # Simple parsing - extract title, URL, and content
        lines = content.split('\n')

        title = "Untitled"
        source_url = ""
        main_content = []
        metadata = {}

        in_content_section = False

        for line in lines:
            if line.startswith('# '):
                title = line[2:].strip()
            elif line.startswith('**Source:**'):
                source_url = line.replace('**Source:**', '').strip()
            elif line.startswith('## Content'):
                in_content_section = True
                continue
            elif line.startswith('## '):
                in_content_section = False
            elif in_content_section and line.strip():
                main_content.append(line)

        return WebSearchResult(
            content='\n'.join(main_content),
            source_url=source_url,
            title=title,
            metadata=metadata
        )


# Global client instance (singleton pattern)
_mcp_client: Optional[MCPWebScraperClient] = None


def get_mcp_client() -> MCPWebScraperClient:
    """
    Get global MCP client instance.

    Returns:
        MCPWebScraperClient instance
    """
    global _mcp_client

    if _mcp_client is None:
        _mcp_client = MCPWebScraperClient()
        logger.info("Created global MCP client instance")

    return _mcp_client
