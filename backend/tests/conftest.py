"""Test fixtures.

A real HTTP stub provider (OpenAI-compatible) is started once per session. LiteLLM talks to it
over the network exactly as it would to Gemini/OpenAI, so LiteLLM's real cache and error mapping
are exercised - nothing in LiteLLM is mocked.
"""
from __future__ import annotations

import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

KEYS = ["test-key-1", "test-key-2"]


def _build_stub() -> FastAPI:
    stub = FastAPI()
    stub.state.failing = {}  # secret -> http status
    stub.state.calls = []    # list of secrets that reached the provider

    @stub.post("/v1/chat/completions")
    async def completions(req: Request):
        secret = req.headers.get("authorization", "").removeprefix("Bearer ")
        body = await req.json()
        stub.state.calls.append(secret)
        if secret in stub.state.failing:
            raise HTTPException(stub.state.failing[secret], "stub failure")
        msgs = body["messages"]
        last_user = next(m["content"] for m in reversed(msgs) if m["role"] == "user")
        reply = f"stub-reply[{uuid.uuid4().hex[:8]}] history={len(msgs)} to: {last_user}"
        prompt = sum(len(m["content"].split()) + 4 for m in msgs)
        completion = len(reply.split())
        return {
            "id": "cmpl-" + uuid.uuid4().hex, "object": "chat.completion", "created": int(time.time()),
            "model": body["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion},
        }

    @stub.post("/_control")
    async def control(req: Request):
        data = await req.json()
        stub.state.failing = data.get("failing", {})
        if data.get("reset_calls"):
            stub.state.calls = []
        return {}

    @stub.get("/_calls")
    async def calls():
        return stub.state.calls

    return stub


@pytest.fixture(scope="session")
def provider():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(_build_stub(), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(base + "/_calls", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)

    class Control:
        url = base

        def fail(self, **by_key):  # fail(test-key-1=429) is not valid kwargs, so use a dict
            raise NotImplementedError

        def set_failing(self, mapping: dict[str, int]):
            httpx.post(base + "/_control", json={"failing": mapping, "reset_calls": True})

        def calls(self) -> list[str]:
            return httpx.get(base + "/_calls").json()

    ctl = Control()
    yield ctl
    server.should_exit = True


@pytest.fixture
def make_client(provider, tmp_path):
    clients: list[TestClient] = []

    def _make(**overrides) -> TestClient:
        values = dict(
            llm_api_keys=",".join(KEYS), llm_model="openai/stub-model", llm_api_base=provider.url + "/v1",
            database_url=f"sqlite:///{tmp_path}/test.db", cache_enabled=True,
            enable_failure_simulation=True, key_cooldown_seconds=0, llm_timeout_seconds=10,
        )
        values.update(overrides)
        client = TestClient(create_app(Settings(_env_file=None, **values)))
        client.__enter__()
        clients.append(client)
        return client

    provider.set_failing({})
    yield _make
    for c in clients:
        c.__exit__(None, None, None)
    provider.set_failing({})


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
