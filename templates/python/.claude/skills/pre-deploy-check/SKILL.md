---
name: pre-deploy-check
description: Run all deploy-gate checks locally before invoking the DevOps MCP deploy tool. Lint, type-check, tests, secret scan, dep audit, /security-review. Reports pass/fail per check.
---

# /pre-deploy-check

Run each step. Print `[PASS] / [FAIL] / [SKIP]` with a one-line reason. Don't stop on first fail — collect all.

## Steps

| # | Step          | Python                                  | Node / React                         |
|---|---------------|-----------------------------------------|--------------------------------------|
| 1 | Manifest      | confirm `requirements.txt` exists + pinned with `==` | `pnpm install --frozen-lockfile --lockfile-only` (dry) |
| 2 | Lint          | `python -m ruff check .`                | `pnpm lint`                          |
| 3 | Format        | `python -m ruff format --check .`       | `pnpm exec prettier --check .`       |
| 4 | Types         | `python -m mypy .`                      | `pnpm typecheck`                     |
| 5 | Tests         | `python -m pytest -q`                   | `pnpm test`                          |
| 6 | Secret scan   | `gitleaks detect --no-banner --redact` (else scan diff using /security-review §Secrets patterns) |
| 7 | Dep audit     | `python -m pip_audit -r requirements.txt` (if `pip-audit` installed) | `pnpm audit --audit-level=high` |
| 8 | Security      | run `/security-review` — report its summary line                                |
| 9 | SSO sanity    | confirm `_decode_token`/`_decodeToken` isn't a stub if APP_ENV > local          |

**Don't run any `pip install` / `pnpm add` to make tools available.** If a tool is missing → `[SKIP]` with install hint for the user.

## Output

```
PRE-DEPLOY CHECK — <project>

[PASS] Lint
[FAIL] Types — 2 errors in src/routes/orders.ts
[SKIP] Secret scan — gitleaks not installed (brew install gitleaks)
[PASS] /security-review — 0 findings
[WARN] SSO sanity — stub still in place

OVERALL: 1 fail · 1 warn · 1 skip
Invoke the DevOps deploy MCP? Not yet — fix the type errors.
```

## Rules

- Never auto-invoke the deploy MCP. End with the user deciding.
- Tool missing → `[SKIP]` + install hint. Don't fail.
- Don't run anything destructive — only `--check`/`--frozen-lockfile`/`--lockfile-only`.
- If the DevOps MCP server isn't installed in this Claude Code instance, note it: ping **#devops** for setup.
