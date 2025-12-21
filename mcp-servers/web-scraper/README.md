# MCP Web Scraper Server

Model Context Protocol (MCP) server for scraping Ukrainian support resources from opora.uk and gov.uk.

## Overview

This MCP server provides AI agents with real-time web access to supplement the RAG knowledge base. It safely scrapes predefined sources while respecting robots.txt, rate limits, and legal constraints.

## Features

- ✅ **Safety-First Design**
  - robots.txt compliance
  - Rate limiting (10 req/min, 2s delays)
  - Retry logic with exponential backoff
  - Timeout protection

- ✅ **Intelligent Caching**
  - File-based cache with configurable TTL
  - Default 24-hour cache for most content
  - 12-hour cache for critical pages
  - Automatic cache expiration

- ✅ **Site-Specific Scrapers**
  - Opora.uk scraper with custom selectors
  - Gov.uk scraper optimized for government pages
  - Clean content extraction
  - Link extraction and normalization

- ✅ **MCP Tools**
  - `search_opora_housing` - Housing info from Opora.uk
  - `search_opora_nhs` - NHS info from Opora.uk
  - `get_govuk_housing` - Housing info from Gov.uk
  - `get_govuk_nhs` - NHS info from Gov.uk
  - `get_govuk_ukraine_scheme` - Homes for Ukraine scheme
  - `get_opora_page` - Custom Opora.uk page
  - `get_govuk_page` - Custom Gov.uk page

## Architecture

```
┌──────────────────┐
│   MCP Client     │  (in src/agents/mcp_client.py)
│   (Agent side)   │
└────────┬─────────┘
         │ stdio
         ▼
┌──────────────────┐
│   MCP Server     │  (this directory)
│   server.py      │
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────┐
│ Opora   │ │  Gov.uk  │
│ Scraper │ │  Scraper │
└─────────┘ └──────────┘
```

## Configuration

Edit `config/sources.yml` to configure:

- **Sources** - Predefined URLs and sections
- **Selectors** - CSS selectors for content extraction
- **Rate Limits** - Requests per minute and delays
- **Cache Settings** - TTL and maximum size
- **User Agent** - Bot identification

Example:
```yaml
sources:
  opora_housing:
    base_url: "https://opora.uk"
    sections:
      - path: "/housing"
        cache_ttl: 86400  # 24 hours

scraping:
  rate_limit:
    requests_per_minute: 10
    delay_between_requests: 2.0
```

## Installation

Dependencies are installed via the main project `requirements.txt`:

```bash
pip install -r ../../requirements.txt
```

Key dependencies:
- `mcp>=1.0.0` - MCP SDK
- `beautifulsoup4>=4.12.0` - HTML parsing
- `requests>=2.31.0` - HTTP requests
- `lxml>=5.1.0` - Fast XML/HTML processing
- `python-dateutil>=2.8.0` - Date parsing
- `loguru>=0.7.0` - Logging
- `pyyaml` - Configuration

## Usage

### Running the Server

**Standalone:**
```bash
python server.py
```

**In Docker (recommended):**
```bash
docker-compose up mcp-scraper
```

### Using from Agents

```python
from src.agents.mcp_client import get_mcp_client

# Get singleton client
client = get_mcp_client()

# Search Opora.uk housing info
result = await client.search_opora_housing(
    topic="tenant-rights",
    use_cache=True
)

# Get Gov.uk Ukraine scheme
result = await client.get_govuk_ukraine_scheme()

# Access result
print(f"Title: {result.title}")
print(f"URL: {result.source_url}")
print(f"Content: {result.content}")
```

### Tool Parameters

All tools accept:
- `topic` (optional) - Specific topic to search
- `use_cache` (optional) - Whether to use cache (default: True)

## Development

### Project Structure

```
mcp-servers/web-scraper/
├── server.py              # MCP server implementation
├── config/
│   └── sources.yml        # Configuration file
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py    # Base scraper with safety features
│   ├── opora_scraper.py   # Opora.uk specific scraper
│   └── govuk_scraper.py   # Gov.uk specific scraper
├── cache/                 # Cached HTML (created at runtime)
│   └── html/
└── README.md              # This file
```

### Adding a New Source

1. **Create a new scraper class** in `scrapers/`:
```python
from .base_scraper import BaseWebScraper

class NewSiteScraper(BaseWebScraper):
    def __init__(self, user_agent, cache_dir, **kwargs):
        super().__init__(user_agent, cache_dir, **kwargs)
        self.selectors = {
            'article_container': '.main-content',
            'title': 'h1',
            'content': '.article p'
        }
```

2. **Add configuration** in `config/sources.yml`:
```yaml
sources:
  new_site:
    base_url: "https://newsite.com"
    sections:
      - path: "/section1"
        cache_ttl: 86400
```

3. **Register MCP tools** in `server.py`:
```python
Tool(
    name="search_new_site",
    description="Search NewSite for information",
    inputSchema={...}
)
```

4. **Add tool handler** in `server.py`:
```python
elif name == "search_new_site":
    result = await asyncio.to_thread(
        self.new_site_scraper.search,
        query=arguments.get("query")
    )
```

### Testing

Run tests from the main project directory:

