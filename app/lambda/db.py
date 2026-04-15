def search_similar_chunks(embedding, top_k: int = 5):
    # TODO: replace stub with PostgreSQL + pgvector query
    return [
        {
            "documentId": "doc-001",
            "chunkId": "chunk-001",
            "text": "Sample chunk returned by stub retrieval.",
            "similarityScore": 0.99,
            "source": "sample-data",
        }
    ][:top_k]
