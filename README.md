# Ledger — AI chat with automatic key failover and response caching

A full-stack chatbot (React + FastAPI + LiteLLM + SQLite) that keeps multi-turn history, fails over across a pool of API keys, caches identical requests with LiteLLM's built-in cache, and shows **per-message** source, model, latency and token usage in the UI.

```
Browser (React/Vite/Tailwind)  ──HTTP/JSON──▶  FastAPI  ──▶  LiteLLM (cache) ──▶ provider (key_1, key_2, …)
                                                   └──▶ SQLite  /data/app.db  (conversation history)
```

## 1. Live URLs

Not deployed yet — no URL has been verified, so none is listed here. After following [Deployment](#deployment), put them here:

- Frontend: _pending_
- Backend: _pending_ (`/health`)

## 2. Run locally: with Docker and without

**Prerequisites:** Docker + Docker Compose (Docker path) or Python 3.11+ and Node 20+ (manual path), and at least one provider API key (two to see failover). Default model: Gemini via a free key from <https://aistudio.google.com/apikey>.

### With Docker

```bash
cp .env.example .env        # then edit LLM_API_KEYS=key_a,key_b
make up                     # frontend http://localhost:3000   backend http://localhost:8000
make logs | make down | make build | make test
```

SQLite lives on the named volume `chat_data` mounted at `/data`, so history survives `make down`/`make up`. `make clean` deletes it.

### Without Docker

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env && edit LLM_API_KEYS      # DATABASE_URL=sqlite:///./local.db for local use
uvicorn app.main:create_app --factory --reload --port 8000

# frontend (second terminal)
cd frontend && npm install && npm run dev          # http://localhost:3000
```

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LLM_API_KEYS` | comma-separated keys → `key_1`, `key_2`, … (required) | – |
| `LLM_MODEL` | any LiteLLM model string | `gemini/gemini-2.0-flash` |
| `LLM_API_BASE` | optional OpenAI-compatible endpoint | empty |
| `DATABASE_URL` | SQLite URL | `sqlite:////data/app.db` |
| `ALLOWED_ORIGINS` | CORS origins, comma-separated | `http://localhost:3000` |
| `ENABLE_FAILURE_SIMULATION` | honour `X-Simulate-Failure` | `false` (`true` in `.env.example`) |
| `CACHE_ENABLED`, `CACHE_TTL_SECONDS` | LiteLLM cache | `true`, 7 days |
| `LLM_TIMEOUT_SECONDS`, `KEY_COOLDOWN_SECONDS`, `MAX_CONTEXT_MESSAGES` | tuning | 30, 30, 100 |
| `VITE_API_BASE_URL` | backend URL baked into the frontend at build time | `http://localhost:8000` |

Startup validation refuses to boot with an empty/placeholder/duplicate key list, a non-SQLite URL or empty CORS list, and prints what to fix.

### API

| Endpoint | Notes |
|---|---|
| `GET /health` | `{"status":"ok","keys_configured":2,"cache_enabled":true}`; `503` if SQLite or the key pool is unavailable |
| `POST /chat` | body `{session_id (1–128), message (1–4000 after trim), system_prompt?}` → `{session_id, reply, metadata}`; `422` on invalid input, `503 {"detail":"all providers unavailable"}` when every key fails |
| `GET /sessions/{id}/messages` | chronological history without system prompt, assistant messages carry `metadata`; `404` for unknown sessions |

```bash
# normal chat
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"session_id":"s-demo1","message":"What is the capital of France?"}'

# cache hit: same input, NEW session
curl -s localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"session_id":"s-demo2","message":"What is the capital of France?"}'

# simulated key_1 failure -> key_2 answers (key_id "key_2", fallback_attempts 1)
curl -s localhost:8000/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"s-demo3","message":"What is the capital of France?"}'

# all keys fail -> 503 {"detail":"all providers unavailable"}
curl -si localhost:8000/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"s-demo4","message":"hello"}'

# history
curl -s localhost:8000/sessions/s-demo2/messages
```

### Tests

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q    # or: make test
```

38 tests cover all 18 required scenarios plus cooldown, CORS, startup validation and key-leak checks. They run against a **real local HTTP stub provider** (OpenAI-compatible), so LiteLLM's real cache, error mapping and HTTP path are exercised; nothing inside LiteLLM is mocked.

### Deployment

**Backend → Render** (Docker, persistent disk; disks need a paid instance). `render.yaml` is included.
1. Push this repo to GitHub. 2. Render → *New → Blueprint* → select the repo. 3. Set `LLM_API_KEYS` and `ALLOWED_ORIGINS` (your frontend origin, no trailing slash) in the dashboard. 4. Confirm the disk mounts at `/data` and `GET /health` is green. The container honours `$PORT`. Railway/Fly work the same way: Dockerfile in `backend/`, volume at `/data`, same env vars.

**Frontend → Vercel/Netlify.** Root directory `frontend`, build `npm run build`, output `dist`, env `VITE_API_BASE_URL=https://<your-backend>`. (`vercel.json` / `netlify.toml` provide the SPA fallback.) Then add the resulting origin to the backend's `ALLOWED_ORIGINS` and redeploy it. Set `ENABLE_FAILURE_SIMULATION=false` in production unless you want the demo hook live.

## 3. Design decisions: key fallback, caching, SQLite session storage

**Key fallback.** `LLM_API_KEYS` becomes a `KeyPool` (`key_1…key_n`, config order). For each request, `llm_service` makes one pass over the pool: it calls `litellm.acompletion(api_key=<key>, num_retries=0, timeout=…)` and on 429, quota, 401/403 (dead key), 5xx, timeouts or connection errors moves to the next key. I chose an explicit loop over LiteLLM's `Router` because it makes `key_id` and `fallback_attempts` exact and deterministic (key_1 always first), and the retry bound is exactly "one attempt per key" — no hidden same-key retries. Non-retryable errors (400/content policy) return `502` immediately because another key can't help. All keys failing → `503 {"detail":"all providers unavailable"}`. Keys that *really* failed are tried last for `KEY_COOLDOWN_SECONDS` (never skipped). Exception text and keys are never returned or logged; logs carry only `key_id`.

**Failure simulation.** `X-Simulate-Failure` (`key_1=429`, `key_1=429,key_2=500`, `*=429`; codes 429/500/502/503) is parsed only when `ENABLE_FAILURE_SIMULATION=true`. A simulated key raises *before* any provider call, so real keys are untouched and nothing is persisted. While a simulation header is active the real call passes `cache={"no-cache": True}`, so a previously cached answer can't short-circuit the demo, and the fallback key returns a genuine model response.

**Caching.** `litellm.cache = Cache(type="local")`. LiteLLM's cache key is built from model + the full `messages` list (system prompt, entire history, new user message) + sampling params, and **not** `api_key`, so the same first message in a new session hits even if a different key would have served it, while any change in prompt/history misses. Hits are detected via `response._hidden_params["cache_hit"]` (not timing), report `LLM_CACHE`, `key_id: null`, `fallback_attempts: 0`, the original token counts, and a measured latency. Findings worth knowing:
- This LiteLLM release no longer supports `type="disk"`, and Redis is out of scope, so the cache is **in-memory and resets on restart** (history in SQLite does not).
- Cache hits import extra LiteLLM modules (`orjson`, `soundfile`, …) shipped in the `litellm[proxy]` extra. Without them hits **silently fall through to live calls**, hence that dependency, plus a startup warm-up so the first hit isn't slow.
- LiteLLM writes cache entries in a background task; the service yields briefly after a live response so an immediate repeat request still hits.
- `mock_response` bypasses the cache, which is why tests use a real HTTP stub instead.

**SQLite session storage.** One `messages` table (schema from the spec, indexed on `session_id`, ISO-8601 UTC timestamps, assistant metadata as JSON in the `metadata` column). The frontend sends only the new message; the backend rebuilds `[system?] + history + new message`. A turn (user + assistant rows) is written in one transaction only after success, so failures never touch history. Turns within a session are serialized by an `asyncio.Lock`. WAL mode is on. History sent to the model is capped at the last `MAX_CONTEXT_MESSAGES`. The system prompt is sent per request, never stored or returned. Token accounting: `input_tokens` = provider-reported prompt tokens for this request (system + history + new message), `output_tokens` = this reply only; nothing is cumulative.

## 4. Verification: how to see failover, cache hits and per-message token usage

1. Open <http://localhost:3000>, send "What is the capital of France?". Under the reply: `LIVE_INFERENCE`, model, `NNN ms`, `Input: N tokens`, `Output: N tokens`.
2. Click **New chat** (new session id), send the identical message: badge turns amber `LLM_CACHE`, same text and token counts, latency a few ms.
3. Send a follow-up in one chat: its input tokens grow (history is included), output tokens stay per-reply.
4. Failover (curl): `-H 'X-Simulate-Failure: key_1=429'` → `key_id: "key_2"`, `fallback_attempts: 1`, even for a message that is already cached. `*=429` → 503, and `GET /sessions/<id>/messages` for that session is 404 (nothing stored).
5. Real (not simulated) failover: put an invalid key first in `LLM_API_KEYS`; the response shows `key_2`.

Measured during development against a stub provider (live 448 ms → cache hit 2–5 ms; the stub is not a real LLM, so real live latency will be higher).

## 5. Setup Used: your editor and AI tools

Built by Claude (Anthropic) in a sandboxed Linux environment with Python 3.12, Node 22, LiteLLM 1.110.3, FastAPI 0.165, SQLModel 0.0.50, Vite 5 and Tailwind 3. Edit this section with your own editor/tools before submitting.

## 6. Bonus features (if any): what you added beyond the requirements and why

- Key cooldown ordering (avoid paying a timeout on a known-dead key every request).
- Per-session locking, history cap, 502 for non-retryable provider errors.
- Startup config validation with actionable messages; secret-safe `PooledKey` repr; key-leak test.
- Copy-reply button, auto-scroll, restore-draft-on-failure, connection indicator, mobile drawer sidebar, reduced-motion support, `render.yaml`, `vercel.json`, `netlify.toml`.
