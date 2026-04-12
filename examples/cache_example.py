"""
Caching Example for AltAPI with Pydantic Integration.

Demonstrates caching with Pydantic response models for OpenAPI schema generation.

Usage:
    python examples/cache_example.py
"""

import asyncio
import time

from pydantic import BaseModel, Field
from typing import List

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache


# Pydantic models for response schemas
class WelcomeResponse(BaseModel):
    """Welcome response model."""
    message: str
    endpoints: List[str]


class ExpensiveOperationResponse(BaseModel):
    """Expensive operation response model."""
    message: str
    timestamp: float
    note: str
    id: int | None = None


class DataResponse(BaseModel):
    """Data response model."""
    data: List[int]
    timestamp: float


app = AltAPI(
    cache_timeout=300,  # 5 minutes by default
    title="AltAPI Caching Example",
    version="1.0.0",
    description="Caching example with Pydantic model integration",
)


@app.get(
    "/",
    response_model=WelcomeResponse,
    summary="Welcome",
    description="Welcome page with endpoint list",
    tags=["system"],
)
async def home(request):
    return JSONResponse(
        {
            "message": "Welcome to AltAPI Caching Example",
            "endpoints": [
                "/api/expensive - Expensive operation (cached for 5 minutes)",
                "/api/expensive/{id:int} - Expensive operation with ID",
                "/api/data - Data with 1 minute cache",
            ],
        }
    )


# Option 1: Using @cache decorator with response_model
@app.get(
    "/api/expensive",
    response_model=ExpensiveOperationResponse,
    summary="Expensive operation",
    description="Simulates an expensive operation with cached result",
    tags=["expensive"],
)
@cache(expires=300)  # Cache for 5 minutes
async def expensive_operation(request):
    """Expensive operation, result is cached."""
    print("called")
    await asyncio.sleep(2)  # Simulate long operation
    return JSONResponse(
        {
            "message": "Expensive operation completed",
            "timestamp": time.time(),
            "note": "First call takes 2 seconds, subsequent calls are instant (from cache)",
        }
    )


# Option 2: Using @cache decorator with path parameter
@app.get(
    "/api/expensive/{id:int}",
    response_model=ExpensiveOperationResponse,
    summary="Expensive operation by ID",
    description="Simulates an expensive operation with ID parameter and cached result",
    tags=["expensive"],
)
@cache(expires=300)  # Cache for 5 minutes
async def expensive_operation_by_id(request):
    """Expensive operation with ID parameter, result is cached."""
    print("called")
    await asyncio.sleep(2)  # Simulate long operation
    return JSONResponse(
        {
            "message": "Expensive operation completed",
            "timestamp": time.time(),
            "note": "First call takes 2 seconds, subsequent calls are instant (from cache)",
            "id": request.path_params["id"],
        }
    )


# Option 3: Using app.cache() with response_model
@app.cache(
    "/api/data",
    expires=60,  # Cache for 1 minute
    response_model=DataResponse,
    summary="Cached data",
    description="Data that updates once per minute",
    tags=["data"],
)
@app.get("/api/data")
async def get_data(request):
    """Data that updates once per minute."""
    return JSONResponse(
        {
            "data": [1, 2, 3, 4, 5],
            "timestamp": time.time(),
        }
    )


if __name__ == "__main__":
    print("AltAPI with caching:")
    print("  GET /api/expensive - 2 sec first time, then from cache")
    print("  GET /api/data      - Data with 1 minute caching")
    print("\nRun: curl http://localhost:8000/api/expensive\n")
    app.run(host="0.0.0.0", port=8000, workers=2)
