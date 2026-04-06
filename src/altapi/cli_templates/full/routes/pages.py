"""Page Routes"""
from altapi.http import HTMLResponse
from altapi.openapi_decorators import openapi


def register_routes(app):
    """Register page routes."""

    @app.get("/about")
    @openapi(summary="About Page", description="About information page", tags=["pages"])
    async def about_page(request):
        return HTMLResponse("<h1>About Page</h1>")
