"""API Routes"""
from altapi.http import JSONResponse


def register_routes(app):
    """Register API routes."""

    @app.get("/api/health")
    async def health_check(request):
        return JSONResponse({"status": "ok"})

    @app.get("/api/version")
    async def version(request):
        return JSONResponse({"version": "1.0.0"})
