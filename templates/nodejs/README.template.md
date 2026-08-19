# {{project_name}} — Apero Node.js project (scaffold docs)

> **This file is `README.template.md` — it documents the *scaffold* this project was bootstrapped from (how to run, what's wired, shape choices). Write your own `README.md` describing what your product actually does; keep this one around (or delete it) as a quick reference. The Apero AI assistant will prefer your `README.md` once it exists.**

Generated from `hq-apero-template/templates/nodejs`. Node 20, TypeScript, `pnpm` — no exotic tooling.

> **Criticality:** `personal` · `team` · `production` — *replace with your choice when you start.*
> *Personal* = your own tool, you accept the risk. *Team* = used by a small group, run `/code-review` before merging. *Production* = customer-facing or holds real data — requires `#devops` review before launch.

> **Reminder: Python is the Apero default stack.** Pick Node only if you can name a JS-ecosystem reason in one sentence. (See the master `CLAUDE.md`.)

## Pick a shape first

The template ships **shape-agnostic** — `pnpm start` just logs "hello" and exits. Before you build anything substantial, decide which shape this project is:

| Shape          | Use when…                                              |
|----------------|--------------------------------------------------------|
| **cli**        | Humans run it from a terminal.                         |
| **cron / batch** | k8s CronJob runs it on a schedule.                   |
| **worker**     | Long-running, consumes from a queue.                   |
| **http-service** | Inbound HTTP from users / browsers / other services. |
| **mcp-server** | An MCP host (Claude Code, Claude Desktop) launches it over stdio JSON-RPC. *Python is the Apero default for MCP — use this Node variant only with a specific JS-ecosystem reason.* |

For `cli` / `cron` / `worker`, **stay on the base** — fill in `main()` in `src/main.ts` and add deps to `package.json` as needed.

For **http-service**, follow `shapes/http-service/README.md` — it adds Express, helmet, `auth.ts`, port mapping.

For **mcp-server**, follow `shapes/mcp-server/README.md` — it adds `@modelcontextprotocol/sdk` and a stdio scaffold.

Tell your AI assistant what the project does in one sentence and ask which shape fits.

## Run

```bash
# 0. Activate the Apero guardrails for this checkout (idempotent — run once after cloning)
./scripts/activate-hooks.sh        # points git at .githooks/, chmods .githooks/* + .claude/hooks/*

# 1. Enable pnpm via corepack (Node 16+ ships with corepack)
corepack enable

# 2. Install dependencies (the AI doesn't do this — you do)
pnpm install

# 3. Copy env template
cp .env.example .env

# 4. Run the app
pnpm dev              # auto-reload via tsx
# or, equivalent:
pnpm start            # one-shot
```

> **About step 0.** Every fresh clone needs to run `activate-hooks.sh` once. `core.hooksPath` lives in `.git/config` (per-clone, not committed) — without flipping it, the pre-commit gate is silent and nothing blocks staged secrets. The same script also chmods the Claude Code PreToolUse hooks under `.claude/hooks/`. Safe to re-run any time.

Out of the box, this prints a single log line and exits — fill in `main()` in `src/main.ts` (or apply a shape) to make it useful.

> **Why `pnpm start` (= `tsx src/main.ts`) and not `tsx main.ts`?** All code lives in `src/`; the project root has zero `.ts` files. Strict separation — "is this code?" is answerable by `ls`. See `CLAUDE.md` (Layout section).

## Entry points

- `pnpm start` → `tsx src/main.ts` — the default. Shape-agnostic stub today.

When you add another entry point, give it a shape-flavored module name *inside `src/`* and a `package.json` script:
- `src/main_cli.ts` → `"start:cli": "tsx src/main_cli.ts"` (cli)
- `src/main_cron.ts` → `"start:cron": "tsx src/main_cron.ts"` (cron)
- `src/main_worker.ts` → `"start:worker": "tsx src/main_worker.ts"` (worker)
- (For http-service / mcp-server the entry stays `src/main.ts`.)

**One module per entry point. The script name says what it runs.**

## Logging

`src/logger.ts` exports a `pino` instance configured from the `LOG_LEVEL` env var. **No `console.log` in shipped code.**

```typescript
import { logger } from './logger.js';
logger.info({ id }, 'something happened');
```

## What's wired (base)

- **Secrets**: declared as `SECRET_*` fields on `src/config.ts::ConfigSchema`, read directly (`getConfig().SECRET_OPENAI_API_KEY`). Values live in `.env` (gitignored — never commit it). A shared secret store (Vault) is a deferred, future option, not required today — see [`docs/vault.md`](../../docs/vault.md).
- **Lint**: `biome` (`pnpm lint`).
- **Format**: `prettier` (`pnpm format`).
- **Types**: `tsc --noEmit` (`pnpm typecheck`).
- **Tests**: `vitest` (`pnpm test`).
- **Container**: `Dockerfile` non-root, pinned base image.

## What you get only when you apply a shape

- **http-service** (apply via `shapes/http-service/README.md`): Express + helmet + pino-http, `src/auth.ts` (`hq-apero-sso`), `docker-compose.yml`. Run `/sso-wire-up` to replace the auth stub.
- **mcp-server** (apply via `shapes/mcp-server/README.md`): `@modelcontextprotocol/sdk` stdio scaffold.
- **cli / cron / worker**: no extra files — just keep filling in `src/main.ts` (or add `src/main_cron.ts` etc.) and pin the queue/scheduler client in `package.json` as needed.

## The AI never installs packages

Your AI will NOT run `pnpm add` / `npm install`. It edits `package.json`, then tells you to run:

```bash
pnpm install
```

## Before you deploy

```
/pre-deploy-check
```

Then ask Claude to deploy via the **DevOps team's MCP server** → Kubernetes.

## Rules

Read `CLAUDE.md` and `CLAUDE.AndrejKarpathy.md` (read it, follow it, never edit it).

## Contact

- Operational → **#devops**
- AI / vibecode → **#vibecode-help**
