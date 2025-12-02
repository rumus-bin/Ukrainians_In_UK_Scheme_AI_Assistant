# Manual Documents Directory

This directory contains manually created documents for the RAG knowledge base.

## Purpose

At this stage of the project, we use manually created documents instead of automated web scraping. This approach:

- Allows for curated, high-quality content
- Reduces complexity during initial development
- Eliminates dependency on external website availability
- Provides complete control over the knowledge base

## Document Formats

The system supports three formats:

### 1. JSON Format (Recommended)

Create JSON files with structured document data:

```json
[
  {
    "text": "Your document content here...",
    "metadata": {
      "source": "gov.uk",
      "title": "Document Title",
      "url": "https://www.gov.uk/...",
      "category": "visa"
    }
  }
]
```

Or use the structured format:

```json
{
  "documents": [
    {
      "text": "Content...",
      "metadata": { ... }
    }
  ]
}
```

### 2. Plain Text Format

Create `.txt` files with document content. The system will:
- Use the filename as the title
- Automatically generate metadata
- Mark source as "manual"

### 3. Markdown Format

Create `.md` files with Markdown content. The system will:
- Extract the title from the first `# Heading`
- Use the filename as fallback title
- Preserve Markdown formatting in the knowledge base

## Directory Structure

You can organize documents in subdirectories:

```
data/manual_docs/
├── README.md
├── visa/
│   ├── ukraine_extension_scheme.json
│   └── visa_requirements.json
├── housing/
│   ├── homes_for_ukraine.json
│   └── tenant_rights.json
└── work/
    ├── work_permits.json
    └── ni_number.json
```

## Example Document

See `example_document.json` for a template.

## Adding Documents

1. Create your document file in this directory (or a subdirectory)
2. Run the ingestion pipeline: `python run_ingestion.py`
3. The documents will be loaded, chunked, and stored in the vector database

## Future Migration

When you're ready to enable web scraping:

1. Set `SCRAPER_GOVUK_ENABLED=true` or `SCRAPER_OPORA_ENABLED=true`
2. Set `SCRAPER_SCHEDULE_ENABLED=true` for automated updates
3. Manual documents will continue to work alongside scraped content
