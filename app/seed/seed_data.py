"""
Seed sample documents into RDS pgvector.
Reads RDS connection info from Terraform outputs + Secrets Manager.
Embeds each chunk with Bedrock Titan Embed v2 before inserting.
Run after `make tf-apply`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
import pg8000.native


SAMPLE_DOCS = Path(__file__).parent / "sample_data" / "documents.json"
EMBEDDING_DIM = 1024


def tf_outputs() -> dict:
    result = subprocess.run(
        ["terraform", "-chdir=terraform", "output", "-json"],
        capture_output=True, text=True, check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def get_db_creds(secret_arn: str, region: str) -> dict:
    sm = boto3.client("secretsmanager", region_name=region)
    return json.loads(sm.get_secret_value(SecretId=secret_arn)["SecretString"])


def embed(text: str, bedrock, model_id: str) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": EMBEDDING_DIM, "normalize": True})
    resp = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]


def main():
    profile = os.environ.get("AWS_PROFILE", "default")
    region = os.environ.get("AWS_REGION", "us-east-1")

    print(f"Using AWS_PROFILE={profile} AWS_REGION={region}")

    outputs = tf_outputs()
    secret_arn = outputs["secret_arn"]
    creds = get_db_creds(secret_arn, region)

    conn = pg8000.native.Connection(
        host=creds["host"],
        port=int(creds["port"]),
        database=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
    )

    print("Connected to RDS. Setting up schema...")
    conn.run("CREATE EXTENSION IF NOT EXISTS vector")
    conn.run(f"""
        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id      TEXT PRIMARY KEY,
            document_id   TEXT NOT NULL,
            text          TEXT NOT NULL,
            source        TEXT,
            embedding     vector({EMBEDDING_DIM})
        )
    """)
    # IVFFlat needs ~100+ rows to be effective; skip index for small POC datasets

    bedrock = boto3.client("bedrock-runtime", region_name=region)
    model_id = "amazon.titan-embed-text-v2:0"
    docs = json.loads(SAMPLE_DOCS.read_text())

    inserted = 0
    for doc in docs:
        for chunk in doc["chunks"]:
            print(f"  Embedding {chunk['chunkId']}...")
            vec = embed(chunk["text"], bedrock, model_id)
            vec_str = "[" + ",".join(str(v) for v in vec) + "]"
            conn.run(
                """
                INSERT INTO document_chunks (chunk_id, document_id, text, source, embedding)
                VALUES (:chunk_id, :doc_id, :text, :source, :vec::vector)
                ON CONFLICT (chunk_id) DO UPDATE
                    SET text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding
                """,
                chunk_id=chunk["chunkId"],
                doc_id=doc["documentId"],
                text=chunk["text"],
                source=chunk.get("source"),
                vec=vec_str,
            )
            inserted += 1

    conn.close()
    print(f"Done. Inserted/updated {inserted} chunks.")


if __name__ == "__main__":
    main()
