# AppSync Manual Configuration Guide

Step-by-step guide for manually creating or recreating the AppSync layer.
Use this when you want to inspect, edit, or rebuild the AppSync resources without running `make tf-apply`.

---

## Prerequisites

The following must already be in place before starting:

| Resource | Detail |
|---|---|
| Lambda function | `fm-appsync-embedding-retrieval-poc-retrieval` deployed in `us-east-1` |
| RDS source 1 | `embeddingdb` database with `document_chunks` table seeded |
| RDS source 2 | `hrpolicydb` database with `policy_chunks` table seeded |
| Operator IAM permissions | `appsync:*`, `iam:CreateRole`, `iam:PutRolePolicy`, `lambda:GetFunction` |

Set your shell environment before running any commands:

```bash
export AWS_PROFILE=uiuc-pjwang
export AWS_REGION=us-east-1
```

---

## Resource map

Six AppSync resources are required, in dependency order:

```
1. GraphQL API          ← top-level container
2. API key              ← authentication credential
3. GraphQL schema       ← SDL contract uploaded to the API
4. IAM role             ← grants AppSync permission to invoke Lambda
5. Lambda data source   ← registers Lambda as a named backend
6. Resolver             ← binds Query.retrieve → Lambda data source
```

---

## Step 1 — Create the GraphQL API

Creates the top-level AppSync API container with API key authentication.

**Console:**
```bash
make -C look appsync-home
```
In the console: **Create API → GraphQL API → Build from scratch → API key authentication → name: `fm-appsync-embedding-retrieval-poc`**.

**CLI:**
```bash
API_ID=$(aws appsync create-graphql-api \
  --name "fm-appsync-embedding-retrieval-poc" \
  --authentication-type API_KEY \
  --query 'graphqlApi.apiId' \
  --output text)

echo "export API_ID=$API_ID"
```

> If the API already exists (e.g. Terraform created it), retrieve the ID instead:
> ```bash
> # From Terraform output:
> export API_ID=$(terraform -chdir=terraform output -raw appsync_url \
>   | sed -E 's|https://([^.]+)\..*|\1|')
>
> # Or directly from the CLI:
> export API_ID=$(aws appsync list-graphql-apis \
>   --query "graphqlApis[?name=='fm-appsync-embedding-retrieval-poc'].apiId" \
>   --output text)
> ```

`$API_ID` is required in every subsequent step.

---

## Step 2 — Create an API key

Creates the credential used in the `x-api-key` request header.

**Console:**
```bash
make -C look appsync-keys                        # pass API_ID if not from Terraform
make -C look appsync-keys APPSYNC_API_ID=$API_ID
```
In the console: **Settings → API Keys → Create → set expiry**.

**CLI:**
```bash
aws appsync create-api-key \
  --api-id $API_ID \
  --expires 1807228800    # 2027-04-16T00:00:00Z
```

Retrieve the key value later with:
```bash
aws appsync list-api-keys --api-id $API_ID \
  --query 'apiKeys[0].id' --output text
```

---

## Step 3 — Upload the GraphQL schema

Uploads the SDL definition. The schema file is the source of truth at `app/graphql/schema.graphql`.

**Console:**
```bash
make -C look schema APPSYNC_API_ID=$API_ID
```
In the console: **Schema → Edit schema → paste or upload `app/graphql/schema.graphql` → Save schema**.

**CLI:**
```bash
aws appsync start-schema-creation \
  --api-id $API_ID \
  --definition fileb://app/graphql/schema.graphql

# Poll until status is ACTIVE (usually a few seconds)
aws appsync get-schema-creation-status --api-id $API_ID
```

Current schema (`app/graphql/schema.graphql`):
```graphql
type Query {
  retrieve(queryText: String!, topK: Int = 5): RetrievalResponse!
}

type RetrievalResponse {
  queryText: String!
  matches: [RetrievalMatch!]!
}

type RetrievalMatch {
  documentId:      String!
  chunkId:         String!
  text:            String!
  similarityScore: Float!
  source:          String
  dataSource:      String
}
```

---

## Step 4 — Create the IAM role for AppSync

AppSync needs an execution role with `lambda:InvokeFunction` permission on the retrieval Lambda.
This role is assumed by AppSync (not Lambda) at resolver invocation time.

**Console:**
```bash
make -C look iam-appsync
```
In the console: **IAM → Roles → Create role → AWS service: AppSync → add inline policy for `lambda:InvokeFunction` on the retrieval Lambda ARN**.

**CLI:**
```bash
# Fetch the Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
  --function-name fm-appsync-embedding-retrieval-poc-retrieval \
  --query 'Configuration.FunctionArn' \
  --output text)

# Create the role with an AppSync trust policy
aws iam create-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "appsync.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach the inline policy granting Lambda invocation
aws iam put-role-policy \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --policy-name fm-appsync-embedding-retrieval-poc-appsync-policy \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"lambda:InvokeFunction\"],
      \"Resource\": \"$LAMBDA_ARN\"
    }]
  }"

# Capture ARN for the next step
ROLE_ARN=$(aws iam get-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --query 'Role.Arn' \
  --output text)
```

