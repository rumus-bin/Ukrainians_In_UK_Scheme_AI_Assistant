"""Test RAG similarity scores."""

from qdrant_client import QdrantClient
import ollama

# Setup
client = QdrantClient(host='qdrant', port=6333)
ollama_client = ollama.Client(host='http://host.docker.internal:11434')

# Test queries
queries = [
    'Як продовжити візу UPE?',
    'Що робити після приїзду до UK?',
    'Де зареєструватися у NHS?',
]

for query in queries:
    print(f'\n{"="*60}')
    print(f'Query: {query}')
    print(f'{"="*60}')

    # Generate embedding
    resp = ollama_client.embed(model='mxbai-embed-large', input=query)
    query_vector = resp['embeddings'][0]

    # Search without threshold
    results = client.query_points(
        collection_name='ukraine_support_knowledge',
        query=query_vector,
        limit=5,
        score_threshold=None
    ).points

    print(f'Found {len(results)} results\n')

    if results:
        for i, hit in enumerate(results, 1):
            print(f'{i}. Score: {hit.score:.4f}')
            print(f'   Text: {hit.payload.get("text", "")[:100]}...')
            print(f'   Source: {hit.payload.get("source", "N/A")}')
            print()
    else:
        print('  No results found!')

print(f'\n{"="*60}')
print('Conclusion:')
print('If scores are below 0.55, reduce RAG_SIMILARITY_THRESHOLD in .env')
print(f'{"="*60}')
