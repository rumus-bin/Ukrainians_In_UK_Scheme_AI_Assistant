"""Document loader for manual documents from filesystem."""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class ManualDocumentLoader:
    """Load documents from manually created files."""

    def __init__(
        self,
        docs_path: Optional[str] = None,
        docs_format: Optional[str] = None,
        recursive: bool = True
    ):
        """
        Initialize the document loader.

        Args:
            docs_path: Path to directory containing documents
            docs_format: Format of documents (json, txt, markdown)
            recursive: Whether to search subdirectories
        """
        settings = get_settings()
        self.docs_path = Path(docs_path or settings.manual_docs_path)
        self.docs_format = docs_format or settings.manual_docs_format
        self.recursive = recursive

    def load_documents(self) -> List[Dict[str, Any]]:
        """
        Load all documents from the configured path.

        Returns:
            List of document dictionaries with 'text' and 'metadata' fields
        """
        if not self.docs_path.exists():
            logger.warning(f"Documents path does not exist: {self.docs_path}")
            return []

        logger.info(f"Loading documents from: {self.docs_path}")
        logger.info(f"Format: {self.docs_format}, Recursive: {self.recursive}")

        documents = []

        if self.docs_format == "json":
            documents = self._load_json_documents()
        elif self.docs_format == "txt":
            documents = self._load_text_documents()
        elif self.docs_format == "markdown":
            documents = self._load_markdown_documents()
        else:
            logger.error(f"Unsupported document format: {self.docs_format}")
            return []

        logger.info(f"Loaded {len(documents)} documents from manual files")
        return documents

    def _load_json_documents(self) -> List[Dict[str, Any]]:
        """Load documents from JSON files."""
        documents = []

        # Pattern for finding JSON files
        pattern = "**/*.json" if self.recursive else "*.json"

        for json_file in self.docs_path.glob(pattern):
            try:
                logger.info(f"Loading JSON file: {json_file}")

                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Support different JSON structures
                if isinstance(data, list):
                    # Array of documents
                    for item in data:
                        doc = self._normalize_document(item, json_file)
                        if doc:
                            documents.append(doc)
                elif isinstance(data, dict):
                    # Single document or structured format
                    if 'documents' in data:
                        # Format: {"documents": [...]}
                        for item in data['documents']:
                            doc = self._normalize_document(item, json_file)
                            if doc:
                                documents.append(doc)
                    else:
                        # Single document
                        doc = self._normalize_document(data, json_file)
                        if doc:
                            documents.append(doc)

                logger.info(f"Loaded {len(documents)} documents from {json_file.name}")

            except Exception as e:
                logger.error(f"Failed to load JSON file {json_file}: {e}")

        return documents

    def _load_text_documents(self) -> List[Dict[str, Any]]:
        """Load documents from plain text files."""
        documents = []

        pattern = "**/*.txt" if self.recursive else "*.txt"

        for txt_file in self.docs_path.glob(pattern):
            try:
                logger.info(f"Loading text file: {txt_file}")

                with open(txt_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()

                if not text:
                    logger.warning(f"Empty text file: {txt_file}")
                    continue

                # Extract title from filename
                title = txt_file.stem.replace('_', ' ').replace('-', ' ').title()

                document = {
                    'text': text,
                    'metadata': {
                        'source': 'manual',
                        'file': str(txt_file.name),
                        'title': title,
                        'url': f"file://{txt_file}",
                        'scraped_at': datetime.now().isoformat(),
                        'type': 'text',
                        'document_type': 'manual'
                    }
                }

                documents.append(document)

            except Exception as e:
                logger.error(f"Failed to load text file {txt_file}: {e}")

        return documents

    def _load_markdown_documents(self) -> List[Dict[str, Any]]:
        """Load documents from Markdown files."""
        documents = []

        pattern = "**/*.md" if self.recursive else "*.md"

        for md_file in self.docs_path.glob(pattern):
            try:
                logger.info(f"Loading Markdown file: {md_file}")

                with open(md_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()

                if not text:
                    logger.warning(f"Empty Markdown file: {md_file}")
                    continue

                # Extract title from first heading or filename
                title = self._extract_markdown_title(text) or md_file.stem.replace('_', ' ').replace('-', ' ').title()

                document = {
                    'text': text,
                    'metadata': {
                        'source': 'manual',
                        'file': str(md_file.name),
                        'title': title,
                        'url': f"file://{md_file}",
                        'scraped_at': datetime.now().isoformat(),
                        'type': 'markdown',
                        'document_type': 'manual'
                    }
                }

                documents.append(document)

            except Exception as e:
                logger.error(f"Failed to load Markdown file {md_file}: {e}")

        return documents

    def _extract_markdown_title(self, text: str) -> Optional[str]:
        """Extract title from Markdown content (first # heading)."""
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return None

    def _normalize_document(self, data: Dict[str, Any], source_file: Path) -> Optional[Dict[str, Any]]:
        """
        Normalize document data to standard format.

        Expected format:
        {
            "text": "content...",
            "metadata": {
                "source": "gov.uk",
                "title": "Document Title",
                "url": "https://...",
                ...
            }
        }

        Args:
            data: Raw document data
            source_file: Source file path for metadata

        Returns:
            Normalized document or None if invalid
        """
        # Check if required fields exist
        if 'text' not in data and 'content' not in data:
            logger.warning(f"Document missing 'text' or 'content' field in {source_file}")
            return None

        # Get text content
        text = data.get('text') or data.get('content', '')
        if not text or not text.strip():
            logger.warning(f"Document has empty text in {source_file}")
            return None

        # Get or create metadata
        metadata = data.get('metadata', {})

        # Ensure required metadata fields
        if 'source' not in metadata:
            metadata['source'] = 'manual'

        if 'file' not in metadata:
            metadata['file'] = str(source_file.name)

        if 'title' not in metadata:
            metadata['title'] = data.get('title', source_file.stem)

        if 'url' not in metadata:
            metadata['url'] = data.get('url', f"file://{source_file}")

        if 'scraped_at' not in metadata:
            metadata['scraped_at'] = datetime.now().isoformat()

        # Add document_type to distinguish manual docs from scraped
        metadata['document_type'] = 'manual'

        return {
            'text': text.strip(),
            'metadata': metadata
        }


def load_manual_documents(
    docs_path: Optional[str] = None,
    docs_format: Optional[str] = None,
    recursive: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function to load manual documents.

    Args:
        docs_path: Path to directory containing documents
        docs_format: Format of documents (json, txt, markdown)
        recursive: Whether to search subdirectories

    Returns:
        List of document dictionaries
    """
    loader = ManualDocumentLoader(
        docs_path=docs_path,
        docs_format=docs_format,
        recursive=recursive
    )
    return loader.load_documents()
