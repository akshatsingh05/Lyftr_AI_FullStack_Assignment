"""LiteLLM integration: one bounded pass over the key pool, with caching."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import litellm

from app.config import Settings
from app.services.cache_service import is_cache_hit
from app.services.failover_service import (
    EmptyProviderReply,
    KeyPool,
    SimulatedProviderError,
    error_status,
    is_retryable,
)

log = logging.getLogger(__name__)


class AllProvidersUnavailable(Exception):
    pass


class ProviderRejected(Exception):
    """Non-retryable provider error (e.g. 400 / content policy) - another key would not help."""


@dataclass
class LLMResult:
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
    resolution_source: str  # LIVE_INFERENCE | LLM_CACHE
    key_id: str | None
    fallback_attempts: int


class LLMService:
    def __init__(self, settings: Settings, pool: KeyPool):
        self.settings = settings
        self.pool = pool

    async def complete(self, messages: list[dict], simulation: dict[str, int] | None = None) -> LLMResult:
        simulation = simulation or {}
        failures = 0
        for key in self.pool.ordered():
            try:
                if key.key_id in simulation:
                    raise SimulatedProviderError(simulation[key.key_id])
                response = await self._call(key.secret, messages, bypass_cache=bool(simulation))
                reply = (response.choices[0].message.content or "").strip()
                if not reply:
                    raise EmptyProviderReply()
            except Exception as exc:  # noqa: BLE001 - classified below; message never surfaced to clients
                simulated = isinstance(exc, SimulatedProviderError)
                log.warning("key=%s failed: %s status=%s%s", key.key_id, type(exc).__name__, error_status(exc),
                            " (simulated)" if simulated else "")
                if not is_retryable(exc):
                    raise ProviderRejected() from None
                if not simulated:
                    self.pool.mark_failed(key.key_id)
                failures += 1
                continue

            hit = is_cache_hit(response)
            if not hit:
                self.pool.mark_ok(key.key_id)
                await asyncio.sleep(0.02)  # let LiteLLM's background cache write land before a repeat request
            in_tok, out_tok = self._usage(response, messages, reply)
            return LLMResult(
                reply=reply,
                model=self.settings.llm_model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                resolution_source="LLM_CACHE" if hit else "LIVE_INFERENCE",
                key_id=None if hit else key.key_id,
                fallback_attempts=failures,
            )
        raise AllProvidersUnavailable()

    async def _call(self, secret: str, messages: list[dict], bypass_cache: bool):
        kwargs: dict = dict(
            model=self.settings.llm_model,
            messages=messages,
            api_key=secret,
            timeout=self.settings.llm_timeout_seconds,
            num_retries=0,  # failover across keys is handled by our loop, not by LiteLLM's same-key retries
            max_tokens=self.settings.llm_max_output_tokens,
        )
        if self.settings.llm_api_base:
            kwargs["api_base"] = self.settings.llm_api_base
        if bypass_cache:
            # Failure demo: never let an existing cache entry short-circuit the key pool.
            kwargs["cache"] = {"no-cache": True}
        return await litellm.acompletion(**kwargs)

    def _usage(self, response, messages: list[dict], reply: str) -> tuple[int, int]:
        usage = getattr(response, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", None)
        out_tok = getattr(usage, "completion_tokens", None)
        if in_tok is None:  # provider omitted usage: count with LiteLLM's tokenizer (real count, not a guess)
            in_tok = litellm.token_counter(model=self.settings.llm_model, messages=messages)
        if out_tok is None:
            out_tok = litellm.token_counter(model=self.settings.llm_model, text=reply)
        return int(in_tok), int(out_tok)
