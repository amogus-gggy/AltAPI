# AltAPI Project Context

## Project Overview

**AltAPI** is a simple and fast ASGI microframework for Python with WebSocket support. It's designed for building high-performance web APIs and applications with minimal overhead.

### Key Features

- ✅ ASGI compliant
- ✅ JSON, HTML, and text responses
- ✅ Typed path parameters (`{id:int}`, `{name:str}`, `{value:float}`)
- ✅ Sync and async handler support
- ✅ Full WebSocket support
- ✅ Built-in server (`app.run()`)
- ✅ Jinja2 templates
- ✅ Response caching with pluggable backends
- ✅ Static file mounting
- ✅ Optimized Cython router

### Tech Stack

- **Language:** Python >= 3.10
- **Core Dependencies:**
  - `uvicorn[standard] >= 0.30.0` - ASGI server
  - `anyio >= 4.0.0` - Async I/O
  - `jinja2 >= 3.0.0` - Template engine
  - `orjson` - Fast JSON serialization
  - `Cython >= 3.0.0` - Router optimization

### Project Structure

```
AltAPI/
├── src/altapi/              # Main package
│   ├── __init__.py          # Package exports with deprecation warnings
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
│   └── caching/             # Caching system
│       └── cache.py         # CacheBackend, InMemoryCache, CacheMiddleware
├── examples/                # Example applications
│   ├── app.py               # Full feature demo
│   ├── basic.py             # Basic example
│   └── cache_example.py     # Caching example
├── test_app.py              # Integration tests
├── pyproject.toml           # Build configuration
├── setup.py                 # Legacy setup
└── DOCS.md                  # Full documentation
```

## Building and Running

### Installation

```bash
# Install from PyPI
pip install altapi

# Install from source
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running the Application

```bash
# Via built-in server
python examples/app.py

# Via uvicorn
uvicorn examples.app:app --reload

# With multiple workers
uvicorn examples.app:app --workers 4
```

### Running Tests

```bash
# Start the server first (in background)
python examples/app.py &

# Run tests
python test_app.py
```

### Building from Source

```bash
# Build wheel distribution
python -m build

# Build with Cython compilation
python setup.py build_ext --inplace
```

## Development Conventions

### Code Style

- The project uses type hints throughout
- Docstrings follow Google style with Args/Returns sections
- All public APIs have docstrings
- Comments and docstrings are in English

### Testing Practices

- Integration tests in `test_app.py` use `requests` for HTTP and `websockets` for WebSocket
- Tests verify status codes, response bodies, and headers
- Server must be running on `http://127.0.0.1:8000` for tests

### Architecture

- **Router:** Cython-based router (`router.pyx`) for performance
- **Middleware:** ASGI-compatible middleware system
- **Response Classes:** Hierarchy with `_HeadersMixin` for header encoding optimization
- **Caching:** Pluggable backend system with `CacheBackend` ABC

### Key Design Patterns

1. **Pre-encoded headers:** Common media types have pre-encoded headers for performance
2. **Lazy evaluation:** Headers and body encoded only when needed
3. **Path parameter typing:** Automatic type conversion for `{param:type}` patterns
4. **Cache interception:** `CacheMiddleware` intercepts responses for caching

## API Quick Reference

### Creating an Application

```python
from altapi import AltAPI
from altapi.http import JSONResponse

app = AltAPI(
    middleware=[],
    templates_directory="templates",
    static_directory="static",  # Optional
    cache_backend=InMemoryCache(),  # Optional
    cache_timeout=300
)
```

### Route Decorators

```python
@app.get("/path")
@app.post("/path")
@app.put("/path")
@app.delete("/path")
@app.patch("/path")
@app.head("/path")
@app.options("/path")
@app.trace("/path")
@app.connect("/path")
@app.websocket("/ws/path")
@app.route("/path", methods=["GET", "POST"])
```

### Response Types

```python
from altapi.http import (
    JSONResponse,      # JSON response
    HTMLResponse,      # HTML response
    PlainTextResponse, # Plain text response
    StreamingResponse, # Streaming/chunked response
    FileResponse,      # File download with range support
    RedirectResponse,  # HTTP redirect
)
```

### Request Handling

```python
@app.get("/users/{id:int}")
async def get_user(request):
    # Path params (auto-converted)
    user_id = request.path_params["id"]
    
    # Query string
    query = request.query_string
    
    # Headers as dict
    headers = request.headers_dict
    
    # Body parsing
    data = await request.json()
    text = await request.text()
```

### WebSocket

```python
from altapi.websocket import WebSocket

@app.websocket("/ws/chat/{room:str}")
async def chat(ws: WebSocket):
    room = ws.path_params["room"]
    await ws.accept()
    
    # Send/receive
    await ws.send_text("Hello")
    text = await ws.receive_text()
    
    await ws.send_json({"key": "value"})
    data = await ws.receive_json()
    
    # Close
    await ws.close(code=1000, reason="OK")
```

### Caching

```python
from altapi.caching import cache, InMemoryCache

# Enable caching in app
app = AltAPI(cache_backend=InMemoryCache(), cache_timeout=300)

# Decorator usage
@app.get("/api/data")
@cache(expires=3600)
async def get_data(request):
    return JSONResponse({"data": "cached"})
```

### Templates

```python
from altapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Home"}
    )
```

### Middleware

```python
from altapi.middleware import BaseMiddleware, Middleware

class TimingMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        start = time.time()
        await self.app(scope, receive, send)
        print(f"Request took {time.time() - start:.4f}s")

app = AltAPI(middleware=[Middleware(TimingMiddleware)])
```

### Mounting

```python
# Mount static files
app.mount("/static", directory="static")

# Mount ASGI app
app.mount("/api", app=sub_app)
```

## License

AGPLv3 - See [LICENSE.txt](LICENSE.txt) for details.
