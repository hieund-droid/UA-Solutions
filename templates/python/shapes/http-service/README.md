# shapes/http-service — convert this project to a FastAPI HTTP service

The base `templates/python/` ships **shape-agnostic** — a CLI / cron / worker is the default. This folder holds everything you add **only if** the project accepts inbound HTTP from users.

**Don't run this folder.** It's a set of files you copy / merge into the project root and into `src/`.

## When to apply this shape

Apply if **any** of these are true:
- Users will call HTTP endpoints on this service from a browser, Apps Script, another service, or a script.
- You need authn/authz on inbound requests (`hq-apero-sso`).
- You're building a webhook receiver.

If the project is invoked by `python -m src.main` from a terminal, a cron, or a queue consumer — **do not apply this shape.** Stay on the base.

## Apply the shape

From the project root (where the base `templates/python/` was copied):

```bash
SHAPE=shapes/http-service           # path inside this template repo

# 1. Replace src/main.py and add src/auth.py
cp -R "$SHAPE/src/." src/

# 2. Add HTTP-service deps to requirements.txt
cat "$SHAPE/requirements-add.txt" >> requirements.txt

# 3. Add HTTP-service env vars to .env.example
cat "$SHAPE/env-additions.txt" >> .env.example
#    (and to your local .env, if you've already created it)

# 4. Add EXPOSE 8000 to the Dockerfile (before the final CMD line)
#    Open Dockerfile and paste:  EXPOSE 8000

# 5. Add docker-compose.yml
cp "$SHAPE/docker-compose.yml" docker-compose.yml

# 6. Replace the FastAPI smoke test
cp "$SHAPE/tests/test_health.py" tests/test_health.py

# 7. Add the HTTP/SSO Settings fields to src/config.py
#    Open src/config.py — copy the field declarations from $SHAPE/config-additions.py
#    into the `Settings` class.

# 8. Install the new deps
python -m pip install -r requirements.txt
```

## What you now have

- `python -m src.main` boots FastAPI + uvicorn on `APP_PORT` (default 8000). Swagger UI at `/docs`.
- `src/auth.py::get_current_user` — protect routes with `user: User = Depends(get_current_user)`.
- `src/auth.py::require_group("g")` — group-based authz.
- `src/auth.py::verify_apps_script_caller("g")` — for endpoints called from Google Apps Script (sheet buttons / triggers). See `docs/google-apps-script.md`.

## Rules that activate with this shape

(All of these are inert until you apply this shape.)

- **Protected routes only via `Depends(get_current_user)` / `Depends(require_group(...))`.** Never parse tokens elsewhere.
- **Request/response shapes: pydantic models.** Never accept raw `dict`.
- **Async-native libs** (`httpx`, `asyncpg`). Sync code in an async handler → `run_in_threadpool`.
- **Tests mock SSO at `get_current_user`**, not deeper. No real network in tests.
- **Apps Script callers** use `src/auth.py::verify_apps_script_caller(group)`. Full pattern: `docs/google-apps-script.md`.

## Rolling back

If you applied this shape by mistake: `git checkout` the modified files and `git rm src/auth.py docker-compose.yml`. The base template is shape-agnostic — nothing else depends on these.
