import json
import os
import boto3

_titan_client = None
_cohere_client = None


def _bedrock_titan():
    global _titan_client
    if _titan_client is None:
        _titan_client = boto3.client("bedrock-runtime")
    return _titan_client


def _bedrock_cohere():
    global _cohere_client
    if _cohere_client is None:
        _cohere_client = boto3.client("bedrock-runtime")
    return _cohere_client


def embed_titan(query_text: str) -> list[float]:
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")
    body = json.dumps({"inputText": query_text, "dimensions": 1024, "normalize": True})
    resp = _bedrock_titan().invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]


def embed_cohere(query_text: str) -> list[float]:
    model_id = os.environ.get("BEDROCK_MODEL_ID_2", "cohere.embed-english-v3")
    body = json.dumps({"texts": [query_text], "input_type": "search_query"})
    resp = _bedrock_cohere().invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embeddings"][0]
