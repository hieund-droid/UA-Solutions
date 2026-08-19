---
name: sso-wire-up
description: Replace the hq-apero-sso stub with a real integration. Detects stack (Python/Node/React), reads SSO docs (https://github.com/Apero-Vibecode/hq-apero-sso), installs the package, replaces the stub, updates .env.example, adds a smoke test.
---

# /sso-wire-up

Detect stack: `requirements.txt` → Python · `package.json` with `react` → React · `package.json` with `express` → Node.

Before editing: WebFetch the SSO repo's README. If you can't read it, ask the user to paste the integration snippet — don't invent the API.

## Python (FastAPI — http-service shape)

> **Prerequisite:** the project has the `http-service` shape applied (`src/auth.py` exists, `fastapi` is in `requirements.txt`). If not, apply `templates/python/shapes/http-service/README.md` first — SSO wire-up is not relevant to cli / cron / worker projects.

1. Add `hq-apero-sso==<version>` to `requirements.txt` (pinned). **Don't run pip install yourself** — tell the user: `python -m pip install -r requirements.txt`.
2. In `src/auth.py`: import the real verifier, replace `_decode_token` body with the real call, return a populated `User`. Remove the `NotImplementedError`.
3. Ensure `.env.example` has every `APERO_SSO_*` var the library needs.
4. Add `tests/test_auth.py` mocking the verifier; assert `get_current_user` returns the expected `User`.

## Node (Express — http-service shape)

> **Prerequisite:** the project has the `http-service` shape applied (`src/auth.ts` exists, `express` is in `package.json`). If not, apply `templates/nodejs/shapes/http-service/README.md` first — SSO wire-up is not relevant to cli / cron / worker / mcp-server projects.

1. Add `"hq-apero-sso": "^<version>"` to `package.json` `dependencies`. Tell the user: `pnpm install`.
2. In `src/auth.ts`: replace `_decodeToken` with the real call.
3. `.env.example` covers required vars.
4. Add `tests/auth.test.ts` mocking the SSO module; assert `requireUser` populates `req.user`.

## React

1. Add `"hq-apero-sso": "^<version>"` to `package.json` `dependencies`. Tell the user: `pnpm install`.
2. In `src/auth/AuthProvider.tsx`: wrap children with the library's provider (`issuer` + `clientId` from `src/lib/config.ts`). Re-export `useAuth` matching the existing shape (`user`, `isLoading`, `login`, `logout`).
3. Update `nginx.conf` CSP `connect-src` to include the SSO domain if missing.
4. Add `tests/AuthProvider.test.tsx` covering logged-in and logged-out states.

## After

Run `/security-review`. Run tests. Tell the user: *"SSO wired. Try login locally. Breakage → ping #devops."*

## Don't

- Don't invent the library API — ask if you can't read it.
- Don't store tokens in `localStorage` yourself; the library handles storage.
- Don't remove `TODO[platform]` until the real wiring is verified.
