#!/usr/bin/env bash
# scripts/bootstrap-in-place.sh — turn a fresh "Use this template" copy into a real project.
#
# Context: a new Apero project is created by clicking **Use this template** on
# GitHub. That copies this whole repo (templates/, docs/, claude-plugin/, the
# master CLAUDE.md, this README) into the new repo. The new repo is NOT a
# project yet — it's the raw template. This script lays the chosen stack down
# at the repo root *in place*, builds the project rulebook, preserves the
# template README as README.origin.md, removes the template-authoring
# machinery, and turns the Apero guardrails on.
#
# Usage:
#   bash scripts/bootstrap-in-place.sh <python|nodejs|react>
#
# Driven by BOOTSTRAP.md — Claude Code asks the user for the stack (and shape),
# then runs this. Idempotent guard: refuses to run twice (the sentinel is gone)
# and refuses to run inside the upstream template repo itself.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

YELLOW=$'\033[33m'; GREEN=$'\033[32m'; RED=$'\033[31m'; RESET=$'\033[0m'
die() { echo "${RED}error:${RESET} $*" >&2; exit 1; }

STACK="${1:-}"
case "$STACK" in
  python|nodejs|react) ;;
  *) die "usage: bash scripts/bootstrap-in-place.sh <python|nodejs|react>" ;;
esac

# --- Guards -----------------------------------------------------------------
[ -f .apero-bootstrap-needed ] || die "no .apero-bootstrap-needed sentinel — this repo is already bootstrapped (or isn't an Apero template copy). Nothing to do."
[ -d "templates/$STACK" ] || die "templates/$STACK not found — is this an Apero template copy?"

# Don't bootstrap the upstream template repo itself. Override only if you
# REALLY mean it (you almost never do): APERO_BOOTSTRAP_FORCE=1.
ORIGIN="$(git remote get-url origin 2>/dev/null || echo '')"
if [[ "$ORIGIN" == *hq-apero-template* && "${APERO_BOOTSTRAP_FORCE:-0}" != "1" ]]; then
  die "origin is the upstream template ($ORIGIN). Bootstrap is for downstream copies, not the template itself. (set APERO_BOOTSTRAP_FORCE=1 to override)"
fi

echo "${GREEN}▶${RESET} bootstrapping this repo as a ${YELLOW}$STACK${RESET} project (in place)…"

# --- 1. Preserve the master rulebook (minus the first-run banner) -----------
# The banner is delimited by HTML-comment markers so it never leaks into the
# project's own CLAUDE.md.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
sed '/APERO:FIRST-RUN-BANNER:START/,/APERO:FIRST-RUN-BANNER:END/d' CLAUDE.md > "$TMP/master.md"

# --- 2. Preserve the template README ----------------------------------------
if [ -f README.md ] && [ ! -f README.origin.md ]; then
  mv README.md README.origin.md
  echo "${GREEN}✓${RESET} README.md → README.origin.md (template README kept for reference)"
fi

# --- 3. Lay the chosen stack at the repo root (overlay) ---------------------
# This brings src/, tests/, requirements/package manifests, .githooks/,
# .claude/ (inline guardrails), shapes/, scripts/activate-hooks.sh, and the
# stack's CLAUDE.md addendum (which lands as ./CLAUDE.md — rebuilt next step).
cp -R "templates/$STACK/." ./
echo "${GREEN}✓${RESET} laid templates/$STACK over the repo root"

# --- 4. Build the project rulebook = master + stack addendum ----------------
# After the overlay, ./CLAUDE.md is the stack addendum.
cat "$TMP/master.md" ./CLAUDE.md > "$TMP/CLAUDE.md"
mv "$TMP/CLAUDE.md" ./CLAUDE.md
echo "${GREEN}✓${RESET} CLAUDE.md = master rulebook + $STACK addendum"

# --- 5. Remove template-authoring machinery (NOT the guardrails/guidelines) -
# Kept: CLAUDE.md, CLAUDE.AndrejKarpathy.md, .claude/, .githooks/, docs/,
#       shapes/ (chosen stack), scripts/activate-hooks.sh,
#       scripts/setup-package-mirror.sh, pip.conf/.npmrc, README.template.md.
# Removed: the multi-stack source, the canonical plugin, shared snippets, the
#          training course, the sync script, this script, the sentinel, BOOTSTRAP.md.
rm -rf templates claude-plugin shared security-training
rm -f scripts/sync-plugin-to-templates.sh
rm -f .apero-bootstrap-needed BOOTSTRAP.md
echo "${GREEN}✓${RESET} removed template-authoring machinery (kept guardrails, docs, shapes)"

# --- 6. Activate the guardrails for this checkout ---------------------------
if [ -d .git ] && [ -x scripts/activate-hooks.sh ]; then
  ./scripts/activate-hooks.sh || echo "${YELLOW}warn:${RESET} activate-hooks.sh reported an issue — re-run it after \`git init\`."
elif [ ! -d .git ]; then
  echo "${YELLOW}note:${RESET} no .git yet. Run \`git init\` then \`./scripts/activate-hooks.sh\` to turn the pre-commit gate on."
else
  chmod +x scripts/activate-hooks.sh 2>/dev/null || true
  echo "${YELLOW}note:${RESET} run \`./scripts/activate-hooks.sh\` to turn the guardrails on."
fi

# --- 7. Package mirror -------------------------------------------------------
# Project-level config (pip.conf / .npmrc) came in with the overlay — that's the
# committed, portable mirror config that travels with the repo. Confirm it, then
# also point this machine's pip/npm at the mirror (user scope, idempotent,
# reversible — see docs/package-mirror.md) so `pip install` / `npm install`
# actually resolve through artifact-keeper, not the public registry.
for f in pip.conf .npmrc; do
  [ -f "$f" ] && echo "${GREEN}✓${RESET} package mirror wired in-project ($f → artifact-keeper)"
done
if [ -x scripts/setup-package-mirror.sh ]; then
  echo "${GREEN}▶${RESET} pointing this machine's pip/npm at the mirror (user scope, idempotent)…"
  bash scripts/setup-package-mirror.sh >/dev/null 2>&1 \
    && echo "${GREEN}✓${RESET} machine pip/npm now resolve through artifact-keeper" \
    || echo "${YELLOW}note:${RESET} couldn't set the global mirror (pip/npm may be absent) — run \`bash scripts/setup-package-mirror.sh\` yourself. See docs/package-mirror.md."
fi

# --- 8. Self-destruct this script -------------------------------------------
rm -f scripts/bootstrap-in-place.sh

echo
echo "${GREEN}✓ bootstrap complete.${RESET} This is now a $STACK project."
echo "  Next (Claude Code drives this): pick the shape, then write README.md describing YOUR product."
echo "  README.origin.md holds the template's original README; README.template.md documents the scaffold."
