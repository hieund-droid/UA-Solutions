# Vault — getting and using secrets (DEFERRED — future feature)

> **STATUS: DEFERRED. Not required today.** Vault is a future option for a shared,
> audited secret store. It's deliberately **not** wired into the templates right now —
> applying it is too heavy for most projects at this stage. **Today's standard is
> `.env`:** declare each secret as a `Settings` / `ConfigSchema` field named `SECRET_*`,
> read it directly, and keep the real value in `.env` (gitignored, never committed).
> See the master `CLAUDE.md` → "Secrets — declared in config, read from `.env`".
>
> Don't wire any of the below pre-emptively. This doc is kept as the reference for
> **when** a venture later adopts Vault — adopting it would reintroduce a thin
> `get_secret()` resolver over the same `SECRET_*` config fields, so call sites
> wouldn't change. Until then, treat everything below as background, not instructions.

Apero will store secrets in HashiCorp Vault at **https://hq-vault.aperogroup.ai** once
this is adopted. This doc covers the two things you'd need then:

1. **One-time human bootstrap** — log into the UI, get your personal token.
2. **Runtime** — your app reads secrets through a `get_secret()` / `getSecret()` resolver using that token.

Your AI assistant will not log you in. The browser step has to happen with your own hands.

---

## 1. Log in and get your personal token (browser, ~30 seconds)

1. Open <https://hq-vault.aperogroup.ai/ui/vault/auth>.
2. **Method**: `OIDC`.
3. Click **More options** (or *Advanced Settings*) → set **Mount path** to your **venture**:
   - `apero-hq`
   - `apero-visionlab`
   - `apero-terasofts`
   - `apero-supermind`
4. Click **Sign in with OIDC Provider** — a browser tab opens, you authenticate via Apero SSO, and you're returned to Vault logged in.
5. Top-right corner → click your user icon → **Copy token**. That's your **personal Vault token** (starts with `hvs.…`).

> **The token is a secret.** Treat it like a password — don't paste it into Slack, tickets, or commits. It expires (typically 24h–7d depending on policy); if a call returns `403`, you've expired — log in again.

## 2. Tell your app where Vault is and which mount to read

Add these to your local `.env` (gitignored). In prod they come from the secret manager configuration — you don't set them by hand:

```bash
SECRET_PROVIDER=vault
VAULT_ADDR=https://hq-vault.aperogroup.ai
VAULT_TOKEN=hvs.CAESI...your-personal-token...
VAULT_MOUNT=apero-hq                   # same name as your venture's OIDC mount
```

In `vault` mode, a spec of `"FOO"` reads from `${VAULT_ADDR}/v1/${VAULT_MOUNT}/data/FOO` (the field named `value`); `"FOO:bar"` reads the `bar` field at path `FOO`. (Call sites always pass `settings.X`, never the literal — see §3. `local` vs `vault` — see §4.)

## 3. The convention — one spec string, string in / string out

**The API has one shape: `get_secret(spec)` returns a string.**

