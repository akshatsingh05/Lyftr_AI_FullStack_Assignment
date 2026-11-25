"""LiteLLM built-in response caching.

LiteLLM derives the cache key from the request parameters (model + full `messages`
list + sampling params). `api_key` is NOT part of the key, so a response generated
with key_1 is reusable when key_2 would have served the same request. The messages
list contains the system prompt, the whole history and the new user message, so
any difference in those produces a different key.
"""
from __future__ import annotations

import logging

import litellm
from litellm import Cache

from app.config import Settings

log = logging.getLogger(__name__)


def configure_cache(settings: Settings) -> bool:
    """Install a fresh LiteLLM cache. Returns True if caching is active."""
    if not settings.cache_enabled:
        litellm.cache = None
        return False
    # In-memory ("local") backend: the only SQLite-compatible, dependency-free type this LiteLLM
    # release supports (disk was removed; redis/s3/etc. are disallowed). Entries reset on restart.
    litellm.cache = Cache(type="local", ttl=settings.cache_ttl_seconds)
    log.info("LiteLLM in-memory cache enabled (ttl=%ss)", settings.cache_ttl_seconds)
    return True


def is_cache_hit(response) -> bool:
    """Reliable hit detection: LiteLLM sets `cache_hit` in the response's hidden params."""
    hidden = getattr(response, "_hidden_params", None) or {}
    return hidden.get("cache_hit") is True


def warm_up() -> None:
    """LiteLLM lazily imports its logging/proxy helpers the first time a cache hit is served
    (~200ms). Import them at startup so the first hit is as fast as every later one."""
    try:
        import litellm.proxy.auth.auth_utils  # noqa: F401
        import litellm.llms.anthropic.messages.native.streaming_iterator  # noqa: F401
    except Exception:  # pragma: no cover - best effort only
        log.debug("cache warm-up skipped", exc_info=True)
