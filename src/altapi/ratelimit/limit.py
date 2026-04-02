"""
Rate limiting module with decorator support.

Provides rate limiting functionality using shared memory for multi-process support.
No network overhead - uses multiprocessing.shared_memory for IPC.
"""

import asyncio
import time
import warnings
from functools import wraps
from typing import Callable, Optional, Tuple, Union

from ..http.responses import JSONResponse
from .storage import (
    BaseRateLimitStorage,
    InMemoryRateLimitStorage,
    SharedMemoryRateLimitStorage,
    RateLimitResult,
)


# Global storage instance (lazy initialized)
_storage: Optional[BaseRateLimitStorage] = None
_use_shared_memory = True  # Use shared memory for multi-process support


def _get_storage() -> BaseRateLimitStorage:
    """Get or create rate limit storage instance."""
    global _storage

    if _storage is None:
        if _use_shared_memory:
            _storage = SharedMemoryRateLimitStorage()
        else:
            _storage = InMemoryRateLimitStorage()

    return _storage


def set_storage(storage: BaseRateLimitStorage) -> None:
    """Set custom rate limit storage."""
    global _storage
    _storage = storage


def use_shared_memory(enabled: bool = True) -> None:
    """
    Enable or disable shared memory mode.

    Args:
        enabled: True to use shared memory (multi-process),
                 False for in-memory (single-process)
    """
    global _use_shared_memory, _storage
    _use_shared_memory = enabled
    _storage = None  # Reset to apply on next use


def rate_limit(
    limit: int = 10,
    period: float = 60,
    key_func: Optional[Callable] = None,
    skip_when: Optional[Callable] = None,
):
    """
    Decorator for rate limiting endpoints.

    Uses shared memory by default for multi-process support.

    ⚠️ WARNING: Rate limiting adds overhead and can significantly slow down endpoints.

    Args:
        limit: Maximum number of requests allowed in the period
        period: Time period in seconds
        key_func: Function to extract rate limit key from request.
                  Default: uses client IP address.
        skip_when: Function to determine if rate limiting should be skipped.

    Returns:
        Decorator function

    Example:
        @app.get("/api/data")
        @rate_limit(limit=10, period=60)  # 10 requests per minute
        async def get_data(request):
            return JSONResponse({"data": "value"})
    """
    storage = _get_storage()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Check if should skip
            if skip_when is not None:
                result = skip_when(request)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    return await func(request, *args, **kwargs) if asyncio.iscoroutinefunction(func) else func(request, *args, **kwargs)

            # Get rate limit key
            if key_func is not None:
                key = key_func(request)
                if asyncio.iscoroutine(key):
                    key = await key
            else:
                # Default: use client IP from scope
                client = request.scope.get("client")
                key = client[0] if client else "unknown"

            # Add function name to key for uniqueness
            key = f"{func.__module__}:{func.__name__}:{key}"

            # Check rate limit
            result = await storage.check_rate_limit(key, limit, period)

            if not result.allowed:
                # Rate limit exceeded
                response = JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again in {int(result.reset - time.time())} seconds.",
                    },
                    status_code=429,
                )
                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(result.limit)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(result.reset))
                response.headers["Retry-After"] = str(int(result.reset - time.time()))
                return response

            # Increment counter
            await storage.increment(key, period)

            # Call handler
            if asyncio.iscoroutinefunction(func):
                response = await func(request, *args, **kwargs)
            else:
                response = func(request, *args, **kwargs)
                if hasattr(response, "__await__"):
                    response = await response

            # Add rate limit headers to response
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(result.limit)
                response.headers["X-RateLimit-Remaining"] = str(result.remaining - 1)
                response.headers["X-RateLimit-Reset"] = str(int(result.reset))

            return response

        return wrapper

    return decorator


def rate_limit_batch(
    limits: list,
    key_func: Optional[Callable] = None,
):
    """
    Decorator for multiple rate limits on the same endpoint.

    Uses shared memory by default.

    ⚠️ WARNING: Rate limiting adds overhead and can significantly slow down endpoints.

    Args:
        limits: List of (limit, period) tuples
        key_func: Function to extract rate limit key

    Example:
        @rate_limit_batch([
            (10, 60),    # 10 per minute
            (100, 3600), # 100 per hour
            (1000, 86400) # 1000 per day
        ])
        async def my_endpoint(request):
            ...
    """
    storage = _get_storage()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Get rate limit key
            if key_func is not None:
                key = key_func(request)
                if asyncio.iscoroutine(key):
                    key = await key
            else:
                # Default: use client IP from scope
                client = request.scope.get("client")
                key = client[0] if client else "unknown"

            key = f"{func.__module__}:{func.__name__}:{key}"

            # Check all limits
            min_remaining = float('inf')
            min_reset = float('inf')
            exceeded_limit = None
            exceeded_reset = None

            for limit, period in limits:
                result = await storage.check_rate_limit(key, limit, period)

                if not result.allowed:
                    exceeded_limit = limit
                    exceeded_reset = result.reset
                    break

                min_remaining = min(min_remaining, result.remaining)
                min_reset = min(min_reset, result.reset)

            if exceeded_limit is not None:
                response = JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again in {int(exceeded_reset - time.time())} seconds.",
                    },
                    status_code=429,
                )
                response.headers["X-RateLimit-Limit"] = str(exceeded_limit)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(exceeded_reset))
                response.headers["Retry-After"] = str(int(exceeded_reset - time.time()))
                return response

            # Increment all counters
            for limit, period in limits:
                await storage.increment(key, period)

            # Call handler
            if asyncio.iscoroutinefunction(func):
                response = await func(request, *args, **kwargs)
            else:
                response = func(request, *args, **kwargs)
                if hasattr(response, "__await__"):
                    response = await response

            # Add headers
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(limits[0][0])
                response.headers["X-RateLimit-Remaining"] = str(int(min_remaining - 1))
                response.headers["X-RateLimit-Reset"] = str(int(min_reset))

            return response

        return wrapper

    return decorator


__all__ = [
    "rate_limit",
    "rate_limit_batch",
    "BaseRateLimitStorage",
    "InMemoryRateLimitStorage",
    "SharedMemoryRateLimitStorage",
    "RateLimitResult",
    "set_storage",
    "use_shared_memory",
]
