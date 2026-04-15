# Project: fm-appsync-embedding-retrieval-poc

## Mission
Build a minimal runnable POC for semantic retrieval over GraphQL.

## Non-negotiables
- Keep this repo outside `~/.hermes`
- Use Terraform for IaC
- Use RDS PostgreSQL + pgvector for the first version
- Use AWS AppSync as the API layer
- Use one Lambda resolver first; pipeline resolver is a later option
- Client contract accepts text question, not embedding vectors
- Return text matches, not raw vectors
- Use `AWS_PROFILE` and `AWS_REGION` from the shell
- Keep the first version cheap, simple, and easy to destroy

## Build order
1. Plan before coding
2. Infra skeleton
3. GraphQL schema
4. Lambda retrieval path
5. Seed data path
6. CLI client
7. Smoke test flow
8. Tighten docs

## Coding preferences
- Prefer simple working code over over-engineering
- Make all common actions available through `make`
- Keep docs concise and operational
- Fail fast on missing config
- Keep sample data fake and small

## Expected directories
- `terraform/`
- `app/lambda/`
- `app/graphql/`
- `app/cli/`
- `app/seed/`
- `docs/`
- `scripts/`

## Do not
- Do not store credentials in repo
- Do not build a UI yet
- Do not expose embedding internals externally
- Do not overcomplicate the first pass
