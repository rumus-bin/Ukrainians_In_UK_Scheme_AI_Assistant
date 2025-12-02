"""Document chunking for RAG pipeline."""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from src.utils.config import get_settings
from src.utils.logger import get_logger

logger = get_logger()


class ChunkingStrategy(Enum):
    """Different strategies for chunking text."""
    FIXED = "fixed"  # Fixed character length
    SENTENCE = "sentence"  # Sentence-aware chunking
    PARAGRAPH = "paragraph"  # Paragraph-aware chunking


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    total_chunks: int = 0
    start_char: int = 0
    end_char: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage."""
        return {
            "text": self.text,
            "metadata": {
                **self.metadata,
                "chunk_index": self.chunk_index,
                "total_chunks": self.total_chunks,
                "start_char": self.start_char,
                "end_char": self.end_char,
            }
        }


class DocumentChunker:
    """Handles text chunking for RAG pipeline."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE
    ):
        """
        Initialize document chunker.

        Args:
            chunk_size: Maximum characters per chunk (default from settings)
            chunk_overlap: Overlap between chunks in characters (default from settings)
            strategy: Chunking strategy to use
        """
        self.settings = get_settings()
        self.chunk_size = chunk_size or self.settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or self.settings.rag_chunk_overlap
        self.strategy = strategy

        # Validate parameters
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        logger.info(
            f"Initialized DocumentChunker with chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, strategy={self.strategy.value}"
        )

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[TextChunk]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        # Clean the text
        cleaned_text = self._clean_text(text)

        if not cleaned_text:
            logger.warning("Text became empty after cleaning")
            return []

        # Apply chunking strategy
        if self.strategy == ChunkingStrategy.SENTENCE:
            chunks = self._chunk_by_sentences(cleaned_text)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            chunks = self._chunk_by_paragraphs(cleaned_text)
        else:  # FIXED
            chunks = self._chunk_fixed(cleaned_text)

        # Create TextChunk objects with metadata
        text_chunks = []
        total_chunks = len(chunks)

        for idx, (chunk_text, start_pos, end_pos) in enumerate(chunks):
            text_chunk = TextChunk(
                text=chunk_text,
                metadata=metadata.copy() if metadata else {},
                chunk_index=idx,
                total_chunks=total_chunks,
                start_char=start_pos,
                end_char=end_pos
            )
            text_chunks.append(text_chunk)

        logger.info(
            f"Chunked text into {len(text_chunks)} chunks "
            f"(original length: {len(text)} chars)"
        )

        return text_chunks

    def chunk_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[TextChunk]:
        """
        Chunk multiple documents.

        Args:
            documents: List of documents with 'text' and optional 'metadata' fields

        Returns:
            List of all TextChunks from all documents
        """
        all_chunks = []

        for doc_idx, doc in enumerate(documents):
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})

            # Add document index to metadata
            doc_metadata = {
                **metadata,
                "document_index": doc_idx
            }

            chunks = self.chunk_text(text, doc_metadata)
            all_chunks.extend(chunks)

        logger.info(
            f"Chunked {len(documents)} documents into {len(all_chunks)} total chunks"
        )

        return all_chunks

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)

        # Normalize newlines
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Remove multiple consecutive newlines (keep max 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _chunk_fixed(self, text: str) -> List[tuple[str, int, int]]:
        """
        Split text into fixed-size chunks with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of (chunk_text, start_pos, end_pos) tuples
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate end position
            end = min(start + self.chunk_size, text_length)

            # Extract chunk
            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append((chunk_text, start, end))

            # Move to next chunk with overlap
            start += self.chunk_size - self.chunk_overlap

            # Prevent infinite loop
            if start <= chunks[-1][1] if chunks else False:
                break

        return chunks

    def _chunk_by_sentences(self, text: str) -> List[tuple[str, int, int]]:
        """
        Split text into chunks respecting sentence boundaries.

        Args:
            text: Text to chunk

        Returns:
            List of (chunk_text, start_pos, end_pos) tuples
        """
        # Split into sentences (handles Ukrainian and Russian text)
        # Ukrainian/Russian sentence endings: . ! ? ... та інші
        sentence_pattern = r'(?<=[.!?…])\s+(?=[А-ЯІЇЄҐA-Z])'
        sentences = re.split(sentence_pattern, text)

        chunks = []
        current_chunk = []
        current_length = 0
        current_start = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            # If single sentence exceeds chunk_size, split it
            if sentence_length > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append((
                        chunk_text,
                        current_start,
                        current_start + len(chunk_text)
                    ))
                    current_chunk = []
                    current_length = 0

                # Split long sentence into fixed chunks
                long_sentence_chunks = self._chunk_fixed(sentence)
                chunks.extend(long_sentence_chunks)
                current_start = long_sentence_chunks[-1][2]
                continue

            # Check if adding this sentence exceeds chunk_size
            if current_length + sentence_length + 1 > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunk_end = current_start + len(chunk_text)
                chunks.append((chunk_text, current_start, chunk_end))

                # Start new chunk with overlap
                # Include last few sentences for overlap
                overlap_sentences = []
                overlap_length = 0

                for sent in reversed(current_chunk):
                    if overlap_length + len(sent) <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_length += len(sent) + 1
                    else:
                        break

                current_chunk = overlap_sentences
                current_length = overlap_length
                current_start = chunk_end - overlap_length

            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append((
                chunk_text,
                current_start,
                current_start + len(chunk_text)
            ))

        return chunks

    def _chunk_by_paragraphs(self, text: str) -> List[tuple[str, int, int]]:
        """
        Split text into chunks respecting paragraph boundaries.

        Args:
            text: Text to chunk

        Returns:
            List of (chunk_text, start_pos, end_pos) tuples
        """
        # Split by paragraphs (double newline)
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = []
        current_length = 0
        current_start = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            para_length = len(paragraph)

            # If single paragraph exceeds chunk_size, split by sentences
            if para_length > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((
                        chunk_text,
                        current_start,
                        current_start + len(chunk_text)
                    ))
                    current_chunk = []
                    current_length = 0

                # Split long paragraph by sentences
                para_chunks = self._chunk_by_sentences(paragraph)
                chunks.extend(para_chunks)
                current_start = para_chunks[-1][2]
                continue

            # Check if adding this paragraph exceeds chunk_size
            if current_length + para_length + 2 > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunk_end = current_start + len(chunk_text)
                chunks.append((chunk_text, current_start, chunk_end))

                # Start new chunk with overlap (last paragraph)
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_para = current_chunk[-1]
                    if len(overlap_para) <= self.chunk_overlap:
                        current_chunk = [overlap_para]
                        current_length = len(overlap_para)
                        current_start = chunk_end - current_length
                    else:
                        current_chunk = []
                        current_length = 0
                        current_start = chunk_end
                else:
                    current_chunk = []
                    current_length = 0
                    current_start = chunk_end

            # Add paragraph to current chunk
            current_chunk.append(paragraph)
            current_length += para_length + 2  # +2 for newlines

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((
                chunk_text,
                current_start,
                current_start + len(chunk_text)
            ))

        return chunks


# Singleton instance
_chunker: Optional[DocumentChunker] = None


def get_chunker(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE
) -> DocumentChunker:
    """
    Get or create the global chunker instance.

    Args:
        chunk_size: Override default chunk size
        chunk_overlap: Override default overlap
        strategy: Chunking strategy

    Returns:
        DocumentChunker instance
    """
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=strategy
        )
    return _chunker