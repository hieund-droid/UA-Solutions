# hq-apero-template

The Apero company project template. One command, one safe-by-default project.

> **Apero starter template.** Name your new repo `<venture>-<purpose>`. For example: `vsl-social-monitoring`, `spm-reelme`, `tera-funnelfox`, `hq-bank-helper`.

This repo is the **distribution mechanism for company guardrails**. If you are vibe-coding at Apero, your project should start from here — not from a blank folder, not from a random GitHub starter.

---

## Who this is for

- **Vibe-coders (non-engineers)** — you describe what you want; AI writes it. The template makes sure AI writes *safe* code. **Start here: [`docs/vibecoder-survival.md`](docs/vibecoder-survival.md)** (tiếng Việt: [`docs/vibecoder-survival.vi.md`](docs/vibecoder-survival.vi.md)) — five-minute read, written for people who don't read code. Then graduate to **[`docs/security-training.md`](docs/security-training.md)** (tiếng Việt: [`docs/security-training.vi.md`](docs/security-training.vi.md)) — the attack-first training doc (~30 min) you should read once when you join and once a quarter after.
- **Engineers** — you skip the boilerplate, you inherit the rules, you spend time on the actual problem.
- **Security & Platform teams** — you ship one update here, everyone gets it.

---

## What you get

Every generated project comes with:

| Concern              | What is pre-wired                                           |
|----------------------|-------------------------------------------------------------|
| Auth                 | `hq-apero-sso` integration stub — applied only when the project shape is `http-service` (not in cli / cron / worker). Never roll your own. |
| Secrets              | KMS / secret manager client, `.env.example` only            |
| Packages             | Internal mirror (`pip.conf` / `.npmrc`) pointed at `artifact-keeper.aperogroup.ai`. For ad-hoc work outside a project, run `bash scripts/setup-package-mirror.sh` — see [`docs/package-mirror.md`](docs/package-mirror.md). |
| Ignores              | `.gitignore`, `.dockerignore`, `.claudeignore`, `.cursorignore` |
| AI rules             | `CLAUDE.md` with the company rulebook                       |
| AI permissions       | `.claude/settings.json` with safe defaults and deny-list    |
| Pre-deploy checks    | `/pre-deploy-check` skill runs lint, types, tests, secret scan, dep audit, security review |
| Container            | `Dockerfile` non-root, pinned base image                    |
| Tests                | Test scaffold + a passing example                           |
| Docs                 | `README.template.md` (scaffold-how-to). `README.md` slot is left empty for you to introduce your product. |

**Deploy path:** all services deploy to Kubernetes via the **DevOps team's MCP server**. No CI files are checked into project repos; you don't write k8s manifests. See `CLAUDE.md §11`.

Every bootstrapped project also ships the **Apero Claude Code guardrails inline** under `.claude/`:
- `/security-review` — automated security review of pending changes
- `/code-review` — automated code review with company conventions
- `/pre-deploy-check` — runs all deploy-gate checks locally
- `/sso-wire-up` — wires up `hq-apero-sso` into your project
- Plus PreToolUse hooks that block secret-shaped writes, dangerous bash, and k8s-manifest edits before they happen.

These travel with the project — every clone gets them, no separate plugin install required. The same content also exists as the standalone **`apero-vibecode` plugin** in `claude-plugin/` for projects that weren't bootstrapped from this template (see `claude-plugin/README.md`).

---

## Choosing a stack

**Default: Python.** It's the best fit for vibe-coding — readable as English, huge library ecosystem, the Apero template has the most mature integrations. Reach for another stack only if you can name a reason in one sentence.

| Stack       | Pick when…                                                         | Path                  |
|-------------|--------------------------------------------------------------------|-----------------------|
| **Python**  | **Default** — scripts, tools, automation, data, ML, backend, web   | `templates/python/`   |
| React       | You are building a browser UI for end users                        | `templates/react/`    |
| Node.js     | You must integrate with a JS-only ecosystem                        | `templates/nodejs/`   |

---

## Bootstrap — click "Use this template", then let Claude Code finish it

**The normal path: no copy commands.**

1. On GitHub, click **Use this template → Create a new repository**. Name it
   `<venture>-<purpose>` (e.g. `spm-reelme`, `hq-bank-helper`).
2. `git clone` your new repo and open it in **Claude Code**.
3. Claude Code sees the `.apero-bootstrap-needed` marker (the `CLAUDE.md`
   FIRST-RUN banner tells it to) and **bootstraps the project in place** — or
   just say *"bootstrap this project"*. It will:
   - ask **one** question — what does this project do (so it can pick the stack
     + shape),
   - run `scripts/bootstrap-in-place.sh <stack>`, which lays the stack onto the
     repo root, rebuilds `CLAUDE.md` = master rulebook + stack addendum,
     **renames the template `README.md` → `README.origin.md`**, removes the
     template's spare parts, and turns the guardrails on,
   - help you write a fresh `README.md` for *your* product,
   - **not** pester you about a database or SSO — those are added only if the
     work actually needs them.

The full runbook Claude Code follows is **[`BOOTSTRAP.md`](BOOTSTRAP.md)**.

