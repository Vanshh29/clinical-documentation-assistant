# syntax=docker/dockerfile:1.7
# Build context is the repository root:  docker build -f apps/worker/Dockerfile .
FROM python:3.12.15-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
COPY apps/worker/pyproject.toml apps/worker/models-requirements.txt apps/worker/
COPY apps/worker/src apps/worker/src
RUN pip install "./apps/api[otel]" ./apps/worker \
 && pip install -r apps/worker/models-requirements.txt

FROM python:3.12.15-slim-bookworm
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    CDA_PROMPTS_DIR=/app/prompts HEARTBEAT_PATH=/tmp/cda-worker-heartbeat
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY apps/worker/prompts ./prompts
USER 10001:10001
EXPOSE 9100
HEALTHCHECK --interval=20s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-m", "cda_worker.health"]
CMD ["python", "-m", "cda_worker.main"]
