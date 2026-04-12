"""
Basic AltAPI Example with Middleware and Templates

Demonstrates middleware, templating, and Pydantic model integration.
"""

from pydantic import BaseModel, Field
from altapi import AltAPI
from altapi.http import HTMLResponse, JSONResponse
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


class GreetResponse(BaseModel):
    """Greeting response model."""
    message: str = Field(..., description="Greeting message")
    name: str = Field(..., description="Person's name")


# Setup directories
templates_dir = Path(__file__).resolve().parent / "templates"
static_dir = Path(__file__).resolve().parent / "static"

app: AltAPI = AltAPI(
    templates_directory=templates_dir,
    static_directory=static_dir,
    middleware=[Middleware(LoggingMiddleware), Middleware(TimingMiddleware)],
    title="AltAPI Basic Example",
    version="1.0.0",
    description="Basic example with Pydantic integration",
)


@app.get("/")
async def root(request):
    return HTMLResponse("<h1>Hello, world!</h1>")


@app.get(
    "/greet/{name:str}",
    response_model=GreetResponse,
    summary="Greet a person",
    description="Returns a greeting for the specified person",
    tags=["greetings"],
)
async def greet(request) -> TemplateResponse:
    return render_template("greet.html", {"name": request.path_params["name"]})


@app.get(
    "/api/info",
    summary="Get API info",
    description="Returns basic API information",
    tags=["system"],
)
async def api_info(request):
    return JSONResponse({
        "name": "AltAPI Basic Example",
        "version": "1.0.0",
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
