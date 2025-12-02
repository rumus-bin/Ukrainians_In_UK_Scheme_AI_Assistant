#!/usr/bin/env python3
"""Test to see actual similarity scores without threshold filtering."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.vectorstore.qdrant_client import get_vector_store
from src.utils.config import get_settings

def test_scores():
    """Test similarity scores for Ukrainian query."""
    settings = get_settings()
    vs = get_vector_store()
    vs.connect()

    # Test query
    query = "Що ти можеш порадити мені робити з моєю візою після прибуття?"

    print(f"Testing query: {query}")
    print("=" * 70)

    # Direct Qdrant query to see ALL scores (bypass threshold bug)
    query_embedding = vs.get_embedding(query)

    from qdrant_client import models
    search_results = vs.client.query_points(
        collection_name=vs.collection_name,
        query=query_embedding,
        limit=10,
        # NO score_threshold to see all scores
    )

    print(f"\nFound {len(search_results.points)} results:")
    print("-" * 70)

    for i, point in enumerate(search_results.points, 1):
        score = point.score
        metadata = point.payload
        text = metadata.get('text', '')[:200]  # First 200 chars
        title = metadata.get('title', 'Unknown')
        category = metadata.get('category', 'Unknown')

        print(f"\n{i}. Score: {score:.4f}")
        print(f"   Title: {title}")
        print(f"   Category: {category}")
        print(f"   Text preview: {text}...")

    print("\n" + "=" * 70)
    if search_results.points:
        print(f"Highest score: {search_results.points[0].score:.4f}")
        print(f"Lowest score: {search_results.points[-1].score:.4f}")
    else:
        print("No results")
    print(f"Current threshold setting: {settings.rag_similarity_threshold}")

if __name__ == "__main__":
    test_scores()
