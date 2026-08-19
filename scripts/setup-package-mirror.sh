#!/usr/bin/env bash
# Point your global pip / npm / pnpm / yarn at Apero's internal mirror
# (artifact-keeper.aperogroup.ai). Safe to re-run.
#
# Usage:
#   bash scripts/setup-package-mirror.sh
#
# Or one-liner from anywhere (e.g. the Claude Desktop code sandbox):
#   curl -fsSL https://raw.githubusercontent.com/Apero-Vibecode/hq-apero-template/main/scripts/setup-package-mirror.sh | bash
#
# What it does:
#   - pip:  writes index-url + trusted-host to ~/.config/pip/pip.conf (user scope)
#   - npm:  writes registry to ~/.npmrc                              (user scope)
#   - pnpm: reads ~/.npmrc, so the npm step covers it                (no extra work)
#   - yarn: configures classic and/or berry if either is installed   (no-op otherwise)
#
# Reset to public registries: see docs/package-mirror.md.

set -euo pipefail

PIP_INDEX_URL="https://artifact-keeper.aperogroup.ai/api/v1/repositories/pypi-proxy/download/simple/"
PIP_TRUSTED_HOST="artifact-keeper.aperogroup.ai"
NPM_REGISTRY="https://artifact-keeper.aperogroup.ai/api/v1/repositories/npm-proxy/download/"
YARN_REGISTRY="https://artifact-keeper.aperogroup.ai/api/v1/repositories/yarn-proxy/download/"

say() { printf '  %s\n' "$*"; }
hdr() { printf '\n== %s ==\n' "$*"; }

hdr "pip"
if command -v pip >/dev/null 2>&1; then
  pip config set --user global.index-url "$PIP_INDEX_URL" >/dev/null
  pip config set --user global.trusted-host "$PIP_TRUSTED_HOST" >/dev/null
  say "index-url    = $(pip config get global.index-url 2>/dev/null)"
  say "trusted-host = $(pip config get global.trusted-host 2>/dev/null)"
else
  say "pip not found — skipped"
fi

hdr "npm / pnpm"
if command -v npm >/dev/null 2>&1; then
  npm config set registry "$NPM_REGISTRY" --location=user
  say "registry     = $(npm config get registry)"
  if command -v pnpm >/dev/null 2>&1; then
    say "pnpm reads ~/.npmrc — no extra step needed"
  fi
else
  say "npm not found — skipped (pnpm also skipped since it reads npm's config)"
fi

hdr "yarn"
if command -v yarn >/dev/null 2>&1; then
  yarn_version="$(yarn --version 2>/dev/null || echo unknown)"
  case "$yarn_version" in
    1.*)
      # yarn classic
      yarn config set registry "$YARN_REGISTRY" >/dev/null
      say "yarn $yarn_version (classic) registry = $(yarn config get registry 2>/dev/null)"
      ;;
    [2-9].*|[0-9][0-9].*)
      # yarn berry
      yarn config set npmRegistryServer "$YARN_REGISTRY" --home >/dev/null
      say "yarn $yarn_version (berry) npmRegistryServer set in ~/.yarnrc.yml"
      ;;
    *)
      say "yarn version '$yarn_version' not recognized — set manually"
      ;;
  esac
else
  say "yarn not found — skipped"
fi

hdr "verify"
say "pip:  pip index versions requests       (should list versions)"
say "npm:  npm view express version          (should print a version)"
say "      and the GET should hit artifact-keeper — confirm with --loglevel=http"
say ""
say "Done. Configs written to your user scope (~/.config/pip/pip.conf, ~/.npmrc, ~/.yarnrc[.yml])."
