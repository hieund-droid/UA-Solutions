"""Single source of truth for environment + secrets.

Rules (CLAUDE.md):
- Secrets live in `.env` (gitignored) — one `Settings` field per secret, read
  directly. Declaring them here keeps every secret the app reads discoverable in
  one place (no `os.environ[...]` scattered through the code).
- `.env` is NEVER committed. In prod the same vars are injected as environment
  variables by the deploy platform — not read from a file.
- A shared secret store (Vault) is a deferred, future option — not required
  today. See ../../docs/vault.md.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="apero-project")
    app_env: Literal["local", "dev", "staging", "prod"] = Field(default="local")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # --- Secrets ---
    # Declare one field per secret your app reads. Name it `secret_*` so pydantic
    # maps it to the matching `SECRET_*` var in `.env` (case-insensitive). Read it
    # directly at the use site — no helper, no provider:
    #     api_key = get_settings().secret_openai_api_key
    # Uncomment + add the matching line to `.env` (and `.env.example`):
    #
    #   secret_openai_api_key: str = Field(default="")
    #   secret_google_oauth_client_id: str = Field(default="")
    #   secret_google_oauth_client_secret: str = Field(default="")
    #
    # Never log the raw value — mask it (see logging_setup.py). Never commit `.env`.

    # HTTP-service / SSO fields are not declared here. They live in
    # shapes/http-service/config-additions.py and get pasted in when that
    # shape is applied. CLI / cron / worker projects don't need them.


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
