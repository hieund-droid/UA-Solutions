# shapes/http-service — convert this Node project to an Express HTTP service

The base `templates/nodejs/` ships **shape-agnostic** — a CLI / cron / worker / MCP server is the default. This folder holds everything you add **only if** the project accepts inbound HTTP from users.

**Don't run this folder.** It's a set of files you copy / merge into the project root and into `src/`.

## When to apply this shape

Apply if **any** of these are true:
- Users will call HTTP endpoints on this service from a browser, Apps Script, another service, or a script.
- You need authn/authz on inbound requests (`hq-apero-sso`).
- You're building a webhook receiver.

If the project is invoked by `pnpm start` from a terminal, a cron, a queue consumer, or speaks MCP over stdio — **do not apply this shape.**

## Apply the shape

From the project root (where the base `templates/nodejs/` was copied):

```bash
SHAPE=shapes/http-service           # path inside this template repo

# 1. Replace src/main.ts and add src/auth.ts
cp -R "$SHAPE/src/." src/

# 2. Merge package-additions.json into your package.json (dependencies +
#    devDependencies). Then install:
#       (open both files; copy the entries; run pnpm install)

# 3. Append HTTP-service env vars to .env.example
cat "$SHAPE/env-additions.txt" >> .env.example
#    (and to your local .env, if you've already created it)

# 4. Add EXPOSE 3000 to the Dockerfile (before the final CMD line)
#    Open Dockerfile and paste:  EXPOSE 3000

# 5. Add docker-compose.yml
cp "$SHAPE/docker-compose.yml" docker-compose.yml

# 6. Replace the smoke test
cp "$SHAPE/tests/main.test.ts" tests/main.test.ts

# 7. Add HTTP/SSO fields to src/config.ts
#    Open src/config.ts — copy the field declarations from
#    $SHAPE/config-additions.ts into the `ConfigSchema` z.object({...}).

# 8. Install the new deps
pnpm install
```

## What you now have

- `pnpm dev` (or `pnpm start`) boots Express on `APP_PORT` (default 3000).
- `src/auth.ts::requireUser` — protect routes with `router.get('/x', requireUser, handler)`.
- `src/auth.ts::requireGroup('g')` — group-based authz.
- `helmet()`, `pino-http` request logging, `express-async-errors` wired.

## Rules that activate with this shape

(All inert until you apply this shape.)

- **Protected routes only via `requireUser` / `requireGroup(...)`.** Never parse JWTs elsewhere.
- **Parse `req.body` / `query` / `params` with `zod` before use.**
- **`helmet()` stays on.** Don't disable security headers.
- **Tests mock SSO at `requireUser`**, not deeper. No real network in tests.

## Rolling back

If you applied this shape by mistake: `git checkout` the modified files and `git rm src/auth.ts docker-compose.yml`. The base template is shape-agnostic — nothing else depends on these.
