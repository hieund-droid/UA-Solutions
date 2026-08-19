# CLAUDE.md — Node.js addendum

Read the master `CLAUDE.md` and `CLAUDE.AndrejKarpathy.md` first. **Python is Apero's default — pick Node only with a one-sentence reason.**

## Project shape — decide before writing code

**The template ships shape-agnostic.** A new project is a plain `pnpm start` that logs "hello" and exits. *You add a shape on top.* Apero Node projects fall into one of five shapes — pick **exactly one** before substantial work:

| Shape          | Pick when…                                              | What it adds                                              |
|----------------|---------------------------------------------------------|-----------------------------------------------------------|
| **cli**        | A human runs it from a terminal: `pnpm start … args`    | stdlib `process.argv` parsing, or `commander` if rich UX is genuinely needed (added to `package.json`). |
| **cron / batch** | Runs on a schedule (k8s CronJob, etc.). No users.    | Structured log per iteration. Idempotent. |
| **worker / queue-consumer** | Long-running loop consuming from a queue (Redis/SQS/RabbitMQ). | One client lib in `package.json`. Graceful shutdown on SIGTERM. Structured log per message. |
| **http-service** | **Inbound HTTP from users / browsers / other services / Apps Script.** | Express + helmet + pino-http + `auth.ts` (`hq-apero-sso`). Apply via `shapes/http-service/README.md`. |
| **mcp-server** | Model Context Protocol server (stdio JSON-RPC) launched by an MCP host (Claude Code, Claude Desktop). **Python is the Apero default for MCP** — `templates/python/shapes/mcp-server/` (`FastMCP` reads as English, friendly to non-coders). Pick this Node shape only with a specific JS-ecosystem reason (existing Node libraries you must call, etc.). | `@modelcontextprotocol/sdk`. **No HTTP, no port, no auth middleware.** Apply via `shapes/mcp-server/README.md`. |

**If unsure, ask the user.** Don't guess. *"Does this serve HTTP, run on a schedule, consume a queue, get called by a human at a terminal, or speak MCP?"* — one question, settles it.

**Default to non-HTTP.** Do not apply the `http-service` shape unless the user names a real need for inbound HTTP. Adding Express to a CLI / cron / MCP server is the most common waste this template tries to prevent.

## Toolchain (fixed — don't substitute)

Node 20 LTS · `pnpm` (lockfile committed) · `zod` validation · `pino` logger · `vitest` · `biome` lint · `prettier` format · `tsc` strict.

`express` and friends (`helmet`, `pino-http`, `express-async-errors`, `supertest`) are **shape-specific** (http-service only). `@modelcontextprotocol/sdk` is **shape-specific** (mcp-server only).

Forbidden substitutes: `yarn` / `npm` (primary) · `eslint+tslint` · `jest` / `mocha` (mixed) · `axios` / `request` / `node-fetch` (mixed — use built-in `fetch` or `undici`) · `winston` / `bunyan` (use `pino`).

## Layout — all code in `src/`, zero `.ts` at the project root

**The rule:** a `.ts` file never sits at the project root. All program code lives under `src/`. Tests live in `tests/` (the one allowed peer of `src/`). Everything else at root is non-code: configs, dotfiles, Dockerfile, manifests, README, CLAUDE.md.

```
package.json · pnpm-lock.yaml · .npmrc · .nvmrc
tsconfig.json · tsconfig.build.json · biome.json · .prettierrc.json
Dockerfile · .env.example
README.md (yours — describe the product) · README.template.md (scaffold docs)
CLAUDE.md · CLAUDE.AndrejKarpathy.md
src/
  main.ts             # real entry point — `pnpm start` → `tsx src/main.ts`
  config.ts           # getConfig() — env + secrets, all from .env
  logger.ts           # pre-configured pino instance
tests/
  main.test.ts        # imports from ../src/main.js
shapes/               # opt-in files per project shape — see shapes/<shape>/README.md
```

**Why:** "code or not code?" should be answerable by `ls` alone. A shim at root costs the reader a context-switch every time they scan the directory. No "thin shim" entry file at root, no exceptions.

**Allowed inside `src/` (one level deep):** topical subdirs — `src/routes/`, `src/middleware/`, `src/models/`, `src/db/`. Don't reintroduce topical-prefix flat naming (`route_*.ts`, `db_*.ts`) — make a folder.

Files added by shapes (when applied): see `shapes/<shape>/README.md`.

## Entry points

- **`pnpm start` (= `tsx src/main.ts`) is the default.** Out of the box it just logs and exits. Fill in `main()`.
- Additional entrypoints get **explicit, shape-flavored names inside `src/`**:
  - cli: `src/main_cli.ts`
  - cron / batch: `src/main_cron.ts`
  - worker: `src/main_worker.ts`
  - http-service: keep `src/main.ts` (boots Express)
  - mcp-server: keep `src/main.ts` (boots stdio transport)
- Add a `package.json` script per entry point (e.g. `"start:cron": "tsx src/main_cron.ts"`) so the script name says what it runs.
- Each entrypoint imports `logger` from `./logger.js` (not `console.log`).

## Dependencies — you (the AI) do NOT install

- Edit `package.json` to add a dep (with a sane pinned version).
- Tell the user: `pnpm install`.
- **Never run `pnpm add` / `npm install` yourself.** The bash guard blocks it.
- **Don't add a dep without a shape-justified reason.** No `express` in a CLI. No `commander` in an http-service. No `lodash` because "it might be useful".

## Logging (shape-agnostic)

- Import `logger` from `./logger.js`. Never `console.log` / `console.error` in shipped code.
- Use structured fields: `logger.info({ userId, action }, 'message')`.
- `LOG_LEVEL` env var: `debug` / `info` / `warn` / `error`.
- **pino redacts sensitive paths automatically** (`password`, `token`, `apiKey`, `authorization`, `headers.cookie`, …). Always pass sensitive values as structured properties — `logger.info({ password: pw }, …)` → `password: '***'`. Never interpolate them into the message string (`'pw=' + pw` defeats the redaction).
- For deliberate partial masking, import `mask`: `import { mask } from './logger.js'` → `logger.info({ key: mask(apiKey) }, 'api call')` → `key: '…cdef'`.
- Passwords / full tokens: **don't log at all** — log the user ID, not the token.
- **mcp-server only:** redirect logger output to stderr (stdout is the MCP transport).

## Patterns (http-service shape only)

These rules **only apply once the http-service shape is applied**. Do not pre-apply them to cli / cron / worker / mcp-server.

- Protected route: `router.get('/x', requireUser, handler)`. Never parse JWTs elsewhere.
- Parse `req.body` / `query` / `params` with `zod` before use.
- `express-async-errors` wired — but don't swallow rejections.
- `helmet()` stays on. Don't disable security headers.

## Patterns (mcp-server shape only)

- **stdout is the transport — DO NOT write to it.** Logger must point at `process.stderr`.
- No auth middleware. The MCP host authenticates the user before launching this process.
