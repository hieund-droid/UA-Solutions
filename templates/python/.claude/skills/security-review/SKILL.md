---
name: security-review
description: Review pending changes against Apero's CLAUDE.md rules. Use before opening a PR or invoking the DevOps deploy MCP. Reads diff vs main, flags hard-rule violations (secrets, custom auth, SQL/shell/eval injection, missing input validation, weakened headers, mirror bypasses, k8s manifests in app repos, license issues). Returns file:line citations.
---

# /security-review

Diff = `git diff main...HEAD` (fall back to unstaged if no upstream or branch is main). Read `CLAUDE.md` first — it's the rulebook.

## Check, in order. Cite `file:line` for every finding.

1. **Secrets** — AWS/Stripe/Slack/GitHub patterns; PEM headers; URIs with creds; literal `apiKey/password/token`; sensitive-looking values not in `.env.example`.
2. **Custom auth** — JWT verify, OAuth, login outside `src/auth.*`. Tokens in `localStorage` outside SSO lib (React).
3. **Authorization gaps** — `requireUser` without ownership/group check on privileged actions.
4. **Injection** — SQL via string concat; `shell=True`/`exec` with non-constants; `eval`/`Function()` on dynamic input; path joins with unsanitized input; `dangerouslySetInnerHTML` on non-constants.
5. **Supply chain** — new deps from git URLs / non-mirror registries; GPL/AGPL/SSPL; disabled TLS (`verify=False`, `rejectUnauthorized:false`).
6. **K8s/infra in app repo** — new `*.yaml`/`*.yml` with `apiVersion:`+`kind:`; new `helm/`/`kustomize/`; `kubectl`/`helm` in scripts. Route to **#devops**.
7. **Headers/CORS** — `Access-Control-Allow-Origin: *` on authed routes; `unsafe-inline`/`unsafe-eval` in CSP; `helmet()` disabled.
8. **Logging** — req bodies on auth/payment; tokens/passwords in logger calls.
9. **AI footguns** — empty `except Exception: pass`; `// TODO` on shipped paths; `NotImplementedError` on prod paths; tests that mock the thing under test.

## Output

```
SECURITY REVIEW — <branch> vs main

HARD FAIL
  - file:line — finding — rule
WARNINGS
  - file:line — finding
OK
  - what looks fine
NEXT
  - what to do
```

Zero findings → say so, recommend `/pre-deploy-check`.

## Rules

- Cite or don't claim. No `file:line` → no finding.
- Template stubs (`NotImplementedError` in `src/auth.*`) aren't findings unless on a prod path.
- Be terse. The reader is a vibe-coder, not an auditor.
