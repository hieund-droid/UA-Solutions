"""Apero HTTP service entry point.

Run with:   python -m src.main
Replaces the base src/main.py when this project is shaped as an HTTP service.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI

from src.auth import User, get_current_user
from src.config import get_settings
from src.logging_setup import setup_logging

setup_logging()
log = logging.getLogger("apero")
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    log.debug("healthz hit")
    return {"status": "ok", "env": settings.app_env}


@app.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, object]:
    log.info("me requested by sub=%s", user.sub)
    return {"sub": user.sub, "email": user.email, "groups": list(user.groups)}


if __name__ == "__main__":
    import uvicorn

    log.info("starting on :%d (env=%s, log_level=%s)", settings.app_port, settings.app_env, settings.log_level)
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.app_port, log_level=settings.log_level.lower())
