import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    payload = {
        "queryText": args.query,
        "matches": [
            {
                "documentId": "doc-001",
                "chunkId": "chunk-001",
                "text": "CLI placeholder result. Wire AppSync call next.",
                "similarityScore": 0.99,
                "source": "placeholder",
            }
        ],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
