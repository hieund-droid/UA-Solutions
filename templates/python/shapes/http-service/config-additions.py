"""HTTP-service-only Settings fields.

When converting the project to an HTTP service, ADD these fields to the
`Settings` class in the project's `src/config.py`. They are split out here so
that CLI / cron / worker projects don't carry inert HTTP/SSO settings.
"""

from typing import Literal

from pydantic import Field


# Add these fields to Settings:
app_port: int = Field(default=8000)

apero_sso_issuer: str = Field(default="")
apero_sso_client_id: str = Field(default="")
apero_sso_audience: str = Field(default="")

# `auth.py::_decode_token` reads these three to verify inbound bearer tokens.
# `auth.py::_verify_apps_script_token` reads `apero_sso_audience` when checking
# the aud claim of Google ID tokens from Apps Script.
#
# NOTE: This file is not imported — it's a reference snippet. Copy the field
# declarations above into your project's `src/config.py` Settings class.
_ = Literal  # keep import alive for the snippet
