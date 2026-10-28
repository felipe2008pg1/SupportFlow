from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline security headers to every response.

    - X-Content-Type-Options: nosniff
        Prevents the browser from MIME-sniffing a response away from the
        declared Content-Type (mitigates some XSS/content-confusion attacks).
    - X-Frame-Options: DENY
        Prevents this API's responses from being framed, mitigating
        clickjacking. (This is a JSON API; there is nothing legitimate to
        embed in an iframe.)
    - Referrer-Policy: strict-origin-when-cross-origin
        Limits how much of the request URL is leaked via the Referer header
        on cross-origin navigations/requests.
    - Permissions-Policy
        Explicitly disables powerful browser features this API never uses.

    Not included here: Strict-Transport-Security (HSTS). HSTS is only
    correct when the connection is actually served over HTTPS. Locally we
    run over plain HTTP, and enabling HSTS there would make browsers force
    HTTPS on localhost, breaking development. HSTS belongs at the TLS
    termination point (reverse proxy/load balancer) in production — see
    README "Production hardening" section.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        return response
