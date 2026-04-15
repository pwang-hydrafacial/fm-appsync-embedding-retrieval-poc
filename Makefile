AWS_PROFILE ?= default
AWS_REGION ?= us-east-1
PYTHON ?= python3
TF_DIR := terraform
CLI := app/cli/main.py
SEED := app/seed/seed_data.py

export AWS_PROFILE
export AWS_REGION

.PHONY: bootstrap fmt lint test tf-init tf-plan tf-apply seed query smoke tf-destroy

bootstrap:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	@if [ -f app/lambda/requirements.txt ]; then . .venv/bin/activate && pip install -r app/lambda/requirements.txt; fi

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-plan:
	terraform -chdir=$(TF_DIR) plan -out=tfplan

tf-apply:
	terraform -chdir=$(TF_DIR) apply tfplan

fmt:
	@echo "Add formatter later"

lint:
	@echo "Add linter later"

test:
	$(PYTHON) -m pytest -q || true

seed:
	$(PYTHON) $(SEED)

query:
	$(PYTHON) $(CLI) --query "$(q)"

smoke:
	@echo "TODO: add smoke test after infra and app wiring are implemented"

tf-destroy:
	terraform -chdir=$(TF_DIR) destroy -auto-approve
