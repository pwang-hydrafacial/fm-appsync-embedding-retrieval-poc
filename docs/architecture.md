# Architecture

## Overview

This POC implements semantic retrieval over GraphQL. A client submits a plain-English question; the system returns ranked text passages from a document store without exposing any vector math externally.

---

## Request Flow

```mermaid
flowchart LR
    subgraph local["Local"]
        CLI["CLI client"]
    end

    subgraph cloud["AWS"]
        AppSync["AppSync\nGraphQL API"]
        Lambda["Lambda\nresolver"]
        Bedrock["Bedrock\nTitan Embed v2"]
        SM["Secrets Manager"]
        RDS["RDS\n+ pgvector"]
    end

    CLI -->|GraphQL query| AppSync
    AppSync -->|invoke| Lambda
    Lambda -->|embed text| Bedrock
    Lambda -->|get creds| SM
    Lambda -->|vector search| RDS

    RDS -.->|top-K matches| Lambda
    Lambda -.->|response| AppSync
    AppSync -.->|matches| CLI
```

ASCII fallback:

```
┌─────────────┐
│  CLI client │  (local)
└──────┬──▲───┘
       │  │ matches
  query│  │
       ▼  │
┌─────────────────────────────────────────────────────────────────┐
│  AWS                                                             │
│                                                                  │
│  AppSync ──invoke──▶ Lambda ┬── embed text ──▶ Bedrock          │
│  GraphQL ←─response─        ├── get creds  ──▶ Secrets Manager  │
│  API                        └── vec search ──▶ RDS + pgvector   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Components

### AWS AppSync
- GraphQL API with `API_KEY` authentication
- Single query: `retrieve(queryText: String!, topK: Int): RetrievalResponse!`
- Routes all requests to the Lambda data source via a VTL resolver
- Hides the Lambda invocation details from the client entirely

### Lambda Resolver

The resolver is split into four modules, each with a single responsibility:

```
app/lambda/
├── handler.py       — AppSync entry point, parses event
├── retrieval.py     — orchestrates embed → search
├── bedrock_embed.py — calls Bedrock, returns float vector
└── db.py            — connects to RDS, runs pgvector query
```

#### `handler.py` — entry point

AppSync invokes this with a payload shaped by the VTL request template:

```python
def handler(event, context):
    args = event.get("arguments", {})
    query_text = args.get("queryText", "")
    top_k = args.get("topK", 5)
    return {
        "queryText": query_text,
        "matches": retrieve_matches(query_text=query_text, top_k=top_k),
    }
```

The AppSync VTL template that produces this event:

```vtl
{
  "version": "2018-05-29",
  "operation": "Invoke",
  "payload": {
    "arguments": $util.toJson($ctx.args)
  }
}
```

#### `retrieval.py` — pipeline orchestrator

Thin glue layer: embed the query, then search with the result.

```python
def retrieve_matches(query_text: str, top_k: int = 5):
    if not query_text:
        return []
    embedding = embed_query(query_text)
    return search_similar_chunks(embedding=embedding, top_k=top_k)
```

#### `bedrock_embed.py` — embedding

Calls Bedrock Titan Embed Text v2. The client is module-level so it is
reused across warm Lambda invocations.

```python
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
```

Key parameters:
- `dimensions: 1024` — matches the `vector(1024)` column in the DB
- `normalize: True` — unit-normalizes the vector so cosine distance == dot-product distance

#### `db.py` — pgvector search

Fetches credentials from Secrets Manager at call time, opens a connection,
runs the similarity query, and closes the connection.

```python
def search_similar_chunks(embedding: list[float], top_k: int = 5) -> list[dict]:
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn = _connect()                      # pulls creds from Secrets Manager
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
        return [{"chunkId": r[0], "documentId": r[1], "text": r[2],
                 "source": r[3], "similarityScore": float(r[4])} for r in rows]
    finally:
        conn.close()
