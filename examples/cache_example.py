"""
Caching Example for AltAPI.

Caching works by default via shared manager.
Use @cache decorator or app.cache() for caching.

Usage:
    python examples/cache_example.py
"""

import asyncio
import time

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

app = AltAPI(cache_timeout=300)  # 5 minutes by default


@app.get("/")
async def home(request):
    return JSONResponse({
        "message": "Welcome to AltAPI Caching Example",
        "endpoints": [
            "/api/expensive - Expensive operation (cached for 5 minutes)",
            "/api/data - Data with different cache times",
        ]
    })


# Option 1: Using @cache decorator
@app.get("/api/expensive")
@cache(expires=300)  # Cache for 5 minutes
async def expensive_operation(request):
    """Expensive operation, result is cached."""
    print("called")
    await asyncio.sleep(2)  # Simulate long operation
    return JSONResponse({
        "message": "Expensive operation completed",
        "timestamp": time.time(),
        "note": "First call takes 2 seconds, subsequent calls are instant (from cache)"
    })

# Option 1: Using @cache decorator
@app.get("/api/expensive/{id:int}")
@cache(expires=300)  # Cache for 5 minutes
async def expensive_operation_by_id(request):
    """Expensive operation with ID parameter, result is cached."""
    print("called")
    await asyncio.sleep(2)  # Simulate long operation
    return JSONResponse({
        "message": "Expensive operation completed",
        "timestamp": time.time(),
        "note": "First call takes 2 seconds, subsequent calls are instant (from cache)",
        "id": request.path_params["id"]
    })


# Option 2: Using app.cache()
@app.cache("/api/data", expires=60)  # Cache for 1 minute
@app.get("/api/data")
async def get_data(request):
    """Data that updates once per minute."""
    return JSONResponse({
        "data": [1, 2, 3, 4, 5],
        "timestamp": time.time(),
    })


if __name__ == "__main__":
    print("AltAPI with caching:")
    print("  GET /api/expensive - 2 sec first time, then from cache")
    print("  GET /api/data      - Data with 1 minute caching")
    print("\nRun: curl http://localhost:8000/api/expensive\n")
    app.run(host="0.0.0.0", port=8000, workers=2)
