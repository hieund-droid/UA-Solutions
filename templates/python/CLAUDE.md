# CLAUDE.md — Python addendum

Read the master `CLAUDE.md` and `CLAUDE.AndrejKarpathy.md` first. This file only adds Python-specific items.

## Project shape — decide before writing code

**The template ships shape-agnostic.** A new project is a plain `python -m src.main` that logs "hello" and exits. *You add a shape on top.* Apero Python projects fall into one of five shapes — pick **exactly one** before substantial work:

| Shape          | Pick when…                                              | What it adds                                              |
|----------------|---------------------------------------------------------|-----------------------------------------------------------|
| **cli**        | A human runs it from a terminal: `python -m src.main …`  | `argparse` (stdlib, default) — only reach for `typer` if rich UX is genuinely needed and added to `requirements.txt`. |
| **cron / batch** | Runs on a schedule (k8s CronJob, etc.). No users.    | Structured log per iteration. Idempotent — re-running the same input produces the same output. |
| **worker / queue-consumer** | Long-running loop consuming from a queue (Redis/SQS/RabbitMQ). | One client lib in `requirements.txt`. Graceful shutdown on SIGTERM. Structured log per message. |
| **http-service** | **Inbound HTTP from users / browsers / other services / Apps Script.** | FastAPI + uvicorn + `auth.py` (`hq-apero-sso`). Apply via `shapes/http-service/README.md`. |
| **mcp-server** | Model Context Protocol server (stdio JSON-RPC) launched by an MCP host (Claude Code, Claude Desktop). **Apero default for MCP** — Python's `FastMCP` reads as English, friendly to non-coders. (Node alternative: `templates/nodejs/shapes/mcp-server/` — pick only with a JS-ecosystem reason.) **No HTTP, no port, no auth middleware.** | `mcp` (Python MCP SDK). Apply via `shapes/mcp-server/README.md`. |

**If unsure, ask the user.** Don't guess. *"Does this serve HTTP, run on a schedule, consume a queue, get called by a human at a terminal, or speak MCP?"* — one question, settles it.

**Default to non-HTTP.** Do not apply the `http-service` shape unless the user names a real need for inbound HTTP. Adding FastAPI to a cron job is the most common waste this template tries to prevent.

### Converting to http-service or mcp-server

Only when the project genuinely needs that shape. See the shape's own `README.md` for the exact steps. Do **not** inline FastAPI / the MCP SDK into the base files — keep the shape's files as the source of truth.

## Toolchain (fixed — don't substitute)

Python 3.12 · plain `pip` · `requirements.txt` (+ `requirements-dev.txt`) · `ruff` (format + lint) · `mypy` strict · `pytest` · `pydantic` v2.

`fastapi` is **shape-specific** (http-service only). `mcp` is **shape-specific** (mcp-server only). Neither is part of the base toolchain.

Forbidden substitutes: `poetry` / `pipenv` / `conda` / `uv` (template uses plain pip for maximum portability) · `black` / `flake8` / `isort` (use ruff).

## Layout — all code in `src/`, zero `.py` at the project root

**The rule:** a `.py` file never sits at the project root. All program code lives under `src/`. Tests live in `tests/` (the one allowed peer of `src/`). Everything else at root is non-code: configs, dotfiles, Dockerfile, manifests, README, CLAUDE.md, config.yaml.

```
requirements.txt
requirements-dev.txt
Dockerfile
pip.conf · mypy.ini · ruff.toml · pytest.ini · .env.example
README.md (yours — describe the product) · README.template.md (scaffold docs)
CLAUDE.md · CLAUDE.AndrejKarpathy.md
src/
  __init__.py
  main.py             # real entry point — `python -m src.main`
  config.py           # get_settings() — env + secrets, all from .env
  logging_setup.py    # setup_logging(), mask, MaskingFilter
tests/
  __init__.py
  test_health.py      # imports from src.main
shapes/               # opt-in files per project shape — see shapes/http-service/
```

**Why:** "code or not code?" should be answerable by `ls` alone. A shim at root costs the reader a context-switch every time they scan the directory — strict separation is cheaper. No "thin shim" `main.py` at root, no exceptions for entry points.

**Allowed inside `src/` (one level deep):** topical subdirs — `src/ssl/`, `src/routes/`, `src/models/`, `src/db/`. Don't go deeper until the project genuinely warrants it. Don't reintroduce topical-prefix flat naming (`ssl_*.py`, `db_*.py`) — make a folder.

Files added by shapes (when applied): see `shapes/<shape>/README.md`.

## Entry points

