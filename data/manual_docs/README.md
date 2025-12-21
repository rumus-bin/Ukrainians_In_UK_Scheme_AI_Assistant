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
      "category": "visa",
      "document_date": "2024-12-21"
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
      "metadata": {
        "title": "Document Title",
        "document_date": "2024-12-21T10:00:00"
      }
    }
  ]
}
```

**Important**: The `document_date` field is crucial for the RAG system to provide up-to-date information. It can be specified in the metadata or at the document level. If not provided, the system will use the file modification time as a fallback.

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

The manual documents directory uses an **active/archive** workflow:

```
data/manual_docs/
├── README.md
├── active/          # Only documents in this folder are processed
│   ├── visa/
│   │   ├── ukraine_extension_scheme.json
│   │   └── visa_requirements.json
│   ├── housing/
│   │   ├── homes_for_ukraine.json
│   │   └── tenant_rights.json
│   └── work/
│       ├── work_permits.json
│       └── ni_number.json
└── archive/         # Previously processed documents (not ingested)
    └── old_data.json
```

**Important**: The ingestion pipeline only processes documents from the `active/` subfolder. After processing, you can optionally move documents to the `archive/` folder to keep them for reference but exclude them from future ingestions.

## Example Document

See `example_document.json` for a template.

## Adding Documents

1. Create your document file in the `active/` directory (or a subdirectory within `active/`)
2. **Important**: Include a `document_date` field in your metadata to ensure accurate date-based retrieval
3. Run the ingestion pipeline: `python run_ingestion.py`
4. The documents will be loaded, chunked, and stored in the vector database
5. Optionally, move processed documents to `archive/` to keep them for reference

### Document Date Format

The system supports multiple date formats:
- ISO format: `"2024-12-21T10:00:00"` or `"2024-12-21"`
- UK format: `"21/12/2024"` or `"21-12-2024"`

Example with explicit date:
```json
{
  "text": "The Ukraine Extension Scheme allows...",
  "metadata": {
    "title": "Ukraine Extension Scheme 2024",
    "source": "gov.uk",
    "document_date": "2024-12-21"
  }
}
```

If no `document_date` is provided, the system will use the file's last modification time.

## Future Migration

When you're ready to enable web scraping:

1. Set `SCRAPER_GOVUK_ENABLED=true` or `SCRAPER_OPORA_ENABLED=true`
2. Set `SCRAPER_SCHEDULE_ENABLED=true` for automated updates
3. Manual documents will continue to work alongside scraped content
