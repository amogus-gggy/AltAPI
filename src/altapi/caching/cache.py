"""
Module for caching requests.
"""
import time
import asyncio
from collections import OrderedDict
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Union, NamedTuple
from functools import wraps

from ..middleware.middleware import BaseMiddleware

# Import shared storage support
try:
    from ..shared import SharedCacheBackend, ManagerConnection
except ImportError:
    SharedCacheBackend = None  # type: ignore
    ManagerConnection = None  # type: ignore


# Optimized cache entry structure - uses __slots__ for memory efficiency
class CacheEntry(NamedTuple):
    """Immutable cache entry with minimal memory footprint."""
    status: int
    headers: list
    body: bytes
    expires_at: float


class CacheBackend(ABC):
    """
    Base abstract class for caching backends.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache by key.

        Args:
            key: Cache key

        Returns:
            Value or None if key not found or expired
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to store
            expires: Lifetime in seconds (None = no limit)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete a value from cache.

        Args:
            key: Cache key
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """
        Clear all cache.
        """
        pass


class InMemoryCache(CacheBackend):
    """
    Optimized in-memory caching backend with LRU eviction.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize InMemoryCache.

        Args:
            max_size: Maximum number of entries in cache
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get a value from cache."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check lifetime
        if time.monotonic() > entry.expires_at:
            # Expired
            await self.delete(key)
            return None

        # Move to end for LRU
        self._cache.move_to_end(key)
        return entry

    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Set a value in cache."""
        # If key exists, just update and move to end
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
            return

        # Remove oldest entries if limit reached (LRU eviction)
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        expires_at = 0.0 if expires is None else time.monotonic() + expires

        # Create optimized cache entry
        entry = CacheEntry(
            status=value["status"],
            headers=value["headers"],
            body=value["body"],
            expires_at=expires_at,
        )
        self._cache[key] = entry

    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()

    async def cleanup_expired(self) -> int:
        """
        Clean up expired entries.

        Returns:
            Number of deleted entries
        """
        now = time.monotonic()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.expires_at != 0.0 and now > entry.expires_at
        ]
        for key in expired_keys:
            await self.delete(key)
        return len(expired_keys)


class CacheManager:
    """
    Manager for managing caching backends.
    """

    _default_backend: Optional[CacheBackend] = None
    _backends: Dict[str, CacheBackend] = {}

    @classmethod
    def set_default_backend(cls, backend: CacheBackend) -> None:
        """
        Set the default backend.

        Args:
            backend: Backend instance
        """
        cls._default_backend = backend

    @classmethod
    def get_default_backend(cls) -> CacheBackend:
        """
        Get the default backend.

        Returns:
            Caching backend
        """
        if cls._default_backend is None:
            # Create InMemoryCache by default
            cls._default_backend = InMemoryCache()
        return cls._default_backend

    @classmethod
    def register_backend(cls, name: str, backend: CacheBackend) -> None:
        """
        Register a named backend.

        Args:
            name: Backend name
            backend: Backend instance
        """
        cls._backends[name] = backend

    @classmethod
    def get_backend(cls, name: Optional[str] = None) -> CacheBackend:
        """
        Get a backend by name or default.

        Args:
            name: Backend name (None = use default backend)

        Returns:
            Caching backend
        """
        if name is None:
            return cls.get_default_backend()
        if name not in cls._backends:
            raise ValueError(f"Backend '{name}' not found")
        return cls._backends[name]


def cache(
    expires: int = 300,
    key_prefix: str = "",
    backend: Optional[Union[str, CacheBackend]] = None,
):
    """
    Decorator for caching function results.

    Works with CacheMiddleware for HTTP responses.
    Registers the route for caching automatically.

    Args:
        expires: Cache lifetime in seconds
        key_prefix: Prefix for cache key
        backend: Backend for caching (string name or CacheBackend instance)

    Example:
        @cache(expires=3600)
        async def get_data(request):
            return JSONResponse({"data": "expensive computation"})
    """
    import inspect

    def decorator(func: Callable) -> Callable:
        # Mark function for caching - will be registered by app when route is added
        func._cache_expires = expires

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Just call the function - caching is handled by CacheMiddleware
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        # Preserve the _cache_expires attribute on wrapper for app.route() to detect
        wrapper._cache_expires = expires

        return wrapper

    return decorator


class CacheMiddleware(BaseMiddleware):
    """
    Middleware for automatic caching of HTTP requests.

    Example usage:
        app = AltAPI(middleware=[
            Middleware(CacheMiddleware, cache_timeout=300)
        ])

        @app.get("/api/data")
        @cache(expires=3600)
        async def get_data(request):
            return JSONResponse({"data": "expensive"})
    """

    def __init__(self, app, cache_timeout: int = 300, backend: Optional[CacheBackend] = None):
        """
        Initialize CacheMiddleware.

        Args:
            app: ASGI application
            cache_timeout: Default cache lifetime in seconds
            backend: Backend for caching (default: get from CacheManager)
        """
        super().__init__(app)
        self.cache_timeout = cache_timeout
        self._backend = backend
        self._cached_handlers: Dict[str, int] = {}  # path -> expires

    @property
    def backend(self) -> CacheBackend:
        """Get backend dynamically from CacheManager."""
        if self._backend is not None:
            return self._backend
        return CacheManager.get_default_backend()

    def register_handler(self, path: str, expires: int) -> None:
        """
        Register a handler for caching.

        Args:
            path: Handler path
            expires: Cache lifetime in seconds
        """
        self._cached_handlers[path] = expires

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Check if handler is in the list of cached handlers
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Cache only GET requests
        if method != "GET":
            return await self.app(scope, receive, send)

        # Check exact path match
        expires = self._cached_handlers.get(path)

        # If no exact match, check patterns
        if expires is None:
            for handler_path, handler_expires in self._cached_handlers.items():
                if self._match_path(path, handler_path):
                    expires = handler_expires
                    break

        if expires is None:
            # Handler not registered for caching
            return await self.app(scope, receive, send)

        # Generate cache key
        query_string = scope.get("query_string", b"").decode()
        cache_key = f"http:{path}:{query_string}"

        # Try to get from cache
        try:
            cached_result = await self.backend.get(cache_key)
        except Exception as e:
            import sys
            print(f"[CacheMiddleware] Error getting {cache_key} from cache: {e}", file=sys.stderr)
            cached_result = None

        if cached_result is not None:
            # Handle both CacheEntry (InMemoryCache) and dict (SharedCacheBackend) formats
            if isinstance(cached_result, CacheEntry):
                # InMemoryCache format
                await send({
                    "type": "http.response.start",
                    "status": cached_result.status,
                    "headers": cached_result.headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": cached_result.body,
                    "more_body": False,
                })
            else:
                # SharedCacheBackend format (dict)
                await send({
                    "type": "http.response.start",
                    "status": cached_result["status"],
                    "headers": cached_result["headers"],
                })
                await send({
                    "type": "http.response.body",
                    "body": cached_result["body"],
                    "more_body": False,
                })
            return

        # Intercept response
        response_data = {
            "status": None,
            "headers": [],
            "body": b"",
        }

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_data["status"] = message["status"]
                response_data["headers"] = message["headers"]
            elif message["type"] == "http.response.body":
                response_data["body"] = message.get("body", b"")
                # If this is the last block, save to cache
                if not message.get("more_body", False):
                    # Save in dict format for SharedCacheBackend compatibility
                    cache_value = {
                        "status": response_data["status"],
                        "headers": response_data["headers"],
                        "body": response_data["body"],
                    }
                    try:
                        await self.backend.set(cache_key, cache_value, expires=expires)
                    except Exception as e:
                        # Log error but don't fail the request
                        import sys
                        print(f"[CacheMiddleware] Error caching {cache_key}: {e}", file=sys.stderr)

            # Always send the message
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _match_path(self, path: str, pattern: str) -> bool:
        """
        Check if path matches pattern.

        Supports simple patterns with parameters:
        - /api/users/{id:int}
        - /api/items/{name:str}
        """
        if pattern == path:
            return True

        # Split into parts
        path_parts = path.strip("/").split("/")
        pattern_parts = pattern.strip("/").split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for path_part, pattern_part in zip(path_parts, pattern_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                # This is a parameter, skip it
                continue
            if path_part != pattern_part:
                return False

        return True
