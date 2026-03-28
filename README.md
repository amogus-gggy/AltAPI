# AltAPI

A simple and fast ASGI microframework for Python with WebSocket support.

## Changelog

### v1.2.0
- Added `workers` parameter to `app.run()` for multi-process support(still unstable sometimes)
- Added `access_log` parameter to enable/disable request logging
- GC optimizations now apply to all workers automatically



## Documentation

📖 Full documentation is available in **[DOCS.md](DOCS.md)**.

## Installation

```bash
pip install altapi
```

**Requirements:**
- Python >= 3.10

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
- ✅ Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`)
- ✅ Sync and async handlers
- ✅ Full WebSocket support
- ✅ Built-in server (`app.run()`)
- ✅ Jinja2 templates
- ✅ Response caching
- ✅ Static file mounting

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
from altapi.caching import InMemoryCache, cache

app = AltAPI(
    cache_backend=InMemoryCache(max_size=1000),
    cache_timeout=300
)


@app.get("/api/data")
@cache(expires=3600)  # cache for 1 hour
async def get_data(request):
    return JSONResponse({"data": "cached"})
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

## Response Types

```python
from altapi.http import (
    JSONResponse,      # JSON response
    HTMLResponse,      # HTML response
    PlainTextResponse, # Plain text response
    StreamingResponse, # Streaming response
    FileResponse,      # File download
    RedirectResponse,  # Redirect
)
```

## Documentation

Full documentation is available in [DOCS.md](DOCS.md).

## License

AGPLv3, see [LICENSE.txt](LICENSE.txt) for details.
