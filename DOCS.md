# AltAPI Documentation

**AltAPI** — это простой и легковесный ASGI-микрофреймворк для Python с поддержкой WebSocket.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
  - [AltAPI](#altapi)
  - [Request](#request)
  - [Response](#response)
    - [JSONResponse](#jsonresponse)
    - [HTMLResponse](#htmlresponse)
    - [PlainTextResponse](#plaintextresponse)
    - [StreamingResponse](#streamingresponse)
    - [FileResponse](#fileresponse)
    - [RedirectResponse](#redirectresponse)
  - [WebSocket](#websocket)
  - [Caching](#caching-api)
    - [CacheBackend](#cachebackend)
    - [InMemoryCache](#inmemorycache)
    - [CacheManager](#cachemanager)
    - [CacheMiddleware](#cachemiddleware)
    - [@cache](#cache-decorator)
- [Routing](#routing)
- [WebSocket](#websocket-1)
- [Middleware](#middleware)
- [Caching](#caching)
  - [Cache Backends](#cache-backends)
  - [Using @cache Decorator](#using-cache-decorator)
  - [Using CacheMiddleware](#using-cachemiddleware)
- [Mounting Static Files and Applications](#mounting-static-files-and-applications)
- [Template Rendering](#template-rendering)
- [Running the Server](#running-the-server)
- [Examples](#examples)
- [Testing](#testing)
- [Development](#development)

---

## Features

- ✅ ASGI compliant
- ✅ JSON and HTML responses
- ✅ Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`)
- ✅ Request body parsing (JSON, text)
- ✅ Multiple HTTP methods (GET, POST, PUT, DELETE)
- ✅ Sync and async handlers
- ✅ Full WebSocket support
- ✅ Optimized Cython router
- ✅ Static file mounting
- ✅ Template rendering (Jinja2)
- ✅ Multiple response types (Streaming, File, Redirect, PlainText)
- ✅ Built-in `app.run()` server

---

## Installation

```bash
pip install altapi
```

### Requirements

- Python >= 3.10
- uvicorn >= 0.30.0
- anyio >= 4.0.0
- jinja2

### For Development

```bash
pip install altapi[dev]
```

Installs additional dependencies:
- pytest >= 8.0.0
- httpx >= 0.27.0
- cython >= 3.0.0

---

## Quick Start

### Minimal Application

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

### Running

```bash
# Via main block
python examples/app.py

# Or via uvicorn
uvicorn examples.app:app --reload
```

---

## API Reference

### AltAPI

Main application class.

```python
from altapi import AltAPI

app = AltAPI(templates_directory="templates")
```

#### Constructor Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `middleware` | `List[Middleware]` | List of middleware | `[]` |
| `templates_directory` | `str` | Directory for Jinja2 templates | `"templates"` |
| `static_directory` | `str` | Directory for static files (mounted at `/static`) | `None` |
| `cache_backend` | `CacheBackend` | Cache backend instance (e.g., InMemoryCache) | `None` |
| `cache_timeout` | `int` | Default cache timeout in seconds | `300` |

#### Decorator Methods

| Method | Description |
|--------|-------------|
| `@app.get(path)` | Register GET route |
| `@app.post(path)` | Register POST route |
| `@app.put(path)` | Register PUT route |
| `@app.delete(path)` | Register DELETE route |
| `@app.websocket(path)` | Register WebSocket route |
| `@app.route(path, methods)` | Universal decorator |

---

### Request

HTTP request object passed to handlers.

```python
from altapi.http import Request


@app.get("/users/{id:int}")
async def get_user(request: Request):
  ...
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `method` | `str` | HTTP method (GET, POST, etc.) |
| `path` | `str` | Request path |
| `query_string` | `str` | Query parameters |
| `headers` | `Dict[str, str]` | Request headers |
| `path_params` | `Dict[str, Any]` | Path parameters |

#### Methods

| Method | Description |
|--------|-------------|
| `async json()` | Parse request body as JSON |
| `async text()` | Get request body as text |

---

### Response

Base HTTP response class.

```python
from altapi.http import Response, JSONResponse, HTMLResponse
```

#### JSONResponse

```python
from altapi.http import JSONResponse


@app.get("/api/data")
async def get_data(request):
  return JSONResponse({"key": "value"}, status_code=200)
```

**Parameters:**
- `content` — data to serialize to JSON
- `status_code` — status code (default 200)
- `headers` — headers (optional)

#### HTMLResponse

```python
from altapi.http import HTMLResponse


@app.get("/")
async def home(request):
  return HTMLResponse("<h1>Welcome!</h1>")
```

**Parameters:**
- `content` — HTML content
- `status_code` — status code (default 200)
- `headers` — headers (optional)

#### PlainTextResponse

```python
from altapi.http import PlainTextResponse


@app.get("/text")
async def text(request):
  return PlainTextResponse("Hello, World!")
```

#### StreamingResponse

```python
from altapi.http import StreamingResponse


@app.get("/stream")
async def stream(request):
  async def generate():
    for i in range(10):
      yield f"Line {i}\n"

  return StreamingResponse(generate())
```

#### FileResponse

```python
from altapi.http import FileResponse


@app.get("/download")
async def download(request):
  return FileResponse("path/to/file.pdf", filename="myfile.pdf")
```

#### RedirectResponse

```python
from altapi.http import RedirectResponse


@app.get("/redirect")
async def redirect(request):
  return RedirectResponse("https://example.com")
```

---

### WebSocket

WebSocket connection handler.

```python
from altapi.websocket import WebSocket


@app.websocket("/ws/echo")
async def echo(ws: WebSocket):
  await ws.accept()
  while True:
    text = await ws.receive_text()
    await ws.send_text(f"Echo: {text}")
```

#### Methods

| Method | Description |
|--------|-------------|
| `async accept()` | Accept connection |
| `async send_text(data)` | Send text message |
| `async send_bytes(data)` | Send binary data |
| `async send_json(data)` | Send JSON |
| `async receive_text()` | Receive text |
| `async receive_bytes()` | Receive binary data |
| `async receive_json()` | Receive JSON |
| `async close(code, reason)` | Close connection |

#### States

```python
from altapi.websocket import WebSocketState

# WebSocketState.CONNECTING — connection establishing
# WebSocketState.CONNECTED — connection active
# WebSocketState.DISCONNECTED — connection closed
```

---

## Caching (API Reference)

### CacheBackend

Abstract base class for cache backends.

```python
from altapi.caching import CacheBackend


class MyCache(CacheBackend):
  async def get(self, key: str) -> Optional[Any]:
    ...

  async def set(self, key: str, value: Any, expires: int = None) -> None:
    ...

  async def delete(self, key: str) -> None:
    ...

  async def clear(self) -> None:
    ...
```

#### Methods

| Method | Description |
|--------|-------------|
| `async get(key)` | Get value from cache |
| `async set(key, value, expires)` | Set value in cache |
| `async delete(key)` | Delete value from cache |
| `async clear()` | Clear all cache |

---

### InMemoryCache

In-memory cache backend implementation.

```python
from altapi.caching import InMemoryCache

cache = InMemoryCache(max_size=1000)
```

**Parameters:**
- `max_size` — Maximum number of entries (default: 1000)

---

### CacheManager

Manager for cache backends.

```python
from altapi.caching import CacheManager, InMemoryCache

# Set default backend
CacheManager.set_default_backend(InMemoryCache())

# Register named backend
CacheManager.register_backend("redis", redis_cache)

# Get backend
backend = CacheManager.get_backend()  # default
backend = CacheManager.get_backend("redis")  # named
```

#### Methods

| Method | Description |
|--------|-------------|
| `set_default_backend(backend)` | Set default cache backend |
| `get_default_backend()` | Get default cache backend |
| `register_backend(name, backend)` | Register named backend |
| `get_backend(name)` | Get backend by name |

---

### CacheMiddleware

Middleware for automatic HTTP response caching.

```python
from altapi import AltAPI
from altapi.middleware import Middleware
from altapi.caching import CacheMiddleware

app = AltAPI(middleware=[
  Middleware(CacheMiddleware, cache_timeout=300)
])
```

**Parameters:**
- `cache_timeout` — Default cache TTL in seconds
- `backend` — Cache backend instance

#### Methods

| Method | Description |
|--------|-------------|
| `register_handler(path, expires)` | Register route for caching |

---

### @cache Decorator

Decorator for caching function results.

```python
from altapi.caching import cache


@app.get("/api/data")
@cache(expires=3600)
async def get_data(request):
  return JSONResponse({"data": "cached"})
```

**Parameters:**
- `expires` — Cache TTL in seconds (default: 300)
- `key_prefix` — Prefix for cache key
- `backend` — Cache backend name or instance

---

## Routing

### Basic Routes

```python
from altapi import AltAPI
from altapi.http import JSONResponse, HTMLResponse

app = AltAPI()


@app.get("/")
async def home(request):
  return HTMLResponse("<h1>Home</h1>")


@app.post("/api/users")
async def create_user(request):
  data = await request.json()
  return JSONResponse({"id": 1, **data})
```

### Typed Path Parameters

AltAPI supports automatic type conversion for path parameters:

```python
from altapi.http import Request, JSONResponse


# int parameter
@app.get("/api/users/{id:int}")
async def get_user(request: Request):
  user_id = request.path_params["id"]  # int
  return JSONResponse({"id": user_id})


# str parameter
@app.get("/api/items/{name:str}")
async def get_item(request: Request):
  name = request.path_params["name"]  # str
  return JSONResponse({"name": name})


# float parameter
@app.get("/api/score/{value:float}")
async def get_score(request: Request):
  value = request.path_params["value"]  # float
  return JSONResponse({"score": value})
```

### Synchronous Handlers

```python
from altapi import AltAPI
from altapi.http import JSONResponse

app = AltAPI()


@app.get("/api/sync")
def sync_handler(request):
  return JSONResponse({"type": "sync"})
```

---

## WebSocket

### Basic Example

```python
from altapi import AltAPI
from altapi.websocket import WebSocket

app = AltAPI()


@app.websocket("/ws/echo")
async def websocket_echo(ws: WebSocket):
  await ws.accept()
  while True:
    text = await ws.receive_text()
    await ws.send_text(f"Echo: {text}")
```

### WebSocket with Path Parameters

```python
from altapi import AltAPI
from altapi.websocket import WebSocket

app = AltAPI()


@app.websocket("/ws/chat/{room:str}")
async def websocket_chat(ws: WebSocket):
  room = ws.path_params["room"]
  await ws.accept()
  await ws.send_text(f"Welcome to room: {room}!")
```

### Iterating Over Messages

```python
from altapi import AltAPI
from altapi.websocket import WebSocket

app = AltAPI()


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
  await ws.accept()
  async for message in ws:
    if "text" in message:
      await ws.send_text(message["text"])
```

### JSON Handling

```python
from altapi import AltAPI
from altapi.websocket import WebSocket

app = AltAPI()


@app.websocket("/ws/json")
async def websocket_json(ws: WebSocket):
  await ws.accept()
  while True:
    data = await ws.receive_json()
    await ws.send_json({"received": data, "status": "ok"})
```

---

## Middleware

AltAPI has middleware support:

```python
from altapi.middleware import Middleware, BaseMiddleware
```

where `BaseMiddleware` is a class which inherits from:

```python
from altapi.middleware import BaseMiddleware


class BaseMiddleware:
  def __init__(self, app):
    self.app = app

  async def __call__(self, scope, receive, send):
    await self.app(scope, receive, send)
```

example middleware:

```python
import time
from altapi.middleware import BaseMiddleware


class TimingMiddleware(BaseMiddleware):
  async def __call__(self, scope, receive, send):
    if scope["type"] == "lifespan":
      return await self.app(scope, receive, send)

    start = time.time()
    await self.app(scope, receive, send)
    print(f"[TIME] {scope.get('path')} took {time.time() - start:.4f}s")
```

to use it:

```python
from altapi import AltAPI
from altapi.middleware import Middleware

app = AltAPI(middleware=[
  Middleware(TimingMiddleware)
])
```

---

## Caching

AltAPI has built-in caching support with a flexible backend system.

### Quick Start

The simplest way to enable caching:

```python
from altapi import AltAPI
from altapi.caching import InMemoryCache, cache

app = AltAPI(
  cache_backend=InMemoryCache(max_size=1000),
  cache_timeout=300
)


@app.get("/api/data")
@cache(expires=3600)
async def get_data(request):
  return JSONResponse({"data": "cached"})
```

### Cache Backends

AltAPI supports multiple cache backends. By default, it uses `InMemoryCache`.

```python
from altapi.caching import InMemoryCache, CacheManager

# Set default cache backend (if not using cache_backend in AltAPI)
CacheManager.set_default_backend(InMemoryCache(max_size=1000))

# Or register named backends
CacheManager.register_backend("redis", MyRedisCache())
```

### Using @cache Decorator

The simplest way to cache a function result:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache, InMemoryCache

app = AltAPI(cache_backend=InMemoryCache())


@app.get("/api/data")
@cache(expires=3600)  # Cache for 1 hour
async def get_data(request):
  # Expensive operation
  return JSONResponse({"data": "cached for 1 hour"})
```

**Parameters:**
- `expires` — Cache TTL in seconds (default: 300)
- `key_prefix` — Prefix for cache key (optional)
- `backend` — Cache backend name or instance (optional)

### Using CacheMiddleware

CacheMiddleware is automatically added when you specify `cache_backend` in `AltAPI()`.

For manual configuration:

```python
from altapi import AltAPI
from altapi.middleware import Middleware
from altapi.caching import CacheMiddleware, InMemoryCache, cache

app = AltAPI(middleware=[
  Middleware(CacheMiddleware, cache_timeout=300, backend=InMemoryCache())
])


@app.get("/api/users/{id:int}")
@cache(expires=3600)
async def get_user(request):
  return JSONResponse({"id": 1, "name": "John"})
```

### Using app.cache() Method

Alternative way to register cached routes:

```python
from altapi import AltAPI
from altapi.caching import InMemoryCache

app = AltAPI(cache_backend=InMemoryCache(), cache_timeout=300)


@app.cache("/api/data", expires=3600)
async def get_data(request):
  return JSONResponse({"data": "cached"})
```

### Custom Cache Backend

To create a custom cache backend, inherit from `CacheBackend`:

```python
from typing import Any, Optional
from altapi.caching import CacheBackend


class RedisCache(CacheBackend):
  async def get(self, key: str):
    # Implement get logic
    pass

  async def set(self, key: str, value: Any, expires: int = None):
    # Implement set logic
    pass

  async def delete(self, key: str):
    # Implement delete logic
    pass

  async def clear(self):
    # Implement clear logic
    pass
```

---

## Mounting Static Files and Applications

### Automatic Static Files (Recommended)

You can specify a static directory when creating the application. Files will be automatically served at `/static`:

```python
from altapi import AltAPI

app = AltAPI(static_directory="static")

# Files are automatically served at /static/<filepath>
# e.g., /static/css/style.css, /static/js/app.js
```

### Manual Mount Static Directory

```python
from altapi import AltAPI

app = AltAPI()

# Mount static files manually
app.mount("/static", directory="static")

# Files are served at /static/<filepath>
# e.g., /static/css/style.css, /static/js/app.js
```

### Mount ASGI Application

```python
from altapi import AltAPI

app = AltAPI()

# Mount another ASGI app
from some_module import sub_app

app.mount("/api", app=sub_app)
```

---

## Template Rendering

AltAPI supports Jinja2 templates for rendering HTML.

### Configuring Templates Directory

You can specify the templates directory when creating the application:

```python
from altapi import AltAPI

app = AltAPI(templates_directory="templates")
```

### Using Jinja2Templates (Recommended)

```python
from altapi import AltAPI
from altapi.templating import Jinja2Templates

app = AltAPI(templates_directory="templates")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home(request):
  return templates.TemplateResponse(
    "index.html",
    {"request": request, "title": "Home Page", "user": "John"}
  )
```

### Using render_template Function

```python
from altapi import AltAPI
from altapi.templating import render_template

app = AltAPI(templates_directory="templates")


@app.get("/")
async def home(request):
  return render_template(
    "index.html",
    {"title": "Home", "user": "John"}
  )
```

### Template Example (templates/index.html)

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
</head>
<body>
    <h1>Hello, {{ user }}!</h1>
</body>
</html>
```

**Note:** Install Jinja2 with `pip install jinja2` or `pip install altapi[templates]`

---

## Running the Server

### Using app.run()

```python
from altapi import AltAPI

app = AltAPI()


@app.get("/")
async def home(request):
  return HTMLResponse("<h1>Hello!</h1>")


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000)
```

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `host` | `str` | Host to bind | `"0.0.0.0"` |
| `port` | `int` | Port to bind | `8000` |
| `workers` | `int` | Number of worker processes | `1` |
| `gc_optimize` | `bool` | Optimize garbage collector settings | `True` |
| `access_log` | `bool` | Enable request logging | `True` |

### Multi-Process Mode

To run the server with multiple worker processes:

```python
if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, workers=4)
```

**Note:** When using `workers > 1`, the application file must be run as a module (not in REPL or interactive mode).

### Using uvicorn Directly

```python
if __name__ == "__main__":
  import uvicorn
  uvicorn.run("myapp:app", host="0.0.0.0", port=8000, workers=4)
```

---

## Examples

### Full Application

```python
from altapi import AltAPI
from altapi.http import JSONResponse, HTMLResponse
from altapi.websocket import WebSocket

app = AltAPI()


@app.get("/")
async def home(request):
  return HTMLResponse("<h1>Welcome to AltAPI!</h1>")


@app.get("/api/hello")
async def hello(request):
  return JSONResponse({"message": "Hello, World!"})


@app.post("/api/echo")
async def echo(request):
  data = await request.json()
  return JSONResponse({"echo": data})


@app.websocket("/ws/echo")
async def websocket_echo(ws: WebSocket):
  await ws.accept()
  while True:
    text = await ws.receive_text()
    await ws.send_text(f"Echo: {text}")


if __name__ == "__main__":
  import uvicorn

  uvicorn.run(app, host="0.0.0.0", port=8000)
```

More examples available in `examples/` folder.

---

## Testing

### Running Tests

```bash
# Make sure server is running on port 8000
python examples/app.py &

# Run tests
python test_app.py
```

### Test Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | HTML page |
| `/api/hello` | GET | JSON response |
| `/api/echo` | POST | Echo JSON |
| `/api/users/{id:int}` | GET | int parameter |
| `/api/items/{name:str}` | GET | str parameter |
| `/api/score/{value:float}` | GET | float parameter |
| `/api/sync` | GET | Sync handler |
| `/ws/echo` | WS | Echo WebSocket |
| `/ws/chat/{room:str}` | WS | Chat with room |
| `/ws/json` | WS | JSON WebSocket |

---

## Development

### Project Structure

```
AltAPI/
├── src/
│   └── altapi/
│       ├── __init__.py          # Main package exports
│       ├── app.py               # Main application class
│       ├── router.pyx           # Cython router
│       ├── http/                # HTTP components
│       │   ├── __init__.py
│       │   ├── request.py       # Request handling
│       │   └── responses.py     # Response classes
│       ├── websocket/           # WebSocket support
│       │   ├── __init__.py
│       │   └── ws.py
│       ├── templating/          # Template rendering
│       │   ├── __init__.py
│       │   ├── templates.py     # Jinja2 templates
│       │   └── default_templates.py
│       ├── caching/             # Caching system
│       │   ├── __init__.py
│       │   └── cache.py
│       └── middleware/          # Middleware support
│           ├── __init__.py
│           └── middleware.py
├── examples/
│   └── app.py                   # Usage examples
├── test_app.py                  # Tests
├── pyproject.toml               # Build configuration
└── setup.py                     # Setup script
```

### Recommended Imports (from subpackages)

For better organization and to avoid deprecation warnings, import from subpackages (except AltAPI):

```python
# Main application
from altapi import AltAPI

# HTTP components
from altapi.http import Request, Response, JSONResponse, HTMLResponse, PlainTextResponse, StreamingResponse,

FileResponse, RedirectResponse

# WebSocket
from altapi.websocket import WebSocket, WebSocketState

# Templates
from altapi.templating import Jinja2Templates, TemplateResponse, render_template

# Caching
from altapi.caching import cache, InMemoryCache, CacheManager, CacheMiddleware, CacheBackend

# Middleware
from altapi.middleware import Middleware, BaseMiddleware, ASGIApp
```

### Deprecated Imports (still supported but not recommended)

Direct imports from `altapi` are deprecated but still work with a warning:

```python
# Deprecated - will show DeprecationWarning
from altapi import Request, JSONResponse, WebSocket, cache
```

### Building

```bash
pip install -e .[dev]
```

### Dependencies

**Core:**
- uvicorn >= 0.30.0

**Development:**
- pytest >= 8.0.0
- httpx >= 0.27.0
- cython >= 3.0.0

---

## License

AGPLv3 License — see `LICENSE.txt` for details.

---

## Links

- [GitHub Repository](https://github.com/amogus-gggy/altapi)
- [PyPI Package](https://pypi.org/project/altapi/)

---
