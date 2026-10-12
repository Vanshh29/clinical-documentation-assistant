# Uses the worker's virtualenv (Presidio, spaCy models and the pipeline code live there).
PY := ../apps/worker/.venv/bin/python
export PYTHONPATH := .:../apps/worker/src:../apps/api/src
PROVIDER ?= fake

.PHONY: run test lint thresholds

run:  ## Evaluate baseline vs fixed, write docs/eval-report.md, fail on regression (fake provider)
	$(PY) -m cda_eval --provider $(PROVIDER) $(if $(filter fake,$(PROVIDER)),--check,--variants fixed)

test:
	$(PY) -m pytest -q

lint:
	../apps/worker/.venv/bin/ruff check . && ../apps/worker/.venv/bin/ruff format --check .

thresholds:  ## Re-record the CI gate from the current run (review the diff before committing)
	$(PY) -m cda_eval --provider fake --write-thresholds
