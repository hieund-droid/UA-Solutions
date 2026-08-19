"""Configure the root logger from the LOG_LEVEL env var.

Call setup_logging() exactly once, at the top of every entrypoint
(main.py, main-queue.py, etc.) before any other code logs anything.

Masking
-------
Secrets / PII must never appear in logs as raw values. Two affordances:

  1. Pass sensitive fields via ``extra=`` — the MaskingFilter scrubs known
     field names automatically:
         log.info("login", extra={"user": uid, "password": pw})
         # → "login user=42 password=***"

  2. For deliberate partial masking ("show last 4"), call mask() yourself:
         log.info("api call with key=%s", mask(api_key))
         # → "api call with key=…cdef"

Passwords and full tokens: do NOT log at all — not even masked. Log the user
ID, not the token.
"""

from __future__ import annotations

import logging
import os

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "id_token",
    "secret", "client_secret", "api_key", "apikey",
    "authorization", "auth", "cookie", "session",
    "credit_card", "card_number", "cvv", "ssn",
})

_REDACTED = "***"


def mask(value: object, *, keep: int = 4) -> str:
    """Partial-mask a value: replace all but the last ``keep`` chars with ``…``.

    Use for values you intentionally want partially visible in logs
    (e.g. an API key suffix for debugging). Never use as an excuse to log
    a password or full token — those should not be logged at all.
    """
    if value is None:
        return _REDACTED
    s = str(value)
    if len(s) <= keep:
        return _REDACTED
    return f"…{s[-keep:]}"


class MaskingFilter(logging.Filter):
    """Scrub known-sensitive keys from ``extra`` fields before formatting.

    Matched case-insensitively against ``_SENSITIVE_KEYS``. Standard
    LogRecord attributes (``name``, ``msg``, ``levelname``, …) are never
    in that set, so they pass through untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key.lower() in _SENSITIVE_KEYS:
                record.__dict__[key] = _REDACTED
        if isinstance(record.args, dict):
            record.args = {
                k: (_REDACTED if str(k).lower() in _SENSITIVE_KEYS else v)
                for k, v in record.args.items()
            }
        return True


def setup_logging() -> None:
    raw = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = raw if raw in _VALID_LEVELS else "INFO"
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    masking = MaskingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(masking)
    if raw not in _VALID_LEVELS:
        logging.getLogger(__name__).warning(
            "LOG_LEVEL=%r is not one of %s — falling back to INFO", raw, sorted(_VALID_LEVELS)
        )
