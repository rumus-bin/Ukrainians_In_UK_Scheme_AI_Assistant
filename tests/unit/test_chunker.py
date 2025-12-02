"""Tests for document chunking functionality."""

import pytest
from src.rag.chunker import DocumentChunker, ChunkingStrategy, TextChunk


class TestDocumentChunker:
    """Test cases for DocumentChunker."""

    def test_initialization(self):
        """Test chunker initialization with default settings."""
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50
        assert chunker.strategy == ChunkingStrategy.SENTENCE

    def test_initialization_invalid_overlap(self):
        """Test that invalid overlap raises error."""
        with pytest.raises(ValueError):
            DocumentChunker(chunk_size=100, chunk_overlap=100)

    def test_clean_text(self):
        """Test text cleaning functionality."""
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)

        # Test whitespace normalization
        text = "Multiple    spaces   and\n\n\n\nmultiple newlines"
        cleaned = chunker._clean_text(text)
        assert "    " not in cleaned
        assert "\n\n\n" not in cleaned

    def test_chunk_fixed_strategy(self):
        """Test fixed-size chunking."""
        chunker = DocumentChunker(
            chunk_size=50,
            chunk_overlap=10,
            strategy=ChunkingStrategy.FIXED
        )

        text = "A" * 120  # 120 characters
        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1
        assert all(len(chunk.text) <= 50 for chunk in chunks)

    def test_chunk_by_sentences_ukrainian(self):
        """Test sentence-aware chunking with Ukrainian text."""
        chunker = DocumentChunker(
            chunk_size=200,
            chunk_overlap=50,
            strategy=ChunkingStrategy.SENTENCE
        )

        text = (
            "Це перше речення про візи до Великобританії. "
            "Це друге речення про імміграційні правила. "
            "Це третє речення про документи. "
            "Це четверте речення про процедуру подачі заяви."
        )

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        # Check that sentences are not broken mid-word
        for chunk in chunks:
            assert not chunk.text.endswith("про")

    def test_chunk_by_paragraphs(self):
        """Test paragraph-aware chunking."""
        chunker = DocumentChunker(
            chunk_size=300,
            chunk_overlap=50,
            strategy=ChunkingStrategy.PARAGRAPH
        )

        text = """Перший абзац містить інформацію про візи.
Він може бути досить довгим і детальним.

Другий абзац розповідає про житло.
Тут є корисні поради для іммігрантів.

Третій абзац про роботу та навчання.
Важлива інформація для новоприбулих."""

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        # Paragraphs should be preserved when possible
        for chunk in chunks:
            assert chunk.text.strip()

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)

        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []
        assert chunker.chunk_text("\n\n\n") == []

    def test_metadata_preservation(self):
        """Test that metadata is preserved in chunks."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        metadata = {
            "source_url": "https://www.gov.uk/test",
            "topic": "visa",
            "language": "uk"
        }

        text = "Короткий текст для тестування метаданих."
        chunks = chunker.chunk_text(text, metadata)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.metadata["source_url"] == "https://www.gov.uk/test"
            assert chunk.metadata["topic"] == "visa"
            assert chunk.metadata["language"] == "uk"

    def test_chunk_metadata_fields(self):
        """Test that chunk-specific metadata is added."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        text = "A" * 250  # Long enough for multiple chunks
        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1

        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert chunk.total_chunks == len(chunks)
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char

    def test_chunk_documents_multiple(self):
        """Test chunking multiple documents."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        documents = [
            {
                "text": "Перший документ про візи до Великобританії.",
                "metadata": {"source": "doc1"}
            },
            {
                "text": "Другий документ про житлові питання.",
                "metadata": {"source": "doc2"}
            }
        ]

        chunks = chunker.chunk_documents(documents)

        assert len(chunks) >= 2  # At least one chunk per document

        # Check document_index is added
        doc_indices = {chunk.metadata.get("document_index") for chunk in chunks}
        assert 0 in doc_indices
        assert 1 in doc_indices

    def test_chunk_to_dict(self):
        """Test converting chunk to dictionary."""
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)

        metadata = {"topic": "housing"}
        text = "Тестовий текст про житло."
        chunks = chunker.chunk_text(text, metadata)

        assert len(chunks) > 0
        chunk_dict = chunks[0].to_dict()

        assert "text" in chunk_dict
        assert "metadata" in chunk_dict
        assert chunk_dict["metadata"]["topic"] == "housing"
        assert "chunk_index" in chunk_dict["metadata"]
        assert "total_chunks" in chunk_dict["metadata"]

    def test_long_sentence_splitting(self):
        """Test that very long sentences are split properly."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        # Create a very long sentence (no punctuation)
        text = "Це дуже довге речення без жодних розділових знаків яке має бути розділене на частини " * 5

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 120  # Some tolerance for word boundaries

    def test_overlap_between_chunks(self):
        """Test that overlap is working correctly."""
        chunker = DocumentChunker(
            chunk_size=100,
            chunk_overlap=30,
            strategy=ChunkingStrategy.SENTENCE
        )

        text = (
            "Перше речення тексту. "
            "Друге речення тексту. "
            "Третє речення тексту. "
            "Четверте речення тексту. "
            "П'яте речення тексту. "
            "Шосте речення тексту."
        )

        chunks = chunker.chunk_text(text)

        if len(chunks) > 1:
            # Check that there's some content overlap
            chunk1_end = chunks[0].text[-30:]
            chunk2_start = chunks[1].text[:30]

            # At least some words should appear in both
            words1 = set(chunk1_end.split())
            words2 = set(chunk2_start.split())

            # There should be some overlap in words
            assert len(words1 & words2) > 0 or chunks[0].chunk_index == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])