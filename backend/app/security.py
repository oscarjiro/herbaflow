"""App-layer security controls: headers, payload cap, per-IP rate limiting (one home)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.errors import problem_json

# One limiter instance for the app; routers import it to decorate specific routes.
# Behind a reverse proxy, run uvicorn with --proxy-headers so get_remote_address sees
# the real client (X-Forwarded-For), not the proxy (documented in docs/security.md).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    enabled=settings.rate_limit_enabled,
)
RATE_LIMIT_CREATE = settings.rate_limit_create
RATE_LIMIT_VALIDATE = settings.rate_limit_validate


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Map slowapi's RateLimitExceeded to the RFC 9457 problem+json shape (429)."""
    response = problem_json(
        429, "Too Many Requests", "Rate limit exceeded. Please slow down and retry."
    )
    response.headers["Retry-After"] = "60"
    return response


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
