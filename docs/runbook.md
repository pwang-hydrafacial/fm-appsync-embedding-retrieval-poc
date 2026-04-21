# Runbook

## Environment

```bash
export AWS_PROFILE=uiuc-pjwang
export AWS_REGION=us-east-1
```

## First-pass flow

```bash
make bootstrap   # create venv, install deps, build Lambda layer
make tf-init
make tf-plan     # verify 32 resources to add
make tf-apply    # ~7 min; provisions 2 RDS instances + Lambda + AppSync + VPC
make seed        # embeds 16 chunks into both RDS instances (Titan v2 + Cohere v3)
make smoke       # sanity check query
make tf-destroy  # tear down everything when done
```

## Bedrock model access required

Both models must be enabled in `us-east-1` before running:
- `amazon.titan-embed-text-v2:0` — source 1 (call-center docs)
- `cohere.embed-english-v3` — source 2 (HR policies)

AWS Console → Bedrock → Model access → Request access

## Data sources

| Source | RDS instance | Table | Model |
|---|---|---|---|
| `documents` | `-db` | `document_chunks` | Titan Embed v2 |
| `hr-policies` | `-hr-db` | `policy_chunks` | Cohere Embed English v3 |

`make seed` seeds both in a single run. Re-running is safe (upsert on `chunk_id`).

## Live endpoints

AppSync: `https://2z6hnrajhbegroeifhotiqxlse.appsync-api.us-east-1.amazonaws.com/graphql`  
RDS 1: `fm-appsync-embedding-retrieval-poc-db.cm2vcfi9brtn.us-east-1.rds.amazonaws.com`  
RDS 2: `fm-appsync-embedding-retrieval-poc-hr-db.cm2vcfi9brtn.us-east-1.rds.amazonaws.com`

## Sample queries

```bash
make query q="How should agents handle customer identity?"   # routes to documents
make query q="What is the leave policy?"                    # routes to hr-policies
make query q="What do I do with a servicing exception?"     # routes to documents
```

## Notes

- Two RDS instances running simultaneously costs ~$40/month. Destroy when idle.
- `dataSource` field in each match tells you which backend returned it.
- Cross-model similarity scores are approximately comparable; rankings are reliable, absolute score values are not cross-calibrated.
