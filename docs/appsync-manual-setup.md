# AppSync Manual Configuration Guide

Step-by-step guide for manually creating or recreating the AppSync layer.
Use this when you want to inspect, edit, or rebuild these resources without running `make tf-apply`.

---

## Prerequisites

The following infrastructure must already be in place:

| Resource | Detail |
|---|---|
| VPC + subnets | `fm-appsync-embedding-retrieval-poc-vpc`, private subnets `-private-a` / `-private-b` |
| Lambda execution IAM role | `fm-appsync-embedding-retrieval-poc-lambda-role` with Bedrock + Secrets Manager + VPC policies |
| Secrets Manager | Two secrets: `.../db` (RDS1 creds) and `.../db2` (RDS2 creds) |
| RDS source 1 | `embeddingdb` database with `document_chunks` table seeded |
| RDS source 2 | `hrpolicydb` database with `policy_chunks` table seeded |
| Operator IAM permissions | `appsync:*`, `iam:CreateRole`, `iam:PutRolePolicy`, `lambda:*` |

Set your shell environment before running any commands:

```bash
export AWS_PROFILE=uiuc-pjwang
export AWS_REGION=us-east-1
```

---

## Resource map

Seven resources are required, in dependency order:

```
1. Lambda function     ← the resolver backend (embed + search + merge)
2. GraphQL API         ← top-level AppSync container
3. API key             ← authentication credential (x-api-key header)
4. GraphQL schema      ← SDL contract uploaded to the API
5. IAM role            ← grants AppSync permission to invoke Lambda
6. Lambda data source  ← registers Lambda as a named backend in AppSync
7. Resolver            ← binds Query.retrieve → Lambda data source
```

---

## Step 1 — Deploy the Lambda resolver function

The Lambda function is the retrieval backend. It embeds the query with both Bedrock models, queries both RDS instances, and returns merged results.

**Console:**
Navigate to: **AWS Console → Lambda → Functions → Create function**
URL (create): `https://console.aws.amazon.com/lambda/home?region=us-east-1#/create/function`
URL (view existing): `https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/fm-appsync-embedding-retrieval-poc-retrieval?tab=code`
```bash
make -C look lambda-create   # open create page
make -C look lambda           # open existing function
```
In the console: **Author from scratch → Runtime: Python 3.12 → name: `fm-appsync-embedding-retrieval-poc-retrieval` → use existing role: `fm-appsync-embedding-retrieval-poc-lambda-role` → VPC: select private subnets → upload zip from `build/lambda.zip`**.

**CLI:**
```bash
# 1. Build the Lambda zip and dependency layer zip
make build   # produces build/lambda.zip and build/layer.zip

# 2. Look up VPC resources
SUBNET_A=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=fm-appsync-embedding-retrieval-poc-private-a" \
  --query 'Subnets[0].SubnetId' --output text)
SUBNET_B=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=fm-appsync-embedding-retrieval-poc-private-b" \
  --query 'Subnets[0].SubnetId' --output text)
LAMBDA_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=fm-appsync-embedding-retrieval-poc-lambda" \
  --query 'SecurityGroups[0].GroupId' --output text)

# 3. Look up IAM and Secrets Manager ARNs
LAMBDA_ROLE_ARN=$(aws iam get-role \
  --role-name fm-appsync-embedding-retrieval-poc-lambda-role \
  --query 'Role.Arn' --output text)
SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id fm-appsync-embedding-retrieval-poc/db \
  --query 'ARN' --output text)
SECRET_ARN_2=$(aws secretsmanager describe-secret \
  --secret-id fm-appsync-embedding-retrieval-poc/db2 \
  --query 'ARN' --output text)

# 4. Publish the dependency layer
LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name fm-appsync-embedding-retrieval-poc-deps \
  --zip-file fileb://build/layer.zip \
  --compatible-runtimes python3.12 \
  --query 'LayerVersionArn' --output text)

# 5a. Create the function (fresh)
aws lambda create-function \
  --function-name fm-appsync-embedding-retrieval-poc-retrieval \
  --runtime python3.12 \
  --handler handler.handler \
  --zip-file fileb://build/lambda.zip \
  --role $LAMBDA_ROLE_ARN \
  --timeout 30 \
  --memory-size 256 \
  --layers $LAYER_ARN \
  --environment "Variables={
    SECRET_ARN=$SECRET_ARN,
    BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0,
    EMBEDDING_DIM=1024,
    SECRET_ARN_2=$SECRET_ARN_2,
    BEDROCK_MODEL_ID_2=cohere.embed-english-v3
  }" \
  --vpc-config "SubnetIds=$SUBNET_A,$SUBNET_B,SecurityGroupIds=$LAMBDA_SG"

# 5b. Or update an existing function's code only
aws lambda update-function-code \
  --function-name fm-appsync-embedding-retrieval-poc-retrieval \
  --zip-file fileb://build/lambda.zip
```

