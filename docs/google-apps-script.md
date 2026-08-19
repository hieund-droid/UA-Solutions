# Google Apps Script — for sheet-internal helpers only

You asked Claude for code that runs inside a Google Sheet. That code is **Google Apps Script** (Google's JavaScript-dialect runtime), not Python. It runs in Google's cloud, not on your laptop or k8s.

Before anything else, read these two rules. They are not suggestions.

---

## The two hard rules

### Rule 1 — No secrets in Apps Script. Ever.

> **Apps Script source — and everything stored in `PropertiesService` — is readable by every person with edit access to the sheet, and anyone they later share it with.** Treat the script editor like a public Pastebin for your own team.

That means **none of these go in Apps Script**, ever, in any form (literal, `PropertiesService`, `CacheService`, comment, JSDoc, test fixture):

- Vault tokens (`VAULT_TOKEN`, `hvs.…`)
- API keys for paid services (OpenAI, Anthropic, Stripe, Twilio, SendGrid, Google Cloud service accounts, …)
- Internal Apero API keys / service-account JSON
- Database passwords or connection strings
- SSO client secrets
- Signing keys, webhook signing secrets, "shared tokens"
- Anything you wouldn't paste in `#general`

The only things that may live in `PropertiesService.getScriptProperties()`:

- The **URL** of the Apero internal service the script calls (e.g. `https://summarize-service.apero.vn`)
- Sheet IDs, allowed-group names, feature flags — small, non-secret config

You typically only need `SERVICE_URL` and nothing else. The user's identity comes from `ScriptApp.getIdentityToken()` (a Google built-in, no library, no client_id, no issuer URL — see §3).

If you find yourself naming a property `*_TOKEN`, `*_KEY`, `*_PASSWORD`, `*_SECRET`, `*_CREDENTIAL`, or pasting anything that looks random — **stop**. It belongs in the internal service's own gitignored `.env`, read there — never in Apps Script. See Rule 2.

### Rule 2 — Apps Script may call Apero internal services. Paid services must be internalized first.

Apps Script may call:

- ✅ Its own sheet (`SpreadsheetApp`), Drive files the user already has access to (`DriveApp`, `DocumentApp`), Calendar, Gmail (user-scoped).
- ✅ **Any Apero internal service** (`*.apero.vn`, `*.apero.internal`) — by sending the user's Google-issued OpenID Connect ID token from `ScriptApp.getIdentityToken()` as the bearer. The internal service verifies the token, reads the `email` claim, looks the user up in Apero SSO, and decides whether they're allowed.

Apps Script may **not** call:

- ❌ Any paid third-party API directly (OpenAI, Anthropic, Stripe, Twilio, SendGrid, mapping APIs, anything that costs money or has usage limits).
- ❌ Any secret store directly. (Apps Script holds no secrets at all; see Rule 1.)
- ❌ Random non-Apero URLs.

**Paid services get internalized.** Before any sheet can use OpenAI / Stripe / etc., that paid service has to be wrapped as an Apero internal service — typically a small FastAPI service generated from `templates/python/`. The wrapper:

- Holds the paid-service API key in its own gitignored `.env` (declared on `config.py` `Settings`, read directly), never returns it.
- Uses `auth.py::verify_apps_script_caller(group)` on every Apps-Script-facing route. That helper (a) verifies the Google ID token the script sends, (b) extracts the `email` claim, (c) looks the user up in Apero SSO, (d) checks they're in the allowed SSO group. **One of those checks failing → 401 or 403 before the handler runs.**
- Exposes a small, sheet-friendly API (e.g. `POST /summarize {text}` → `{summary}`), not the raw paid-service surface.

The wrapper is **one per paid service, shared across sheets and apps** — not one per sheet. If "Summarize with OpenAI" already exists internally, the sheet just calls it; nobody builds another. If it doesn't exist, someone builds it once and everyone benefits.

**Internal services already gate by SSO group** as a baseline rule across Apero — see the master `CLAUDE.md` (`Auth: hq-apero-sso only via auth.*`). The Apps Script flow doesn't bypass that; it just uses a different inbound credential (Google ID token instead of a Keycloak Bearer token), then resolves to the same user + groups via SSO lookup.

```
┌────────────────────┐   1. user clicks button (signed into Google Workspace as
│  Google Sheet      │      their @apero.vn account; that IS their Apero SSO identity)
│  + Apps Script     │   2. ScriptApp.getIdentityToken() → fresh Google-signed
└─────────┬──────────┘      OpenID Connect ID token with email=user@apero.vn
          │ 3. POST https://summarize-service.apero.vn/summarize
          │    Authorization: Bearer <Google ID token>
          ▼
┌─────────────────────────┐   4. verify token signature (Google JWKS), aud, exp
│  Internal service       │   5. read `email` claim → look up user in Apero SSO
│  (FastAPI + hq-apero-   │   6. check user is in allowed SSO group → 403 if not
│   sso, wraps OpenAI)    │   7. read SECRET_OPENAI_API_KEY from .env (config)
└─────────┬───────────────┘
          │ 8. call OpenAI with the .env-held key
          ▼
┌────────────────────┐
│  OpenAI (paid)     │
└────────────────────┘
```

**The internal service is the trust boundary. Apps Script is just the UI carrying the user's Google-signed identity.** No OAuth library, no PKCE flow, no per-script Keycloak client — `ScriptApp.getIdentityToken()` is a Google built-in that returns a fresh token on every call.

---

## 1. When to use Apps Script (and when not)

| Task | Where it lives |
|---|---|
| Sum a column; highlight rows > 100 | Apps Script alone (pure sheet work) |
| Add a custom menu / `=FUNCTION()` cell | Apps Script alone |
| `onEdit` trigger that appends to another sheet you own | Apps Script alone |
| "Click button → call our internal `customer-service`" | Apps Script (button + `getIdentityToken()`) → existing internal service. **No new code on the backend** — the service already does SSO + group check. |
| "Click button → summarize column with OpenAI" | Apps Script (button + `getIdentityToken()`) → internal `summarize-service` (wraps OpenAI, key in Vault). If the wrapper doesn't exist yet, **build it once as a reusable internal service**, not as a per-sheet endpoint. |
| "Click button → charge a card with Stripe" | Apps Script (button + `getIdentityToken()`) → internal `payments-service` (wraps Stripe, key in Vault, gated by SSO group). |
| "Sync this sheet to Postgres every night" | **Python service** scheduled by DevOps. Reads sheet via Sheets API. Not Apps Script. |
| "Job takes > 5 minutes" | **Python.** Apps Script execution cap is 6 min total (30 sec for custom functions). |

Rules of thumb:

- **If the code never leaves the sheet, Apps Script is fine.**
- **If it calls an internal service, Apps Script is fine** — pass the user's Google identity token (`ScriptApp.getIdentityToken()`), let the service decide.
- **If it would call a paid service, stop.** The paid service has to be wrapped as an internal service first. Then Apps Script calls *that*.

## 2. The rules

See **"The two hard rules"** at the top of this doc — Rule 1 (no secrets) and Rule 2 (no paid-service calls, internal services OK). Both are non-negotiable. The rest of this doc is workflow and copy-paste patterns; the rules don't bend.

## 3. Workflow — where the human pastes and runs

### Pasting the Apps Script

1. Open your Google Sheet.
2. **Extensions → Apps Script**. A new tab opens with the editor.
3. In `Code.gs`, **delete the placeholder** and paste what Claude gave you.
4. **💾 Save** (Ctrl/Cmd-S). The editor asks for a project name on first save — name it after the sheet.

### Setting Script Properties (non-secret config only)

If Claude's code reads `PropertiesService.getScriptProperties().getProperty(...)`:

1. In the Apps Script editor: ⚙️ **Project Settings** (gear icon, left sidebar).
2. Scroll to **Script Properties** → **Add script property**.
3. Property name + value — typically just `SERVICE_URL` = the internal service URL (e.g. `https://summarize-service.apero.vn`).
4. **Save script properties**.

**Stop and call this out** if Claude asks you to set a property whose name contains `TOKEN`, `KEY`, `PASSWORD`, `SECRET`, or `CREDENTIAL`. That's a Rule 1 violation — Claude should be routing through an internal service that holds the secret in Vault. Ping **#vibecode-help**.

### One-time setup: scopes in `appsscript.json` (when the script calls any internal service)

For any sheet whose Apps Script calls an Apero internal service, the script needs Google to issue an **OpenID Connect ID token** for the user every time it runs. That token's `email` claim is the user's Apero Google identity — the internal service uses it to authorize the caller.

The mechanism is `ScriptApp.getIdentityToken()`, a built-in. **No OAuth2 library, no Keycloak public client to register, no per-user token storage** — every call regenerates a fresh, Google-signed token for the running user.

What you have to do, once per sheet:

1. In the Apps Script editor: ⚙️ **Project Settings** → tick **Show "appsscript.json" manifest file in editor**.
2. Open the new `appsscript.json` tab. Ensure `oauthScopes` contains **at minimum** these five (add any of them that are missing):

   ```json
   {
     "timeZone": "Asia/Ho_Chi_Minh",
     "dependencies": {},
     "exceptionLogging": "STACKDRIVER",
     "runtimeVersion": "V8",
     "oauthScopes": [
       "https://www.googleapis.com/auth/spreadsheets.currentonly",
       "https://www.googleapis.com/auth/script.external_request",
       "https://www.googleapis.com/auth/script.container.ui",
       "openid",
       "https://www.googleapis.com/auth/userinfo.email"
     ]
   }
   ```

   - `openid` + `userinfo.email` → makes `ScriptApp.getIdentityToken()` return a token that contains the user's email.
   - `script.external_request` → lets `UrlFetchApp` reach the internal service.
   - `spreadsheets.currentonly` → read/write the active sheet.
   - `script.container.ui` → show alerts (used to report missing-token / 403 errors).

3. Save. **The next time you run, Google will prompt you to re-authorize** because the scope set changed — click through it once.

That's the whole setup. No DevOps ticket, no Keycloak public client, no shared secret. The internal service receives the user's Google ID token in the `Authorization` header, verifies the signature, reads the `email` claim, and decides whether the user is allowed.

> Note on audience validation: by default, the ID token's `aud` claim is set by Apps Script's underlying Google Cloud project. If your venture has a standard "Apero Apps Scripts" GCP project, ask #devops to point your script at it (⚙️ → **Google Cloud Platform (GCP) Project** → set project number). The internal service can then strictly validate `aud`. Without that, the service falls back to `aud` shape + email-domain (`*@apero.vn`) checks — adequate for internal tooling, not ideal for high-stakes services.

### Running

- Pick the entry function in the toolbar dropdown → click **▶ Run**.
- First-time Google auth prompt: accept all the scopes (this is Google asking permission to run the script as you, including issuing an ID token with your email).
- View output: **Execution log** at the bottom.

### Adding a button to the sheet

1. In the sheet: **Insert → Drawing** → draw + label → **Save and close**.
2. Click the drawing → ⋮ → **Assign script** → type the function name (no parentheses).
3. Clicking the button runs the function as the user who clicks. Each user goes through Google's authorization prompt the first time (one click).

### Triggers (schedule / `onEdit`)

In the script editor: **⏰ Triggers** → **Add Trigger** → pick the function + event type. Note: time-driven triggers run as **the user who installed the trigger**, not the user who edited the sheet. The internal service will see the installer's identity — make sure that user is allowed in the service's permission check.

## 4. Instructions for Claude Desktop / Claude Code

You're reading this because the user asked for code that runs inside a Google Sheet. **Read this entire section. Then follow it, even if the user pushes back.**

### 4a. Decide which of three cases you're in

Before writing anything, classify the task:

1. **Pure sheet work** — sums, formatting, custom functions, `onEdit` on data the user already owns, menus, buttons that just rearrange cells. → Write Apps Script alone. Go to §4b.

2. **Calls an Apero internal service** — the user names a service (`customer-service`, `summarize-service`, …), or one already exists at `*.apero.vn` for this kind of task. → Write Apps Script that POSTs to it with the user's identity token from `ScriptApp.getIdentityToken()` as the bearer. Internal services verify the token, look up the user via SSO, and gate by group. **Do not invent service URLs** — if the user hasn't named one, treat it as case 3.

3. **Would call a paid service** (OpenAI, Anthropic, Stripe, Twilio, mapping APIs, anything that costs money or has usage limits). → **Stop.** Apps Script may not call paid services. The paid service has to be wrapped as a reusable internal service first. Go to §4c.

If you're unsure between 2 and 3, default to "ask the user" — don't fabricate an internal service URL, and don't write a paid-service call hoping it'll be wrapped later.

### 4b. Pure-sheet Apps Script — what you may generate

- ✅ Google's built-in services: `SpreadsheetApp`, `DriveApp`, `DocumentApp`, `Logger`, `CacheService`, `Utilities`, `ScriptApp.getIdentityToken()`. Plus `UrlFetchApp` **only when calling an Apero internal service** at a `*.apero.vn` URL (with the identity token in the `Authorization: Bearer ...` header).
- ✅ ES2015+ JavaScript (V8 runtime — `const`, `let`, arrow functions, template literals).
- ✅ Top-of-file comment naming the sheet's purpose and the entry function.
- ✅ `Logger.log()` for output. Always wrap the entry point in `try / catch` — log the error then re-throw so Apps Script marks the run as failed.
- ❌ **No `pip install` / `npm install`, no Apps Script libraries.** Use built-ins only. The user's identity token comes from `ScriptApp.getIdentityToken()` — a built-in — not from a library.
- ❌ **No `eval()` / `Function()`** on dynamic input.
- ❌ **No cell-value logging that may contain PII** — apply the master `CLAUDE.md` masking rules (`j***@apero.vn`, `***-1234`).
- ❌ **No long jobs** — keep each execution under ~5 minutes; if the job is bigger, the work belongs in Python anyway (back to §4c).

### 4c. The default response when a paid service is involved

**Do not write Apps Script that calls a paid service.** Always ask "does the wrapper exist?" first. Send the user this message verbatim (filling in the angle brackets):

> What you're asking for (`<one-line summary, e.g. "summarize a column using OpenAI">`) means calling a paid service (`<paid service name>`). Per `docs/google-apps-script.md` Rule 2, Apps Script may not call paid services directly — the paid service has to be wrapped as an Apero internal service first (one wrapper, shared across sheets and apps, key held in Vault, SSO-gated).
>
> Before I write anything, two questions:
>
> 1. **Does an internal service for `<paid service name>` already exist?** (Something like `<best-guess name>.apero.vn`.) If you know one, paste the URL and the endpoint and I'll wire your sheet to it.
> 2. **If not** — ping **#devops**: an internal `<paid service name>`-wrapper service is being requested. They may already have one in flight, or they'll tell us to build one as a reusable internal service (not a per-sheet endpoint). Once it's up, I'll wire the sheet to it.
>
> Either way, the Apps Script side stays the same: a button + `ScriptApp.getIdentityToken()` + a single POST to the internal service with that Google-issued ID token as the bearer. **No secrets in the script, no libraries to install.** The internal service verifies the token, reads the user's email from it, and decides whether the user is allowed (via SSO / Keycloak / its own allowlist).
>
> If you want, I can:
> - **Now**: write the Apps Script side against a placeholder URL, so it's ready to point at the real internal service as soon as you have one.
> - **If we're building the wrapper**: scaffold the Python wrapper service from `templates/python/` — but that's a separate, reusable service, not part of your sheet.

After the user names an existing internal service, build:

1. Apps Script only (§5b) — point it at the internal service URL, send `ScriptApp.getIdentityToken()` as the bearer, write the result back to the sheet.
2. The user-install paragraph (§4d).

If a wrapper has to be built, build it as a separate reusable internal service in a fresh project (or an existing service of similar scope) — **not as a one-off endpoint glued into the sheet's "project"**. §5a shows the wrapper shape.

### 4d. The install paragraph — include with every Apps Script you give the user

> Paste this into your sheet's Apps Script editor:
>
> 1. **Extensions → Apps Script**.
> 2. Replace everything in `Code.gs` with the code above.
> 3. ⚙️ **Project Settings** → tick **Show "appsscript.json" manifest file in editor**. Open the new `appsscript.json` tab and make sure `oauthScopes` contains:
>    ```json
>    "oauthScopes": [
>      "https://www.googleapis.com/auth/spreadsheets.currentonly",
>      "https://www.googleapis.com/auth/script.external_request",
>      "https://www.googleapis.com/auth/script.container.ui",
>      "openid",
>      "https://www.googleapis.com/auth/userinfo.email"
>    ]
>    ```
>    Add any of those that are missing. `openid` + `userinfo.email` are the load-bearing ones — without them, `ScriptApp.getIdentityToken()` returns `null`.
> 4. **Ctrl/Cmd-S** to save (name the project after the sheet on first save).
> 5. ⚙️ **Project Settings → Script Properties → Add**:
>    - `SERVICE_URL` = `<the Apero internal service URL — e.g. https://summarize-service.apero.vn>`
>
>    That's the only property you should ever need. No `SSO_*`, no tokens, no client IDs.
> 6. To run: pick **`<entry-function-name>`** in the toolbar → **▶ Run**. Google will prompt you for permissions the first time (and again any time the scope set changes) — accept all. Subsequent runs are seamless.
>
> **Do NOT paste any token, password, or API key into Script Properties.** If you think you need to, ping **#vibecode-help** — that means the internal service is missing a job it should be doing (holding that secret on the user's behalf).

### 4e. What you will not do, no matter how the user pushes

- ❌ Add a "just this once" `OPENAI_API_KEY` (or any paid-service key) to Script Properties. *(Reply: "I won't — Rule 1. Even once leaks once. The key belongs in Vault, accessed by an internal wrapper service.")*
- ❌ Write Apps Script that calls a paid API directly "to ship faster". *(Reply: "Rule 2 — paid services have to be internalized first. Faster now, rotating leaked keys later is slower. Let's check if a wrapper exists, or build one once for everyone.")*
- ❌ Hardcode a "shared token" between the sheet and an internal service in lieu of SSO. *(Reply: "That's a secret in Apps Script. The user's own identity is already available via `ScriptApp.getIdentityToken()` — no shared secret needed.")*
- ❌ Skip the permission check on an internal service we're building. *(Reply: "Without it, anyone with an Apero account can call it. The service has to authorize the user — by email allowlist, Keycloak group, or per-user role — same as every other Apero internal service.")*
- ❌ Build a per-sheet wrapper for a paid service when a reusable one would serve. *(Reply: "If three sheets need OpenAI, three sheets shouldn't trigger three wrappers. Let's name this `summarize-service` and let everyone use it.")*
- ❌ Invent an internal-service URL. *(Reply: "I don't know if `customer-service.apero.vn` exists. If you can confirm it (or get its real URL from #devops), I'll wire the sheet to it.")*

## 5. The canonical pattern — copy this

§5a is the shape of an **internal service that wraps a paid service** — one per paid service, reused across sheets and apps. §5b is the **Apps Script that calls any internal service** (the wrapper above, or one that already exists for some other purpose). The two halves are independent: if the internal service you need already exists, you only write §5b.

### 5a. Internal service that wraps a paid service (FastAPI route)

This is built **once, as a reusable Apero internal service** — not as a per-sheet endpoint. Sheets, scripts, and other apps all call it.

```python
# routes/summarize.py — exposed at https://summarize-service.apero.vn/summarize
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.auth import User, verify_apps_script_caller   # see templates/python/shapes/http-service/src/auth.py
from src.config import get_settings                  # secret_openai_api_key lives in .env (gitignored)
# import the paid client of your choice; the key is read from config below

router = APIRouter()
log = logging.getLogger("apero.summarize")

ALLOWED_GROUP = "summarize-service-users"           # SSO group; managed by DevOps

class SummarizeReq(BaseModel):
    sheet_id: str
    text: str

class SummarizeResp(BaseModel):
    summary: str

@router.post("/summarize", response_model=SummarizeResp)
def summarize(
    body: SummarizeReq,
    user: User = Depends(verify_apps_script_caller(ALLOWED_GROUP)),
) -> SummarizeResp:
    log.info(
        "summarize",
        extra={"sub": user.sub, "sheet_id": body.sheet_id, "chars": len(body.text)},
    )
    api_key = get_settings().secret_openai_api_key  # from .env; never logged, never returned
    # ... call the paid service with api_key, build summary ...
    summary = "..."  # replace with real call
    return SummarizeResp(summary=summary)
```

What this enforces:

- `verify_apps_script_caller(ALLOWED_GROUP)` (defined in `templates/python/shapes/http-service/src/auth.py` — applied when the project takes the http-service shape) does all four steps in one Depends: **(1)** verify the Google ID token's signature, issuer, exp, and audience; **(2)** require the `email` claim end in `@apero.vn`; **(3)** look the user up in Apero SSO by email; **(4)** check the user is in `ALLOWED_GROUP`. Any failure → 401/403 before your handler runs.
- The real implementation lives in `hq-apero-sso` (DevOps territory) — `auth.py` has a stub that raises `NotImplementedError` until the package is wired. Same pattern as `_decode_token` for Keycloak Bearer tokens.
- `user.sub` is the stable SSO identifier — log this, not `user.email` (PII).
- `get_settings().secret_openai_api_key` — real secret lives in the service's gitignored `.env`, never in Apps Script, never in the response.
- The raw `text` is never logged; only its length, so big payloads / PII don't leak into logs.

For an endpoint that serves **both** human callers (web frontend with a Keycloak Bearer token) and Apps Script callers (Google ID token), expose two routes that share a handler body — one with `Depends(require_group(...))`, one with `Depends(verify_apps_script_caller(...))`. Don't try to auto-detect: the two token types want different validation rules, and dispatching by issuer claim hides bugs.

### 5b. Apps Script (in the sheet)

Two files. **Both** are required — Apps Script projects have an editable manifest, and the manifest must declare the `openid` + `userinfo.email` scopes for `getIdentityToken()` to return anything.

**`appsscript.json`** (open via ⚙️ → tick "Show 'appsscript.json' manifest file in editor"):

```json
{
  "timeZone": "Asia/Ho_Chi_Minh",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets.currentonly",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/script.container.ui",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email"
  ]
}
```

**`Code.gs`**:

```javascript
// Sheet helper — calls an Apero internal service with the user's Google identity token.
// Entry: runSummarize()  (assign this to a button or menu)
//
// REQUIRES (see docs/google-apps-script.md §3, §4d):
//   - appsscript.json with `openid` + `userinfo.email` in oauthScopes (above)
//   - Script Property: SERVICE_URL  (e.g. https://summarize-service.apero.vn)
//
// NO SECRETS LIVE IN THIS SCRIPT. ScriptApp.getIdentityToken() returns a fresh
// Google-signed OpenID Connect token for the running user. The internal service
// verifies the signature, reads the email claim, and decides whether to allow.

function runSummarize() {
  const token = ScriptApp.getIdentityToken();
  Logger.log('identity token: ' + (token ? 'present (len=' + token.length + ')' : 'MISSING'));
  if (!token) {
    try {
      SpreadsheetApp.getUi().alert(
        'Missing identity token — add "openid" and "userinfo.email" to oauthScopes in appsscript.json, then re-run and re-authorize.'
      );
    } catch (e) {}
    return;
  }

  const serviceUrl = PropertiesService.getScriptProperties().getProperty('SERVICE_URL');
  if (!serviceUrl) {
    SpreadsheetApp.getUi().alert('SERVICE_URL is not set. ⚙️ → Project Settings → Script Properties.');
    return;
  }

  const sheet = SpreadsheetApp.getActiveSheet();
  const cell = sheet.getActiveCell();
  const text = cell.getValue();
  if (!text) {
    SpreadsheetApp.getUi().alert('Select a cell with text first.');
    return;
  }

  try {
    const res = UrlFetchApp.fetch(`${serviceUrl}/summarize`, {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: `Bearer ${token}` },
      payload: JSON.stringify({ sheet_id: sheet.getParent().getId(), text }),
      muteHttpExceptions: true,
    });
    const code = res.getResponseCode();
    if (code === 401) {
      SpreadsheetApp.getUi().alert("Identity token was rejected. Try re-running; if it persists, ping #devops with the Execution log.");
      return;
    }
    if (code === 403) {
      SpreadsheetApp.getUi().alert("You're authenticated, but not in the allowed group for this service. Ping #devops to be added.");
      return;
    }
    if (code !== 200) {
      throw new Error(`service ${code}: ${res.getContentText()}`);
    }
    const body = JSON.parse(res.getContentText());
    cell.setNote(body.summary);
  } catch (err) {
    Logger.log(`runSummarize failed: ${err}`);
    throw err;
  }
}
```

What this script does **not** contain: any secret, any direct call to a paid service, any shared token, any OAuth library. The only credential in play is a fresh Google-issued ID token for the running user — generated on each call by `ScriptApp.getIdentityToken()`, never persisted by the script. The internal service decides if the user (by email → SSO group) is allowed.

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Alert: "Missing identity token — add 'openid'…" | `appsscript.json` is missing `openid` and/or `userinfo.email` in `oauthScopes` | Add both scopes (see §3 / §4d), save, re-run, accept the new permissions prompt |
| Google permission dialog keeps reappearing | Scope set changed since last authorization | Accept once; if it loops, check that `oauthScopes` matches what the code actually uses |
| Internal service returns `401` | Token rejected — signature failed, `aud` mismatch, expired, or email not `@apero.vn` | Re-run (tokens are short-lived; a fresh one is issued each call). If it persists, check the service log — usually `aud` mismatch (script not bound to the expected GCP project) |
| Internal service returns `403` | User authenticated but not in the allowed SSO group / not on the service's allowlist | Ask #devops to add the user to the service's allowed group, then re-run |
| `ScriptApp.getIdentityToken()` returns `null` | `openid` scope not granted, or user hasn't completed the auth prompt | Add `openid` to `oauthScopes`, save, run again, accept the prompt |
| "Exceeded maximum execution time" | Job > 6 min (or > 30 sec in a `=FUNCTION()`) | The job is too big for Apps Script — move it to Python entirely, schedule it |
| `UrlFetchApp` DNS error | Internal service not reachable from public internet | Apps Script runs from Google IPs; the internal service must be reachable at its public `*.apero.vn` URL. If it's currently VPN-only, ask #devops to expose it publicly (it's already SSO-gated, so that's safe) |
| Custom function returns `#ERROR!` | Threw an exception, or returned `undefined` | Open the Execution log for the real error |

## Contacts

- "Is there an internal service for `<paid service>`?" / "Bind my Apps Script to the shared GCP project so `aud` validates" / "Add me to the allowed group for `<service>`" → **#devops**
- "How do I structure this Apps Script / which internal service should I call?" → **#vibecode-help**
