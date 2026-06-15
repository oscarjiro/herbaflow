"""App-layer security controls: headers, payload cap, per-IP rate limiting (one home)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.errors import problem_json


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


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies above ``max_bytes`` before the handler reads them.

    Checks the Content-Length header (set by httpx and the generated TS client). A
    chunked request with no Content-Length is not caught here; the size guard for that
    edge is left to the host/proxy layer (documented in docs/security.md).
    """

    def __init__(self, app: object, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return problem_json(
                        413,
                        "Payload Too Large",
                        f"Request body exceeds the {self.max_bytes}-byte limit.",
                    )
            except ValueError:
                pass  # malformed header — let the handler/validation deal with it
        return await call_next(request)
