"""
CLI client for the AppSync semantic retrieval API.
Usage: python app/cli/main.py --query "your question here"
Reads AppSync URL and API key from Terraform outputs.
"""
import argparse
import json
import subprocess
import urllib.request
import sys


GRAPHQL_QUERY = """
query RetrieveMatchingDocuments($queryText: String!, $topK: Int) {
  retrieveMatchingDocuments(queryText: $queryText, topK: $topK) {
    queryText
    totalResults
    hasMore
    hrPolicyDocuments {
      documentId
      chunkId
      text
      similarityScore
      source
      metadata {
        category
      }
    }
    callCenterDocuments {
      documentId
      chunkId
      text
      similarityScore
      source
      metadata {
        category
      }
    }
  }
}
"""


def tf_outputs() -> dict:
    result = subprocess.run(
        ["terraform", "-chdir=terraform", "output", "-json"],
        capture_output=True, text=True, check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def call_appsync(url: str, api_key: str, query_text: str, top_k: int) -> dict:
    body = json.dumps({
        "query": GRAPHQL_QUERY,
        "variables": {"queryText": query_text, "topK": top_k},
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-api-key": api_key},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def print_docs(label: str, docs: list) -> None:
    print(f"\n{label} ({len(docs)}):")
    for i, d in enumerate(docs, 1):
        category = (d.get("metadata") or {}).get("category", "")
        cat_str = f"  category={category}" if category else ""
        print(f"  [{i}] score={d['similarityScore']:.4f}  source={d['source']}{cat_str}")
        print(f"      {d['text']}\n")


def main():
    parser = argparse.ArgumentParser(description="Semantic retrieval via AppSync")
    parser.add_argument("--query", "-q", required=True, help="Text question to search")
    parser.add_argument("--top-k", "-k", type=int, default=5)
    args = parser.parse_args()

    outputs = tf_outputs()
    url = outputs["appsync_url"]
    api_key = outputs["appsync_api_key"]

    result = call_appsync(url, api_key, args.query, args.top_k)

    if "errors" in result:
        print("GraphQL errors:", json.dumps(result["errors"], indent=2), file=sys.stderr)
        sys.exit(1)

    data = result["data"]["retrieveMatchingDocuments"]
    print(f"\nQuery: {args.query}")
    print(f"Total results: {data['totalResults']}")
    print_docs("HR Policy Documents", data["hrPolicyDocuments"])
    print_docs("Call Center Documents", data["callCenterDocuments"])


if __name__ == "__main__":
    main()
