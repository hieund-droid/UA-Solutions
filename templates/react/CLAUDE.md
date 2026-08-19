# CLAUDE.md — React (Vite + TS) addendum

Read the master `CLAUDE.md` and `CLAUDE.AndrejKarpathy.md` first.

## Toolchain (fixed)

Node 20 (build) · `pnpm` · Vite · React 18 + TS strict · `react-router-dom` v6 · `vitest` + `@testing-library/react` · `eslint` · `prettier`

Forbidden: `webpack`/CRA · class components · multiple HTTP clients · Redux (use react-query / Zustand on demand) · `console.log` in shipped code (use `src/lib/logger.ts`).

## Layout (Vite convention — don't fight it)

```
index.html
src/
  main.tsx               # Vite entry — wired to index.html, don't rename
  App.tsx
  lib/config.ts          # PUBLIC config only (VITE_*) — never secrets
  lib/logger.ts          # log.debug/info/warn/error (controlled by VITE_LOG_LEVEL)
  auth/AuthProvider.tsx
  auth/RequireAuth.tsx
  pages/
```

`src/main.tsx` is the Vite entry — its name and location are fixed by Vite. **This is React's "obvious entrypoint": you run `pnpm dev` and Vite serves the page from `index.html` which loads `src/main.tsx`.**

## Run

- `pnpm dev` — Vite dev server
- `pnpm build` — production bundle to `dist/`

## Dependencies — you (the AI) do NOT install

- Edit `package.json` to add a dep. Tell the user: `pnpm install`.
- **Never run `pnpm add` / `npm install` yourself.** Bash guard blocks it.

## Logging

- Import: `import { log } from './lib/logger';`
- Use: `log.info('user clicked save', { id })`. Never `console.log` in shipped code.
- `VITE_LOG_LEVEL` controls visibility. Default `info`. **Note: this is PUBLIC** (baked in bundle) — it's a UX/debug knob, not a security setting.
- **The browser console is visible to anyone with DevTools.** Default position: **don't log sensitive data at all** in the browser. The logger has a safety-net scrubber (objects with keys like `password`, `token`, `authorization` become `[redacted: <key>]`) but it can't catch raw strings — `log.info('the password is ' + pw)` will leak.
- For deliberate partial masking, import `mask`: `import { log, mask } from './lib/logger'` → `log.info('api call', { key: mask(apiKey) })` → `key: '…cdef'`.
- Tokens / passwords: never put them in a log call — not even via the scrubber.

## Browser-specific hard rules

- **`VITE_*` is PUBLIC.** No API keys, no tokens.
- No `localStorage.setItem('token', …)` outside the SSO library.
- No `dangerouslySetInnerHTML` on non-constant content.
- Redirects: `new URL(input)` + `https:` allow-list.
- Don't weaken the CSP in `nginx.conf`.
- Don't import backend-only libs into the client bundle.
