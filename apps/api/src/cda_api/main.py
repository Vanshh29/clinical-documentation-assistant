import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from cda_api.adapters.db.session import make_engine, make_session_factory
from cda_api.api.routers import admin, auth, notes
from cda_api.config import Settings, get_settings
from cda_api.domain.errors import (
    AuthenticationFailed,
    Forbidden,
    InvalidTransition,
    NotFound,
    ValidationFailed,
)
from cda_api.logging_setup import configure_logging
from cda_api.observability import (
    install_metrics_middleware,
    instrument_engine,
    setup_tracing,
    start_metrics_server,
)

log = logging.getLogger("cda.api")

DISCLAIMER = "Demo only. Not a medical device. Not for real patient data."


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        if tracing:
            instrument_engine(engine)
        start_metrics_server(settings.metrics_port)
        app.state.session_factory = make_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(
        title="Clinical Documentation Assistant API",
        version="0.1.0",
        description=DISCLAIMER,
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_metrics_middleware(app)
    tracing = setup_tracing(app, settings.otel_exporter_otlp_endpoint, settings.service_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id[:64]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def _problem(status_code: int, detail: str) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": detail})

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound) -> JSONResponse:
        return _problem(404, str(exc))

    @app.exception_handler(Forbidden)
    async def _fb(_: Request, exc: Forbidden) -> JSONResponse:
        return _problem(403, str(exc))

    @app.exception_handler(AuthenticationFailed)
    async def _af(_: Request, exc: AuthenticationFailed) -> JSONResponse:
        return _problem(401, str(exc))

    @app.exception_handler(InvalidTransition)
    async def _it(_: Request, exc: InvalidTransition) -> JSONResponse:
        return _problem(409, str(exc))

    @app.exception_handler(ValidationFailed)
    async def _vf(_: Request, exc: ValidationFailed) -> JSONResponse:
        return _problem(422, str(exc))

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz(request: Request) -> JSONResponse:
        try:
            async with request.app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness check failed")
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ready"})

    app.include_router(auth.router)
    app.include_router(notes.router)
    app.include_router(admin.router)
    return app


def app_factory() -> FastAPI:
    return create_app()
