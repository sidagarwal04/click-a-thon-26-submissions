"""Server-side auto-login for the embedded LibreChat iframe.

LibreChat is a separate self-hosted app (its own docker-compose, own auth,
own MongoDB) — we don't touch its account model beyond calling its normal
login endpoint. A shared demo account is pre-registered there; this module
logs into it server-to-server and hands the resulting cookies back to the
browser, so the LibreChat iframe never shows its own sign-in screen.

Why this works: browser cookies are scoped by hostname, not port. This
dashboard and LibreChat are both served at hostname "localhost" (different
ports) in local dev, so a cookie *this* backend sets on the browser is sent
by the browser to LibreChat's origin too — no cross-origin cookie sharing
trick needed, just the ordinary same-hostname behavior.
"""
import os

import httpx

LIBRECHAT_INTERNAL_URL = os.environ.get("LIBRECHAT_INTERNAL_URL", "http://host.docker.internal:3080")
LIBRECHAT_EMAIL = os.environ.get("LIBRECHAT_EMAIL")
LIBRECHAT_PASSWORD = os.environ.get("LIBRECHAT_PASSWORD")


def login_and_get_cookies():
    """Returns the raw Set-Cookie header values LibreChat issued for the
    shared demo account, or None if not configured / the call failed."""
    if not LIBRECHAT_EMAIL or not LIBRECHAT_PASSWORD:
        return None
    try:
        resp = httpx.post(
            f"{LIBRECHAT_INTERNAL_URL}/api/auth/login",
            json={"email": LIBRECHAT_EMAIL, "password": LIBRECHAT_PASSWORD},
            timeout=10.0,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    return resp.headers.get_list("set-cookie")
