"""
Shared manager process for cache and rate limiting.

Runs as a separate process and handles requests from worker processes
via TCP socket connection.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, Dict, Deque, Optional, Set

from .protocol import (
    Request, Response, create_response,
    MSG_PING, MSG_PONG, MSG_SHUTDOWN, MSG_ERROR,
    MSG_CACHE_GET, MSG_CACHE_SET, MSG_CACHE_DELETE, MSG_CACHE_CLEAR,
    MSG_RATELIMIT_CHECK, MSG_RATELIMIT_INCREMENT,
)


class SharedManager:
    """
    Central manager for shared cache and rate limiting.

    Runs in a separate process and handles all state storage.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 58000,
        max_cache_size: int = 10000,
        cleanup_interval: int = 60,
    ):
        """
        Initialize the shared manager.

        Args:
            host: Host to bind to
            port: Port to listen on
            max_cache_size: Maximum number of cache entries
            cleanup_interval: Interval for cleanup in seconds
        """
        self.host = host
        self.port = port
        self.max_cache_size = max_cache_size
        self.cleanup_interval = cleanup_interval

        # Cache storage: key -> {value, expires_at}
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Rate limit storage: key -> deque of timestamps
        self._ratelimits: Dict[str, Deque[float]] = defaultdict(deque)

        # Connected clients
        self._clients: Set[asyncio.StreamWriter] = set()

        # Shutdown flag
        self._shutdown = False

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        response: Response,
    ) -> None:
        """Send response to client."""
        try:
            writer.write(response.to_bytes())
            await writer.drain()
        except Exception:
            pass

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a client connection."""
        self._clients.add(writer)
        try:
            while not self._shutdown:
                # Read length prefix
                length_data = await asyncio.wait_for(reader.readexactly(4), timeout=60.0)
                if not length_data:
                    break

                length = int.from_bytes(length_data, 'big')
                if length > 10 * 1024 * 1024:  # 10MB max
                    break

                # Read message
                data = await asyncio.wait_for(reader.readexactly(length), timeout=30.0)
                if not data:
                    break

                request = Request.from_bytes(data)
                response = await self._process_request(request)
                await self._send_response(writer, response)

        except asyncio.TimeoutError:
            pass
        except asyncio.IncompleteReadError:
            pass
        except Exception:
            pass
        finally:
            self._clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_request(self, request: Request) -> Response:
        """Process a request and return response."""
        try:
            if request.type == MSG_PING:
                return create_response(request, {"status": "ok"})

            elif request.type == MSG_SHUTDOWN:
                self._shutdown = True
                return create_response(request, {"status": "shutting_down"})

            # Cache operations
            elif request.type == MSG_CACHE_GET:
                return await self._handle_cache_get(request)

            elif request.type == MSG_CACHE_SET:
                return await self._handle_cache_set(request)

            elif request.type == MSG_CACHE_DELETE:
                return await self._handle_cache_delete(request)

            elif request.type == MSG_CACHE_CLEAR:
                return await self._handle_cache_clear(request)

            # Rate limit operations
            elif request.type == MSG_RATELIMIT_CHECK:
                return await self._handle_ratelimit_check(request)

            elif request.type == MSG_RATELIMIT_INCREMENT:
                return await self._handle_ratelimit_increment(request)

            else:
                return create_response(
                    request,
                    {},
                    error=f"Unknown message type: {request.type}"
                )

        except Exception as e:
            return create_response(request, {}, error=str(e))

    async def _handle_cache_get(self, request: Request) -> Response:
        """Handle cache get operation."""
        key = request.data.get("key")
        if not key:
            return create_response(request, {}, error="Missing 'key'")

        entry = self._cache.get(key)
        if entry is None:
            return create_response(request, {"found": False, "value": None})

        # Check expiration
        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            # Expired
            del self._cache[key]
            return create_response(request, {"found": False, "value": None})

        return create_response(request, {"found": True, "value": entry["value"]})

    async def _handle_cache_set(self, request: Request) -> Response:
        """Handle cache set operation."""
        key = request.data.get("key")
        value = request.data.get("value")
        expires = request.data.get("expires")  # in seconds

        if not key:
            return create_response(request, {}, error="Missing 'key'")

        # Remove oldest entry if at capacity
        if len(self._cache) >= self.max_cache_size and key not in self._cache:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        expires_at = None
        if expires is not None:
            expires_at = time.time() + expires

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
        }

        return create_response(request, {"ok": True})

    async def _handle_cache_delete(self, request: Request) -> Response:
        """Handle cache delete operation."""
        key = request.data.get("key")
        if not key:
            return create_response(request, {}, error="Missing 'key'")

        self._cache.pop(key, None)
        return create_response(request, {"ok": True})

    async def _handle_cache_clear(self, request: Request) -> Response:
        """Handle cache clear operation."""
        self._cache.clear()
        return create_response(request, {"ok": True})

    async def _handle_ratelimit_check(self, request: Request) -> Response:
        """Handle rate limit check operation."""
        key = request.data.get("key")
        limit = request.data.get("limit", 10)
        period = request.data.get("period", 60)

        if not key:
            return create_response(request, {}, error="Missing 'key'")

        now = time.time()
        window_start = now - period

        timestamps = self._ratelimits[key]

        # Remove old timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        count = len(timestamps)
        remaining = max(0, limit - count)
        allowed = count < limit

        # Calculate reset time
        if timestamps:
            reset_time = timestamps[0] + period
        else:
            reset_time = now + period

        return create_response(
            request,
            {
                "allowed": allowed,
                "remaining": remaining,
                "limit": limit,
                "reset": reset_time,
            }
        )

    async def _handle_ratelimit_increment(self, request: Request) -> Response:
        """Handle rate limit increment operation."""
        key = request.data.get("key")
        period = request.data.get("period", 60)

        if not key:
            return create_response(request, {}, error="Missing 'key'")

        now = time.time()
        window_start = now - period

        timestamps = self._ratelimits[key]

        # Remove old timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        # Add current timestamp
        timestamps.append(now)

        count = len(timestamps)

        # Calculate reset time
        if timestamps:
            reset_time = timestamps[0] + period
        else:
            reset_time = now + period

        return create_response(
            request,
            {
                "count": count,
                "reset": reset_time,
            }
        )

    async def _cleanup_expired(self) -> None:
        """Periodic cleanup of expired entries."""
        while not self._shutdown:
            await asyncio.sleep(self.cleanup_interval)
            try:
                now = time.time()

                # Clean expired cache entries
                expired_keys = [
                    key for key, entry in self._cache.items()
                    if entry.get("expires_at") is not None and now > entry["expires_at"]
                ]
                for key in expired_keys:
                    del self._cache[key]

                # Clean empty rate limit deques
                empty_keys = [
                    key for key, timestamps in self._ratelimits.items()
                    if not timestamps
                ]
                for key in empty_keys:
                    del self._ratelimits[key]

            except Exception:
                pass

    async def run(self) -> None:
        """Run the manager server."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )

        addr = server.sockets[0].getsockname()

        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_expired())

        async with server:
            await server.serve_forever()

        await cleanup_task


def run_manager(
    host: str = "127.0.0.1",
    port: int = 58000,
    max_cache_size: int = 10000,
    cleanup_interval: int = 60,
) -> None:
    """
    Run the shared manager as a standalone process.

    Args:
        host: Host to bind to
        port: Port to listen on
        max_cache_size: Maximum number of cache entries
        cleanup_interval: Interval for cleanup in seconds
    """
    manager = SharedManager(
        host=host,
        port=port,
        max_cache_size=max_cache_size,
        cleanup_interval=cleanup_interval,
    )
    asyncio.run(manager.run())
