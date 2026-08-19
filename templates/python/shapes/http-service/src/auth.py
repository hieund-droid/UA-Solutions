"""hq-apero-sso integration.

This is the ONLY place auth lives. Route handlers take
`user: User = Depends(get_current_user)` — they do not parse tokens themselves.

Replace `_decode_token` with the real call once the package is wired (see
https://github.com/Apero-Vibecode/hq-apero-sso) — or invoke `/sso-wire-up`.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    sub: str          # SSO-issued stable identity — use this, not email
    email: str
    groups: tuple[str, ...]


def _decode_token(token: str) -> User:
    """TODO[devops]: replace with the real hq-apero-sso verify_token call."""
    _ = get_settings()
    _ = token
    raise NotImplementedError(
        "Wire hq-apero-sso into _decode_token. See https://github.com/Apero-Vibecode/hq-apero-sso"
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return _decode_token(creds.credentials)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="SSO not yet wired — see auth.py")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_group(group: str):
    """Use as: user: User = Depends(require_group('finance'))."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if group not in user.groups:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires group: {group}")
        return user

    return _checker


# ---------------------------------------------------------------------------
# Google Apps Script callers (see docs/google-apps-script.md)
#
# Apps Script sends a Google-issued OpenID Connect ID token (from
# ScriptApp.getIdentityToken()) as the Authorization bearer. The token's
# 'email' claim is the user's Apero Google identity — we verify the token,
# then look the user up in hq-apero-sso to apply the same group-based authz
# as every other Apero internal call.
# ---------------------------------------------------------------------------


def _verify_apps_script_token(token: str) -> User:
    """TODO[devops]: replace with hq-apero-sso's Apps-Script verifier.

    Expected behavior:
      1. Verify token signature against Google's JWKS (https://www.googleapis.com/oauth2/v3/certs).
      2. Validate iss ∈ {"https://accounts.google.com", "accounts.google.com"} and exp not past.
      3. Validate aud matches the expected Apero Apps Scripts client_id (set in config).
      4. Read `email` claim; require it to end in '@apero.vn'.
      5. Look up the user in hq-apero-sso by email and return a User with groups filled in.
    """
    _ = token
    raise NotImplementedError(
        "Wire hq-apero-sso's verify_apps_script_token here. "
        "See https://github.com/Apero-Vibecode/hq-apero-sso"
    )


def verify_apps_script_caller(group: str):
    """Use on endpoints called from Google Apps Script (sheet buttons, triggers).

    Verifies the Google ID token, resolves the user via SSO, and checks the
    user is in `group`. Use exactly like `require_group` — only the inbound
    token type differs.

    Example:
        user: User = Depends(verify_apps_script_caller('sheet-summarize-users'))
    """

    def _checker(
        creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> User:
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing identity token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user = _verify_apps_script_token(creds.credentials)
        except NotImplementedError:
            raise HTTPException(status_code=501, detail="Apps Script SSO not yet wired — see auth.py")
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity token")
        if group not in user.groups:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires group: {group}")
        return user

    return _checker
