# syntax=docker/dockerfile:1.7
# Build context is the repository root:  docker build -f apps/api/Dockerfile .
FROM python:3.12.15-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
RUN pip install "./apps/api[otel]"

FROM python:3.12.15-slim-bookworm
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
USER 10001:10001
EXPOSE 8000 9100
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "cda_api.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
