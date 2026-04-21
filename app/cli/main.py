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
query Retrieve($queryText: String!, $topK: Int) {
  retrieve(queryText: $queryText, topK: $topK) {
    queryText
    matches {
      documentId
      chunkId
      text
      similarityScore
      source
      dataSource
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

    matches = result["data"]["retrieve"]["matches"]
    print(f"\nQuery: {args.query}")
    print(f"Matches ({len(matches)}):\n")
    for i, m in enumerate(matches, 1):
        print(f"  [{i}] score={m['similarityScore']:.4f}  source={m['source']}  dataSource={m['dataSource']}")
        print(f"      {m['text']}\n")


if __name__ == "__main__":
    main()
