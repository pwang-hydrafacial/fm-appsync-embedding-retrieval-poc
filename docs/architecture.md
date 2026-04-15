# Architecture

## Flow
1. Client submits text question to AppSync
2. AppSync calls Lambda resolver
3. Lambda requests embedding from Bedrock
4. Lambda queries RDS PostgreSQL pgvector index
5. Lambda returns top chunk matches

## Design notes
- External contract is semantic query, not vector search
- First version uses one Lambda resolver for simplicity
- Pipeline resolver remains a later option if orchestration needs to be shown explicitly
