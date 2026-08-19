#!/usr/bin/env bash
# PreToolUse hook on Bash. Deterministic deny-list — saves the AI from having
# to memorize every forbidden pattern. Exit 0 = allow, exit 2 = block.

set -euo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | sed -n 's/.*"command":[[:space:]]*"\([^"]*\)".*/\1/p')"
[[ -z "$cmd" ]] && exit 0

block() {
  echo "BLOCKED by apero-vibecode: $1" >&2
  echo "Escalate to #devops if you genuinely need this." >&2
  exit 2
}

case "$cmd" in
  # --- Supply chain ---
  *"curl "*"|"*" bash"*|*"curl "*"|"*" sh"*|*"wget "*"|"*" bash"*)
                                  block "curl|bash / wget|bash forbidden (supply chain)";;

  # --- The AI never installs packages. Period. ---
  # Edit the manifest (requirements.txt / package.json) and tell the user to install.
  "pip install"*|*"pip install "*|"pip3 install"*|*"pip3 install "*)
                                  block "AI does not run 'pip install' — edit requirements.txt and tell the user to run 'python -m pip install -r requirements.txt'";;
  *"python -m pip install"*|*"python3 -m pip install"*)
                                  block "AI does not run 'python -m pip install' — edit requirements.txt and tell the user to run it themselves";;
  *"pipx install"*|*"pip uninstall"*)
                                  block "AI does not install/uninstall Python packages — edit requirements.txt";;
  "npm install"|"npm install "*|"npm i "|"npm i "*)
                                  block "AI does not run 'npm install' — edit package.json and tell the user to run 'pnpm install'";;
  "pnpm install"|"pnpm install "*|"pnpm add"|"pnpm add "*)
                                  block "AI does not run 'pnpm install/add' — edit package.json and tell the user to run 'pnpm install'";;
  "yarn install"|"yarn install "*|"yarn add"|"yarn add "*)
                                  block "AI does not run 'yarn install/add' — edit package.json and tell the user to install";;
  *"npm uninstall"*|*"pnpm remove"*|*"yarn remove"*)
                                  block "AI does not uninstall packages — edit package.json";;
  "npx -y "*)                     block "no 'npx -y' — that runs an unaudited package. Add to package.json instead.";;

  # --- Destruction / force ---
  *"rm -rf /"*|*"rm -fr /"*)      block "rm -rf / is never the right answer";;
  *"git push --force"*|*"git push -f"*|*"git push --force-with-lease"*)
                                  block "force-push is denied by company policy";;
  *"git reset --hard"*)           block "destructive reset — stash or branch instead";;
  *"--no-verify"*)                block "do not bypass git hooks. Fix the failing hook.";;
  *"chmod 777"*|*"chmod -R 777"*) block "chmod 777 is never correct";;
  *" sudo "*|"sudo "*)            block "sudo is unnecessary in a project repo";;

  # --- Destruction / force ---
  *"rm -rf /"*|*"rm -fr /"*)      block "rm -rf / is never the right answer";;
  *"git push --force"*|*"git push -f"*|*"git push --force-with-lease"*)
                                  block "force-push is denied by company policy";;
  *"git reset --hard"*)           block "destructive reset — stash or branch instead";;
  *"--no-verify"*)                block "do not bypass git hooks. Fix the failing hook.";;
  *"chmod 777"*|*"chmod -R 777"*) block "chmod 777 is never correct";;
  *" sudo "*|"sudo "*)            block "sudo is unnecessary in a project repo";;

  # --- Deploy / infra (DevOps owns these) ---
  kubectl*|*" kubectl "*)         block "no kubectl in an app repo — invoke the DevOps deploy MCP";;
  helm*|*" helm "*)               block "no helm in an app repo — DevOps owns manifests";;
  kustomize*|*" kustomize "*)     block "no kustomize in an app repo — DevOps owns manifests";;
  *"aws eks "*|*"aws ecr "*)      block "no aws eks/ecr in an app repo — DevOps owns the cluster";;
  *"gcloud container "*)          block "no gcloud container in an app repo — DevOps owns the cluster";;
  *"docker push "*)               block "image push happens via the DevOps deploy MCP, not from your shell";;
  *"terraform apply"*|*"terraform destroy"*)
                                  block "terraform changes are DevOps-only — open a ticket in #devops";;

  # --- Crypto / dangerous patterns ---
  *"openssl genrsa"*|*"openssl req"*"-x509"*) block "no ad-hoc key generation — get certs from #devops";;
esac

exit 0