```

Notes:
- `<=>` is pgvector's cosine distance operator (lower = more similar)
- `1 - distance` converts distance to a similarity score (higher = better match)
- `CAST(:vec AS vector)` rather than `::vector` avoids a pg8000 named-parameter parsing conflict
- `pg8000.native` is used (pure Python, no compiled binary needed in the Lambda layer)

### Amazon Bedrock — Titan Embed Text v2
- Model: `amazon.titan-embed-text-v2:0`
- Input: plain-text string
- Output: 1024-dimensional normalized float vector
- Called once per query; no caching in this version

### RDS PostgreSQL + pgvector
- Engine: PostgreSQL 16.6 on `db.t4g.micro`
- Extension: `vector` (pgvector)
- Table: `document_chunks` with a `vector(1024)` column
- Search operator: `<=>` (cosine distance)
- Sequential scan used (IVFFlat index requires ~100+ rows to be effective)

**Schema:**
```sql
CREATE TABLE document_chunks (
    chunk_id      TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL,
    text          TEXT NOT NULL,
    source        TEXT,
    embedding     vector(1024)
);
```

**Query pattern:**
```sql
SELECT chunk_id, document_id, text, source,
       1 - (embedding <=> CAST($1 AS vector)) AS similarity_score
FROM document_chunks
ORDER BY embedding <=> CAST($1 AS vector)
LIMIT $2;
```

### Secrets Manager
- Stores DB host, port, name, username, and password as a JSON secret
- Lambda fetches it at runtime; no credentials in code or environment variables

---

## Networking

```
VPC (10.0.0.0/16)
├── private-subnet-a (10.0.1.0/24, us-east-1a)
│   ├── Lambda ENI
│   └── RDS primary
├── private-subnet-b (10.0.2.0/24, us-east-1b)
│   └── RDS standby subnet (required by subnet group)
├── VPC Interface Endpoint → secretsmanager
├── VPC Interface Endpoint → bedrock-runtime
└── Internet Gateway (required for RDS public endpoint)
```

**Why VPC endpoints instead of NAT Gateway:**
Lambda needs to reach Bedrock and Secrets Manager. VPC interface endpoints (~$14/mo for two) are cheaper than a NAT Gateway (~$32/mo) and keep traffic off the public internet.

**Why RDS is publicly accessible:**
The seed script runs locally and connects directly to RDS. Making RDS publicly accessible avoids the need for a bastion host or a separate seed Lambda. The random 24-character password is the access control. Destroy with `make tf-destroy` when done.

---

## Seed Flow

```
local machine
  → reads documents.json
  → calls Bedrock to embed each chunk
  → connects to RDS public endpoint
  → INSERT INTO document_chunks (upsert on chunk_id)
```

This runs outside AWS (no Lambda involved) using the local AWS credentials.

---

## GraphQL Contract

```graphql
type Query {
  retrieve(queryText: String!, topK: Int = 5): RetrievalResponse!
}

type RetrievalResponse {
  queryText: String!
  matches: [RetrievalMatch!]!
}

type RetrievalMatch {
  documentId: String!
  chunkId:    String!
  text:       String!
  similarityScore: Float!
  source:     String
}
```

The client never sends or receives a vector. Embedding is an internal implementation detail.

---

## Cost Estimate (us-east-1, while running)

| Resource | ~$/month |
|---|---|
| RDS db.t4g.micro (20 GB gp2) | ~$13 |
| VPC endpoint × 2 | ~$14 |
| Lambda + Bedrock invocations | ~$0 at POC scale |
| **Total** | **~$27/month** |

Run `make tf-destroy` to stop all charges.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Single Lambda resolver | Simplest path; pipeline resolver is a later option |
| pgvector over a managed vector DB | Reuses existing RDS skill; cheap; destroyable |
| API_KEY auth on AppSync | Sufficient for a POC; swap to Cognito for production |
| Sequential scan (no IVFFlat) | IVFFlat requires ~100+ rows; seqscan is fine at POC scale |
| pg8000 (pure Python) | No compiled binaries needed in the Lambda layer |
| No NAT Gateway | VPC endpoints are cheaper and sufficient |
