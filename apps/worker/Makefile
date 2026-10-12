PY := .venv/bin
export PYTHONPATH := src:../api/src

.PHONY: install test lint run pii-report

install:
	python3.12 -m venv .venv && $(PY)/pip install -e ../api -e ".[dev]" && $(PY)/pip install -r models-requirements.txt

test:
	$(PY)/pytest -q --cov

lint:
	$(PY)/ruff check . && $(PY)/ruff format --check . && $(PY)/mypy

run:
	set -a; . ../../.env; set +a; $(PY)/python -m cda_worker.main

pii-report:
	PYTHONPATH=src:../api/src:. $(PY)/python scripts/pii_report.py
