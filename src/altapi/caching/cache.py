"""
Module for caching requests.
Optimized for high-performance JSON response caching.

Uses per-worker InMemoryCache for zero IPC overhead.
For shared caching across workers, use a reverse proxy cache (e.g., Varnish).
"""
import time
import asyncio
from collections import OrderedDict
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Union, List, Tuple, TYPE_CHECKING
from functools import wraps

if TYPE_CHECKING:
    from ..middleware.middleware import BaseMiddleware


class CacheEntry:
    """
    Ultra-lightweight cache entry with __slots__.
    Headers stored as list of tuples for ASGI compatibility.
    """
    __slots__ = ('status', 'headers', 'body', 'expires_at')

    def __init__(self, status: int, headers: Any, body: bytes, expires_at: float):
        self.status = status
        # Convert headers to list of tuples for ASGI compatibility
        if isinstance(headers, (list, tuple)):
            self.headers = [
                tuple(h) if isinstance(h, (list, tuple)) else h
                for h in headers
            ]
        else:
            self.headers = headers
        self.body = body
        self.expires_at = expires_at


class CacheBackend(ABC):
    """Base abstract class for caching backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache."""
        pass


class InMemoryCache(CacheBackend):
    """
    Ultra-fast in-memory caching backend with LRU eviction.
    No locks - asyncio is single-threaded.
    """

    __slots__ = ('_cache', '_max_size')

    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value - optimized hot path."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        now = time.monotonic()
        if now > entry.expires_at:
            self._cache.pop(key, None)
            return None

        # LRU touch
        self._cache.move_to_end(key)
        return entry

    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Set value - optimized for speed."""
        cache = self._cache

        # Fast path: if value is already CacheEntry, just store it
        if isinstance(value, CacheEntry):
            if key in cache:
                cache.move_to_end(key)
            else:
                # LRU eviction
                while len(cache) >= self._max_size:
                    cache.popitem(last=False)
            cache[key] = value
            return

        # Update existing entry
        if key in cache:
            cache.move_to_end(key)
            cache[key] = value
            return

        # LRU eviction
        while len(cache) >= self._max_size:
            cache.popitem(last=False)

        expires_at = 0.0 if expires is None else time.monotonic() + expires

        # Inline entry creation
        cache[key] = CacheEntry(
            status=value["status"],
            headers=value["headers"],
            body=value["body"],
            expires_at=expires_at,
        )

    async def delete(self, key: str) -> None:
        """Delete value."""
        self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        now = time.monotonic()
        expired = [
            k for k, e in self._cache.items()
            if e.expires_at != 0.0 and now > e.expires_at
        ]
        for k in expired:
            self._cache.pop(k, None)
        return len(expired)


class CacheManager:
    """Manager for caching backends."""

    _default_backend: Optional[CacheBackend] = None
    _backends: Dict[str, CacheBackend] = {}

    @classmethod
    def set_default_backend(cls, backend: CacheBackend) -> None:
        cls._default_backend = backend

    @classmethod
    def get_default_backend(cls) -> CacheBackend:
        if cls._default_backend is None:
            cls._default_backend = InMemoryCache()
        return cls._default_backend

    @classmethod
    def register_backend(cls, name: str, backend: CacheBackend) -> None:
        cls._backends[name] = backend

    @classmethod
    def get_backend(cls, name: Optional[str] = None) -> CacheBackend:
        if name is None:
            return cls.get_default_backend()
        if name not in cls._backends:
            raise ValueError(f"Backend '{name}' not found")
        return cls._backends[name]


def cache(
    expires: int = 300,
    key_prefix: str = "",
    backend: Optional[Union[str, CacheBackend]] = None,
    key_func: Optional[Callable] = None,
):
    """
    High-performance caching decorator for async handlers.

    Works with CacheMiddleware to cache HTTP responses.
    The decorator marks the route for caching, and CacheMiddleware handles the actual caching.

    Args:
        expires: Cache lifetime in seconds
        key_prefix: Prefix for cache key
        backend: Backend instance or name (default: global default)
        key_func: Custom function to generate cache key from (request, *args, **kwargs)

    Example:
        @cache(expires=3600)
        async def get_data(request):
            return JSONResponse({"data": "expensive"})
    """
    def decorator(func: Callable) -> Callable:
        # Store metadata for app.route() to detect
        func._cache_expires = expires
        func._cache_key_prefix = key_prefix
        func._cache_backend = backend

        # Pre-compute at decorator time (performance optimization)
        is_async = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Just call the handler - caching is handled by CacheMiddleware
            if is_async:
                return await func(request, *args, **kwargs)
            return func(request, *args, **kwargs)

        # Preserve metadata
        wrapper._cache_expires = expires
        wrapper._cache_key_prefix = key_prefix
        wrapper._cache_backend = backend

        return wrapper

    return decorator


class CacheMiddleware:
    """
    ASGI middleware for automatic request caching.
    
    Only use this if you need middleware-based caching.
    For better performance, use @cache decorator directly.
    
    Example:
        app = AltAPI(middleware=[
            Middleware(CacheMiddleware, cache_timeout=300)
        ])
    """

    __slots__ = ('app', 'cache_timeout', '_backend', '_cached_handlers', '_backend_ref')

    def __init__(self, app, cache_timeout: int = 300, backend: Optional[CacheBackend] = None):
        self.app = app
        self.cache_timeout = cache_timeout
        self._backend = backend
        self._cached_handlers: Dict[str, int] = {}
        self._backend_ref: Optional[CacheBackend] = None

    @property
    def backend(self) -> CacheBackend:
        if self._backend is not None:
            return self._backend
        if self._backend_ref is None:
            self._backend_ref = CacheManager.get_default_backend()
        return self._backend_ref

    def register_handler(self, path: str, expires: int) -> None:
        """Register handler for caching."""
        self._cached_handlers[path] = expires

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        method = scope["method"]

        # Only cache GET requests
        if method != "GET":
            return await self.app(scope, receive, send)

        # Fast path: check exact match in cached_handlers (most common case)
        cached_handlers = self._cached_handlers
        expires = cached_handlers.get(path)

        if expires is None:
            # Not cached - FAST PASSTHROUGH (no dict iteration, no pattern matching)
            return await self.app(scope, receive, send)

        # Generate cache key (only for cached routes)
        query_string = scope.get("query_string", b"")
        cache_key = f"http:{path}:{query_string.decode()}" if query_string else f"http:{path}:"

        # Try cache
        backend = self.backend
        try:
            cached_result = await backend.get(cache_key)
        except Exception as e:
            import sys
            print(f"[CacheMiddleware] Cache get error: {e}", file=sys.stderr)
            cached_result = None

        if cached_result is not None:
            # Cache hit - send directly (CacheEntry only)
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
            return

        # Cache miss - intercept response
        response_status = 0
        response_headers: Optional[List[tuple]] = None
        response_body = b""
        message_count = [0]  # Use list for mutability in closure

        async def send_wrapper(message):
            nonlocal response_status, response_headers, response_body
            msg_type = message["type"]
            message_count[0] += 1

            if msg_type == "http.response.start":
                response_status = message["status"]
                # Copy headers to avoid mutation
                response_headers = list(message["headers"])
            elif msg_type == "http.response.body":
                body = message.get("body", b"")
                response_body += body  # Accumulate body for multi-part responses
                more_body = message.get("more_body", False)
                if not more_body:
                    # Create CacheEntry directly for performance
                    if response_headers is not None:
                        cache_entry = CacheEntry(
                            status=response_status,
                            headers=response_headers,
                            body=response_body,
                            expires_at=time.monotonic() + expires,
                        )
                        try:
                            await backend.set(cache_key, cache_entry, expires=None)
                        except Exception as e:
                            import sys
                            print(f"[CacheMiddleware] Cache set error: {e}", file=sys.stderr)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _match_path(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern with parameter support."""
        if pattern == path:
            return True

        # Fast path stripping
        if pattern and pattern[0] == '/':
            pattern = pattern[1:]
        if path and path[0] == '/':
            path = path[1:]

        path_parts = path.split("/")
        pattern_parts = pattern.split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for pp, patp in zip(path_parts, pattern_parts):
            if patp and patp[0] == '{':
                continue
            if pp != patp:
                return False

        return True
