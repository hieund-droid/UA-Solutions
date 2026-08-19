# Package mirror — `artifact-keeper.aperogroup.ai`

Apero proxies and security-scans Python / Node / Yarn packages through **`artifact-keeper.aperogroup.ai`**. All installs in Apero code should go through it.

You have two ways to wire it up. Pick based on whether you're working inside a project or outside of one.

| Where you're working                                | How to configure                                              |
|-----------------------------------------------------|---------------------------------------------------------------|
| Inside a project cloned from this template         | Already done — the project ships with `pip.conf` / `.npmrc`. |
| Ad-hoc work on your machine, outside any project    | Run the global setup script (below).                          |
| Claude Desktop's "code" sandbox / a fresh container | Paste the one-liner (below) at the start of your session.     |

---

## Set up globally (your machine)

From a checkout of this repo:

```sh
bash scripts/setup-package-mirror.sh
```

The script writes to your **user** config (not system-wide, no `sudo`):

- pip → `~/.config/pip/pip.conf`
- npm → `~/.npmrc` (pnpm reads this too)
- yarn → `~/.yarnrc` (classic) or `~/.yarnrc.yml` (berry)

It's idempotent — re-run any time.

### Without cloning the repo (Claude Desktop sandbox, fresh container, etc.)

```sh
curl -fsSL https://raw.githubusercontent.com/Apero-Vibecode/hq-apero-template/main/scripts/setup-package-mirror.sh | bash
```

### Windows

PowerShell, run once per machine:

```powershell
# pip
pip config set --user global.index-url    "https://artifact-keeper.aperogroup.ai/api/v1/repositories/pypi-proxy/download/simple/"
pip config set --user global.trusted-host "artifact-keeper.aperogroup.ai"

# npm (pnpm picks this up too)
npm config set registry "https://artifact-keeper.aperogroup.ai/api/v1/repositories/npm-proxy/download/" --location=user

# yarn classic (skip if you don't use yarn)
yarn config set registry "https://artifact-keeper.aperogroup.ai/api/v1/repositories/yarn-proxy/download/"
```

---

## Verify it worked

The trap to avoid: an `npm view` or `pip index` that **silently falls back to the public registry** looks like success. Always confirm the request hit artifact-keeper.

```sh
# pip — should list versions of requests
pip index versions requests

# npm — confirm the GET line shows artifact-keeper in the URL
npm view express version --loglevel=http
# look for: npm http fetch GET 200 https://artifact-keeper.aperogroup.ai/...
```

If the `http fetch` line points anywhere other than `artifact-keeper.aperogroup.ai`, the config didn't apply (most often: there's a `.npmrc` in cwd or in a parent dir overriding it).

---

## Reset to the public registries

If you ever need to undo (e.g. you're off the corp network and just need to install something to debug):

```sh
pip config unset --user global.index-url
pip config unset --user global.trusted-host
npm config delete registry --location=user
yarn config unset registry        # yarn classic
yarn config unset npmRegistryServer --home   # yarn berry
```

Don't commit a project with the public registry pinned — `.npmrc` / `pip.conf` inside this template's projects must keep pointing at artifact-keeper.

---

## What if the mirror is down?

The mirror is the only sanctioned source for production builds. If it's unavailable:

1. Don't switch to the public registry in a committed config — that bypasses the security scan and the `.claude/settings.json` bash guard blocks registry overrides anyway.
2. Ping **#devops**. They own the mirror.
3. For unblock-myself-locally: temporarily `pip install --index-url https://pypi.org/simple/ <pkg>` or `npm install <pkg> --registry=https://registry.npmjs.org/` on the command line. Don't write that into the repo.

---

## URLs in one place

| Tool | URL                                                                                       |
|------|-------------------------------------------------------------------------------------------|
| pip  | `https://artifact-keeper.aperogroup.ai/api/v1/repositories/pypi-proxy/download/simple/`   |
| npm  | `https://artifact-keeper.aperogroup.ai/api/v1/repositories/npm-proxy/download/`           |
| yarn | `https://artifact-keeper.aperogroup.ai/api/v1/repositories/yarn-proxy/download/`          |

The `/api/v1/repositories/<repo>/download/` shape is specific to artifact-keeper — it is not Sonatype Nexus and does not follow Nexus URL conventions. Use these URLs verbatim.
