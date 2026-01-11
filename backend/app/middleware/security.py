"""Security middleware for adding security headers."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    # Paths that should allow iframe embedding
    EMBED_PATHS = ("/api/public/embed", "/ws/public/embed")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        path = request.url.path

        # Check if this is an embed route that needs iframe access
        is_embed_route = any(path.startswith(p) for p in self.EMBED_PATHS)

        if is_embed_route:
            # For embed routes: allow framing from any origin
            # The embed API itself validates allowed_domains per agent
            response.headers["Content-Security-Policy"] = "frame-ancestors *"
            # Don't set X-Frame-Options for embed routes (CSP takes precedence)
        else:
            # For all other routes: prevent clickjacking
            response.headers["X-Frame-Options"] = "DENY"
            # Content Security Policy for non-embed routes
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'"
            )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - allow microphone for embed routes (voice chat)
        if is_embed_route:
            response.headers["Permissions-Policy"] = "geolocation=(), camera=(), payment=()"
        else:
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), payment=()"
            )

        return response
