# apero-vibecode — Claude Code plugin

The Apero company plugin for Claude Code. Ships skills, a security-review sub-agent, and recommended hooks/permissions so every vibe-coder gets the same guardrails.

> **This directory is the canonical source of truth.** Projects bootstrapped from `hq-apero-template/templates/<stack>/` already ship a mirror of `hooks/`, `skills/`, and `agents/` under their own `.claude/` directory (synced via `scripts/sync-plugin-to-templates.sh`). They do **not** need a separate install — opening a bootstrapped project in Claude Code is enough. Install this plugin user-wide only for projects that were NOT bootstrapped from the Apero template.

## What you get

| Skill                 | When to run                                                            |
|-----------------------|-------------------------------------------------------------------------|
| `/security-review`    | Before opening a PR. Reviews the diff against Apero's `CLAUDE.md` rules. |
| `/code-review`        | When you want a second AI pass on style, naming, clarity, and likely bugs. |
| `/pre-deploy-check`   | Before invoking the DevOps MCP deploy tool. Runs all deploy-gate checks locally. |
| `/sso-wire-up`        | When integrating `hq-apero-sso` into a fresh service.                  |

Plus a sub-agent `apero-security-reviewer` for deeper, isolated security passes.

## Install (per user, one-time) — only for non-template projects

If you're working in a project bootstrapped from `hq-apero-template`, skip this — the guardrails are already inline under that project's `.claude/`. Install this plugin user-wide only when you want the same guardrails in a project that wasn't bootstrapped from the template.

```bash
# Option A — local plugin directory:
mkdir -p ~/.claude/plugins
cp -r hq-apero-template/claude-plugin ~/.claude/plugins/apero-vibecode

# Option B — install from internal Git mirror (when published):
# git clone https://git.apero.vn/platform/apero-vibecode-plugin ~/.claude/plugins/apero-vibecode
```

Restart Claude Code. Run `/security-review` to confirm it's loaded.

## Keeping templates in sync with this plugin

After editing anything under `hooks/`, `skills/`, or `agents/`, run:

```bash
bash scripts/sync-plugin-to-templates.sh
```

from the template repo root. This mirrors the changes into every `templates/<stack>/.claude/` so newly-bootstrapped projects get the updated guardrails. Commit the resulting tree.

## Structure

```
claude-plugin/
  .claude-plugin/plugin.json    # plugin manifest
  skills/
    security-review/SKILL.md
    code-review/SKILL.md
    pre-deploy-check/SKILL.md
    sso-wire-up/SKILL.md
  agents/
    apero-security-reviewer.md  # sub-agent for deeper review
  hooks/hooks.json              # recommended hooks (secret scan, danger bash)
  settings.template.json        # recommended settings — merge into your ~/.claude/settings.json
```

## Contact

Plugin maintained by the **DevOps team**. File issues in **#devops**.