- **`python -m src.main` is the default.** Out of the box it just logs and exits. Fill in `main() -> int`.
- Additional entrypoints get **explicit, shape-flavored module names inside `src/`** (underscores — these are Python modules, not hyphenated scripts):
  - cli: `src/main_cli.py` → `python -m src.main_cli`
  - cron / batch: `src/main_cron.py` → `python -m src.main_cron`
  - worker: `src/main_worker.py` → `python -m src.main_worker`
  - http-service: keep `src/main.py` (boots uvicorn); add `src/web_gui.py` etc. if there's a separate UI.
- Each entrypoint calls `setup_logging()` **first**.

## Dependencies — you (the AI) do NOT install

- Add the line to `requirements.txt` (runtime) or `requirements-dev.txt` (lint/test).
- Pin with `==`. Lockfile equivalent = the pinned `requirements*.txt`.
- Tell the user: `python -m pip install -r requirements.txt` (or `-dev.txt`).
- **Never run `pip install` yourself.** The bash guard blocks it.
- **Don't add a dep without a shape-justified reason.** No `fastapi` in a cron job. No `typer` in an http-service. No `pandas` because "it might be useful".

## Logging

- Every entrypoint imports and calls `setup_logging()` before any work.
- Get a logger: `log = logging.getLogger("apero")` (or a sub-name like `"apero.queue"`).
- Never `print()` in shipped code. Use the logger.
- `LOG_LEVEL` env var controls verbosity (`DEBUG` / `INFO` / `WARNING` / `ERROR`).
- **Pass sensitive fields via `extra=`** so the `MaskingFilter` (in `logging_setup.py`) scrubs them automatically: `log.info("login", extra={"user_id": uid, "password": pw})` → `password=***`. Keys matched case-insensitively against `_SENSITIVE_KEYS`.
- For deliberate partial masking, import `mask`: `from src.logging_setup import mask` → `log.info("api key=%s", mask(api_key))` → `key=…cdef`.
- Passwords / full tokens: **don't log at all** — log the user ID, not the token.

## Patterns (shape-agnostic)

- DB: SQLAlchemy / SQLModel. Raw SQL → parameterized.
- Tests live under `tests/`. No real network. Mock external services at the seam.
- Async-native libs (`httpx`, `asyncpg`) when concurrency is needed; sync code is fine for cli/cron/worker if there's no concurrency requirement.

## Patterns (http-service shape only)

These rules **only apply once the http-service shape is applied**. Do not pre-apply them to cli/cron/worker/mcp-server.

- Protected routes: `user: User = Depends(get_current_user)`. Never parse tokens elsewhere.
- Request/response shapes: pydantic models. Never accept raw `dict`.
- Sync code in async handler → `run_in_threadpool`.
- Tests mock SSO at `get_current_user`, not deeper.
- Apps-Script-facing endpoints use `auth.py::verify_apps_script_caller(group)`. Full pattern: `docs/google-apps-script.md`.

## Patterns (mcp-server shape only)

- **stdout is the transport — DO NOT write to it.** `print(...)` is already banned; the Python `logging` module defaults to stderr, so `log.info(...)` is safe. Don't override `setup_logging()` to redirect to stdout.
- **No auth middleware.** The MCP host authenticates the user before launching this process.
- Tools are functions decorated with `@server.tool()`. Type hints become the input schema automatically — keep them accurate.

## Secrets — declared in `Settings`, read from `.env`

Every secret is declared once as a `Settings` field (named `secret_*`) and read directly. The value lives in `.env` (gitignored, never committed). No helper, no provider, no spec string — just a field.

```python
# src/config.py
class Settings(BaseSettings):
    secret_openai_api_key:             str = Field(default="")
    secret_google_oauth_client_id:     str = Field(default="")
    secret_google_oauth_client_secret: str = Field(default="")
```

```dotenv
# .env  (gitignored — paste the REAL values here, never commit)
SECRET_OPENAI_API_KEY=sk-your-real-key-here
SECRET_GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
SECRET_GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
```

```python
# call sites — read the Settings field directly
settings     = get_settings()
api_key      = settings.secret_openai_api_key
oauth_id     = settings.secret_google_oauth_client_id
oauth_secret = settings.secret_google_oauth_client_secret
```

Why declare in `Settings`: every secret a program reads is discoverable in one place — no `os.environ[...]` scattered through the code, no grep across the repo. Never log the raw value — mask it (see `logging_setup.py`).

**A shared secret store (Vault) is deferred — not required today.** `.env` (gitignored) is the current standard for every environment. When a venture later needs a shared/audited store, that's a config-layer change documented in `../../docs/vault.md`; don't wire it pre-emptively.
