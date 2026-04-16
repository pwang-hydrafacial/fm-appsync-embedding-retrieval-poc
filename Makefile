AWS_PROFILE ?= default
AWS_REGION  ?= us-east-1
PYTHON      ?= .venv/bin/python3
TF_DIR      := terraform

export AWS_PROFILE
export AWS_REGION

.PHONY: bootstrap build tf-init tf-plan tf-apply tf-destroy seed query smoke

# Install Python deps and build Lambda layer zip (run once before tf-plan)
bootstrap:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip --quiet
	. .venv/bin/activate && pip install boto3 pg8000 --quiet
	$(MAKE) build

# Build Lambda dependency layer zip
build:
	mkdir -p build/layer/python
	$(PYTHON) -m pip install \
		-r app/lambda/requirements.txt \
		--target build/layer/python \
		--quiet
	cd build/layer && zip -r ../layer.zip python/ --quiet

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-plan: build
	terraform -chdir=$(TF_DIR) plan -out=tfplan

tf-apply:
	terraform -chdir=$(TF_DIR) apply tfplan

tf-destroy:
	terraform -chdir=$(TF_DIR) destroy -auto-approve

# Seed sample data into RDS (run after tf-apply)
seed:
	$(PYTHON) app/seed/seed_data.py

# Run a semantic query: make query q="your question"
query:
	$(PYTHON) app/cli/main.py --query "$(q)"

smoke:
	@echo "Running smoke test..."
	$(MAKE) query q="How should agents handle customer identity?"
