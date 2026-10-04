.DEFAULT_GOAL := check
PYTHON ?= python3

check:
	@$(PYTHON) tests/test_round_yield.py
	@$(PYTHON) tests/test_integrations.py

demo:
	@$(PYTHON) scripts/generate_demo.py

assets:
	@$(PYTHON) assets/build.py

asset-check:
	@$(PYTHON) assets/build.py --check

.PHONY: check demo assets asset-check
