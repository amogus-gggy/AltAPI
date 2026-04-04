# AltAPI Documentation

**AltAPI** is a simple and fast ASGI microframework for Python with WebSocket support.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Features](#features)
- [API Reference](#api-reference)
  - [AltAPI](#altapi)
  - [Request](#request)
  - [Response Classes](#response-classes)
    - [JSONResponse](#jsonresponse)
    - [HTMLResponse](#htmlresponse)
    - [PlainTextResponse](#plaintextresponse)
    - [StreamingResponse](#streamingresponse)
    - [FileResponse](#fileresponse)
    - [RedirectResponse](#redirectresponse)
  - [WebSocket](#websocket)
- [Routing](#routing)
- [WebSocket Support](#websocket-support)
- [OpenAPI & SwaggerUI](#openapi--swaggerui)
- [Middleware](#middleware)
- [Dependency Injection](#dependency-injection)
- [Caching](#caching)
- [Rate Limiting](#rate-limiting)
- [Mounting Static Files and Applications](#mounting-static-files-and-applications)
- [Template Rendering](#template-rendering)
- [Running the Server](#running-the-server)
- [Examples](#examples)
- [Testing](#testing)
- [Development](#development)

---

## Features

- ✅ ASGI compliant
- ✅ JSON, HTML, and text responses
- ✅ Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`, `{path:path}`)
- ✅ Sync and async handler support
- ✅ Full WebSocket support
- ✅ Built-in server (`app.run()`) with multi-worker support
- ✅ Jinja2 templates
- ✅ Response caching with per-worker InMemoryCache
- ✅ Rate limiting with shared manager for multi-worker support
- ✅ Static file mounting
- ✅ Optimized Cython router
- ✅ GC optimizations for better performance
- ✅ Pre-encoded headers for common media types
- ✅ **Dependency Injection** with automatic cleanup
- ✅ **Request state** for passing data between middleware and handlers
- ✅ **Form data parsing** (urlencoded and multipart)
- ✅ **OpenAPI 3.0 specification** auto-generation
- ✅ **SwaggerUI** interactive API documentation

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
- ujson
- Cython >= 3.0.0

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
| `cache_timeout` | `int` | Default cache timeout in seconds | `300` |
| `enable_openapi` | `bool` | Enable OpenAPI/SwaggerUI (set `False` for production) | `True` |
| `openapi_url` | `str` | URL for OpenAPI JSON specification (`None` to disable) | `"/openapi.json"` |
| `docs_url` | `str` | URL for SwaggerUI documentation (`None` to disable) | `"/docs"` |
| `title` | `str` | API title for OpenAPI spec | `"AltAPI"` |
| `version` | `str` | API version for OpenAPI spec | `"0.1.0"` |
| `description` | `str` | API description for OpenAPI spec | `""` |

#### HTTP Method Decorators

| Method | Description |
|--------|-------------|
| `@app.get(path)` | Register GET route |
| `@app.post(path)` | Register POST route |
| `@app.put(path)` | Register PUT route |
| `@app.delete(path)` | Register DELETE route |
| `@app.patch(path)` | Register PATCH route |
| `@app.head(path)` | Register HEAD route |
| `@app.options(path)` | Register OPTIONS route |
| `@app.trace(path)` | Register TRACE route |
| `@app.connect(path)` | Register CONNECT route |
| `@app.websocket(path)` | Register WebSocket route |
| `@app.route(path, methods)` | Universal decorator for multiple methods |

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
| `headers_dict` | `Dict[str, str]` | Request headers as dictionary |
| `path_params` | `Dict[str, Any]` | Path parameters (auto-converted) |
| `scope` | `Dict` | ASGI scope |
| `client` | `Tuple[str, int]` | Client (host, port) |
| `state` | `RequestState` | Per-request state storage |

#### Methods

| Method | Description |
|--------|-------------|
| `async json()` | Parse request body as JSON |
| `async text()` | Get request body as text |
| `async form()` | Parse form data (urlencoded or multipart) |

---

### Response Classes

Base HTTP response classes.

```python
from altapi.http import (
    Response,
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    StreamingResponse,
    FileResponse,
    RedirectResponse,
)
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

**Parameters:**
- `content` — text content
- `status_code` — status code (default 200)
- `headers` — headers (optional)

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

**Parameters:**
- `content` — async generator or callable returning async generator
- `status_code` — status code (default 200)
- `headers` — headers (optional)
- `media_type` — media type (default "text/plain")

#### FileResponse

```python
from altapi.http import FileResponse


@app.get("/download")
async def download(request):
    return FileResponse("path/to/file.pdf", filename="myfile.pdf")
```

**Parameters:**
- `path` — path to file
- `status_code` — status code (default 200)
- `headers` — headers (optional)
- `media_type` — media type (auto-detected from extension)
- `filename` — download filename (default: basename of path)

**Features:**
- Automatic MIME type detection
- Range request support (partial content)
- Last-Modified header

#### RedirectResponse

```python
from altapi.http import RedirectResponse


@app.get("/redirect")
async def redirect(request):
    return RedirectResponse("https://example.com")
```

**Parameters:**
- `url` — redirect URL
- `status_code` — status code (default **303** for POST→GET redirect)
- `headers` — headers (optional)

**Status Codes:**
- `303` (default) — "See Other", redirects POST to GET (recommended)
- `307` — "Temporary Redirect", preserves original method
- `308` — "Permanent Redirect", preserves original method

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

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | WebSocket path |
| `headers` | `Dict[str, str]` | Request headers |
| `path_params` | `Dict[str, Any]` | Path parameters |
| `state` | `WebSocketState` | Connection state |

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


# path parameter (captures rest of path)
@app.get("/files/{path:path}")
async def get_file(request: Request):
    file_path = request.path_params["path"]  # str with slashes
    return JSONResponse({"path": file_path})
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

### Universal Route Decorator

```python
@app.route("/api/multi", methods=["GET", "POST"])
async def multi_handler(request):
    if request.method == "GET":
        return JSONResponse({"method": "GET"})
    else:
        data = await request.json()
        return JSONResponse({"method": "POST", "data": data})
```

---

## WebSocket Support

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

### Binary Data

```python
from altapi import AltAPI
from altapi.websocket import WebSocket

app = AltAPI()


@app.websocket("/ws/binary")
async def websocket_binary(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_bytes()
        await ws.send_bytes(data)
```

---

## Middleware

AltAPI has middleware support:

```python
from altapi.middleware import Middleware, BaseMiddleware
```

`BaseMiddleware` is a class which inherits from:

```python
from altapi.middleware import BaseMiddleware


class BaseMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
```

Example middleware:

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

To use it:

```python
from altapi import AltAPI
from altapi.middleware import Middleware

app = AltAPI(middleware=[
    Middleware(TimingMiddleware)
])
```

---

## Dependency Injection

AltAPI has built-in **Dependency Injection (DI)** system for managing resources and sharing logic between handlers.

### Quick Start

The simplest way to use DI:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.depends import Depends

app = AltAPI()


# Create a dependency (e.g., database connection)
def get_db():
    import sqlite3
    conn = sqlite3.connect("mydb.db")
    try:
        yield conn  # Provide the resource
    finally:
        conn.close()  # Cleanup automatically


# Use dependency in handler
@app.get("/users")
async def list_users(db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return JSONResponse({"users": users})
```

### How It Works

```
Request → AltAPI → Resolve Depends(get_db)
                  ↓
            Call get_db()
                  ↓
            yield conn ← Return to handler
                  ↓
            Handler uses conn
                  ↓
            After handler: finally block
                  ↓
            conn.close() ← Automatic cleanup
```

### Dependency Function Types

#### 1. Generator-based (with cleanup)

```python
def get_db():
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()  # Guaranteed cleanup
```

#### 2. Simple function (no cleanup needed)

```python
def get_settings():
    return Settings.load_from_env()
```

#### 3. Async dependency

```python
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
def get_db():
    conn = sqlite3.connect("mydb.db")
    try:
        yield conn
    finally:
        conn.close()


def get_repository(db=Depends(get_db)):
    return UserRepository(db)


@app.get("/users/{id:int}")
async def get_user(id: int, repo=Depends(get_repository)):
    user = await repo.get_by_id(id)
    return JSONResponse(user)
```

### Request in Dependencies

`Request` is automatically injected if the dependency expects it:

```python
from altapi.http import Request


def get_current_user(request: Request, db=Depends(get_db)):
    token = request.headers.get("Authorization")
    if not token:
        return None
    # Query user from DB
    return db.get_user_by_token(token)


@app.get("/profile")
async def profile(user=Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return JSONResponse(user)
```

### Caching

Dependencies are **cached per request** by default:

```python
def get_db():
    print("Creating connection")  # ← Called only once per request
    conn = sqlite3.connect("mydb.db")
    try:
        yield conn
    finally:
        conn.close()


@app.get("/users")
async def list_users(db1=Depends(get_db), db2=Depends(get_db)):
    # db1 and db2 are the SAME connection
    # get_db() is called only once
    ...
```

### Request State

Use `request.state` to pass data between middleware and handlers:

```python
# Middleware
@app.middleware
async def auth_middleware(request, call_next):
    token = request.headers.get("X-API-Key")
    request.state.api_key = token  # Store for later
    return await call_next(request)


# Handler
@app.get("/me")
async def get_me(request):
    api_key = request.state.api_key  # Access from middleware
    ...
```

### Examples

#### Database Connection

```python
import sqlite3
from altapi.depends import Depends


def get_db():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@app.get("/users/{id:int}")
async def get_user(id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()
    if not user:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(dict(user))
```

#### Authentication

```python
from altapi.http import Request, JSONResponse


async def get_current_user(request: Request, db=Depends(get_db)):
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE token = ?", (token[7:],))
    return cursor.fetchone()


@app.get("/protected")
async def protected_route(user=Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, 401)
    return JSONResponse({"user": dict(user)})
```

#### Configuration/Settings

```python
from dataclasses import dataclass


@dataclass
class Settings:
    debug: bool
    database_url: str
    secret_key: str
    
    @classmethod
    def load_from_env(cls):
        return cls(
            debug=os.getenv("DEBUG", "false") == "true",
            database_url=os.getenv("DATABASE_URL"),
            secret_key=os.getenv("SECRET_KEY"),
        )


def get_settings():
    return Settings.load_from_env()


@app.get("/config")
async def get_config(settings=Depends(get_settings)):
    return JSONResponse({
        "debug": settings.debug,
        "version": "1.0.0"
    })
```

---

## Caching

AltAPI has built-in caching support with a flexible backend system.

### Quick Start

The simplest way to enable caching:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

app = AltAPI()


@app.get("/api/data")
@cache(expires=3600)  # Cache for 1 hour
async def get_data(request):
    return JSONResponse({"data": "cached"})
```

### How It Works

AltAPI uses **per-worker InMemoryCache** for zero IPC overhead. Each worker maintains its own cache, which is optimal for most use cases.

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│    Worker 1     │      │    Worker 2     │      │    Worker 3     │
│  ┌───────────┐  │      │  ┌───────────┐  │      │  ┌───────────┐  │
│  │   Cache   │  │      │  │   Cache   │  │      │  │   Cache   │  │
│  │ (in-mem)  │  │      │  │ (in-mem)  │  │      │  │ (in-mem)  │  │
│  └───────────┘  │      │  └───────────┘  │      │  └───────────┘  │
│  (uvicorn)      │      │  (uvicorn)      │      │  (uvicorn)      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

For shared caching across workers, consider using a reverse proxy cache (e.g., Varnish) or external cache (e.g., Redis).

### Automatic Startup

The caching system is **automatically** initialized when calling `app.run()`:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # Caching initialized automatically!
```

### Using @cache Decorator

The simplest way to cache a function result:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

app = AltAPI()


@app.get("/api/data")
@cache(expires=3600)  # Cache for 1 hour
async def get_data(request):
    # Expensive operation
    return JSONResponse({"data": "cached for 1 hour"})
```

**Parameters:**
- `expires` — Cache TTL in seconds (default: 300)
- `key_prefix` — Prefix for cache key (optional)
- `backend` — Cache backend instance (optional)
- `key_func` — Custom function to generate cache key (optional)

### Using app.cache() Method

Alternative way to register cached routes:

```python
from altapi import AltAPI
from altapi.caching import InMemoryCache

app = AltAPI(cache_timeout=300)


@app.cache("/api/data", expires=3600)
@app.get("/api/data")
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

### CacheMiddleware

For automatic response caching via middleware:

```python
from altapi import AltAPI
from altapi.middleware import Middleware
from altapi.caching import CacheMiddleware

app = AltAPI(middleware=[
    Middleware(CacheMiddleware, cache_timeout=300)
])
```

---

## OpenAPI & SwaggerUI

AltAPI provides built-in support for **OpenAPI 3.0 specification** generation and **SwaggerUI** interactive documentation.

### Quick Start

OpenAPI and SwaggerUI are enabled **by default**:

```python
from altapi import AltAPI
from altapi.http import JSONResponse

app = AltAPI(
    title="My API",
    version="1.0.0",
    description="My awesome API",
)


@app.get("/api/hello")
async def hello(request):
    return JSONResponse({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run()
```

After running the server:
- **SwaggerUI**: http://localhost:8000/docs
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Disabling Documentation

To disable OpenAPI/SwaggerUI (recommended for production):

```python
# Option 1: Disable completely
app = AltAPI(enable_openapi=False)

# Option 2: Disable only SwaggerUI (keep OpenAPI JSON)
app = AltAPI(docs_url=None)

# Option 3: Disable only OpenAPI JSON (keep SwaggerUI)
app = AltAPI(openapi_url=None)
```

### Custom URLs

To customize the documentation URLs:

```python
app = AltAPI(
    openapi_url="/api/openapi.json",  # Custom OpenAPI URL
    docs_url="/api/docs",              # Custom docs URL
)
```

### Adding Metadata to Endpoints

Use the `@openapi` decorator to add detailed documentation:

```python
from altapi.openapi_decorators import openapi


@app.get("/api/users/{id:int}")
@openapi(
    summary="Get user by ID",
    description="Returns a single user object by their ID",
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

### Request Body Documentation

For POST/PUT/PATCH endpoints, use `@describe_request_body`:

```python
from altapi.openapi_decorators import openapi, describe_request_body


@app.post("/api/users")
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
@openapi(
    summary="Create user",
    description="Creates a new user",
    tags=["users"],
)
async def create_user(request):
    data = await request.json()
    return JSONResponse({"id": 1, **data})
```

### Tags and Deprecation

```python
from altapi.openapi_decorators import tag, deprecated


@app.get("/api/items")
@tag("items", "catalog")
async def list_items(request):
    return JSONResponse({"items": []})


@app.get("/api/old-endpoint")
@deprecated
async def old_endpoint(request):
    return JSONResponse({"message": "Use /api/new-endpoint instead"})
```

### Available OpenAPI Decorators

| Decorator | Description |
|-----------|-------------|
| `@openapi(...)` | Add full OpenAPI metadata to endpoint |
| `@tag(...)` | Add tags to endpoint |
| `@deprecated` | Mark endpoint as deprecated |
| `@describe_responses(...)` | Add response schemas |
| `@describe_request_body(...)` | Add request body schema |

### Auto-generated Documentation

AltAPI automatically generates OpenAPI 3.0 specification from:
- Registered routes
- Path parameter types (`{id:int}`, `{name:str}`, `{value:float}`)
- Handler function signatures (query parameters)
- Handler docstrings
- `@openapi` decorator metadata

### Example Output

OpenAPI JSON structure:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "My API",
    "version": "1.0.0",
    "description": "My awesome API"
  },
  "servers": [
    {"url": "http://localhost:8000", "description": "Local development"}
  ],
  "paths": {
    "/api/users/{id}": {
      "get": {
        "summary": "Get user by ID",
        "operationId": "get__api_users__id_",
        "tags": ["users"],
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "schema": {"type": "integer", "format": "int64"}
          }
        ],
        "responses": {
          "200": {"description": "Successful Response"},
          "404": {"description": "Not Found"}
        }
      }
    }
  }
}
```

---

## Rate Limiting

Rate Limiting is a mechanism for controlling the number of requests a client can send within a specified time period. It's an important part of protecting APIs from abuse, DDoS attacks, and excessive server load.

### Quick Start

Rate limiting in AltAPI is extremely simple to use. All you need is to import the decorator:

```python
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.ratelimit import rate_limit

app = AltAPI()


@app.get("/api/data")
@rate_limit(limit=10, period=60)  # 10 requests per minute
async def get_data(request):
    return JSONResponse({"data": "value"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### Key Features

- ✅ **Simple import** — just `from altapi.ratelimit import rate_limit`
- ✅ **No configuration** — manager starts automatically at `app.run()`
- ✅ **Multi-worker support** — all data stored in central process via shared manager
- ✅ **Production ready** — works out of the box

⚠️ **Warning:** Rate limiting adds overhead (approximately 9.5x slowdown on average). Use only when necessary.

### What Happens When Limit Exceeded

```json
{
    "error": "Rate limit exceeded",
    "message": "Too many requests. Try again in 45 seconds."
}
```

Response includes headers:
- `X-RateLimit-Limit` — Maximum requests per period
- `X-RateLimit-Remaining` — Requests remaining
- `X-RateLimit-Reset` — Reset time (Unix timestamp)
- `Retry-After` — Seconds until reset (on 429)

---

### @rate_limit Decorator

Main decorator for rate limiting requests.

#### Syntax

```python
from altapi.ratelimit import rate_limit


@app.get("/api/endpoint")
@rate_limit(
    limit=10,           # Maximum requests
    period=60,          # Period in seconds
    key_func=None,      # Function to get key
    skip_when=None      # Condition to skip
)
async def my_endpoint(request):
    ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | `int` | `10` | Maximum number of requests per period |
| `period` | `float` | `60` | Period duration in seconds |
| `key_func` | `Callable` | `None` | Function to extract unique key from request |
| `skip_when` | `Callable` | `None` | Function to determine when to skip rate limiting |

#### limit and period Parameters

**`limit`** — maximum number of requests allowed per period.

**`period`** — period duration in seconds.

##### Examples

```python
# 5 requests per second
@rate_limit(limit=5, period=1)
async def fast_endpoint(request):
    ...

# 100 requests per minute
@rate_limit(limit=100, period=60)
async def normal_endpoint(request):
    ...

# 1000 requests per hour
@rate_limit(limit=1000, period=3600)
async def hourly_endpoint(request):
    ...

# 10000 requests per day
@rate_limit(limit=10000, period=86400)
async def daily_endpoint(request):
    ...
```

#### key_func Parameter

**`key_func`** — function that extracts a unique identifier from the request. By default, the client IP address is used.

##### Default Function (IP Address)

```python
# Internal default implementation
def default_key_func(request):
    return request.client.host if request.client else "unknown"
```

##### Custom Key Function

```python
def get_api_key(request):
    """Get key from X-API-Key header."""
    return request.headers.get("X-API-Key", "anonymous")


@app.get("/api/premium")
@rate_limit(limit=100, period=60, key_func=get_api_key)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

##### Async Key Function

```python
async def get_user_key(request):
    """Async user key extraction."""
    token = request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        # Token verification in DB here
        user_id = await get_user_id_from_token(token[7:])
        return f"user:{user_id}"
    return "anonymous"


@app.get("/api/user")
@rate_limit(limit=50, period=60, key_func=get_user_key)
async def user_endpoint(request):
    return JSONResponse({"user": "data"})
```

#### skip_when Parameter

**`skip_when`** — function that determines when to skip rate limiting. Returns `True` to skip or `False` to apply rate limiting.

##### Skip for Administrators

```python
def is_admin(request):
    """Skip rate limiting for administrators."""
    admin_key = request.headers.get("X-Admin-Key", "")
    return admin_key == "supersecretadminkey"


@app.get("/api/admin")
@rate_limit(limit=10, period=60, skip_when=is_admin)
async def admin_endpoint(request):
    return JSONResponse({"admin": "data"})
```

##### Skip for Local Requests

```python
def is_local(request):
    """Skip rate limiting for local requests."""
    return request.client.host in ("127.0.0.1", "localhost")


@app.get("/api/internal")
@rate_limit(limit=100, period=60, skip_when=is_local)
async def internal_endpoint(request):
    return JSONResponse({"internal": "data"})
```

##### Async Check

```python
async def has_premium_access(request):
    """Skip rate limiting for premium users."""
    api_key = request.headers.get("X-API-Key", "")
    # Check in DB or cache
    is_premium = await check_premium_status(api_key)
    return is_premium


@app.get("/api/premium")
@rate_limit(limit=100, period=60, skip_when=has_premium_access)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

---

### @rate_limit_batch Decorator

Decorator for applying **multiple limits simultaneously** to a single endpoint.

#### Syntax

```python
from altapi.ratelimit import rate_limit_batch


@app.get("/api/endpoint")
@rate_limit_batch(
    limits=[
        (10, 60),      # 10 requests per minute
        (100, 3600),   # 100 requests per hour
        (1000, 86400)  # 1000 requests per day
    ],
    key_func=None     # Function to get key
)
async def my_endpoint(request):
    ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limits` | `List[Tuple[int, float]]` | **Required** | List of (limit, period) tuples |
| `key_func` | `Callable` | `None` | Function to extract key |

#### How It Works

All limits are checked **simultaneously**. If **any** limit is exceeded, a 429 error is returned.

```
Request → Check limit 1 (10/min) → OK
        → Check limit 2 (100/hour) → OK
        → Check limit 3 (1000/day) → OK
        → Allow request
```

#### Examples

##### Standard API

```python
@app.get("/api/data")
@rate_limit_batch([
    (10, 60),      # 10 requests per minute
    (100, 3600),   # 100 requests per hour
    (1000, 86400)  # 1000 requests per day
])
async def get_data(request):
    return JSONResponse({"data": "value"})
```

##### Strict Authentication Limit

```python
@app.post("/api/login")
@rate_limit_batch([
    (5, 60),       # 5 attempts per minute
    (20, 3600),    # 20 attempts per hour
    (50, 86400)    # 50 attempts per day
])
async def login(request):
    data = await request.json()
    # Authentication logic
    return JSONResponse({"token": "..."})
```

##### Public API with Different Tiers

```python
@app.get("/api/public")
@rate_limit_batch([
    (30, 60),      # 30 requests per minute
    (500, 3600)    # 500 requests per hour
])
async def public_api(request):
    return JSONResponse({"public": "data"})
```

---

### How Rate Limiting Works

#### Architecture

AltAPI uses a **centralized shared manager** for rate limit data storage. This ensures operation in multi-worker mode without additional configuration.

```
┌─────────────────────────────────────────────────────────┐
│                  Shared Manager Process                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Rate Limit Store                   │    │
│  │              (in-memory)                        │    │
│  └─────────────────────────────────────────────────┘    │
│                    TCP: 127.0.0.1:58000                 │
└─────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
    ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐
    │  Worker 1   │      │  Worker 2   │      │  Worker 3   │
    │  (uvicorn)  │      │  (uvicorn)  │      │  (uvicorn)  │
    └─────────────┘      └─────────────┘      └─────────────┘
```

#### Automatic Startup

The manager starts **automatically** when calling `app.run()`:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # Manager started automatically!
```

When the application stops, the manager also shuts down gracefully.

#### Advantages

- **No configuration** — works out of the box
- **Multi-worker support** — all workers see shared state
- **Automatic reconnection** — on connection loss
- **Centralized storage** — data in one process

---

### Customization

#### Custom Key Functions

The key function determines how to identify the client. By default, the IP address is used.

##### By API Key

```python
def get_api_key(request):
    """Identification by X-API-Key header."""
    return request.headers.get("X-API-Key", "anonymous")


@app.get("/api/data")
@rate_limit(limit=100, period=60, key_func=get_api_key)
async def get_data(request):
    return JSONResponse({"data": "value"})
```

##### By User (from Token)

```python
async def get_user_id(request):
    """Identification by JWT token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "anonymous"

    token = auth_header[7:]
    # JWT decoding and user_id extraction here
    try:
        payload = decode_jwt(token)
        return f"user:{payload['sub']}"
    except Exception:
        return "anonymous"


@app.get("/api/user/profile")
@rate_limit(limit=50, period=60, key_func=get_user_id)
async def get_profile(request):
    return JSONResponse({"profile": "data"})
```

##### By Combined Parameters

```python
def get_combined_key(request):
    """Key based on IP and User-Agent."""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    return f"{ip}:{user_agent}"


@app.get("/api/browser")
@rate_limit(limit=100, period=60, key_func=get_combined_key)
async def browser_endpoint(request):
    return JSONResponse({"browser": "data"})
```

---

#### Custom Skip Conditions

The `skip_when` function determines when not to apply rate limiting.

##### Skip for Internal IPs

```python
def is_internal(request):
    """Skip for internal IPs."""
    internal_ips = ["10.", "172.16.", "172.17.", "192.168."]
    ip = request.client.host if request.client else ""
    return any(ip.startswith(prefix) for prefix in internal_ips)


@app.get("/api/internal")
@rate_limit(limit=10, period=60, skip_when=is_internal)
async def internal_endpoint(request):
    return JSONResponse({"internal": "data"})
```

##### Skip in Debug Mode

```python
import os

def is_debug_mode(request):
    """Skip in debug mode."""
    return os.getenv("DEBUG", "false").lower() == "true"


@app.get("/api/debug")
@rate_limit(limit=5, period=60, skip_when=is_debug_mode)
async def debug_endpoint(request):
    return JSONResponse({"debug": "data"})
```

##### Skip for Whitelist Keys

```python
WHITELIST_KEYS = {"premium-key-1", "premium-key-2", "admin-key"}

def is_whitelisted(request):
    """Skip for whitelist keys."""
    api_key = request.headers.get("X-API-Key", "")
    return api_key in WHITELIST_KEYS


@app.get("/api/premium")
@rate_limit(limit=100, period=60, skip_when=is_whitelisted)
async def premium_endpoint(request):
    return JSONResponse({"premium": "data"})
```

---

### HTTP Headers

AltAPI adds standard rate limiting headers to responses.

#### Headers in Successful Response

```
X-RateLimit-Limit: 10          # Maximum requests per period
X-RateLimit-Remaining: 7       # Requests remaining
X-RateLimit-Reset: 1711737600  # Reset time (Unix timestamp)
```

#### Headers When Limit Exceeded (429)

```
X-RateLimit-Limit: 10          # Maximum requests per period
X-RateLimit-Remaining: 0       # Requests remaining
X-RateLimit-Reset: 1711737600  # Reset time (Unix timestamp)
Retry-After: 45                # Seconds until reset
```

#### Example 429 Response

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711737600
Retry-After: 45

{
    "error": "Rate limit exceeded",
    "message": "Too many requests. Try again in 45 seconds."
}
```

#### Reading Headers on Client

```python
import requests

response = requests.get("http://localhost:8000/api/data")

# Check limits
limit = response.headers.get("X-RateLimit-Limit")
remaining = response.headers.get("X-RateLimit-Remaining")
reset = response.headers.get("X-RateLimit-Reset")

print(f"Limit: {limit}, Remaining: {remaining}, Reset: {reset}")

# Handle 429
if response.status_code == 429:
    retry_after = response.headers.get("Retry-After")
    print(f"Retry after {retry_after} seconds")
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
| `access_log` | `bool` | Enable request logging | `True` |

### Multi-Process Mode

To run the server with multiple worker processes:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=4)
```

**Note:** When using `workers > 1`, the application file must be run as a module (not in REPL or interactive mode).

### GC Optimizations

AltAPI applies GC optimizations automatically when the server starts:
- Forced garbage collection
- Object freezing
- Increased GC thresholds

These optimizations apply to all workers automatically.

### Using uvicorn Directly (Not Recommended)

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("myapp:app", host="0.0.0.0", port=8000)
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
    app.run(host="0.0.0.0", port=8000)
```

### Example: CRUD Application with SQLite

Full-featured web application with Dependency Injection:

```python
from altapi import AltAPI
from altapi.http import JSONResponse, RedirectResponse
from altapi.depends import Depends
import sqlite3

app = AltAPI(templates_directory="templates")

# Database dependency
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# List users (web page)
@app.get("/")
async def home(request, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

# API: List users
@app.get("/api/users")
async def api_list_users(db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    return JSONResponse({"users": [dict(row) for row in cursor.fetchall()]})

# API: Create user
@app.post("/api/users")
async def api_create_user(request, db=Depends(get_db)):
    data = await request.json()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (data["name"], data["email"])
    )
    db.commit()
    return JSONResponse({"id": cursor.lastrowid}, status_code=201)

# API: Delete user
@app.delete("/api/users/{id:int}")
async def api_delete_user(id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    db.commit()
    return JSONResponse({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

More examples available in `examples/` folder:
- `examples/webapp.py` — Full CRUD app with web UI and API
- `examples/sqlite_example.py` — SQLite + Dependency Injection
- `examples/app.py` — Feature demonstration

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
├── src/altapi/              # Main package
│   ├── __init__.py          # Package exports
│   ├── app.py               # AltAPI application class
│   ├── router.pyx           # Cython router implementation
│   ├── http/                # HTTP components
│   │   ├── request.py       # Request class
│   │   └── responses.py     # Response classes
│   ├── websocket/           # WebSocket support
│   │   └── ws.py            # WebSocket class
│   ├── middleware/          # Middleware system
│   │   └── middleware.py    # BaseMiddleware, Middleware
│   ├── templating/          # Jinja2 integration
│   │   └── templates.py     # Jinja2Templates, render_template
│   ├── caching/             # Caching system
│   │   └── cache.py         # CacheBackend, InMemoryCache, CacheMiddleware
│   ├── ratelimit/           # Rate limiting
│   │   └── limit.py         # rate_limit, rate_limit_batch
│   └── shared/              # Shared manager for multi-worker
├── examples/                # Example applications
├── test_app.py              # Integration tests
├── pyproject.toml           # Build configuration
├── setup.py                 # Legacy setup
└── DOCS.md                  # This documentation
```

### Building from Source

```bash
# Build wheel distribution
python -m build

# Build with Cython compilation
python setup.py build_ext --inplace
```

### License

AGPLv3 - See [LICENSE.txt](LICENSE.txt) for details.

---

## See Also

- [Middleware](#middleware) — for creating custom middleware
- [WebSocket Support](#websocket-support) — for WebSocket support
- [Template Rendering](#template-rendering) — for Jinja2 templates
