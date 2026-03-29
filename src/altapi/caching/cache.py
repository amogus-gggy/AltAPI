"""
Module for caching requests.
"""
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Union
from functools import wraps

from ..middleware.middleware import BaseMiddleware

# Import shared storage support
try:
    from ..shared import SharedCacheBackend, ManagerConnection
except ImportError:
    SharedCacheBackend = None  # type: ignore
    ManagerConnection = None  # type: ignore


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
    Simple in-memory caching backend.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize InMemoryCache.

        Args:
            max_size: Maximum number of entries in cache
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check lifetime
        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            # Expired
            await self.delete(key)
            return None

        return entry["value"]

    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Set a value in cache."""
        # Remove oldest entry if limit reached
        if len(self._cache) >= self._max_size and key not in self._cache:
            # Simple strategy: remove first found (can be improved to LRU)
            oldest_key = next(iter(self._cache))
            await self.delete(oldest_key)

        expires_at = None
        if expires is not None:
            expires_at = time.time() + expires

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
        }

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
        now = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if entry.get("expires_at") is not None and now > entry["expires_at"]
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
        print(f"[CacheMiddleware] Request: {scope.get('path')} method={scope.get('method')}")
        
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Check if handler is in the list of cached handlers
        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Cache only GET requests
        if method != "GET":
            print(f"[CacheMiddleware] Not a GET request, skipping cache")
            return await self.app(scope, receive, send)

        # Check exact path match
        expires = self._cached_handlers.get(path)
        print(f"[CacheMiddleware] Cached handlers: {self._cached_handlers}")
        print(f"[CacheMiddleware] Path {path} expires={expires}")

        # If no exact match, check patterns
        if expires is None:
            for handler_path, handler_expires in self._cached_handlers.items():
                if self._match_path(path, handler_path):
                    expires = handler_expires
                    print(f"[CacheMiddleware] Pattern match: {handler_path} -> {expires}")
                    break

        if expires is None:
            # Handler not registered for caching
            print(f"[CacheMiddleware] Not a cached handler, passing through")
            return await self.app(scope, receive, send)

        # Generate cache key
        query_string = scope.get("query_string", b"").decode()
        cache_key = f"http:{path}:{query_string}"
        print(f"[CacheMiddleware] Cache key: {cache_key}")

        # Try to get from cache
        print(f"[CacheMiddleware] Getting from cache...")
        cached_response = await self.backend.get(cache_key)
        print(f"[CacheMiddleware] Cache result: {cached_response is not None}")
        
        if cached_response is not None:
            # Send cached response
            print(f"[CacheMiddleware] Sending cached response!")
            await send({
                "type": "http.response.start",
                "status": cached_response["status"],
                "headers": cached_response["headers"],
            })
            await send({
                "type": "http.response.body",
                "body": cached_response["body"],
                "more_body": False,
            })
            return

        # Intercept response
        response_data = {
            "status": None,
            "headers": [],
            "body": b"",
        }
        print(f"[CacheMiddleware] Intercepting response...")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_data["status"] = message["status"]
                response_data["headers"] = message["headers"]
            elif message["type"] == "http.response.body":
                response_data["body"] = message.get("body", b"")
                # If this is the last block, save to cache
                if not message.get("more_body", False):
                    print(f"[CacheMiddleware] Saving to cache: {cache_key} expires={expires}")
                    await self.backend.set(cache_key, response_data, expires=expires)
            
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

        # Разбиваем на части
        path_parts = path.strip("/").split("/")
        pattern_parts = pattern.strip("/").split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for path_part, pattern_part in zip(path_parts, pattern_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                # Это параметр, пропускаем
                continue
            if path_part != pattern_part:
                return False

        return True
