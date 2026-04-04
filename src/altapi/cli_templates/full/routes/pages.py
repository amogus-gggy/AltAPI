"""Page Routes"""
from altapi.http import HTMLResponse


def register_routes(app):
    """Register page routes."""

    @app.get("/about")
    async def about_page(request):
        return HTMLResponse("<h1>About Page</h1>")
