# BOOTSTRAP.md — first thing to do in a fresh Apero project

**Read this if `.apero-bootstrap-needed` exists at the repo root.** It means
someone created this repo by clicking **Use this template** on GitHub. GitHub
copied the *entire* Apero template here — every stack, the docs, the guardrails,
the master rulebook. **This repo is not a project yet.** Your first job is to
turn it into one, *in place*.

> **Are you in the upstream template repo itself?** If `git remote get-url origin`
> contains `hq-apero-template`, you are *maintaining the template*, not starting a
> project. **Do not bootstrap.** Ignore the sentinel and the FIRST-RUN banner and
> work on the template as asked.

---

## Why this exists (for the non-coder reading along)

This template is the company's **safety rail**. Every Apero project starts from
it so that the AI assistant (me, Claude Code) **can't quietly do something
harmful** — leak a secret, call a paid API from a spreadsheet, hand-roll login,
push to prod. The rules live in `CLAUDE.md`, the automatic blocks live in
`.claude/` and `.githooks/`. **Those travel with your project forever.** That's
the whole point: wherever this project goes, the guardrails go with it.

Bootstrapping just picks *which kind* of project this is and clears away the
template's spare parts. It does **not** remove the guardrails.

---

## The steps (I, Claude Code, run these — you just answer one or two questions)

### 1. Ask the user the shape question — exactly once, no menu-dumping

Default stack is **Python**. Only switch if the user names a reason:
- **React** — building a browser UI for end users.
- **Node.js** — must integrate a JS-only ecosystem.

Then ask the single question that settles the **shape**:

> *"What does this project do — does a person run it in a terminal, does it run
> on a schedule, does it watch a queue, does it serve web requests, or is it an
> MCP server for Claude?"*

Map the answer:

| Answer | Stack default | Shape |
|--------|---------------|-------|
| Run by a human in a terminal | Python | `cli` |
| Runs on a schedule | Python | `cron` |
| Watches a queue | Python | `worker` |
| Serves web/HTTP requests | Python | `http-service` |
| MCP server for Claude | Python (FastMCP) | `mcp-server` |
| Browser UI | React | (React has one shape) |

If they don't know, infer from their one-sentence description. Don't read the
whole table to them.

### 2. Lay the stack down + turn guardrails on

```bash
bash scripts/bootstrap-in-place.sh <python|nodejs|react>
```

This script (read it before running — it's short) does the mechanical part:
- saves the template's `README.md` → `README.origin.md`,
- overlays `templates/<stack>/.` onto the repo root (brings `src/`, manifests,
  `.githooks/`, the inline `.claude/` guardrails, `shapes/`),
- rebuilds `CLAUDE.md` = master rulebook **+** the stack addendum,
- deletes the template-authoring spare parts (`templates/`, `claude-plugin/`,
  `shared/`, `security-training/`, the sync script, this `BOOTSTRAP.md`, the
  sentinel) — **but keeps `CLAUDE.md`, `CLAUDE.AndrejKarpathy.md`, `.claude/`,
  `.githooks/`, `docs/`, `shapes/`, the package-mirror config, and
  `scripts/setup-package-mirror.sh`**,
- runs `scripts/activate-hooks.sh` so the pre-commit gate and Claude hooks fire,
- wires the **package mirror**: the project ships `pip.conf` / `.npmrc` pointed
  at `artifact-keeper.aperogroup.ai` (committed, travels with the repo), and the
  script also runs `scripts/setup-package-mirror.sh` to point this machine's
  pip/npm at the mirror (user scope, idempotent) so the human's
  `pip install` / `npm install` resolve through it. See `docs/package-mirror.md`
  (and its reset steps).

If `activate-hooks.sh` warns there's no `.git`, run `git init` then
`./scripts/activate-hooks.sh`. If the mirror step couldn't run (no pip/npm on
the box yet), run `bash scripts/setup-package-mirror.sh` once the human has the
toolchain installed.

### 3. Apply the shape

- **`cli` / `cron` / `worker`** — stay on the base. Fill in `main()` in the
  entry module; add deps to the manifest (you edit it, the human installs).
- **`http-service`** — follow `shapes/http-service/README.md` (adds FastAPI/
  Express + `auth.py`/`hq-apero-sso`).
- **`mcp-server`** — follow `shapes/mcp-server/README.md`.

### 4. Write the project's own README.md

`bootstrap-in-place.sh` did **not** create `README.md` — that's deliberate, the
slot is yours. Write one describing **this product** (not the scaffold). Minimum:

```markdown
# <project name>

<one line: what this does and who it's for>

> Criticality: personal · team · production  ← pick one

## Run
<the run command for this stack/shape>

## What's wired
Apero guardrails inline (`CLAUDE.md`, `.claude/`, `.githooks/`). SSO/secrets/
package-mirror per the Apero rulebook. Scaffold details: `README.template.md`.
```

`README.template.md` (scaffold how-to) and `README.origin.md` (the template's
original landing page) stay in the repo as references.

### 5. Database and SSO — only when the project actually needs them

**Do not prompt the user about a database or SSO by default. That's redundant
and confusing.** Apply the Apero rules instead:

- **Storage:** the default is a JSON file in `output/`. Only reach for MongoDB /
  Postgres / Redis when the task genuinely needs one. Don't ask "what database?"
  — assume none until the work demands it.
- **SSO / auth:** only the `http-service` shape gets `hq-apero-sso` (via
  `/sso-wire-up` when wiring the real thing). `cli`, `cron`, `worker`,
  `mcp-server` have **no inbound auth** — never add login to them. Don't ask
  about SSO unless the project serves HTTP to users.

### 6. Confirm and hand back

Tell the user, in one or two lines: the stack + shape chosen, that the
guardrails are active, and that they own `README.md`. Then continue with
whatever they originally asked for.

---

## What you must NOT do during bootstrap

- Don't hand-edit the rule content — `CLAUDE.AndrejKarpathy.md`, the master
  rulebook body, or the inline `.claude/` guardrails. The script consumes them
  verbatim. Improvements to the rules are a **separate PR to
  `hq-apero-template`**, never part of a project bootstrap.
- Don't pre-wire FastAPI/Express/auth/a database "just in case." Shape first.
- Don't `pip install` / `npm install` / `pnpm add` — edit the manifest, tell the
  user the install command.