---

## Step 5 — Register the Lambda data source

Registers the Lambda function as a named data source inside AppSync. The resolver created in Step 6 will reference it by name (`LambdaRetrieval`).

**Console:**
```bash
make -C look appsync-datasources APPSYNC_API_ID=$API_ID
```
In the console: **Data sources → Create data source → Type: AWS Lambda function → select `fm-appsync-embedding-retrieval-poc-retrieval` → assign the IAM role created in Step 4 → name: `LambdaRetrieval`**.

**CLI:**
```bash
LAMBDA_ARN=$(aws lambda get-function \
  --function-name fm-appsync-embedding-retrieval-poc-retrieval \
  --query 'Configuration.FunctionArn' \
  --output text)

ROLE_ARN=$(aws iam get-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --query 'Role.Arn' \
  --output text)

aws appsync create-data-source \
  --api-id $API_ID \
  --name LambdaRetrieval \
  --type AWS_LAMBDA \
  --service-role-arn $ROLE_ARN \
  --lambda-config lambdaFunctionArn=$LAMBDA_ARN
```

---

## Step 6 — Create the resolver

Binds `Query.retrieve` to the `LambdaRetrieval` data source using VTL mapping templates.
The request template passes GraphQL arguments into the Lambda payload; the response template passes the result straight through.

**Console:**
```bash
make -C look schema APPSYNC_API_ID=$API_ID
```
In the console: **Schema → click `retrieve` field under `Query` type → Attach resolver → Data source: LambdaRetrieval → paste templates below → Save resolver**.

Request mapping template:
```vtl
{
  "version": "2018-05-29",
  "operation": "Invoke",
  "payload": {
    "arguments": $util.toJson($ctx.args)
  }
}
```

Response mapping template:
```vtl
$util.toJson($ctx.result)
```

**CLI:**
```bash
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Query \
  --field-name retrieve \
  --data-source-name LambdaRetrieval \
  --request-mapping-template \
    '{"version":"2018-05-29","operation":"Invoke","payload":{"arguments":$util.toJson($ctx.args)}}' \
  --response-mapping-template \
    '$util.toJson($ctx.result)'
```

---

## Step 7 — Verify

Confirm the API endpoint and run a live query.

**Console:**
```bash
make -C look appsync APPSYNC_API_ID=$API_ID
```
In the console: **API overview → copy the GraphQL endpoint URL → Queries tab → run a test query**.

**CLI:**
```bash
# Retrieve the GraphQL endpoint
aws appsync get-graphql-api \
  --api-id $API_ID \
  --query 'graphqlApi.uris.GRAPHQL' \
  --output text

# Retrieve the API key value
aws appsync list-api-keys \
  --api-id $API_ID \
  --query 'apiKeys[0].id' \
  --output text

# Run a smoke test (reads endpoint + key from Terraform outputs)
make smoke

# Or query directly without Terraform outputs
APPSYNC_URL=$(aws appsync get-graphql-api --api-id $API_ID \
  --query 'graphqlApi.uris.GRAPHQL' --output text)
API_KEY=$(aws appsync list-api-keys --api-id $API_ID \
  --query 'apiKeys[0].id' --output text)

curl -s -X POST "$APPSYNC_URL" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query":"query { retrieve(queryText: \"What is the leave policy?\") { matches { text similarityScore dataSource } } }"}' \
  | python3 -m json.tool
```

---

## Reference — resource names

| Resource | Name / Value |
|---|---|
| GraphQL API | `fm-appsync-embedding-retrieval-poc` |
| Authentication | `API_KEY` |
| API key expiry | `2027-04-16T00:00:00Z` (Unix: `1807228800`) |
| AppSync IAM role | `fm-appsync-embedding-retrieval-poc-appsync-role` |
| AppSync IAM policy | `fm-appsync-embedding-retrieval-poc-appsync-policy` |
| Data source name | `LambdaRetrieval` |
| Data source type | `AWS_LAMBDA` |
| Resolver type | `Query` |
| Resolver field | `retrieve` |
| Lambda function | `fm-appsync-embedding-retrieval-poc-retrieval` |

---

## Tear down AppSync only

To remove just the AppSync resources without touching Lambda or RDS:

```bash
# Delete resolver first (depends on data source)
aws appsync delete-resolver --api-id $API_ID --type-name Query --field-name retrieve

# Delete data source
aws appsync delete-data-source --api-id $API_ID --name LambdaRetrieval

# Delete API (also removes schema and API keys)
aws appsync delete-graphql-api --api-id $API_ID

# Delete IAM role
aws iam delete-role-policy \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --policy-name fm-appsync-embedding-retrieval-poc-appsync-policy

aws iam delete-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role
```
