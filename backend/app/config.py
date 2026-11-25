"""Environment-driven configuration with startup validation."""
from __future__ import annotations

from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    llm_api_keys: str = Field(default="", description="Comma-separated provider API keys")
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_api_base: str | None = None  # optional: OpenAI-compatible / self-hosted endpoint
    llm_timeout_seconds: float = 30.0
    llm_max_output_tokens: int = 1024
    key_cooldown_seconds: float = 30.0  # real-failure keys are tried last for this long

    database_url: str = "sqlite:////data/app.db"
    allowed_origins: str = "http://localhost:3000"
    enable_failure_simulation: bool = False

    cache_enabled: bool = True
    cache_ttl_seconds: int = 60 * 60 * 24 * 7
    max_context_messages: int = 100

    @field_validator("llm_api_keys")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def api_keys(self) -> list[str]:
        return [k.strip() for k in self.llm_api_keys.split(",") if k.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    def validate_for_startup(self) -> None:
        problems: list[str] = []
        keys = self.api_keys
        if not keys:
            problems.append("LLM_API_KEYS is empty. Set it to a comma-separated list, e.g. LLM_API_KEYS=key_one,key_two")
        elif any(k.startswith("your_") for k in keys):
            problems.append("LLM_API_KEYS still contains the placeholder values from .env.example. Add real keys.")
        if len(set(keys)) != len(keys):
            problems.append("LLM_API_KEYS contains duplicate keys; each key must be unique.")
        if not self.llm_model.strip():
            problems.append("LLM_MODEL is empty (example: gemini/gemini-2.0-flash).")
        if not self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must be a SQLite URL (e.g. sqlite:////data/app.db). SQLite is the only supported database.")
        if not self.cors_origins:
            problems.append("ALLOWED_ORIGINS is empty. Set the frontend origin, e.g. http://localhost:3000")
        if problems:
            raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
