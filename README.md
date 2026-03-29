# AltAPI

A simple and fast ASGI microframework for Python with WebSocket support.

[![PyPI](https://img.shields.io/pypi/v/altapi.svg)](https://pypi.org/project/altapi/)
[![Python](https://img.shields.io/pypi/pyversions/altapi.svg)](https://pypi.org/project/altapi/)
[![License](https://img.shields.io/badge/license-AGPLv3-green.svg)](https://github.com/amogus-gggy/AltAPI/blob/main/LICENSE.txt)
[![Documentation](https://img.shields.io/badge/docs-DOCS.md-blue.svg)](https://github.com/amogus-gggy/AltAPI/blob/main/DOCS.md)

## Changelog

### v1.3.0
- Added rate limiting with `@rate_limit` and `@rate_limit_batch` decorators(right now, please dont use them, they are very unoptimized)
- Added shared manager for multi-worker rate limiting support
- Added support for all HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE, CONNECT


### v1.2.0
- Added `workers` parameter to `app.run()` for multi-process support
- Added `access_log` parameter to enable/disable request logging
- GC optimizations now apply to all workers automatically


## Installation

```bash
pip install altapi
```

**Requirements:**
- Python >= 3.10
- uvicorn >= 0.30.0
- anyio >= 4.0.0
- jinja2 >= 3.0.0
- ujson
- Cython >= 3.0.0

## Quick Start

### Minimal Example

```python
from altapi import AltAPI
from altapi.http import JSONResponse

app = AltAPI()


@app.get("/")
async def home(request):
    return JSONResponse({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

Run:
```bash
python app.py
```

Or via uvicorn:
```bash
uvicorn app:app --reload
```

## Features

- ✅ ASGI compliant
- ✅ JSON, HTML, and text responses
- ✅ Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`, `{path:path}`)
- ✅ Sync and async handlers
- ✅ Full WebSocket support
- ✅ Built-in server (`app.run()`) with multi-worker support
- ✅ Jinja2 templates
- ✅ Response caching with per-worker InMemoryCache
- ✅ Rate limiting with shared manager
- ✅ Static file mounting
- ✅ Optimized Cython router
- ✅ GC optimizations for better performance
- ✅ All HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS, TRACE, CONNECT

## Usage Examples

### Path Parameters

```python
from altapi.http import JSONResponse


@app.get("/users/{id:int}")
async def get_user(request):
    user_id = request.path_params["id"]  # automatically int
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})


@app.get("/items/{name:str}")
async def get_item(request):
    name = request.path_params["name"]  # str
    return JSONResponse({"name": name})


@app.get("/files/{path:path}")
async def get_file(request):
    file_path = request.path_params["path"]  # captures full path with slashes
    return JSONResponse({"path": file_path})
```

### Handling POST Requests

```python
@app.post("/api/echo")
async def echo(request):
    data = await request.json()
    return JSONResponse({"echo": data})
```

### WebSocket

```python
from altapi.websocket import WebSocket


@app.websocket("/ws/echo")
async def websocket_echo(ws: WebSocket):
    await ws.accept()
    while True:
        text = await ws.receive_text()
        await ws.send_text(f"Echo: {text}")
```

### Caching

```python
from altapi.caching import cache

app = AltAPI()


@app.get("/api/data")
@cache(expires=3600)  # cache for 1 hour
async def get_data(request):
    return JSONResponse({"data": "cached"})
```

### Rate Limiting

```python
from altapi.ratelimit import rate_limit

app = AltAPI()


@app.get("/api/data")
@rate_limit(limit=10, period=60)  # 10 requests per minute
async def get_data(request):
    return JSONResponse({"data": "value"})


# Multiple limits on same endpoint
from altapi.ratelimit import rate_limit_batch


@app.get("/api/strict")
@rate_limit_batch([
    (10, 60),      # 10 per minute
    (100, 3600),   # 100 per hour
    (1000, 86400)  # 1000 per day
])
async def strict_endpoint(request):
    return JSONResponse({"data": "rate limited"})
```

### Jinja2 Templates

```python
from altapi.templating import Jinja2Templates

app = AltAPI(templates_directory="templates")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home(request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Home Page"}
    )
```

### Static Files

```python
# Automatically serves files at /static
app = AltAPI(static_directory="static")
```

### Multi-Worker Server

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=4, access_log=True)
```

## Response Types

```python
from altapi.http import (
    JSONResponse,      # JSON response
    HTMLResponse,      # HTML response
    PlainTextResponse, # Plain text response
    StreamingResponse, # Streaming response
    FileResponse,      # File download with range support
    RedirectResponse,  # Redirect
)
```

## Documentation

Full documentation is available in [DOCS.md](https://github.com/amogus-gggy/AltAPI/blob/main/DOCS.md).

## License

AGPLv3, see [LICENSE.txt](https://github.com/amogus-gggy/AltAPI/blob/main/LICENSE.txt) for details.
