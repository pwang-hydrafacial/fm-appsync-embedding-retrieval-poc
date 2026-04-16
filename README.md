# fm-appsync-embedding-retrieval-poc

Semantic search over GraphQL: send a plain-English question, get back ranked text passages.

**Stack:** AWS AppSync → Lambda → Amazon Bedrock (Titan Embed v2) → RDS PostgreSQL + pgvector

---

## Prerequisites

- AWS CLI configured (`AWS_PROFILE=uiuc-pjwang AWS_REGION=us-east-1`)
- Terraform >= 1.6
- Python 3.x
- Bedrock model access enabled for `amazon.titan-embed-text-v2:0` in us-east-1
  (AWS Console → Bedrock → Model access → Request access)

---

## First-time setup

```bash
# 1. Install Python deps and build Lambda layer
make bootstrap

# 2. Initialize Terraform providers
make tf-init

# 3. Preview what will be created (28 resources)
make tf-plan

# 4. Provision everything in AWS (~7 min, ~$27/month while running)
make tf-apply

# 5. Create pgvector schema and embed + load sample docs
make seed
```

---

## Query

```bash
make query q="How should agents handle customer identity?"
```

Open related AWS Console pages:

```bash
make -C look print
make -C look appsync
make -C look schema
make -C look lambda
make -C look rds
make -C look rds-query
```

Output:
```
Query: How should agents handle customer identity?
Matches (2):

  [1] score=0.5873  source=sample-doc-1
      Agents should verify customer identity before discussing loan details.

  [2] score=0.0316  source=sample-doc-1
      Escalate servicing exceptions to the specialist queue.
```

---

## Adding your own documents

Edit `app/seed/sample_data/documents.json` following the same structure:

```json
[
  {
    "documentId": "doc-002",
    "title": "My document",
    "chunks": [
      { "chunkId": "chunk-003", "text": "...", "source": "my-doc" }
    ]
  }
]
```

Then re-run:
```bash
make seed
```

---

## Tear down

```bash
make tf-destroy
```

Destroys all AWS resources. RDS has `skip_final_snapshot = true` so no snapshot is kept.

---

## Architecture

```
CLI client
  → AppSync (GraphQL, API_KEY auth)
    → Lambda resolver
      → Secrets Manager (DB credentials)
      → Bedrock (text → 1024-dim embedding)
      → RDS PostgreSQL + pgvector (cosine similarity search)
    ← top-K matching text chunks + similarity scores
```

**Networking:** Lambda runs inside a VPC (private subnets). Bedrock and Secrets Manager are reached via VPC interface endpoints (no NAT gateway). RDS is publicly accessible so the seed script can connect from your local machine.

---

## What was provisioned

| Resource | Detail |
|---|---|
| RDS PostgreSQL 16.6 | db.t4g.micro, pgvector extension |
| Lambda | Python 3.12, 256 MB, 30s timeout |
| AppSync | API_KEY auth, expires 2027-04-16 |
| VPC endpoints | Bedrock Runtime + Secrets Manager |

AppSync URL: `https://4nua7ac2tbd6dpvmvawtcwvyem.appsync-api.us-east-1.amazonaws.com/graphql`
RDS endpoint: `fm-appsync-embedding-retrieval-poc-db.cm2vcfi9brtn.us-east-1.rds.amazonaws.com`

---

## All make targets

| Target | Description |
|---|---|
| `make bootstrap` | Create venv, install deps, build Lambda layer |
| `make build` | Rebuild Lambda layer zip only |
| `make tf-init` | Initialize Terraform providers |
| `make tf-plan` | Preview infrastructure changes |
| `make tf-apply` | Apply Terraform plan |
| `make tf-destroy` | Destroy all AWS resources |
| `make seed` | Embed and load documents into RDS |
| `make query q="..."` | Run a semantic query via AppSync |
| `make smoke` | Run a canned smoke test query |
| `make -C look <target>` | Open AWS Console pages for provisioned resources |
