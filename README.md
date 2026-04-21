# fm-appsync-embedding-retrieval-poc

Semantic search over GraphQL: send a plain-English question, get back ranked text passages from multiple knowledge sources.

**Stack:** AWS AppSync → Lambda → Amazon Bedrock (Titan Embed v2 + Cohere Embed English v3) → 2× RDS PostgreSQL + pgvector

---

## Prerequisites

- AWS CLI configured (`AWS_PROFILE=<your-profile> AWS_REGION=us-east-1`)
- Terraform >= 1.6
- Python 3.x
- Bedrock model access enabled in us-east-1 for:
  - `amazon.titan-embed-text-v2:0`
  - `cohere.embed-english-v3`
  (AWS Console → Bedrock → Model access → Request access)

---

## First-time setup

```bash
# 1. Install Python deps and build Lambda layer
make bootstrap

# 2. Initialize Terraform providers
make tf-init

# 3. Preview what will be created (32 resources)
make tf-plan

# 4. Provision everything in AWS (~7 min, ~$40/month while running)
make tf-apply

# 5. Embed and load sample data into both RDS instances
make seed
```

---

## Query

```bash
# Call-center domain query
make query q="How should agents handle customer identity?"

# HR policy domain query
make query q="What is the leave policy?"
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

Sample output:
```
Query: What is the leave policy?
Matches (5):

  [1] score=0.4116  source=hr-policy-leave  dataSource=hr-policies
      Parental leave of up to 12 weeks is available for primary caregivers following the birth or adoption of a child.

  [2] score=0.3624  source=hr-policy-leave  dataSource=hr-policies
      Requests for leave exceeding five consecutive days must be submitted at least two weeks in advance.

  [3] score=0.3227  source=hr-policy-leave  dataSource=hr-policies
      Employees accrue 1.5 days of paid time off per month, up to a maximum of 18 days per calendar year.

  [4] score=0.2243  source=hr-policy-onboarding  dataSource=hr-policies
      All new hires must complete mandatory compliance training within the first 30 days of employment.

  [5] score=0.2070  source=hr-policy-performance  dataSource=hr-policies
      Employees receiving a below-expectations rating must complete a 60-day performance improvement plan.
```

The `dataSource` field tells you which backend database each match came from.

---

## Data sources

| Source | Table | Embedding model | Content |
|---|---|---|---|
| `documents` | `document_chunks` | Bedrock Titan Embed v2 (1024-dim) | Call-center process docs |
| `hr-policies` | `policy_chunks` | Bedrock Cohere Embed English v3 (1024-dim) | HR policy documents |

Each source lives in its own RDS instance. The Lambda fans out to both on every query, merges the results, and re-ranks by cosine similarity score before returning.

---

## Adding your own data

**Source 1 (call-center docs):** edit `app/seed/sample_data/documents.json` following the existing structure.

**Source 2 (HR policies):** edit `app/seed/sample_data/hr_policies.json` following the existing structure. Each policy has a `category` field (e.g. `"onboarding"`, `"leave"`, `"performance"`) stored in the DB.

Re-seed after any changes:
```bash
make seed
```

---

## Tear down

```bash
make tf-destroy
```

Destroys all 32 AWS resources. Both RDS instances have `skip_final_snapshot = true`.

---

## Architecture

```
CLI client
  → AppSync (GraphQL, API_KEY auth)
    → Lambda resolver
      → Secrets Manager (credentials for both DBs)
      → Bedrock Titan Embed v2    → RDS1 (document_chunks) cosine search
      → Bedrock Cohere Embed v3   → RDS2 (policy_chunks)   cosine search
      → merge + re-rank by score
    ← top-K matches with dataSource labels
```

**Networking:** Lambda runs inside a VPC (private subnets). Both Bedrock models and Secrets Manager are reached via VPC interface endpoints (no NAT gateway). Both RDS instances are publicly accessible so the seed script can connect from your local machine.

---

## What is provisioned

| Resource | Detail |
|---|---|
| RDS PostgreSQL 16.6 (source 1) | db.t4g.micro, `document_chunks` table, Titan Embed v2 |
| RDS PostgreSQL 16.6 (source 2) | db.t4g.micro, `policy_chunks` table, Cohere Embed v3 |
| Lambda | Python 3.12, 256 MB, 30s timeout |
| AppSync | API_KEY auth, expires 2027-04-16 |
| VPC endpoints | Bedrock Runtime + Secrets Manager |

AppSync URL: `https://2z6hnrajhbegroeifhotiqxlse.appsync-api.us-east-1.amazonaws.com/graphql`  
RDS source 1: `fm-appsync-embedding-retrieval-poc-db.cm2vcfi9brtn.us-east-1.rds.amazonaws.com`  
RDS source 2: `fm-appsync-embedding-retrieval-poc-hr-db.cm2vcfi9brtn.us-east-1.rds.amazonaws.com`

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
| `make seed` | Embed and load all sample data into both RDS instances |
| `make query q="..."` | Run a semantic query via AppSync |
| `make smoke` | Run a canned smoke test query |
| `make -C look <target>` | Open AWS Console pages for provisioned resources |
