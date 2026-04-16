import json
import os
import boto3
import pg8000.native


def _get_secret() -> dict:
    sm = boto3.client("secretsmanager")
    return json.loads(sm.get_secret_value(SecretId=os.environ["SECRET_ARN"])["SecretString"])


def _connect():
    s = _get_secret()
    return pg8000.native.Connection(
        host=s["host"],
        port=int(s["port"]),
        database=s["dbname"],
        user=s["username"],
        password=s["password"],
    )


def search_similar_chunks(embedding: list[float], top_k: int = 5) -> list[dict]:
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn = _connect()
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
            }
            for r in rows
        ]
    finally:
        conn.close()
