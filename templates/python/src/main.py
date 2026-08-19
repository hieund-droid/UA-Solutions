"""Apero Python entry point.

Run with:   python -m src.main

This is the shape-agnostic default. Out of the box it logs "hello" and exits —
your job is to fill in what the program actually does.

If this project is going to accept inbound HTTP from users, see
`shapes/http-service/` for the FastAPI conversion. CLI / cron / worker projects
stay shaped like this file (single entry point, logger, exit).
"""

from __future__ import annotations

import logging

from src.config import get_settings
from src.logging_setup import setup_logging

setup_logging()
log = logging.getLogger("apero")
settings = get_settings()


def main() -> int:
    log.info("hello from %s (env=%s)", settings.app_name, settings.app_env)
    # TODO: replace this stub with what your program actually does.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