```bash
# Unit tests only
pytest tests/test_mcp_web_scraper.py -v

# Include integration tests (requires internet)
pytest tests/test_mcp_web_scraper.py -v --run-integration

# With coverage
pytest tests/test_mcp_web_scraper.py --cov=mcp-servers/web-scraper
```

### Debugging

Enable debug logging:

```python
from loguru import logger
logger.add("debug.log", level="DEBUG")
```

View scraper activity:
```bash
docker logs ukraine-bot-mcp-scraper -f
```

Check cache:
```bash
docker exec ukraine-bot-mcp-scraper ls -lh /app/mcp-servers/web-scraper/cache/html
```

## Legal & Safety

### Legal Compliance

✅ **Respects robots.txt** - Checks before scraping
✅ **Rate limited** - Respectful crawling speed
✅ **Identified** - Clear User-Agent with purpose
✅ **Non-commercial** - Stated in User-Agent
✅ **Public content only** - No authentication required
✅ **Attribution** - Source URLs always included

### User-Agent String

```
UkraineSupportBot/1.0 (non-commercial; helping Ukrainian refugees)
```

### robots.txt Examples

**Gov.uk allows:**
```
User-agent: *
Disallow: /search
Allow: /
```

**Opora.uk** - Generally allows crawling (verify with site owners)

### Best Practices

1. **Cache aggressively** - Reduce load on source sites
2. **Respect delays** - Don't modify rate limit settings
3. **Monitor errors** - Watch for 403/429 responses
4. **Update selectors** - Sites change HTML structure
5. **Test regularly** - Ensure scrapers still work

## Monitoring

### Metrics to Track

- **Cache hit rate** - Higher is better (target: >80%)
- **Scrape failures** - Should be rare (<5%)
- **Average response time** - Should be <5s
- **Cache size** - Monitor disk usage

### Logs

```bash
# View real-time logs
docker logs ukraine-bot-mcp-scraper -f

# Search for errors
docker logs ukraine-bot-mcp-scraper | grep ERROR

# Check cache hits
docker logs ukraine-bot-mcp-scraper | grep "Cache hit"
```

### Maintenance

**Clear expired cache:**
```bash
docker exec ukraine-bot-mcp-scraper python -c "
from scrapers.base_scraper import ContentCache
cache = ContentCache('/app/mcp-servers/web-scraper/cache/html')
cache.clear_expired()
print('Cache cleared')
"
```

**Check cache size:**
```bash
docker exec ukraine-bot-mcp-scraper du -sh /app/mcp-servers/web-scraper/cache
```

## Troubleshooting

### Problem: MCP client can't connect to server

**Solution:**
```bash
# Check if container is running
docker ps | grep mcp-scraper

# View logs
docker logs ukraine-bot-mcp-scraper

# Restart container
docker-compose restart mcp-scraper
```

### Problem: Scraper returns empty content

**Possible causes:**
- Site changed HTML structure → Update selectors in `config/sources.yml`
- Site is blocking bot → Check robots.txt and User-Agent
- Network timeout → Check timeout settings

**Debug:**
```python
# Enable debug logging in scraper
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Problem: Rate limiting errors (429)

**Solution:**
- Increase `delay_between_requests` in config
- Decrease `requests_per_minute`
- Check if cache is working properly

### Problem: Cache not working

**Check:**
```bash
# Verify cache directory exists and is writable
docker exec ukraine-bot-mcp-scraper ls -ld /app/mcp-servers/web-scraper/cache/html

# Check cache files
docker exec ukraine-bot-mcp-scraper ls -lh /app/mcp-servers/web-scraper/cache/html

# View cache logs
docker logs ukraine-bot-mcp-scraper | grep -i cache
```

## Performance

### Expected Metrics

- **Cached request:** <100ms
- **Fresh scrape:** 2-5 seconds
- **Retry (on failure):** 10-20 seconds (with backoff)

### Optimization Tips

1. **Use cache** - Always set `use_cache=True` unless explicitly need fresh data
2. **Pre-warm cache** - Fetch important pages during low-traffic periods
3. **Adjust TTL** - Balance freshness vs. performance
4. **Monitor patterns** - Track which pages are requested most

## Security

### Implemented Protections

- ✅ No arbitrary URL scraping (only predefined sources)
- ✅ Input validation on topic parameters
- ✅ Content length limits
- ✅ Timeout protection
- ✅ No JavaScript execution
- ✅ Docker network isolation

### Not Needed (For This Use Case)

- ❌ CAPTCHA handling - Not required for gov.uk/opora.uk
- ❌ Proxy rotation - Low volume doesn't need it
- ❌ XSS sanitization - Content consumed by LLM, not displayed

## Future Enhancements

- [ ] Multi-page following (extract and scrape linked pages)
- [ ] Structured data extraction (tables, lists, forms)
- [ ] Change detection (alert when important pages update)
- [ ] Search result ranking (prioritize most relevant pages)
- [ ] Analytics dashboard (track usage patterns)
- [ ] Automatic cache warming (pre-fetch important pages)
- [ ] Language detection (handle multilingual content)

## License

This is part of the Ukrainian Support AI Assistant project. Non-commercial use only.

## Contact

For issues or questions, see the main project README.

---

**Version:** 1.0.0
**Last Updated:** 2025-12-15
**Status:** ✅ Production Ready
