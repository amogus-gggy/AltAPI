"""API Routes"""

from altapi.http import JSONResponse
from altapi.openapi_decorators import openapi


def register_routes(app):
    """Register API routes."""

    @app.get("/api/health")
    @openapi(summary="Health Check", description="API health status", tags=["system"])
    async def health_check(request):
        return JSONResponse({"status": "ok"})

    @app.get("/api/version")
    @openapi(summary="Version", description="API version info", tags=["system"])
    async def version(request):
        return JSONResponse({"version": "1.0.0"})
