# {{project_name}} — Apero Python project (scaffold docs)

> **This file is `README.template.md` — it documents the *scaffold* this project was bootstrapped from (how to run, what's wired, shape choices). Write your own `README.md` describing what your product actually does; keep this one around (or delete it) as a quick reference. The Apero AI assistant will prefer your `README.md` once it exists.**

Generated from `hq-apero-template/templates/python`. Python 3.12, plain `pip`, `requirements.txt` — no exotic tooling.

> **Criticality:** `personal` · `team` · `production` — *replace with your choice when you start.*
> *Personal* = your own tool, you accept the risk. *Team* = used by a small group, run `/code-review` before merging. *Production* = customer-facing or holds real data — requires `#devops` review before launch.

## Pick a shape first

The template ships **shape-agnostic** — `python -m src.main` just logs "hello" and exits. Before you build anything substantial, decide which shape this project is:

| Shape          | Use when…                                              |
|----------------|--------------------------------------------------------|
| **cli**        | Humans run it from a terminal.                         |
| **cron / batch** | k8s CronJob (or similar) runs it on a schedule.      |
| **worker**     | Long-running, consumes from a queue.                   |
| **http-service** | Inbound HTTP from users / browsers / other services. |
| **mcp-server** | An MCP host (Claude Code, Claude Desktop) launches it over stdio JSON-RPC. *Python is the Apero default for MCP — Node alternative lives in `templates/nodejs/shapes/mcp-server/`.* |

For `cli` / `cron` / `worker`, **stay on the base** — fill in `main()` in `src/main.py` and add deps to `requirements.txt` as needed.

For **http-service**, follow `shapes/http-service/README.md` — it adds FastAPI, uvicorn, `auth.py` (`hq-apero-sso`), and a Swagger UI.

For **mcp-server**, follow `shapes/mcp-server/README.md` — it adds the `mcp` Python SDK and a `FastMCP` stdio scaffold. Pick this over the Node variant unless you have a specific JS-ecosystem reason.

When you're unsure, tell your AI assistant what the project does in one sentence and ask which shape fits.

## Run

```bash
# 0. Activate the Apero guardrails for this checkout (idempotent — run once after cloning)
./scripts/activate-hooks.sh        # points git at .githooks/, chmods .githooks/* + .claude/hooks/*

# 1. Create a local virtual environment (one-time)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies into the venv
python -m pip install -r requirements-dev.txt

# 3. Copy env template
cp .env.example .env

# 4. Run the app
python -m src.main
```

> **About step 0.** Every fresh clone needs to run `activate-hooks.sh` once. `core.hooksPath` lives in `.git/config` (per-clone, not committed) — without flipping it, the pre-commit gate is silent and nothing blocks staged secrets. The same script also chmods the Claude Code PreToolUse hooks under `.claude/hooks/`. Safe to re-run any time.

Out of the box, this prints a single log line and exits — fill in `main()` (or apply a shape) to make it useful.

> **Why `python -m src.main` and not `python main.py`?** All code lives in `src/`; the project root has zero `.py` files. Strict separation — "is this code?" is answerable by `ls`. See `CLAUDE.md` (Layout section).

## Entry points

- `python -m src.main` — the default. Shape-agnostic stub today.

When you add another entry point, give it a shape-flavored module name *inside `src/`* (underscores, since these are Python modules):
- `src/main_cli.py` → `python -m src.main_cli` (cli)
- `src/main_cron.py` → `python -m src.main_cron` (cron)
- `src/main_worker.py` → `python -m src.main_worker` (worker)
- (For http-service the entry stays `src/main.py` — uvicorn boots there.)

**One module per entry point. The module name is the documentation.**

## Logging

Every entrypoint calls `setup_logging()` first. Level via the `LOG_LEVEL` env var (`DEBUG` / `INFO` / `WARNING` / `ERROR`). **No `print()` in shipped code.**

```python
import logging
log = logging.getLogger("apero")
log.info("something happened: id=%s", thing_id)
```

## What's wired (base)

- **Secrets**: declared as `secret_*` fields on `config.py::Settings`, read directly (`get_settings().secret_openai_api_key`). Values live in `.env` (gitignored — never commit it). A shared secret store (Vault) is a deferred, future option, not required today — see [`docs/vault.md`](../../docs/vault.md).
- **Lint / format**: `ruff` (`ruff check . && ruff format .`).
- **Types**: `mypy` (`mypy .`).
- **Tests**: `pytest` (`pytest`).
- **Container**: `Dockerfile` non-root, pinned base image.

## What you get only when you apply a shape

- **http-service** (apply via `shapes/http-service/README.md`): FastAPI + uvicorn, `auth.py` (`hq-apero-sso`), `docker-compose.yml`, Swagger UI at `/docs`. Run `/sso-wire-up` to replace the auth stub.
- **mcp-server** (apply via `shapes/mcp-server/README.md`): `mcp` Python SDK + `FastMCP` stdio scaffold. Tools are functions with `@server.tool()` — type hints become the input schema automatically.
- **cli / cron / worker**: no extra files — just keep filling in `src/main.py` (or add `src/main_cli.py` etc.) and pin the queue/scheduler client in `requirements.txt` as needed.

## The AI never installs packages

Your AI assistant will NOT run `pip install`. Instead, it edits `requirements.txt` (or `requirements-dev.txt`) and tells you to run:

```bash
python -m pip install -r requirements.txt
```

This keeps the project portable — the manifest is the only source of truth.

## Before you deploy

```
/pre-deploy-check          # runs lint, types, tests, secret scan, dep audit, security review
```

Then ask Claude to deploy. Deployments at Apero go through the **DevOps team's MCP server**, which targets Kubernetes. You don't run `kubectl` and you don't write k8s manifests.

## Rules

Read `CLAUDE.md` in this directory, and `CLAUDE.AndrejKarpathy.md` for the working principles (read it, follow it, never edit it).

## Contact

- Anything operational → **#devops**
- AI / vibecode → **#vibecode-help**
