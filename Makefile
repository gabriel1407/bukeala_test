.PHONY: help terraform-init terraform-plan terraform-apply terraform-apply-real terraform-output test clean-venv

AWS_PROFILE ?= default
TF_DIR ?= infra/terraform
TF_WORKSPACE ?= aws-real
TF_VAR_FILE ?= aws-account.tfvars
PYTHON ?= python3
VENV_DIR ?= .venv

help:
	@echo "Targets disponibles:"
	@echo "  make terraform-init   -> init + workspace aws-real + validate"
	@echo "  make terraform-plan   -> plan contra cuenta AWS"
	@echo "  make terraform-apply  -> aplica cambios en AWS"
	@echo "  make terraform-apply-real -> aplica directo en workspace aws-real"
	@echo "  make terraform-output -> muestra outputs"
	@echo "  make test             -> corre tests unitarios de Python"

terraform-init:
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) init
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace select $(TF_WORKSPACE) || AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace new $(TF_WORKSPACE)
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) validate

terraform-plan:
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace select $(TF_WORKSPACE)
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) plan -var-file=$(TF_VAR_FILE)

terraform-apply:
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace select $(TF_WORKSPACE)
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) apply -var-file=$(TF_VAR_FILE) -auto-approve

terraform-apply-real:
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace select aws-real || AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace new aws-real
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) apply -var-file=aws-account.tfvars -auto-approve

terraform-output:
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) workspace select $(TF_WORKSPACE)
	AWS_PROFILE=$(AWS_PROFILE) terraform -chdir=$(TF_DIR) output

test:
	$(PYTHON) -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install -r requirements.txt
	. $(VENV_DIR)/bin/activate && python -m unittest tests.test_upload_cv_url tests.test_get_cv tests.test_process_cv -v

clean-venv:
	rm -rf $(VENV_DIR)