Capture the Lambda ARN — needed in Steps 5 and 6:
```bash
LAMBDA_ARN=$(aws lambda get-function \
  --function-name fm-appsync-embedding-retrieval-poc-retrieval \
  --query 'Configuration.FunctionArn' --output text)
```

---

## Step 2 — Create the GraphQL API

Creates the top-level AppSync API container with API key authentication.

**Console:**
Navigate to: **AWS Console → AppSync → APIs → Create API**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1`
```bash
make -C look appsync-home
```
In the console: **Create API → GraphQL API → Build from scratch → Authentication: API key → name: `fm-appsync-embedding-retrieval-poc`**.

**CLI:**
```bash
API_ID=$(aws appsync create-graphql-api \
  --name "fm-appsync-embedding-retrieval-poc" \
  --authentication-type API_KEY \
  --query 'graphqlApi.apiId' \
  --output text)

echo "export API_ID=$API_ID"
export API_ID
```

> If the API already exists, retrieve the ID instead:
> ```bash
> # From Terraform output:
> export API_ID=$(terraform -chdir=terraform output -raw appsync_url \
>   | sed -E 's|https://([^.]+)\..*|\1|')
>
> # Or from the CLI:
> export API_ID=$(aws appsync list-graphql-apis \
>   --query "graphqlApis[?name=='fm-appsync-embedding-retrieval-poc'].apiId" \
>   --output text)
> ```

`$API_ID` is required in every step from here on.

---

## Step 3 — Create an API key

Creates the credential passed in the `x-api-key` request header.

**Console:**
Navigate to: **AWS Console → AppSync → [API name] → Settings → API Keys → Create**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1#/apis/${API_ID}/v1/settings`
```bash
make -C look appsync-keys APPSYNC_API_ID=$API_ID
```
In the console: **Settings → API Keys → Create → set expiry date**.

**CLI:**
```bash
aws appsync create-api-key \
  --api-id $API_ID \
  --expires 1807228800    # 2027-04-16T00:00:00Z
```

Retrieve the key value later:
```bash
aws appsync list-api-keys --api-id $API_ID \
  --query 'apiKeys[0].id' --output text
```

---

## Step 4 — Upload the GraphQL schema

Uploads the SDL type definitions. The source of truth is `app/graphql/schema.graphql`.

**Console:**
Navigate to: **AWS Console → AppSync → [API name] → Schema**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1#/apis/${API_ID}/v1/schema`
```bash
make -C look schema APPSYNC_API_ID=$API_ID
```
In the console: **Schema → Edit schema → paste or upload `app/graphql/schema.graphql` → Save schema**.

**CLI:**
```bash
aws appsync start-schema-creation \
  --api-id $API_ID \
  --definition fileb://app/graphql/schema.graphql

# Poll until ACTIVE (usually a few seconds)
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

## Step 5 — Create the IAM role for AppSync

AppSync needs an execution role so it can call `lambda:InvokeFunction` on the retrieval Lambda.
This is a separate role from the Lambda execution role — it is assumed by AppSync, not Lambda.

**Console:**
Navigate to: **AWS Console → IAM → Roles → Create role**
URL (create): `https://console.aws.amazon.com/iamv2/home#/roles/create`
URL (view existing): `https://console.aws.amazon.com/iamv2/home#/roles/fm-appsync-embedding-retrieval-poc-appsync-role`
```bash
make -C look iam-appsync
```
In the console: **Create role → Trusted entity: AWS service → Use case: AppSync → Next → add inline policy: `lambda:InvokeFunction` on the retrieval Lambda ARN**.

**CLI:**
```bash
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

# Attach the inline policy (uses $LAMBDA_ARN set in Step 1)
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

# Capture the role ARN for Step 6
ROLE_ARN=$(aws iam get-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --query 'Role.Arn' --output text)
```

