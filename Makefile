.PHONY: help env dev infra up down test lint eval

help:  ## Show targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-8s %s\n", $$1, $$2}'

env:  ## Create .env with a fresh PII encryption key (never overwrites)
	@test -f .env && echo '.env already exists' || ( cp .env.example .env && \
	  KEY=$$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") && \
	  sed -i.bak "s|^PII_ENCRYPTION_KEY=.*|PII_ENCRYPTION_KEY=$$KEY|" .env && rm -f .env.bak && echo 'created .env' )

up: env  ## Build and start the whole stack: http://localhost:8080 (demo logins in README)
	docker compose up -d --build --wait

down:  ## Stop the stack (add V=1 to also delete data volumes)
	docker compose down $(if $(V),-v,)

infra:  ## Only Postgres + Redpanda, for running the apps from source
	docker compose up -d --wait postgres redpanda

dev: infra  ## Infra in Docker; start the apps from source in three terminals
	@echo "Infra is up. Now run: make -C apps/api run | make -C apps/worker run | npm --prefix apps/web run dev"

test:  ## Run all test suites (wired per app as they land)
	@for d in apps/api apps/worker apps/web eval; do \
	  if [ -f $$d/Makefile ]; then $(MAKE) -C $$d test || exit 1; fi; done

lint:  ## Run all linters
	@for d in apps/api apps/worker apps/web eval; do \
	  if [ -f $$d/Makefile ]; then $(MAKE) -C $$d lint || exit 1; fi; done

eval:  ## Run the evaluation harness (Phase 5)
	@if [ -f eval/Makefile ]; then $(MAKE) -C eval run; else echo "eval harness lands in Phase 5"; fi
