# {{project_name}} — Apero React app (scaffold docs)

> **This file is `README.template.md` — it documents the *scaffold* this project was bootstrapped from (how to run, what's wired). Write your own `README.md` describing what your product actually does; keep this one around (or delete it) as a quick reference. The Apero AI assistant will prefer your `README.md` once it exists.**

Generated from `hq-apero-template/templates/react`. Vite + React 18 + TypeScript, package manager is `pnpm`.

> **Criticality:** `personal` · `team` · `production` — *replace with your choice when you start.*
> *Personal* = your own tool, you accept the risk. *Team* = used by a small group, run `/code-review` before merging. *Production* = customer-facing or holds real data — requires `#devops` review before launch.

## Run

```bash
# 0. Activate the Apero guardrails for this checkout (idempotent — run once after cloning)
./scripts/activate-hooks.sh        # points git at .githooks/, chmods .githooks/* + .claude/hooks/*

# 1. Enable pnpm (Node 16+ ships with corepack)
corepack enable

# 2. Install dependencies (the AI doesn't do this — you do)
pnpm install

# 3. Copy env template
cp .env.example .env

# 4. Run dev server
pnpm dev
```

> **About step 0.** Every fresh clone needs to run `activate-hooks.sh` once. `core.hooksPath` lives in `.git/config` (per-clone, not committed) — without flipping it, the pre-commit gate is silent and nothing blocks staged secrets. The same script also chmods the Claude Code PreToolUse hooks under `.claude/hooks/`. Safe to re-run any time.

Open http://localhost:5173.

## Entry

React's entry is `src/main.tsx` (Vite convention, don't rename). You start it via `pnpm dev` — that IS the obvious entrypoint for a Vite app.

## Logging

`src/lib/logger.ts` exposes a level-aware logger. **No raw `console.log` in shipped code.**

```typescript
import { log } from './lib/logger';
log.info('user clicked save', { id });
```

`VITE_LOG_LEVEL` controls visibility (`debug` / `info` / `warn` / `error`). Note: `VITE_*` is public — this is a debug knob, not a security control.

## What's wired

- **Auth**: `hq-apero-sso` browser client — see `src/auth/`. Run `/sso-wire-up` to replace the stub.
- **Config**: `src/lib/config.ts` — only reads `VITE_*` vars (PUBLIC). No secrets in the bundle.
- **Routing**: `react-router-dom`
- **Lint**: `eslint` · **Format**: `prettier` · **Types**: `tsc --noEmit`
- **Tests**: `vitest` + `@testing-library/react`
- **Build**: `vite build` → static files served by nginx (see `Dockerfile`, `nginx.conf`)

## The AI never installs packages

Your AI will NOT run `pnpm add` / `npm install`. It edits `package.json`, then tells you to run `pnpm install`.

## Important: secrets and the browser

Anything you put in `VITE_*` is **public**. It gets baked into the JS bundle that ships to every user. Do **not** put API keys, tokens, or anything that would let someone act as the app there. Talk to a backend; let the backend hold secrets.

## Before you deploy

```
/pre-deploy-check          # runs lint, types, tests, secret scan, dep audit, security review
```

Then ask Claude to deploy. Deployments at Apero go through the **DevOps team's MCP server**, which targets Kubernetes. You don't run `kubectl` and you don't write k8s manifests. See `CLAUDE.md §11`.

Read `CLAUDE.md` in this directory before making changes.

## Contact

- Anything operational (deploys, security, infra) → **#devops**
- AI / vibecode → **#vibecode-help**
