"""App-layer security controls: headers, payload cap, per-IP rate limiting (one home)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set the minimal OWASP baseline headers on every response.

    The full document-CSP (script/style/connect sources) is deferred to the frontend
    serving layer; ``frame-ancestors 'none'`` is the only CSP directive meaningful on a
    JSON API and is the clickjacking control alongside X-Frame-Options.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response
