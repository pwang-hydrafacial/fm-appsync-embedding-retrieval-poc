from retrieval import retrieve_matches_split


def handler(event, context):
    args = event.get("arguments", {})
    query_text = args.get("queryText", "")
    top_k = args.get("topK", 5)
    hr_docs, cc_docs = retrieve_matches_split(query_text=query_text, top_k=top_k)
    return {
        "queryText": query_text,
        "hrPolicyDocuments": hr_docs,
        "callCenterDocuments": cc_docs,
        "totalResults": len(hr_docs) + len(cc_docs),
        "hasMore": False,
        "nextToken": None,
    }
