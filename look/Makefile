AWS_PROFILE ?= default
AWS_REGION ?= us-east-1
TF_DIR      ?= ../terraform
TABLE_NAME  ?= document_chunks

export AWS_PROFILE
export AWS_REGION

APP_SYNC_URL     := $(shell terraform -chdir=$(TF_DIR) output -raw appsync_url 2>/dev/null)
APPSYNC_API_ID   ?= $(shell echo "$(APP_SYNC_URL)" | sed -E 's|https://([^.]+)\..*|\1|')
LAMBDA_NAME      := $(shell terraform -chdir=$(TF_DIR) output -raw lambda_function_name 2>/dev/null)
RDS_ENDPOINT     := $(shell terraform -chdir=$(TF_DIR) output -raw rds_endpoint 2>/dev/null)
RDS_IDENTIFIER   := $(shell echo "$(RDS_ENDPOINT)" | cut -d. -f1)
APPSYNC_ROLE_NAME := $(patsubst %-retrieval,%-appsync-role,$(LAMBDA_NAME))

.PHONY: help check rds rds-query appsync schema lambda all print \
        appsync-home appsync-datasources appsync-keys iam-appsync

help:
	@echo "Open AWS Console pages for this POC"
	@echo ""
	@echo "Usage:"
	@echo "  make -C look <target> [AWS_PROFILE=<profile>] [AWS_REGION=<region>] [APPSYNC_API_ID=<id>]"
	@echo ""
	@echo "General targets:"
	@echo "  print                Show discovered Terraform values"
	@echo "  rds                  Open RDS DB instance page"
	@echo "  rds-query            Open RDS Query Editor page (table: $(TABLE_NAME))"
	@echo "  lambda               Open Lambda function page"
	@echo "  all                  Open all pages"
	@echo ""
	@echo "AppSync targets:"
	@echo "  appsync-home         Open AppSync service home (use when creating a new API)"
	@echo "  appsync              Open AppSync API overview"
	@echo "  schema               Open AppSync schema editor (also entry point for resolvers)"
	@echo "  appsync-datasources  Open AppSync data sources page"
	@echo "  appsync-keys         Open AppSync API keys / settings page"
	@echo ""
	@echo "IAM targets:"
	@echo "  iam-appsync          Open the AppSync IAM execution role"
	@echo ""
	@echo "Note: targets that require an API ID accept APPSYNC_API_ID=<id> as an override"
	@echo "      when the API was not created by Terraform."

check:
	@if [ -z "$(APP_SYNC_URL)" ] || [ -z "$(LAMBDA_NAME)" ] || [ -z "$(RDS_ENDPOINT)" ]; then \
		echo "Missing Terraform outputs."; \
		echo "Run from repo root after provisioning: make tf-apply"; \
		exit 1; \
	fi

print: check
	@echo "AWS_PROFILE    = $(AWS_PROFILE)"
	@echo "AWS_REGION     = $(AWS_REGION)"
	@echo "APP_SYNC_URL   = $(APP_SYNC_URL)"
	@echo "APPSYNC_API_ID = $(APPSYNC_API_ID)"
	@echo "LAMBDA_NAME    = $(LAMBDA_NAME)"
	@echo "RDS_ENDPOINT   = $(RDS_ENDPOINT)"
	@echo "RDS_IDENTIFIER = $(RDS_IDENTIFIER)"
	@echo "TABLE_NAME     = $(TABLE_NAME)"

rds: check
	open "https://console.aws.amazon.com/rds/home?region=$(AWS_REGION)#database:id=$(RDS_IDENTIFIER);is-cluster=false"

rds-query: check
	@echo "Query table in editor: SELECT * FROM $(TABLE_NAME) LIMIT 10;"
	open "https://console.aws.amazon.com/rds/home?region=$(AWS_REGION)#query-editor:"

appsync: check
	open "https://console.aws.amazon.com/appsync/home?region=$(AWS_REGION)#/apis/$(APPSYNC_API_ID)/v1/home"

schema: check
	open "https://console.aws.amazon.com/appsync/home?region=$(AWS_REGION)#/apis/$(APPSYNC_API_ID)/v1/schema"

lambda: check
	open "https://console.aws.amazon.com/lambda/home?region=$(AWS_REGION)#/functions/$(LAMBDA_NAME)?tab=code"

all: rds rds-query appsync schema lambda

# ── AppSync manual-setup targets ──────────────────────────────────────────────

# Step 1: open AppSync home to create a new API (no API ID needed)
appsync-home:
	open "https://console.aws.amazon.com/appsync/home?region=$(AWS_REGION)"

# Step 2: API keys / settings (also used for API key creation)
appsync-keys: check
	open "https://console.aws.amazon.com/appsync/home?region=$(AWS_REGION)#/apis/$(APPSYNC_API_ID)/v1/settings"

# Step 5: data sources list
appsync-datasources: check
	open "https://console.aws.amazon.com/appsync/home?region=$(AWS_REGION)#/apis/$(APPSYNC_API_ID)/v1/datasources"

# Step 4: AppSync IAM execution role
iam-appsync: check
	open "https://console.aws.amazon.com/iamv2/home#/roles/$(APPSYNC_ROLE_NAME)"
