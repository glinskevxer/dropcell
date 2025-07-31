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

migrations:
	$(PY) -m dropcell.tools.check_migrations

smoke:
	$(PY) -m dropcell.cli.main --version
	$(PY) -m dropcell.cli.main handbook list

check: lint typecheck migrations test smoke
	@echo "all clear"

ci: lint typecheck migrations cover smoke
	@echo "everything the pipeline runs"

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache dist build htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
