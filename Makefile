PY ?= python

.PHONY: install lint format typecheck test cover check clean

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff format .

typecheck:
	$(PY) -m mypy

test:
	$(PY) -m pytest -q

cover:
	$(PY) -m pytest -q --cov=dropcell --cov-report=term-missing

check: lint typecheck test
	@echo "all clear"

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache dist build htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
