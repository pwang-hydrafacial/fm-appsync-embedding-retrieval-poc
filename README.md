# fm-appsync-embedding-retrieval-poc

AWS AppSync embedding retrieval POC.

## Goal
Build a cheap first-pass POC that exposes semantic retrieval through GraphQL:
- client sends question text
- AppSync receives the GraphQL query
- Lambda generates embeddings with Amazon Bedrock
- PostgreSQL + pgvector performs similarity search
- API returns matching text chunks

## Scope
- RDS PostgreSQL + pgvector
- AWS AppSync
- Lambda resolver
- Bedrock embedding generation
- Python CLI client
- Terraform-based infrastructure

## Repo boundary
This is the implementation repo intended for Claude Code and GitHub.
Internal Hermes continuity/project memory is maintained separately under `~/.hermes/knowledge-base/projects/aws-appsync-embedding-retrieval-poc/`.

## Initial architecture
1. GraphQL query takes `queryText`
2. AppSync invokes a single Lambda resolver
3. Lambda calls Bedrock to create query embedding
4. Lambda queries pgvector in RDS PostgreSQL
5. Lambda returns top matching chunks

## First-pass response shape
- queryText
- matches[]
  - documentId
  - chunkId
  - text
  - similarityScore
  - source

## AWS execution model
Use shell-provided AWS credentials only:
- `AWS_PROFILE=<profile>`
- `AWS_REGION=us-east-1`

Do not hardcode credentials or secrets.

## Quick start targets
- `make bootstrap`
- `make tf-init`
- `make tf-plan`
- `make tf-apply`
- `make seed`
- `make query q="What is ...?"`
- `make smoke`
- `make tf-destroy`

## Status
Initial skeleton only.
