"""
Basic AltAPI Example with Middleware and Templates

Demonstrates middleware and templating.
"""

from altapi import AltAPI
from altapi.http import HTMLResponse
from altapi.middleware import Middleware, BaseMiddleware
from altapi.templating import render_template, TemplateResponse
from pathlib import Path
import time


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        print(f"[LOG] {scope['type']} {scope.get('path')}")
        await self.app(scope, receive, send)
        print(f"[LOG END] {scope.get('path')}")


class TimingMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        start = time.time()
        await self.app(scope, receive, send)
        print(f"[TIME] {scope.get('path')} took {time.time() - start:.4f}s")


# Setup directories
templates_dir = Path(__file__).resolve().parent / "templates"
static_dir = Path(__file__).resolve().parent / "static"

app: AltAPI = AltAPI(
    templates_directory=templates_dir,
    static_directory=static_dir,
    middleware=[Middleware(LoggingMiddleware), Middleware(TimingMiddleware)],
)


@app.get("/")
async def root(request):
    return HTMLResponse("<h1>Hello, world!</h1>")


@app.get("/greet/{name:str}")
async def greet(request) -> TemplateResponse:
    return render_template("greet.html", {"name": request.path_params["name"]})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
