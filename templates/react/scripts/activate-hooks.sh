#!/usr/bin/env bash
# scripts/activate-hooks.sh — turn on the Apero guardrails for this checkout.
#
# Run this:
#   - once at bootstrap (after `git init`)
#   - once per fresh clone (the git config is per-clone, not committed)
#
# What it does (idempotent — safe to re-run):
#   1. Point git at .githooks/ so the pre-commit gate is active.
#   2. Make .githooks/pre-commit and .claude/hooks/*.sh executable.
#   3. Print a status line so you know the guardrails are on.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

YELLOW=$'\033[33m'
GREEN=$'\033[32m'
RESET=$'\033[0m'

if [ ! -d .git ]; then
  echo "${YELLOW}warn:${RESET} no .git directory here — run \`git init\` first, then re-run this script." >&2
  exit 1
fi

git config core.hooksPath .githooks

if [ -f .githooks/pre-commit ]; then
  chmod +x .githooks/pre-commit
fi

if [ -d .claude/hooks ]; then
  find .claude/hooks -type f -name '*.sh' -exec chmod +x {} +
fi

echo "${GREEN}✓${RESET} git core.hooksPath = $(git config --get core.hooksPath)"
echo "${GREEN}✓${RESET} pre-commit gate active (.githooks/pre-commit)"
if [ -d .claude/hooks ]; then
  echo "${GREEN}✓${RESET} Claude Code hooks active (.claude/hooks/*.sh)"
fi
echo "${GREEN}✓${RESET} guardrails ready."
