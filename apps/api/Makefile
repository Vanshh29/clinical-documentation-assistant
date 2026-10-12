PY := .venv/bin

.PHONY: install test lint migrate seed run

install:
	python3.12 -m venv .venv && $(PY)/pip install -e ".[dev]"

test:
	$(PY)/pytest -q --cov

lint:
	$(PY)/ruff check . && $(PY)/ruff format --check . && $(PY)/mypy

migrate:
	$(PY)/alembic upgrade head

seed:
	PYTHONPATH=src $(PY)/python -m cda_api.seed

run:
	PYTHONPATH=src $(PY)/uvicorn cda_api.main:app_factory --factory --reload --port 8000
