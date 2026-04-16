import json
import os
import boto3

_client = None


def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime")
    return _client


def embed_query(query_text: str) -> list[float]:
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")
    body = json.dumps({"inputText": query_text, "dimensions": 1024, "normalize": True})
    resp = _bedrock().invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]
