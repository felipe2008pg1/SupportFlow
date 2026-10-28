from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware

settings = get_settings()

# Docs are exposed only outside production to reduce reconnaissance surface
# (endpoint enumeration, schema disclosure) for unauthenticated actors.
app = FastAPI(
    title="SupportFlow API",
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    debug=settings.debug,
)

app.add_middleware(SecurityHeadersMiddleware)

# CORS is explicit and origin-scoped: no wildcard, methods/headers limited
# to what is actually used. allow_credentials stays False until session
# cookies are introduced, at which point allow_origins="*" would become
# invalid anyway per the CORS spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    """Liveness probe.

    Returns a static, minimal payload only. Intentionally does not expose
    version numbers, hostnames, dependency status, or stack details —
    that information is only useful to an attacker probing the service.
    """
    return {"status": "ok"}
