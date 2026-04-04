"""MyProject - Full-Featured AltAPI Application"""
from altapi import AltAPI
from altapi.templating import render_template
import os

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

# Create app
app = AltAPI(
    templates_directory=templates_dir,
    static_directory=static_dir,
    cache_timeout=300
)


@app.get("/")
async def home(request):
    return render_template("index.html", {"request": request, "title": "Home"})


# Import and register routes from modules
from routes.api import register_routes as register_api_routes
from routes.pages import register_routes as register_pages_routes

register_api_routes(app)
register_pages_routes(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=2)
