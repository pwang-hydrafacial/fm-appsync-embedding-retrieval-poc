import json
import os
import boto3
import pg8000.native


def _get_secret(secret_arn: str) -> dict:
    sm = boto3.client("secretsmanager")
    return json.loads(sm.get_secret_value(SecretId=secret_arn)["SecretString"])


def _connect(secret_arn: str):
    s = _get_secret(secret_arn)
    return pg8000.native.Connection(
        host=s["host"],
        port=int(s["port"]),
        database=s["dbname"],
        user=s["username"],
        password=s["password"],
    )


def search_source1(embedding: list[float], top_k: int = 5) -> list[dict]:
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn = _connect(os.environ["SECRET_ARN"])
    try:
        rows = conn.run(
            """
            SELECT chunk_id, document_id, text, source,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similarity_score
            FROM document_chunks
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """,
            vec=vec_str,
            k=top_k,
        )
        return [
            {
                "chunkId": r[0],
                "documentId": r[1],
                "text": r[2],
                "source": r[3],
                "similarityScore": float(r[4]),
                "dataSource": "documents",
            }
            for r in rows
        ]
    finally:
        conn.close()


def search_source2(embedding: list[float], top_k: int = 5) -> list[dict]:
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn = _connect(os.environ["SECRET_ARN_2"])
    try:
        rows = conn.run(
            """
            SELECT chunk_id, policy_id, text, source,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similarity_score
            FROM policy_chunks
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """,
            vec=vec_str,
            k=top_k,
        )
        return [
            {
                "chunkId": r[0],
                "documentId": r[1],
                "text": r[2],
                "source": r[3],
                "similarityScore": float(r[4]),
                "dataSource": "hr-policies",
            }
            for r in rows
        ]
    finally:
        conn.close()
