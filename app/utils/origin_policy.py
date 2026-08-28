"""Canonical allowed-origin policy for both CORS and CSRF-style origin
validation.

Fix for AUTH-4: two independently-maintained origin allowlists previously
existed and had drifted out of sync -- app/main.py's CORSMiddleware
allow_origins list (missing the production https://distroos.in domains
entirely, relying only on the ALLOWED_ORIGINS env var to add them) and
app/api/v1/auth.py's separate ALLOWED_ORIGINS list (missing
localhost:3000/127.0.0.1:3000 as explicit entries, though covered via a
separate startswith() check). Worse, _validate_origin() -- the only
actual origin-based CSRF check in the app -- was only ever called by
POST /auth/refresh and POST /auth/logout; every other cookie-authenticated,
state-changing endpoint across the rest of the API (orders, customers,
payments, shipments, etc.) had zero origin validation at all, even
though production cookies are set with samesite="none" (required for
the frontend's cross-origin deployment), which disables SameSite's
own CSRF protection entirely and relies on origin validation as the
actual backstop.

This module is the single source of truth both consumers now share.
"""
import os

# Production frontend origins that this API accepts credentialed
# cross-origin requests from. Additional origins can be added via the
# ALLOWED_ORIGINS env var (comma-separated) without a code change.
ALLOWED_ORIGINS: list[str] = [
    "https://distributor-os-ui.onrender.com",
    "https://distroos.in",
    "https://www.distroos.in",
]

_env_origins = os.getenv("ALLOWED_ORIGINS")
if _env_origins:
    ALLOWED_ORIGINS.extend(o.strip() for o in _env_origins.split(",") if o.strip())

# Local dev origins are always accepted regardless of ENVIRONMENT, matching
# the pre-existing dev-mode behavior in auth.py's original _validate_origin.
_DEV_ORIGIN_PREFIXES = ("http://localhost:", "http://127.0.0.1:")


def is_origin_allowed(origin: str) -> bool:
    """True if `origin` (an Origin header value) is an accepted origin for
    credentialed requests -- in production, must be an exact match against
    ALLOWED_ORIGINS; in development, additionally accepts any localhost/
    127.0.0.1 origin (any port) for local frontend dev servers."""
    if origin in ALLOWED_ORIGINS:
        return True
    is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    if not is_prod and origin.startswith(_DEV_ORIGIN_PREFIXES):
        return True
    return False
