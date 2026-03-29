"""
Rate limiting module with decorator support.

Provides rate limiting functionality similar to SlowAPI with @rate_limit decorator.
Uses shared storage by default for multi-worker support.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Deque, Dict, List, Optional, Tuple, Union

from ..http.responses import JSONResponse
from ..shared import ManagerConnection, SharedRateLimitStorage


# Global shared storage instance (lazy initialized)
_shared_storage: Optional[SharedRateLimitStorage] = None
_manager_connection: Optional[ManagerConnection] = None


def _get_shared_storage() -> SharedRateLimitStorage:
    """Get or create shared storage instance."""
    global _shared_storage, _manager_connection
    
    if _shared_storage is None:
        _manager_connection = ManagerConnection()
        _shared_storage = SharedRateLimitStorage(_manager_connection)
    
    return _shared_storage


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    limit: int
    reset: float


class BaseRateLimitStorage(ABC):
    """Abstract base class for rate limit storage."""

    @abstractmethod
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """
        Check rate limit for a key.

        Args:
            key: Unique identifier (e.g., IP address)
            limit: Maximum requests allowed
            period: Time period in seconds

        Returns:
            RateLimitResult with allowed status and metadata
        """
        pass

    @abstractmethod
    async def increment(self, key: str, period: float) -> int:
        """
        Increment request count for a key.

        Args:
            key: Unique identifier
            period: Time period in seconds

        Returns:
            Current request count
        """
        pass


def rate_limit(
    limit: int = 10,
    period: float = 60,
    key_func: Optional[Callable] = None,
    skip_when: Optional[Callable] = None,
):
    """
    Decorator for rate limiting endpoints.

    Uses shared storage by default for multi-worker support.

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
    storage = _get_shared_storage()

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
            
            # Handle both tuple and RateLimitResult
            if isinstance(result, tuple):
                allowed, remaining, reset = result
                limit_val = limit
            else:
                allowed = result.allowed
                remaining = result.remaining
                reset = result.reset
                limit_val = result.limit

            if not allowed:
                # Rate limit exceeded
                response = JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again in {int(reset - time.time())} seconds.",
                    },
                    status_code=429,
                )
                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(limit_val)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(reset))
                response.headers["Retry-After"] = str(int(reset - time.time()))
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
                response.headers["X-RateLimit-Limit"] = str(limit_val)
                response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
                response.headers["X-RateLimit-Reset"] = str(int(reset))

            return response

        return wrapper

    return decorator


def rate_limit_batch(
    limits: List[Tuple[int, float]],
    key_func: Optional[Callable] = None,
):
    """
    Decorator for multiple rate limits on the same endpoint.

    Uses shared storage by default.

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
    storage = _get_shared_storage()

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
                
                # Handle both tuple and RateLimitResult
                if isinstance(result, tuple):
                    allowed, remaining, reset = result
                else:
                    allowed = result.allowed
                    remaining = result.remaining
                    reset = result.reset
                
                if not allowed:
                    exceeded_limit = limit
                    exceeded_reset = reset
                    break

                min_remaining = min(min_remaining, remaining)
                min_reset = min(min_reset, reset)

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


# Import for shared storage support
try:
    from ..shared import SharedRateLimitStorage, ManagerConnection
except ImportError:
    SharedRateLimitStorage = None  # type: ignore
    ManagerConnection = None  # type: ignore

__all__ = [
    "rate_limit",
    "rate_limit_batch",
    "BaseRateLimitStorage",
    "InMemoryRateLimitStorage",
    "RateLimitResult",
    "SharedRateLimitStorage",
    "ManagerConnection",
]
