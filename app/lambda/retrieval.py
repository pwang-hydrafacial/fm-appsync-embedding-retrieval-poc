from bedrock_embed import embed_titan, embed_cohere
from db import search_source1, search_source2


def retrieve_matches(query_text: str, top_k: int = 5):
    if not query_text:
        return []
    emb1 = embed_titan(query_text)
    emb2 = embed_cohere(query_text)
    merged = search_source1(emb1, top_k) + search_source2(emb2, top_k)
    merged.sort(key=lambda x: x["similarityScore"], reverse=True)
    return merged[:top_k]