---

## Step 6 — Register the Lambda data source

Registers the Lambda function as a named data source inside AppSync.
The resolver in Step 7 references it by name (`LambdaRetrieval`).

**Console:**
Navigate to: **AWS Console → AppSync → [API name] → Data sources → Create data source**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1#/apis/${API_ID}/v1/datasources`
```bash
make -C look appsync-datasources APPSYNC_API_ID=$API_ID
```
In the console: **Data sources → Create data source → Name: `LambdaRetrieval` → Type: AWS Lambda function → select `fm-appsync-embedding-retrieval-poc-retrieval` → IAM role: use the role from Step 5 → Create**.

**CLI:**
```bash
# Uses $LAMBDA_ARN from Step 1 and $ROLE_ARN from Step 5
aws appsync create-data-source \
  --api-id $API_ID \
  --name LambdaRetrieval \
  --type AWS_LAMBDA \
  --service-role-arn $ROLE_ARN \
  --lambda-config lambdaFunctionArn=$LAMBDA_ARN
```

---

## Step 7 — Create the resolver

Binds `Query.retrieve` to the `LambdaRetrieval` data source using VTL mapping templates.
The request template wraps GraphQL arguments into the Lambda event payload; the response template passes the result through unchanged.

**Console:**
Navigate to: **AWS Console → AppSync → [API name] → Schema → click `retrieve` field on Query type → Attach resolver**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1#/apis/${API_ID}/v1/schema`
```bash
make -C look schema APPSYNC_API_ID=$API_ID
```
In the console: **Schema → click `retrieve` under the `Query` type → Attach resolver → Data source: `LambdaRetrieval` → paste templates below → Save resolver**.

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

## Step 8 — Verify

Confirm the endpoint is live and queries return results.

**Console:**
Navigate to: **AWS Console → AppSync → [API name] → Queries**
URL: `https://console.aws.amazon.com/appsync/home?region=us-east-1#/apis/${API_ID}/v1/home`
```bash
make -C look appsync APPSYNC_API_ID=$API_ID
```
In the console: **Queries tab → run the query below → confirm matches are returned**.

**CLI:**
```bash
APPSYNC_URL=$(aws appsync get-graphql-api \
  --api-id $API_ID \
  --query 'graphqlApi.uris.GRAPHQL' --output text)

API_KEY=$(aws appsync list-api-keys \
  --api-id $API_ID \
  --query 'apiKeys[0].id' --output text)

curl -s -X POST "$APPSYNC_URL" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query":"query { retrieve(queryText: \"What is the leave policy?\") { matches { text similarityScore dataSource } } }"}' \
  | python3 -m json.tool
```

Or via the Makefile (reads endpoint and key from Terraform outputs):
```bash
make smoke
```

---

## Reference — resource names

| Resource | Name / Value |
|---|---|
| Lambda function | `fm-appsync-embedding-retrieval-poc-retrieval` |
| Lambda execution role | `fm-appsync-embedding-retrieval-poc-lambda-role` |
| Lambda layer | `fm-appsync-embedding-retrieval-poc-deps` |
| GraphQL API | `fm-appsync-embedding-retrieval-poc` |
| Authentication | `API_KEY` |
| API key expiry | `2027-04-16T00:00:00Z` (Unix: `1807228800`) |
| AppSync IAM role | `fm-appsync-embedding-retrieval-poc-appsync-role` |
| AppSync IAM policy | `fm-appsync-embedding-retrieval-poc-appsync-policy` |
| Data source name | `LambdaRetrieval` |
| Data source type | `AWS_LAMBDA` |
| Resolver type + field | `Query.retrieve` |

---

## Tear down AppSync only

To remove just the AppSync resources without touching Lambda or RDS:

```bash
# Delete resolver first (it depends on the data source)
aws appsync delete-resolver --api-id $API_ID --type-name Query --field-name retrieve

# Delete data source
aws appsync delete-data-source --api-id $API_ID --name LambdaRetrieval

# Delete the API (also removes schema and all API keys)
aws appsync delete-graphql-api --api-id $API_ID

# Delete the AppSync IAM role
aws iam delete-role-policy \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role \
  --policy-name fm-appsync-embedding-retrieval-poc-appsync-policy

aws iam delete-role \
  --role-name fm-appsync-embedding-retrieval-poc-appsync-role
```
