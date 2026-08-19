#!/usr/bin/env bash
# scripts/sync-plugin-to-templates.sh
#
# Canonical source of truth for hook scripts, skills, and the security-reviewer
# sub-agent lives in claude-plugin/. Each templates/<stack>/.claude/ ships an
# inlined copy so a bootstrapped project gets them at clone time, without a
# separate plugin install.
#
# This script mirrors claude-plugin/{hooks,skills,agents} into every
# templates/<stack>/.claude/. Idempotent — safe to run any time. Run before
# committing changes to claude-plugin/ so the templates stay in sync.
#
# Usage:
#   bash scripts/sync-plugin-to-templates.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN="$ROOT/claude-plugin"
STACKS=(python nodejs react)

if [ ! -d "$PLUGIN/hooks" ] || [ ! -d "$PLUGIN/skills" ] || [ ! -d "$PLUGIN/agents" ]; then
  echo "ERROR: expected claude-plugin/{hooks,skills,agents} at $PLUGIN" >&2
  exit 1
fi

for stack in "${STACKS[@]}"; do
  dest="$ROOT/templates/$stack/.claude"
  if [ ! -d "$dest" ]; then
    echo "skip: $dest (template missing .claude/)" >&2
    continue
  fi

  rm -rf "$dest/hooks" "$dest/skills" "$dest/agents"
  mkdir -p "$dest/hooks" "$dest/skills" "$dest/agents"

  cp "$PLUGIN/hooks/"*.sh "$dest/hooks/"
  chmod +x "$dest/hooks/"*.sh

  cp -R "$PLUGIN/skills/"* "$dest/skills/"
  cp "$PLUGIN/agents/"*.md "$dest/agents/"

  echo "synced: templates/$stack/.claude/ ← claude-plugin/"
done

echo "done."