**The guardrails travel with the project for good.** `CLAUDE.md`,
`CLAUDE.AndrejKarpathy.md`, `.claude/` (hooks + skills), and `.githooks/` stay
inline in your repo so the AI assistant can't quietly do something harmful — in
this project or any clone of it. Bootstrap removes the *template machinery*
(`templates/`, `claude-plugin/`, `shared/`, `security-training/`), never the
rules.

> **What gets kept vs removed.** Kept: `CLAUDE.md`, `CLAUDE.AndrejKarpathy.md`,
> `.claude/`, `.githooks/`, `docs/`, `shapes/` (your stack), the package-mirror
> config (`pip.conf` / `.npmrc`) + `scripts/setup-package-mirror.sh`,
> `README.template.md` (scaffold how-to), `README.origin.md` (this template's
> original landing page). Removed: `templates/` (other stacks), `claude-plugin/`
> (canonical source — the inline `.claude/` copy is all a project needs),
> `shared/`, `security-training/`, the sync script, `BOOTSTRAP.md`, and the sentinel.

> **Packages always go through the mirror.** Bootstrap wires
> `artifact-keeper.aperogroup.ai` two ways: the committed `pip.conf` / `.npmrc`
> travel with the repo, and `setup-package-mirror.sh` points your machine's
> pip/npm at it so installs resolve through the security-scanned mirror, never
> the public registry. Details + reset: [`docs/package-mirror.md`](docs/package-mirror.md).

> **What `./scripts/activate-hooks.sh` does** (bootstrap runs it for you; re-run on every fresh clone). Git normally looks for hooks in `.git/hooks/` — a per-clone directory that isn't tracked by git. The script flips git to look in `.githooks/` (which IS tracked) so the pre-commit gate survives clones, then chmods the scripts. The pre-commit gate blocks committed secrets and obviously dangerous patterns (`eval`, `dangerouslySetInnerHTML`, raw SQL interpolation), and it chmods the Claude Code `.claude/hooks/*.sh` PreToolUse hooks. **`core.hooksPath` is per-clone and does not travel with the repo**, so every contributor re-runs this one-liner once after cloning.

### Alternative: manual copy (engineers / ad-hoc)

No Claude Code handy, or you want a stack subfolder without the GitHub flow? Copy a single stack out by hand:

```bash
STACK=python                          # python | nodejs | react
DEST=my-project
mkdir "$DEST"
cp -R "templates/$STACK/." "$DEST/"                 # includes .claude/, .githooks/, scripts/
cat CLAUDE.md "templates/$STACK/CLAUDE.md" > "$DEST/CLAUDE.md"   # master + addendum
cd "$DEST" && git init && ./scripts/activate-hooks.sh
# Then pick a shape (cli|cron|worker|http-service|mcp-server) and write README.md.
```

> **Shape, not stack.** "Python project" is not a shape — a cron job, a CLI tool, and a FastAPI service all use Python, but only one needs an HTTP framework. The template defaults to the minimum so you don't inherit dead `auth.py` / `fastapi` / `uvicorn` files in a project that never serves HTTP. For `http-service` / `mcp-server`, follow `shapes/<shape>/README.md`; for `cli` / `cron` / `worker`, stay on the base. mcp-server defaults to Python (FastMCP reads as English) — pick the Node variant only with a JS-ecosystem reason.

> **Why a separate `README.md`.** A project's `README.md` should describe *that product* — for engineers, stakeholders, and an AI scanning the repo. Shipping the scaffold's "how to run this template" doc as `README.md` would squat that slot, so the template keeps it as `README.template.md` and leaves `README.md` free for you. Your AI assistant prefers your `README.md` once it exists.

---

## What lives where

```
hq-apero-template/
  CLAUDE.md                    <- THE master company rulebook (read this)
  BOOTSTRAP.md                 <- runbook Claude Code follows to turn a fresh
                                  "Use this template" copy into a real project
  .apero-bootstrap-needed      <- marker: present = not bootstrapped yet
                                  (removed by bootstrap; ignore it in THIS repo)
  README.md                    <- you are here
  templates/
    python/                    <- Python scaffold (shape-agnostic; shapes/ adds http-service etc.)
    nodejs/                    <- Node.js scaffold (shape-agnostic; shapes/ adds http-service, mcp-server)
    react/                     <- React (Vite + TS) scaffold
  shared/                      <- snippets reused across templates
  claude-plugin/               <- canonical Apero Claude Code hooks/skills/agents.
                                  Templates mirror these under .claude/ via
                                  scripts/sync-plugin-to-templates.sh — so a
                                  bootstrapped project ships them inline. The
                                  same dir is also installable as a standalone
                                  plugin for non-template projects.
  docs/
    vibecoder-survival.md      <- READ THIS if you don't read code professionally
    vibecoder-survival.vi.md   <- bản tiếng Việt
    security-training.md       <- attack-first deep training (~30 min)
    security-training.vi.md    <- bản tiếng Việt
    contact-points.md          <- who to ping for what
```

---

## Contact

- Anything operational — deploys, security, infra, secrets, SSO, this template: **#devops** · devops@apero.vn
- AI / vibecode help: **#vibecode-help**

See `docs/contact-points.md`.
