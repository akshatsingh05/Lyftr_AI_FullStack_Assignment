"""FastAPI application factory.  Run with: uvicorn app.main:create_app --factory"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.routes import router
from app.config import Settings, get_settings
from app.database import init_db, make_engine
from app.services.cache_service import configure_cache, warm_up
from app.services.failover_service import KeyPool
from app.services.llm_service import LLMService
from app.utils.logging import setup_logging

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    setup_logging()
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.validate_for_startup()  # fail fast with a readable message
        app.state.settings = settings
        app.state.engine = make_engine(settings.database_url)
        init_db(app.state.engine)
        app.state.cache_enabled = configure_cache(settings)
        if app.state.cache_enabled:
            await run_in_threadpool(warm_up)
        app.state.pool = KeyPool(settings.api_keys, settings.key_cooldown_seconds)
        app.state.llm = LLMService(settings, app.state.pool)
        app.state.session_locks = {}
        log.info("started: model=%s keys=%d cache=%s failure_simulation=%s", settings.llm_model,
                 len(app.state.pool), app.state.cache_enabled, settings.enable_failure_simulation)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="AI Chatbot API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse({"detail": "internal server error"}, status_code=500)

    return app
