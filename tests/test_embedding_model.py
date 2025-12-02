#!/usr/bin/env python3
"""Test embedding model with Ukrainian text."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import ollama
from src.utils.config import get_settings

def test_ukrainian_embedding():
    """Test embedding generation for Ukrainian text."""
    settings = get_settings()
    client = ollama.Client(host=settings.ollama_base_url)

    # Test cases
    test_cases = [
        "Що потрібно для отримання візи?",
        "Як зареєструватися у GP?",
        "Де знайти житло у Великій Британії?"
    ]

    print(f"Testing embedding model: {settings.ollama_embedding_model}")
    print("=" * 70)

    for i, text in enumerate(test_cases, 1):
        print(f"\nTest {i}: {text}")

        try:
            response = client.embeddings(
                model=settings.ollama_embedding_model,
                prompt=text
            )

            embedding = response.get("embedding")

            if embedding:
                print(f"✅ SUCCESS")
                print(f"   Embedding size: {len(embedding)}")
                print(f"   First 5 values: {[round(v, 3) for v in embedding[:5]]}")
            else:
                print(f"❌ FAILED: No embedding returned")
                return False

        except Exception as e:
            print(f"❌ ERROR: {e}")
            return False

    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    return True

if __name__ == "__main__":
    success = test_ukrainian_embedding()
    sys.exit(0 if success else 1)
