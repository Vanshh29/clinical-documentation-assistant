PY := .venv/bin

.PHONY: install test lint migrate seed run

install:
	python3.12 -m venv .venv && $(PY)/pip install -e ".[dev]"

test:
	$(PY)/pytest -q --cov

lint:
	$(PY)/ruff check . && $(PY)/ruff format --check . && $(PY)/mypy

migrate:
	set -a; . ../../.env; set +a; $(PY)/alembic upgrade head

seed:
	set -a; . ../../.env; set +a; PYTHONPATH=src $(PY)/python -m cda_api.seed

run:
	set -a; . ../../.env; set +a; PYTHONPATH=src $(PY)/uvicorn cda_api.main:app_factory --factory --reload --port 8000
