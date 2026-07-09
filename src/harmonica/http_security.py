"""Request-level security for the Harmonica daemon.

Two protections, layered on top of the per-profile token model:

1. CSRF (always on, both modes). A state-changing request (or the sensitive ``/spotify/playlist``
   read) from another website is refused. This uses the browser's ``Sec-Fetch-Site`` metadata,
   falling back to an ``Origin`` check, so a page the user merely visits cannot drive the local
   daemon via a bare ``<img>`` or auto-submitting ``<form>``. Non-browser clients (curl, the native
   app, the test suite) send neither header and are unaffected.

2. Authenticated access (exposed mode only). When the daemon is bound off loopback (a NAS on
   0.0.0.0) or ``require_auth`` is forced on, every non-public endpoint needs a valid profile bearer
   token. A client cannot read or change a profile's data, or reach the outbound Spotify connector,
   without one. In local (loopback) mode this is a no-op, so single-user local use is unchanged.

Every response also carries a strict Content-Security-Policy and related hardening headers.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) so it never buffers the response body:
media streaming and HTTP range requests (audio/video seeking) pass through untouched.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from harmonica.security import verify_config_token

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# GET endpoints that have a side effect or drive an outbound call, so they get CSRF protection too.
_SENSITIVE_GETS = {"/spotify/playlist"}

# Path prefixes that belong to the API (everything else is the SPA / static assets, always public).
_API_PREFIXES = (
    "/settings", "/stats", "/tracks", "/rating-factors", "/scan", "/queue",
    "/playback-events", "/playlist-runs", "/cover-sets", "/cover-comparisons",
    "/cover-verdicts", "/library", "/configs", "/media", "/youtube", "/spotify", "/health",
)

# API GETs a browser must reach before it can authenticate (to render the app and the claim screen)
# or that serve the shared media pool. Exact paths or prefixes; everything else API needs a token.
_PUBLIC_GET_PATHS = {"/settings", "/configs", "/youtube/config", "/spotify/config", "/health"}
_PUBLIC_GET_PREFIXES = ("/media/",)

# Onboarding/auth POSTs that must work before a token exists (they are how you get one).
_AUTH_EXEMPT_POSTS = {"/configs", "/configs/claim"}

_CSP = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'self'; "
    "script-src 'self' https://www.youtube.com https://s.ytimg.com; "
    "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
    "img-src 'self' data: https:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; connect-src 'self'"
)
_SECURITY_HEADERS = {
    "content-security-policy": _CSP,
    "x-content-type-options": "nosniff",
    "x-frame-options": "SAMEORIGIN",
    "referrer-policy": "same-origin",
}


def _is_api_path(path: str) -> bool:
    return path.startswith(_API_PREFIXES)


def _needs_csrf(request: Request) -> bool:
    return request.method in _UNSAFE_METHODS or request.url.path in _SENSITIVE_GETS


def _csrf_ok(request: Request, allowed_origins: set[str]) -> bool:
    """Same-origin (or non-browser) requests only. Blocks cross-site browser requests."""
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        # Modern browsers stamp this on every request, including <img>/<form>/<script> loads.
        return fetch_site in {"same-origin", "none"}
    origin = request.headers.get("origin")
    if origin is not None:
        host = request.headers.get("host", "")
        return (
            origin in allowed_origins
            or origin == f"http://{host}"
            or origin == f"https://{host}"
        )
    # No browser metadata at all: a non-browser client (curl, native app, tests), not a CSRF vector.
    return True


def _requires_token(request: Request) -> bool:
    """Whether this endpoint needs a valid profile token when the daemon is in exposed mode."""
    path = request.url.path
    if not _is_api_path(path):
        return False  # SPA / static assets
    method = request.method
    if method in {"GET", "HEAD"}:
        if path in _PUBLIC_GET_PATHS or path.startswith(_PUBLIC_GET_PREFIXES):
            return False
        return True
    if method in _UNSAFE_METHODS:
        if method == "POST" and path in _AUTH_EXEMPT_POSTS:
            return False
        return True
    return False  # OPTIONS (CORS preflight) and anything else


def _has_valid_token(request: Request, secret: str) -> bool:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    return verify_config_token(auth[7:].strip(), secret) is not None


class SecurityMiddleware:
    """Pure-ASGI security gate. Reads its live policy from ``app_ref.state`` (set by create_app):
    ``auth_required`` (bool), ``secret`` (str), ``allowed_origins`` (set[str])."""

    def __init__(self, app, *, app_ref) -> None:
        self.app = app
        self.app_ref = app_ref

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        state = self.app_ref.state
        allowed = getattr(state, "allowed_origins", set())

        if _needs_csrf(request) and not _csrf_ok(request, allowed):
            await self._reject(scope, receive, send, 403, "Cross-site request refused")
            return
        if (
            getattr(state, "auth_required", False)
            and _requires_token(request)
            and not _has_valid_token(request, getattr(state, "secret", ""))
        ):
            await self._reject(
                scope, receive, send, 401,
                "This server requires a profile. Claim or create one to continue.",
            )
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    async def _reject(self, scope, receive, send, status: int, detail: str) -> None:
        response = JSONResponse({"detail": detail}, status_code=status)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        await response(scope, receive, send)


def install_security(app) -> None:
    """Register the security middleware on a FastAPI app. Call before adding CORS so CORS stays the
    outermost layer (its headers wrap even the rejection responses)."""
    app.add_middleware(SecurityMiddleware, app_ref=app)
