"""Prometheus metrics and optional OpenTelemetry tracing.

Metrics are served on a separate internal port so they are never reachable through the public
ingress. Tracing is off unless OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, start_http_server

log = logging.getLogger("cda.observability")

REQUESTS = Counter("cda_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram(
    "cda_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

_metrics_server_started = False


def start_metrics_server(port: int) -> None:
    """Idempotent: the app factory can be called more than once (tests, reload)."""
    global _metrics_server_started
    if port and not _metrics_server_started:
        start_http_server(port)
        _metrics_server_started = True


def route_label(request: Request) -> str:
    """Use the route template, never the raw path, so ids do not explode label cardinality."""
    route = request.scope.get("route")
    return str(getattr(route, "path", "unmatched"))


def install_metrics_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = route_label(request)
            if route not in ("/healthz", "/readyz"):
                REQUESTS.labels(request.method, route, str(status)).inc()
                LATENCY.labels(request.method, route).observe(time.perf_counter() - started)


def setup_tracing(app: FastAPI | None, endpoint: str, service_name: str) -> bool:
    """Returns True if tracing was enabled. Requires the `otel` extra."""
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("OTEL endpoint set but the 'otel' extra is not installed; tracing disabled")
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz")
    return True


def instrument_engine(engine: object) -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=getattr(engine, "sync_engine", engine))
