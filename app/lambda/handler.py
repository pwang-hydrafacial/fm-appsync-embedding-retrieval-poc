from retrieval import retrieve_matches


def handler(event, context):
    args = event.get("arguments", {})
    query_text = args.get("queryText", "")
    top_k = args.get("topK", 5)
    return {
        "queryText": query_text,
        "matches": retrieve_matches(query_text=query_text, top_k=top_k),
    }
