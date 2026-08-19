#!/usr/bin/env bash
# PreToolUse hook on Write|Edit:
# - Block writes that look like real secrets.
# - Block writes that add k8s manifests to an app repo (DevOps owns those).
# Exit 0 = allow, exit 2 = block (stderr is shown to the user + the model).
# Hook payload is JSON on stdin: { "tool_input": { ... } }.

set -euo pipefail

input="$(cat)"

block() {
  echo "BLOCKED by apero-vibecode: $1" >&2
  echo "Route: $2" >&2
  exit 2
}

# --- Secret patterns ---
secret_patterns=(
  "AKIA[0-9A-Z]{16}"                          # AWS access key
  "-----BEGIN [A-Z ]*PRIVATE KEY-----"        # PEM private key
  "sk_live_[0-9a-zA-Z]{20,}"                  # Stripe live
  "xox[abp]-[0-9A-Za-z-]{10,}"                # Slack
  "ghp_[0-9a-zA-Z]{30,}"                      # GitHub PAT
  "ya29\\.[0-9A-Za-z_-]{20,}"                 # Google OAuth
  # No-prefix hardcoded-assignment catcher; relies on -i (below) for case-insensitivity.
  # (Old inline `(?i)` was non-portable on strict POSIX grep.)
  "(api[_-]?key|apikey|secret(_key)?|password|passwd|access[_-]?token|auth[_-]?token|bearer[_-]?token|client[_-]?secret|private[_-]?key)[[:space:]]*[:=][[:space:]]*[\"'][^\"']{20,}[\"']"
)
for pat in "${secret_patterns[@]}"; do
  if printf '%s' "$input" | grep -iE -q "$pat"; then
    block "edit contains a secret-shaped value (matches /$pat/)" \
          "if false-positive, send the literal value to #devops"
  fi
done

# --- K8s / Helm manifests in app repo ---
# Heuristic: payload contains both `apiVersion:` and `kind:` near each other.
if printf '%s' "$input" | grep -E -q 'apiVersion:[[:space:]]*[a-zA-Z]' \
&& printf '%s' "$input" | grep -E -q 'kind:[[:space:]]*(Deployment|Service|Ingress|ConfigMap|Secret|StatefulSet|DaemonSet|Job|CronJob|HorizontalPodAutoscaler|HelmChart|HelmRelease|Kustomization)'; then
  block "edit looks like a Kubernetes/Helm manifest — manifests live with the DevOps team, not in app repos" \
        "ask #devops to make the change, or describe the desired k8s behavior to them"
fi

exit 0
