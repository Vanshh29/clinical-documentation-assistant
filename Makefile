.PHONY: help dev up down test lint eval

help:  ## Show targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-8s %s\n", $$1, $$2}'

up:  ## Start local infrastructure (Postgres, Redpanda)
	docker compose up -d --wait

down:  ## Stop local infrastructure
	docker compose down

dev: up  ## Infra + app dev servers (apps added in later phases)
	@echo "Infra is up. App services are added in Phase 2+."

test:  ## Run all test suites (wired per app as they land)
	@for d in apps/api apps/worker apps/web; do \
	  if [ -f $$d/Makefile ]; then $(MAKE) -C $$d test || exit 1; fi; done

lint:  ## Run all linters
	@for d in apps/api apps/worker apps/web; do \
	  if [ -f $$d/Makefile ]; then $(MAKE) -C $$d lint || exit 1; fi; done

eval:  ## Run the evaluation harness (Phase 5)
	@if [ -f eval/Makefile ]; then $(MAKE) -C eval run; else echo "eval harness lands in Phase 5"; fi
