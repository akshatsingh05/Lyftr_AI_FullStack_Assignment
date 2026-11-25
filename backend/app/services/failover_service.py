"""API-key pool, failure classification and the failure-simulation hook.

Design: LiteLLM is called once per key with an explicit `api_key=` and `num_retries=0`.
We own the (bounded) retry loop - at most one attempt per configured key - so that
`key_id` and `fallback_attempts` are exact and deterministic (key_1 first, then key_2 ...).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import litellm

SUPPORTED_SIMULATED_STATUSES = {429, 500, 502, 503}
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504, 401, 403}  # 401/403 = revoked or exhausted key


class SimulationHeaderError(ValueError):
    pass


class SimulatedProviderError(Exception):
    """Raised instead of calling the provider for a key the demo header marked as failing."""

    def __init__(self, status_code: int):
        super().__init__(f"simulated provider failure ({status_code})")
        self.status_code = status_code


@dataclass(frozen=True)
class PooledKey:
    key_id: str
    secret: str

    def __repr__(self) -> str:  # never leak the secret via repr/logging
        return f"PooledKey(key_id={self.key_id!r})"


class KeyPool:
    def __init__(self, secrets: list[str], cooldown_seconds: float = 30.0):
        self.keys = [PooledKey(f"key_{i}", s) for i, s in enumerate(secrets, start=1)]
        self._cooldown = cooldown_seconds
        self._cooled_until: dict[str, float] = {}

    def __len__(self) -> int:
        return len(self.keys)

    @property
    def key_ids(self) -> list[str]:
        return [k.key_id for k in self.keys]

    def ordered(self) -> list[PooledKey]:
        """Config order, but keys that recently failed for real are tried last (never skipped)."""
        now = time.monotonic()
        fresh = [k for k in self.keys if self._cooled_until.get(k.key_id, 0) <= now]
        cooled = [k for k in self.keys if self._cooled_until.get(k.key_id, 0) > now]
        return fresh + cooled

    def mark_failed(self, key_id: str) -> None:
        if self._cooldown > 0:
            self._cooled_until[key_id] = time.monotonic() + self._cooldown

    def mark_ok(self, key_id: str) -> None:
        self._cooled_until.pop(key_id, None)


def parse_simulation(header: str | None, key_ids: list[str]) -> dict[str, int]:
    """Parse `key_1=429,key_2=500` or `*=429` into {key_id: status}."""
    if not header or not header.strip():
        return {}
    result: dict[str, int] = {}
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        name, sep, code = part.partition("=")
        name, code = name.strip(), code.strip()
        if not sep or not code.isdigit() or int(code) not in SUPPORTED_SIMULATED_STATUSES:
            raise SimulationHeaderError(
                "Invalid X-Simulate-Failure header. Use e.g. 'key_1=429', 'key_1=429,key_2=500' or '*=429' "
                f"with status in {sorted(SUPPORTED_SIMULATED_STATUSES)}."
            )
        if name == "*":
            result.update({kid: int(code) for kid in key_ids})
        elif name in key_ids:
            result[name] = int(code)
        else:
            raise SimulationHeaderError(f"Unknown key '{name}' in X-Simulate-Failure. Configured keys: {key_ids}.")
    return result


def error_status(exc: BaseException) -> int | None:
    return getattr(exc, "status_code", None)


def is_retryable(exc: BaseException) -> bool:
    """True if trying another key may help (rate limit, quota, 5xx, timeout, network, bad key)."""
    if isinstance(exc, (litellm.Timeout, litellm.APIConnectionError, EmptyProviderReply)):
        return True
    status = error_status(exc)
    if status is not None:
        return status in RETRYABLE_STATUSES or status >= 500
    return isinstance(exc, (litellm.RateLimitError, litellm.AuthenticationError, litellm.ServiceUnavailableError,
                            litellm.InternalServerError, litellm.BadGatewayError))


class EmptyProviderReply(Exception):
    """The provider answered 200 but returned no text (treated as a transient failure)."""
