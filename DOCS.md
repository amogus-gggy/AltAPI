# AltAPI Documentation

**AltAPI** is a simple, fast ASGI microframework for Python with WebSocket support, built-in dependency injection, caching, rate limiting, and automatic OpenAPI documentation.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [Application](#application)
  - [Routing](#routing)
  - [Request](#request)
  - [Responses](#responses)
  - [WebSocket](#websocket)
- [Middleware](#middleware)
- [Dependency Injection](#dependency-injection)
- [Caching](#caching)
- [Rate Limiting](#rate-limiting)
- [OpenAPI & Swagger UI](#openapi--swagger-ui)
- [Static Files & Mounting](#static-files--mounting)
- [Template Rendering](#template-rendering)
- [Running the Server](#running-the-server)
- [CLI](#cli)
- [Examples](#examples)
- [Testing](#testing)
- [Development](#development)

---

## Features

| Category | Features |
|---|---|
| **HTTP** | JSON, HTML, plain text, streaming, file, redirect responses |
| **Routing** | Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`, `{path:path}`), sync & async handlers |
| **WebSocket** | Full WebSocket support with text, binary, and JSON messaging |
| **Performance** | Optimized Cython router, GC optimizations, pre-encoded headers for common media types |
| **DI** | Dependency injection with automatic resource cleanup |
| **Caching** | Per-worker in-memory cache with pluggable backends |
| **Rate Limiting** | Multi-worker shared rate limiting with batch limits |
| **OpenAPI** | Auto-generated OpenAPI 3.0 spec and Swagger UI |
| **Templates** | Jinja2 template rendering |
| **Server** | Built-in multi-worker server via `app.run()` |
| **CLI** | Project scaffolding and run commands |
| **ASGI** | Fully ASGI compliant |

---

## Installation

```bash
pip install altapi
```

### Requirements

- Python >= 3.10
- uvicorn >= 0.30.0
- anyio >= 4.0.0
- jinja2 >= 3.0.0
- orjson
- Cython >= 3.0.0

### Development extras

```bash
pip install altapi[dev]
```

Adds: `pytest >= 8.0.0`, `httpx >= 0.27.0`, `cython >= 3.0.0`

---

## Quick Start

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

```bash
# Run directly
python app.py

# Or via uvicorn
uvicorn app:app --reload
```

After starting, visit:
- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Core Concepts

### Application

The `AltAPI` class is the main entry point.

```python
from altapi import AltAPI

app = AltAPI(
    title="My API",
    version="1.0.0",
    description="My awesome API",
    templates_directory="templates",
    static_directory="static",
)
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `middleware` | `List[Middleware]` | `[]` | List of middleware |
| `templates_directory` | `str` | `"templates"` | Directory for Jinja2 templates |
| `static_directory` | `str` | `None` | Static files directory (served at `/static`) |
| `cache_timeout` | `int` | `300` | Default cache TTL in seconds |
| `enable_openapi` | `bool` | `True` | Enable OpenAPI/Swagger UI (disable in production) |
| `openapi_url` | `str` | `"/openapi.json"` | URL for OpenAPI JSON spec (`None` to disable) |
| `docs_url` | `str` | `"/docs"` | URL for Swagger UI (`None` to disable) |
| `title` | `str` | `"AltAPI"` | API title in OpenAPI spec |
| `version` | `str` | `"0.1.0"` | API version in OpenAPI spec |
| `description` | `str` | `""` | API description in OpenAPI spec |

> **Note:** Cache backend is automatically initialized as `InMemoryCache` on `app.run()`. Each worker gets its own isolated cache.

---

### Routing

#### HTTP Method Decorators

```python
@app.get("/users")
@app.post("/users")
@app.put("/users/{id:int}")
@app.delete("/users/{id:int}")
@app.patch("/users/{id:int}")
@app.head("/users")
@app.options("/users")
@app.trace("/users")
@app.connect("/users")
@app.websocket("/ws/chat")
```

Use `@app.route()` to handle multiple methods on one handler:

```python
@app.route("/api/resource", methods=["GET", "POST"])
async def handler(request):
    if request.method == "GET":
        return JSONResponse({"method": "GET"})
    data = await request.json()
    return JSONResponse({"method": "POST", "data": data})
```

#### Typed Path Parameters

AltAPI automatically converts path parameters to the declared type:

| Type | Example | Result |
|---|---|---|
| `int` | `{id:int}` | `int` |
| `str` | `{name:str}` | `str` |
| `float` | `{value:float}` | `float` |
| `path` | `{path:path}` | `str` (captures slashes) |

```python
@app.get("/users/{id:int}")
async def get_user(request):
    user_id = request.path_params["id"]  # int
    return JSONResponse({"id": user_id})


@app.get("/files/{path:path}")
async def get_file(request):
    file_path = request.path_params["path"]  # e.g. "a/b/c.txt"
    return JSONResponse({"path": file_path})
```

#### Sync Handlers

Both sync and async handlers are supported:

```python
@app.get("/sync")
def sync_handler(request):
    return JSONResponse({"type": "sync"})
```

---

### Request

The `Request` object is passed to every handler.

```python
from altapi.http import Request

@app.get("/users/{id:int}")
async def get_user(request: Request):
    ...
```

#### Attributes

| Attribute | Type | Description |
|---|---|---|
| `method` | `str` | HTTP method (`GET`, `POST`, …) |
| `path` | `str` | Request path |
| `query_string` | `str` | Raw query string |
| `headers` | `Dict[str, str]` | Request headers |
| `path_params` | `Dict[str, Any]` | Typed path parameters |
| `client` | `Tuple[str, int]` | Client `(host, port)` |
| `scope` | `Dict` | Raw ASGI scope |
| `state` | `RequestState` | Per-request state (see [Dependency Injection](#dependency-injection)) |

#### RequestState Methods

The `request.state` object provides methods for passing data between middleware and handlers:

| Method | Description |
|---|---|
| `state.get(name, default=None)` | Get value by name |
| `state.set(name, value)` | Set value by name |
| `state.clear()` | Clear all values |

You can also use attribute access: `state.api_key = "value"` and `state.api_key`.

#### Methods

| Method | Description |
|---|---|
| `await request.json()` | Parse body as JSON |
| `await request.text()` | Get body as text |
| `await request.form()` | Parse form data (urlencoded or multipart) |

---

### Responses

Import from `altapi.http`:

```python
from altapi.http import (
    JSONResponse, HTMLResponse, PlainTextResponse,
    StreamingResponse, FileResponse, RedirectResponse,
)
```

All response classes share common parameters: `status_code` (default `200`) and `headers` (optional).

#### JSONResponse

```python
return JSONResponse({"key": "value"}, status_code=200)
```

- `content` — data to serialize as JSON

#### HTMLResponse

```python
return HTMLResponse("<h1>Welcome!</h1>")
```

- `content` — HTML string

#### PlainTextResponse

```python
return PlainTextResponse("Hello!")
```

- `content` — plain text string

#### StreamingResponse

```python
async def generate():
    for i in range(10):
        yield f"Line {i}\n"

return StreamingResponse(generate(), media_type="text/plain")
```

- `content` — async generator
- `media_type` — default `"text/plain"`

#### FileResponse

```python
return FileResponse("path/to/file.pdf", filename="report.pdf")
```

- `path` — filesystem path to file
- `filename` — download filename (default: basename of path)
- `media_type` — auto-detected from extension

Features: automatic MIME detection, range request support, `Last-Modified` header.

#### RedirectResponse

```python
return RedirectResponse("https://example.com")           # 303
return RedirectResponse("/new-path", status_code=307)    # preserve method
return RedirectResponse("/new-path", status_code=308)    # permanent
```

- `url` — redirect target
- `status_code` — `303` (default, POST→GET), `307` (temporary), `308` (permanent)

---

### WebSocket

```python
from altapi.websocket import WebSocket

@app.websocket("/ws/echo")
async def echo(ws: WebSocket):
    await ws.accept()
    while True:
        text = await ws.receive_text()
        await ws.send_text(f"Echo: {text}")
```

#### Attributes

| Attribute | Type | Description |
|---|---|---|
| `path` | `str` | WebSocket path |
| `headers` | `Dict[str, str]` | Connection headers |
| `path_params` | `Dict[str, Any]` | Typed path parameters |
| `state` | `WebSocketState` | Connection state |

#### Methods

| Method | Description |
|---|---|
| `await ws.accept()` | Accept the connection |
| `await ws.send_text(data)` | Send a text message |
| `await ws.send_bytes(data)` | Send binary data |
| `await ws.send_json(data)` | Send JSON |
| `await ws.receive_text()` | Receive text |
| `await ws.receive_bytes()` | Receive binary |
| `await ws.receive_json()` | Receive JSON |
| `await ws.close(code, reason)` | Close connection |
| `async for msg in ws` | Async iteration over messages |

#### States

```python
from altapi.websocket import WebSocketState

WebSocketState.CONNECTING   # Handshake in progress
WebSocketState.CONNECTED    # Active connection
WebSocketState.DISCONNECTED # Closed
```

#### Patterns

**Path parameters:**
```python
@app.websocket("/ws/chat/{room:str}")
async def chat(ws: WebSocket):
    room = ws.path_params["room"]
    await ws.accept()
    await ws.send_text(f"Joined room: {room}")
```

**Async iteration:**
```python
@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    async for message in ws:
        if "text" in message:
            await ws.send_text(message["text"])
```

---

## Middleware

Middleware intercepts every request before and after your handlers.

```python
from altapi.middleware import BaseMiddleware, Middleware
```

`BaseMiddleware` provides the base interface:

```python
class BaseMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
```

#### Example: Request Timing

```python
import time
from altapi.middleware import BaseMiddleware, Middleware

class TimingMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        start = time.time()
        await self.app(scope, receive, send)
        print(f"[{scope.get('path')}] {time.time() - start:.4f}s")

app = AltAPI(middleware=[Middleware(TimingMiddleware)])
```

#### Request State

Use `request.state` to pass data from middleware to handlers:

```python
# Middleware sets state
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # extract token, set state before passing through
        ...

# Handler reads state
@app.get("/me")
async def get_me(request):
    api_key = request.state.api_key
    ...
```

---

## Dependency Injection

AltAPI's DI system resolves dependencies automatically and handles cleanup after each request.

### Basic Usage

```python
from altapi.depends import Depends

def get_db():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn          # provide to handler
    finally:
        conn.close()        # cleanup guaranteed


@app.get("/users")
async def list_users(db=Depends(get_db)):
    users = db.cursor().execute("SELECT * FROM users").fetchall()
    return JSONResponse({"users": [dict(u) for u in users]})
```

### Dependency Types

```python
# Generator — with guaranteed cleanup
def get_db():
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()

# Simple function — no cleanup needed
def get_settings():
    return Settings.load_from_env()

# Async generator
async def get_redis():
    redis = await aioredis.create_redis()
    try:
        yield redis
    finally:
        redis.close()
        await redis.wait_closed()
```

### Nested Dependencies

Dependencies can depend on other dependencies:

```python
def get_repository(db=Depends(get_db)):
    return UserRepository(db)


@app.get("/users/{id:int}")
async def get_user(id: int, repo=Depends(get_repository)):
    return JSONResponse(repo.get_by_id(id))
```

### Request Injection

If a dependency declares a `Request` parameter, it is injected automatically:

```python
from altapi.http import Request

def get_current_user(request: Request, db=Depends(get_db)):
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    return db.get_user_by_token(token[7:])


@app.get("/profile")
async def profile(user=Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return JSONResponse(user)
```

### Per-Request Caching

Each dependency is resolved **once per request**. Multiple `Depends(get_db)` calls in the same request share the same instance:

```python
@app.get("/users")
async def handler(db1=Depends(get_db), db2=Depends(get_db)):
    # db1 is db2 — get_db() called only once
    ...
```

---

## Caching

AltAPI provides a per-worker in-memory cache, initialized automatically on `app.run()`.

> **Architecture:** Each worker maintains its own isolated cache (zero IPC overhead). For cross-worker cache sharing, use an external solution like Redis or a reverse proxy cache like Varnish.

### `@cache` Decorator

```python
from altapi.caching import cache

@app.get("/api/data")
@cache(expires=3600)
async def get_data(request):
    return JSONResponse({"data": "cached for 1 hour"})
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `expires` | `int` | `300` | Cache TTL in seconds |
| `key_prefix` | `str` | `""` | Optional prefix for the cache key |
| `backend` | `CacheBackend` | `None` | Custom backend instance |
| `key_func` | `Callable` | `None` | Custom cache key generator |

### `app.cache()` Method

```python
@app.cache("/api/data", expires=3600)
@app.get("/api/data")
async def get_data(request):
    return JSONResponse({"data": "cached"})
```

### `CacheMiddleware`

Cache responses automatically for all routes:

```python
from altapi.caching import CacheMiddleware

app = AltAPI(middleware=[Middleware(CacheMiddleware, cache_timeout=300)])
```

### Custom Cache Backend

```python
from altapi.caching import CacheBackend

class RedisCache(CacheBackend):
    async def get(self, key: str): ...
    async def set(self, key: str, value, expires: int = None): ...
    async def delete(self, key: str): ...
    async def clear(self): ...
```

### `InMemoryCache` Additional Methods

```python
from altapi.caching import InMemoryCache

cache = InMemoryCache(max_size=10000)
removed = await cache.cleanup_expired()  # Remove expired entries, returns count
```

| Method | Description |
|---|---|
| `cleanup_expired()` | Remove expired entries, returns number of removed entries |

---

## Rate Limiting

Rate limiting is applied per-endpoint via decorators. In multi-worker mode, state is stored in a **centralized shared manager process** (started automatically by `app.run()`).

> ⚠️ **Performance note:** Rate limiting adds significant overhead (~9.5x). Apply only where needed.

### `@rate_limit`

```python
from altapi.ratelimit import rate_limit

@app.get("/api/data")
@rate_limit(limit=100, period=60)   # 100 requests per minute
async def get_data(request):
    return JSONResponse({"data": "value"})
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `10` | Max requests per period |
| `period` | `float` | `60` | Window duration in seconds |
| `key_func` | `Callable` | `None` | Extracts client key from request (default: client IP) |
| `skip_when` | `Callable` | `None` | Return `True` to bypass rate limiting |

### `@rate_limit_batch`

Apply multiple limits simultaneously — all must pass:

```python
from altapi.ratelimit import rate_limit_batch

@app.post("/api/login")
@rate_limit_batch([
    (5, 60),       # 5 per minute
    (20, 3600),    # 20 per hour
    (50, 86400),   # 50 per day
])
async def login(request): ...
```

| Parameter | Type | Description |
|---|---|---|
| `limits` | `List[Tuple[int, float]]` | List of `(limit, period)` tuples |
| `key_func` | `Callable` | Custom key extractor |

### Custom Key Functions

By default the client IP is used. Override with `key_func`:

```python
# By API key header
def get_api_key(request):
    return request.headers.get("X-API-Key", "anonymous")

# By JWT user ID (async supported)
async def get_user_id(request):
    token = request.headers.get("Authorization", "")[7:]
    try:
        return f"user:{decode_jwt(token)['sub']}"
    except Exception:
        return "anonymous"
```

### Skip Conditions

Use `skip_when` to bypass limiting for specific clients:

```python
# Skip for internal network
def is_internal(request):
    ip = request.client.host if request.client else ""
    return any(ip.startswith(p) for p in ["10.", "172.16.", "192.168."])

# Skip for whitelisted API keys
WHITELIST = {"admin-key", "premium-key-1"}
def is_whitelisted(request):
    return request.headers.get("X-API-Key", "") in WHITELIST

# Skip in debug mode
def is_debug(request):
    return os.getenv("DEBUG", "false").lower() == "true"
```

### Rate Limit Headers

Every response includes:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 73
X-RateLimit-Reset: 1711737600
```

On `429 Too Many Requests`:

```
Retry-After: 45
```

```json
{
    "error": "Rate limit exceeded",
    "message": "Too many requests. Try again in 45 seconds."
}
```

### Storage Backends

AltAPI provides multiple storage backends for rate limiting:

```python
from altapi.ratelimit import (
    InMemoryRateLimitStorage,
    SharedMemoryRateLimitStorage,
    set_storage,
    use_shared_memory,
)
```

| Class | Description |
|---|---|
| `InMemoryRateLimitStorage` | Simple in-memory storage for single-process apps |
| `SharedMemoryRateLimitStorage` | Uses `multiprocessing.shared_memory` for multi-worker apps (default) |
| `BaseRateLimitStorage` | Abstract base class for custom backends |

#### `RateLimitResult`

The `check_rate_limit()` method returns a dataclass:

```python
from altapi.ratelimit import RateLimitResult

# Fields:
#   allowed: bool    — Whether request is allowed
#   remaining: int   — Remaining requests in period
#   limit: int       — Max requests per period
#   reset: float     — Timestamp when the period resets
```

#### Custom Storage

Set a custom storage instance globally:

```python
from altapi.ratelimit import set_storage, InMemoryRateLimitStorage

set_storage(InMemoryRateLimitStorage())
```

#### Disable Shared Memory

For single-process deployment:

```python
from altapi.ratelimit import use_shared_memory

use_shared_memory(False)  # Use in-memory storage instead of shared memory
```

---

## OpenAPI & Swagger UI

OpenAPI 3.0 spec and Swagger UI are enabled by default.

```
GET /docs        → Swagger UI
GET /openapi.json → OpenAPI spec
```

### Disabling Documentation

```python
app = AltAPI(enable_openapi=False)   # disable entirely
app = AltAPI(docs_url=None)          # disable Swagger UI only
app = AltAPI(openapi_url=None)       # disable OpenAPI JSON only
```

### Custom URLs

```python
app = AltAPI(
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
)
```

### `@openapi` Decorator

Add metadata to individual endpoints:

```python
from altapi.openapi_decorators import openapi

@app.get("/users/{id:int}")
@openapi(
    summary="Get user by ID",
    description="Returns a single user object",
    tags=["users"],
    responses={
        "200": {
            "description": "User found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                        }
                    }
                }
            }
        },
        "404": {"description": "User not found"}
    }
)
async def get_user(request):
    user_id = request.path_params["id"]
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})
```

### `@describe_request_body`

Document POST/PUT/PATCH request bodies:

```python
from altapi.openapi_decorators import openapi, describe_request_body

@app.post("/users")
@describe_request_body({
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["name", "email"],
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                }
            }
        }
    }
})
@openapi(summary="Create user", tags=["users"])
async def create_user(request):
    data = await request.json()
    return JSONResponse({"id": 1, **data})
```

### All OpenAPI Decorators

| Decorator | Description |
|---|---|
| `@openapi(...)` | Full endpoint metadata (summary, description, tags, responses) |
| `@tag(...)` | Add tags to endpoint |
| `@deprecated` | Mark endpoint as deprecated |
| `@describe_responses(...)` | Add response schemas |
| `@describe_request_body(...)` | Add request body schema |

AltAPI also auto-generates documentation from: registered routes, path parameter types, handler docstrings, and function signatures.

---

## Static Files & Mounting

### Automatic (Recommended)

```python
app = AltAPI(static_directory="static")
# Files served at /static/<filepath>
```

### Manual Mount

```python
app.mount("/static", directory="static")
```

### Mount a Sub-Application

```python
from some_module import sub_app

app.mount("/api/v2", app=sub_app)
```

---

## Template Rendering

AltAPI uses Jinja2 for HTML templating.

```bash
pip install altapi[templates]  # or: pip install jinja2
```

### Setup

```python
app = AltAPI(templates_directory="templates")
```

### Using `Jinja2Templates` (Recommended)

```python
from altapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Home", "user": "John"}
    )
```

### Using `render_template`

```python
from altapi.templating import render_template

@app.get("/")
async def home(request):
    return render_template("index.html", {"title": "Home", "user": "John"})
```

### Template Example

```html
<!DOCTYPE html>
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>Hello, {{ user }}!</h1>
</body>
</html>
```

---

## Running the Server

### `app.run()`

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=4)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | `"0.0.0.0"` | Bind host |
| `port` | `int` | `8000` | Bind port |
| `workers` | `int` | `1` | Number of worker processes |
| `access_log` | `bool` | `True` | Enable request logging |

> **Note:** When using `workers > 1`, run the app as a module, not from a REPL.

### GC Optimizations

`app.run()` automatically applies performance optimizations to all workers: forced garbage collection on startup, object freezing, and increased GC thresholds.

### Using uvicorn Directly

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

> Note: `app.run()` is recommended over invoking uvicorn directly, as it includes AltAPI's GC optimizations and automatic shared manager startup.

---

## CLI

AltAPI includes a CLI for project creation and running.

```bash
altapi --help
altapi --version
```

### Commands

| Command | Description |
|---|---|
| `altapi create <name>` | Create a new project from template |
| `altapi run [app_path]` | Run an AltAPI application |
| `altapi init [name]` | Initialize a minimal app in the current directory |
| `altapi scaffold [name]` | Scaffold a full-featured project |
| `altapi list-templates` | List available templates |
| `altapi show-template <name>` | Show contents of a template |

---

### `altapi create`

```bash
altapi create <name> [--template|-t TEMPLATE] [--dir|-d DIR]
```

```bash
altapi create myapi                  # basic template
altapi create myapi -t full          # full-featured template
altapi create myapi -d /path/to/dir  # custom output directory
```

---

### `altapi run`

```bash
altapi run [app_path] [options]
```

| Flag | Default | Description |
|---|---|---|
| `--host`, `-h` | `0.0.0.0` | Bind host |
| `--port`, `-p` | `8000` | Bind port |
| `--workers`, `-w` | `1` | Worker processes |
| `--reload`, `-r` | `False` | Auto-reload on code changes |
| `--log-level` | `info` | `critical` / `error` / `warning` / `info` / `debug` |
| `--app-dir` | auto | Override app module directory |

```bash
altapi run                       # default: app:app
altapi run main:app
altapi run -p 8080 --reload
altapi run -w 4
altapi run examples.app:app --log-level debug
```

---

### `altapi init`

Creates `app.py` and `requirements.txt` in the current directory.

```bash
cd /path/to/project
altapi init myproject
```

---

### `altapi scaffold`

Generates a full project layout:

```
myproject/
├── app.py
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── api.py
│   └── pages.py
├── templates/
│   ├── base.html
│   └── index.html
└── static/
    ├── css/style.css
    └── js/main.js
```

```bash
altapi scaffold myapi
altapi scaffold myapi -d /path/to/projects
```

---

### Template System

Templates live in `src/altapi/cli_templates/`. Each template is a directory of project files.

**Placeholders:**
- `myproject` → replaced with lowercase project name
- `MyProject` → replaced with title-case project name

Add an optional `DESCRIPTION` file for a short description shown in `list-templates`.

**Creating a custom template:**

```bash
mkdir src/altapi/cli_templates/my-template
# Add project files
# Optionally add DESCRIPTION file
```

---

## Examples

### Minimal App

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
    return JSONResponse({"echo": await request.json()})


@app.websocket("/ws/echo")
async def ws_echo(ws: WebSocket):
    await ws.accept()
    while True:
        text = await ws.receive_text()
        await ws.send_text(f"Echo: {text}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### CRUD Application with SQLite & DI

```python
from altapi import AltAPI
from altapi.http import JSONResponse, RedirectResponse
from altapi.depends import Depends
import sqlite3

app = AltAPI(templates_directory="templates")


def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/users")
async def list_users(db=Depends(get_db)):
    users = db.cursor().execute("SELECT * FROM users").fetchall()
    return JSONResponse({"users": [dict(u) for u in users]})


@app.post("/api/users")
async def create_user(request, db=Depends(get_db)):
    data = await request.json()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (data["name"], data["email"]))
    db.commit()
    return JSONResponse({"id": cursor.lastrowid}, status_code=201)


@app.delete("/api/users/{id:int}")
async def delete_user(id: int, db=Depends(get_db)):
    db.cursor().execute("DELETE FROM users WHERE id = ?", (id,))
    db.commit()
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

More examples in `examples/`:
- `examples/webapp.py` — Full CRUD app with web UI and API
- `examples/sqlite_example.py` — SQLite + Dependency Injection
- `examples/app.py` — Feature showcase

---

## Testing

```bash
# Start the server
python examples/app.py &

# Run tests
python test_app.py
```

### Test Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | HTML page |
| `/api/hello` | GET | JSON response |
| `/api/echo` | POST | Echo JSON body |
| `/api/users/{id:int}` | GET | Int path parameter |
| `/api/items/{name:str}` | GET | String path parameter |
| `/api/score/{value:float}` | GET | Float path parameter |
| `/api/sync` | GET | Sync handler |
| `/ws/echo` | WS | Echo WebSocket |
| `/ws/chat/{room:str}` | WS | Roomed chat WebSocket |
| `/ws/json` | WS | JSON WebSocket |

---

## Development

### Project Structure

```
AltAPI/
├── src/altapi/
│   ├── __init__.py              # Package exports
│   ├── app.py                   # AltAPI class
│   ├── router.pyx               # Cython router
│   ├── cli.py                   # CLI tool
│   ├── cli_templates/           # Project templates
│   ├── http/
│   │   ├── request.py           # Request class
│   │   └── responses.py         # Response classes
│   ├── websocket/
│   │   └── ws.py                # WebSocket class
│   ├── middleware/
│   │   └── middleware.py        # BaseMiddleware, Middleware
│   ├── templating/
│   │   └── templates.py         # Jinja2Templates, render_template
│   ├── caching/
│   │   └── cache.py             # CacheBackend, InMemoryCache, CacheMiddleware
│   ├── ratelimit/
│   │   └── limit.py             # rate_limit, rate_limit_batch
│   └── shared/                  # Shared manager for multi-worker
├── examples/
├── test_app.py
├── pyproject.toml
├── setup.py
└── DOCS.md
```

### Building from Source

```bash
# Build wheel
python -m build

# Compile Cython extensions in-place
python setup.py build_ext --inplace
```

### License

AGPLv3 — see [LICENSE.txt](LICENSE.txt) for details.
