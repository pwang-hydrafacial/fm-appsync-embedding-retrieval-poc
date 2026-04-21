"""
Seed sample data into both RDS pgvector instances.
Source 1 (document_chunks): call-center docs embedded with Bedrock Titan Embed v2.
Source 2 (policy_chunks):   HR policies embedded with Cohere Embed English v3.
Reads connection info from Terraform outputs + Secrets Manager.
Run after `make tf-apply`.
"""
import json
import os
import subprocess
from pathlib import Path

import boto3
import pg8000.native


SAMPLE_DOCS = Path(__file__).parent / "sample_data" / "documents.json"
SAMPLE_POLICIES = Path(__file__).parent / "sample_data" / "hr_policies.json"
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


def embed_titan(text: str, bedrock, model_id: str) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": EMBEDDING_DIM, "normalize": True})
    resp = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]


def embed_cohere(text: str, bedrock, model_id: str) -> list[float]:
    body = json.dumps({"texts": [text], "input_type": "search_document"})
    resp = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embeddings"][0]


def seed_source1(creds: dict, bedrock, region: str) -> int:
    conn = pg8000.native.Connection(
        host=creds["host"],
        port=int(creds["port"]),
        database=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
    )
    print("\n[Source 1] Connected to documents RDS. Setting up schema...")
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

    model_id = "amazon.titan-embed-text-v2:0"
    docs = json.loads(SAMPLE_DOCS.read_text())
    inserted = 0
    for doc in docs:
        for chunk in doc["chunks"]:
            print(f"  Embedding {chunk['chunkId']} (Titan v2)...")
            vec = embed_titan(chunk["text"], bedrock, model_id)
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
    return inserted


def seed_source2(creds: dict, bedrock, region: str) -> int:
    conn = pg8000.native.Connection(
        host=creds["host"],
        port=int(creds["port"]),
        database=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
    )
    print("\n[Source 2] Connected to HR policy RDS. Setting up schema...")
    conn.run("CREATE EXTENSION IF NOT EXISTS vector")
    conn.run(f"""
        CREATE TABLE IF NOT EXISTS policy_chunks (
            chunk_id    TEXT PRIMARY KEY,
            policy_id   TEXT NOT NULL,
            text        TEXT NOT NULL,
            category    TEXT,
            source      TEXT,
            embedding   vector({EMBEDDING_DIM})
        )
    """)

    model_id = "cohere.embed-english-v3"
    policies = json.loads(SAMPLE_POLICIES.read_text())
    inserted = 0
    for policy in policies:
        for chunk in policy["chunks"]:
            print(f"  Embedding {chunk['chunkId']} (Cohere English v3)...")
            vec = embed_cohere(chunk["text"], bedrock, model_id)
            vec_str = "[" + ",".join(str(v) for v in vec) + "]"
            conn.run(
                """
                INSERT INTO policy_chunks (chunk_id, policy_id, text, category, source, embedding)
                VALUES (:chunk_id, :policy_id, :text, :category, :source, :vec::vector)
                ON CONFLICT (chunk_id) DO UPDATE
                    SET text = EXCLUDED.text,
                        category = EXCLUDED.category,
                        embedding = EXCLUDED.embedding
                """,
                chunk_id=chunk["chunkId"],
                policy_id=policy["policyId"],
                text=chunk["text"],
                category=policy.get("category"),
                source=chunk.get("source"),
                vec=vec_str,
            )
            inserted += 1

    conn.close()
    return inserted


def main():
    profile = os.environ.get("AWS_PROFILE", "default")
    region = os.environ.get("AWS_REGION", "us-east-1")
    print(f"Using AWS_PROFILE={profile} AWS_REGION={region}")

    outputs = tf_outputs()
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    creds1 = get_db_creds(outputs["secret_arn"], region)
    n1 = seed_source1(creds1, bedrock, region)
    print(f"[Source 1] Done. Inserted/updated {n1} chunks.")

    creds2 = get_db_creds(outputs["secret_arn_2"], region)
    n2 = seed_source2(creds2, bedrock, region)
    print(f"[Source 2] Done. Inserted/updated {n2} chunks.")

    print(f"\nTotal: {n1 + n2} chunks across both sources.")


if __name__ == "__main__":
    main()