`spec` is either:
- `"<path>"` — reads the field named `value` at that path. The single-field default.
- `"<path>:<field>"` — reads a named field. Use when the path holds **multiple fields that rotate together** (e.g. an OAuth provider's `client-id` + `client-secret` under `oauth/google` — regenerating the OAuth client rotates both at once).

Each Apero project declares its secrets as `Settings` fields, one entry per logical secret, defaulted to a spec string and overridable from `.env`. Call sites are uniform: `get_secret(settings.X)`. They don't know whether `X` is single-field or shares a path with siblings — that's encoded in the spec.

**Rotation is the grouping test.** Share a path only when an ops event rotates all the fields at once. Unrelated secrets (`openai/api-key`, `cloudflare/api-token`) get their own paths — sharing means rotating one forces re-saving all.

Need a JSON blob in one field? Stringify before storing, parse after reading. The helper still returns a string.

### Storing (human, in the Vault UI — ~20 seconds)

You don't need the Vault CLI. The browser UI is the supported path.

1. Open <https://hq-vault.aperogroup.ai/ui> and make sure you're signed in (see §1).
2. **Secrets** (left sidebar) → click your venture's KV mount: `apero-headquarter/` (or your venture name).
3. Click **Create secret +**.
4. **Path for this secret**: the part of the spec **before** the colon — e.g. `openai/api-key`, or `oauth/google` for a multi-field secret. **Use only the secret name. Don't include the mount.**
5. **Secret data**:
   - **Single-field** (spec is just `"<path>"`): Key = `value` (lowercase, exactly this), Value = the actual secret string.
   - **Multi-field** (spec is `"<path>:<field>"`): add one row per field — e.g. `client-id`, `client-secret` — each with its own value.
6. **Save**.

Verify by reopening the secret — you should see one row per field, each value hidden as `********` (click the eye to reveal).

<details>
<summary>CLI equivalent (only if you have <code>vault</code> installed)</summary>

```bash
# Single-field — the default convention
vault kv put apero-headquarter/openai/api-key value='sk-…'

# Multi-field — only when the fields rotate together
vault kv put apero-headquarter/oauth/google \
  client-id='…apps.googleusercontent.com' \
  client-secret='GOCSPX-…'
```
</details>

### Reading (in code — always via a `Settings` field, never a literal)

```python
# src/config.py
class Settings(BaseSettings):
    secret_openai_api_key:             str = Field(default="openai/api-key")
    secret_google_oauth_client_id:     str = Field(default="oauth/google:client-id")
    secret_google_oauth_client_secret: str = Field(default="oauth/google:client-secret")

# call sites
api_key      = get_secret(settings.secret_openai_api_key)               # single-field
oauth_id     = get_secret(settings.secret_google_oauth_client_id)       # multi-field — sibling of the next
oauth_secret = get_secret(settings.secret_google_oauth_client_secret)
```

```ts
// Node / TS — same pattern
const apiKey      = await getSecret(config.SECRET_OPENAI_API_KEY);
const oauthId     = await getSecret(config.SECRET_GOOGLE_OAUTH_CLIENT_ID);
const oauthSecret = await getSecret(config.SECRET_GOOGLE_OAUTH_CLIENT_SECRET);
```

That's the entire API. No `get_secrets(path) -> dict`, no field-name discovery, no `field=` kwarg. If you want all fields of a path, declare one `Settings` entry per field and call `get_secret(settings.X)` for each — explicit, auditable, and each secret has its own line in `.env` that ops can repoint.

## 4. `SECRET_PROVIDER` — `local` vs `vault`

One env var, `SECRET_PROVIDER`, switches how `get_secret(settings.X)` resolves every secret. **The call site never changes** — `get_secret(settings.secret_openai_api_key)` is identical in both modes. Only the *value* of the `SECRET_*` var in `.env` differs, and the provider decides how to read it.

| | `SECRET_PROVIDER=local` | `SECRET_PROVIDER=vault` |
|---|---|---|
| What the `.env` var holds | the **real secret value** | a **Vault spec** (`"<path>"` or `"<path>:<field>"`) |
| Example `.env` line | `SECRET_OPENAI_API_KEY=sk-abc123…` | `SECRET_OPENAI_API_KEY=openai/api-key` |
| What `get_secret` does | returns the value as-is | fetches that field from Vault at run time |
| Where the secret lives | in your gitignored `.env` only | in Vault (`.env` holds only the pointer) |
| Use for | laptop dev | dev / staging / prod, anything shared |

Going from local to vault is config-only — no code changes: flip `SECRET_PROVIDER=vault`, change each `SECRET_*` line from the literal value to its Vault path, and set `VAULT_TOKEN` + `VAULT_MOUNT` (§1–§2).

```bash
# laptop dev — secret values live in .env
SECRET_PROVIDER=local
SECRET_OPENAI_API_KEY=sk-abc123…

# shared / prod — .env points at Vault; the value lives in Vault
SECRET_PROVIDER=vault
SECRET_OPENAI_API_KEY=openai/api-key
VAULT_TOKEN=hvs.…
VAULT_MOUNT=apero-headquarter
```

**Never ship `SECRET_PROVIDER=local` past your laptop** — it means real secret values sit in an env file instead of Vault. In k8s, the provider is `vault` and values come from Vault, never a committed file.

> `aws` and `gcp` providers are stubbed in `config.py` / `config.ts` for future use — #devops wires them when a venture needs them.

## 5. Instructions for Claude Code (and any AI assistant)

You're reading this because the code you're writing needs a secret. **Read this section, then send the user the exact message in 5b. Do not improvise.**

### 5a. What you (the AI) will and won't do

- ✅ Edit `src/config.py` / `src/config.ts` to wire a new secret: add a `Settings` entry with a `"<path>"` or `"<path>:<field>"` default, add the matching line to `.env.example`, and call `get_secret(settings.X)` at the use site.
- ✅ Reference the secret by its Settings name in docs / READMEs.
- ❌ Log into Vault for the user. The OIDC flow is a browser step — you can't do it.
- ❌ Type the secret value into Vault for the user — whether via the UI or CLI. The user puts the value in, in their own browser. You only tell them *where* to click and *what to fill in*.
- ❌ Print, echo, or log the secret value — not even masked, not even once, not even in tests.
- ❌ Pass a literal spec to `get_secret(...)`. Always go through a `Settings` field — ops control depends on it.
- ❌ Pack unrelated secrets under one path. Multi-field is allowed **only** when the fields rotate together (OAuth `client-id` + `client-secret`; an API key + its webhook-signing secret). Two API keys with independent rotation cycles get two paths.
- ❌ Commit a real `VAULT_TOKEN` or a real secret value to git. If you see one in a diff, stop and tell the user.

### 5b. Message to send the user when a new secret is needed

When your code adds `get_secret("NEW_SECRET_NAME")` (or `getSecret(...)`), the secret doesn't exist in Vault yet — the user has to store it. **Send them exactly this** (filling in the angle brackets, keeping the structure). Use the single-field block for `get_secret(path)` and the multi-field block for `get_secret(path, field=…)`.

**Single-field** (the default — `get_secret(path)`):

> I added `get_secret("<NEW_PATH>")` at `<file:line>`. Before you run this, store the value in Vault — all in the browser, no CLI needed:
>
> **1. Sign in to Vault** (skip if you already have `VAULT_TOKEN` in `.env` and it hasn't expired):
>   - Open <https://hq-vault.aperogroup.ai/ui/vault/auth>
>   - Method: **OIDC**
>   - Click **More options** → Mount path: **`<your-venture>`** (one of `apero-hq` / `apero-visionlab` / `apero-terasofts` / `apero-supermind`)
>   - **Sign in with OIDC Provider** → authenticate via Apero SSO.
>   - Top-right user icon → **Copy token** → paste into `.env`: `VAULT_TOKEN=hvs.…`
>
> **2. Create the secret in the UI**:
>   - From the Vault sidebar: **Secrets** → click **`<your-venture>/`**.
>   - Click **Create secret +**.
>   - **Path for this secret**: `<NEW_PATH>` (exactly this — don't prefix with the mount).
>   - **Secret data**:
>     - Key: `value`
>     - Value: *(paste the real secret here, in your browser only)*
>   - Click **Save**.
>
> **3. Confirm**: reopen the secret in the UI — you should see one row with `value = ********`.
>
> Don't paste the secret value back into this chat — I don't need it, and pasting it here would log it. Once it's saved, just say "done" and I'll continue.

**Multi-field** (`get_secret(path, field=…)` — fields rotate together, e.g. `db/main` with `host` / `port` / `user` / `password`):

> I added `get_secret("<NEW_PATH>", field=...)` at `<file:line>` for fields: `<field1>`, `<field2>`, … . These fields rotate together, so they live under one Vault path. Before you run this, store them all in Vault:
>
> **1. Sign in to Vault** (skip if you already have `VAULT_TOKEN` in `.env` and it hasn't expired):
>   - *(same as the single-field flow above — OIDC at <https://hq-vault.aperogroup.ai/ui/vault/auth>, mount = your venture, copy token into `.env`)*
>
> **2. Create the secret in the UI**:
>   - **Secrets** → **`<your-venture>/`** → **Create secret +**.
>   - **Path for this secret**: `<NEW_PATH>` (exactly this — don't prefix with the mount).
>   - **Secret data**: add one row per field —
>     - `<field1>` → *(value in your browser only)*
>     - `<field2>` → *(value in your browser only)*
>     - …
>   - Click **Save**.
>
> **3. Confirm**: reopen the secret — you should see one row per field, each `********`.
>
> Don't paste any of the values back into this chat. Once saved, say "done".

### 5c. Message when the user hasn't set `VAULT_TOKEN` yet

If you're about to test and `.env` is missing `VAULT_TOKEN`, send:

> Your `.env` doesn't have a `VAULT_TOKEN` — `get_secret()` will fail. Get one from <https://hq-vault.aperogroup.ai/ui/vault/auth> (OIDC, mount path = your venture), then paste it into `.env` as `VAULT_TOKEN=hvs.…`. Full bootstrap: `docs/vault.md` §1.

## 6. When things break

| Symptom | Likely cause | Fix |
|---|---|---|
| `403 permission denied` | Token expired, or wrong `VAULT_MOUNT` for your venture | Re-login; double-check mount path |
| `404 ... not found` | Secret doesn't exist at that path, or KV v2 path mismatch | `vault kv get <mount>/<name>` to confirm |
| `connection refused` / DNS | Not on the office network / VPN | Connect to VPN |
| `Secret X has no 'value' field` | You stored it under a different key, but the call site used the default `field="value"` | Either re-put with `value=...`, or update the call site to `get_secret(path, field="<the field you used>")` |
| `Secret X has no 'password' field. Available fields: ['host', 'port', 'user']` | Field name typo, or the field wasn't stored | The error tells you what *is* there — either fix the call-site field name or add the missing field in the Vault UI |

## Contacts

- Vault outages / policy questions / your token doesn't get the right access → **#devops**
- "How do I use `get_secret()` in my app?" → **#vibecode-help**
