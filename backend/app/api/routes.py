from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.database import check_db
from app.schemas.chat import ChatMetadata, ChatRequest, ChatResponse
from app.services import chat_store
from app.services.failover_service import SimulationHeaderError, parse_simulation
from app.services.llm_service import AllProvidersUnavailable, ProviderRejected

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    st = request.app.state
    db_ok = await run_in_threadpool(check_db, st.engine)
    keys = len(st.pool)
    body = {"status": "ok", "keys_configured": keys, "cache_enabled": st.cache_enabled}
    if not db_ok or keys == 0:
        body["status"] = "error"
        body["detail"] = "database unavailable" if not db_ok else "no API keys configured"
        return JSONResponse(body, status_code=503)
    return body


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    x_simulate_failure: str | None = Header(default=None),
):
    started = time.perf_counter()
    st = request.app.state
    settings = st.settings

    simulation: dict[str, int] = {}
    if settings.enable_failure_simulation and x_simulate_failure:  # header ignored unless explicitly enabled
        try:
            simulation = parse_simulation(x_simulate_failure, st.pool.key_ids)
        except SimulationHeaderError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None

    lock = st.session_locks.setdefault(body.session_id, asyncio.Lock())
    async with lock:  # serialize turns within one session so history stays ordered
        history = await run_in_threadpool(chat_store.load_context, st.engine, body.session_id,
                                          settings.max_context_messages)
        messages: list[dict] = []
        if body.system_prompt:
            messages.append({"role": "system", "content": body.system_prompt})
        messages += history
        messages.append({"role": "user", "content": body.message})

        try:
            result = await st.llm.complete(messages, simulation)
        except AllProvidersUnavailable:
            raise HTTPException(status_code=503, detail="all providers unavailable") from None
        except ProviderRejected:
            raise HTTPException(status_code=502, detail="provider rejected the request") from None

        metadata = ChatMetadata(
            resolution_source=result.resolution_source,
            model=result.model,
            latency_ms=int(round((time.perf_counter() - started) * 1000)),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            key_id=result.key_id,
            fallback_attempts=result.fallback_attempts,
        )
        await run_in_threadpool(chat_store.save_exchange, st.engine, body.session_id, body.message,
                                result.reply, metadata.model_dump())
    return ChatResponse(session_id=body.session_id, reply=result.reply, metadata=metadata)


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, request: Request):
    engine = request.app.state.engine
    messages = await run_in_threadpool(chat_store.list_messages, engine, session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "messages": messages}
