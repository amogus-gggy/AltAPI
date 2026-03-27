# AltAPI

Simple ASGI micro framework for Python, which supports both HTTP and WebSockets.

## Changelog

### Version 1.1
- Added caching system (`InMemoryCache`, `CacheMiddleware`, `@cache` decorator)
- Improved `render_template()` and `Jinja2Templates` integration
- Added automatic static file serving via `static_directory` parameter
- Minor improvements for static and templates directory handling

## Installation

```bash
pip install project-nebula
```


## Usage

```python
from nebula import Nebula
from nebula.http import JSONResponse, HTMLResponse

app = Nebula()


@app.get("/")
async def home(request):
    return HTMLResponse("<h1>Welcome to Nebula!</h1>")


@app.get("/api/hello")
async def hello(request):
    return JSONResponse({"message": "Hello, World!"})


@app.post("/api/echo")
async def echo(request):
    data = await request.json()
    return JSONResponse({"echo": data})


# Typed path parameters
@app.get("/api/users/{id:int}")
async def get_user(request):
    user_id = request.path_params["id"]  # int
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})


# Sync handler example
@app.get("/api/sync")
def sync_handler(request):
    return JSONResponse({"type": "sync", "message": "I'm synchronous!"})


# Run server directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## Run

```bash
python examples/app.py
```

Or with uvicorn directly:

```bash
uvicorn examples.app:app --reload
```

Or using app.run():

```bash
python your_app.py
```

## Project Structure

```
src/nebula/
├── __init__.py          # Main package exports
├── app.py               # Main Nebula application class
├── router.pyx           # Cython router (optimized)
├── http/                # HTTP components
│   ├── __init__.py
│   ├── request.py       # Request handling
│   └── responses.py     # Response classes
├── websocket/           # WebSocket support
│   ├── __init__.py
│   └── ws.py
├── templating/          # Template rendering (Jinja2)
│   ├── __init__.py
│   ├── templates.py
│   └── default_templates.py
├── caching/             # Caching system
│   ├── __init__.py
│   └── cache.py
└── middleware/          # Middleware support
    ├── __init__.py
    └── middleware.py
```

### Recommended Imports

```python
# Main application
from nebula import Nebula

# HTTP components
from nebula.http import Request, JSONResponse, HTMLResponse, PlainTextResponse, StreamingResponse, FileResponse, RedirectResponse

# WebSocket
from nebula.websocket import WebSocket, WebSocketState

# Templates
from nebula.templating import Jinja2Templates, render_template

# Caching
from nebula.caching import cache, InMemoryCache, CacheMiddleware

# Middleware
from nebula.middleware import Middleware, BaseMiddleware
```

## Features

- ASGI compliant
- JSON and HTML responses
- Typed path parameters (`/users/{id:int}`, `{name:str}`, `{value:float}`)
- Request body parsing (JSON, text)
- Multiple HTTP methods (GET, POST, PUT, DELETE)
- Sync and async handlers
- Full WebSocket support
- Optimized Cython router
- Static file mounting (automatic via `static_directory`)
- Template rendering (Jinja2)
- Multiple response types (PlainText, Streaming, File, Redirect)
- Built-in caching with `InMemoryCache`
- Built-in server (`app.run()`)
