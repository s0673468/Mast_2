PYTHON ?= python3

.PHONY: check lint test

check: lint test

lint:
	$(PYTHON) scripts/static_check.py --required-notebook WSP_2V4.ipynb --required-requirements requirements.txt --require-pinned-requirements

test:
	@echo "No executable test suite configured; static validation runs in lint."
