from bedrock_embed import embed_query
from db import search_similar_chunks


def retrieve_matches(query_text: str, top_k: int = 5):
    if not query_text:
        return []
    embedding = embed_query(query_text)
    return search_similar_chunks(embedding=embedding, top_k=top_k)
