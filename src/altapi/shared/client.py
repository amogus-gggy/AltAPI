"""
Async client for connecting to the shared manager.

Provides connection pooling and automatic reconnection.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

from .protocol import (
    Request, Response, create_request,
    MSG_PING, MSG_CACHE_GET, MSG_CACHE_SET, MSG_CACHE_DELETE, MSG_CACHE_CLEAR,
    MSG_RATELIMIT_CHECK, MSG_RATELIMIT_INCREMENT,
)


class ManagerConnection:
    """
    Async connection to the shared manager.

    Handles connection, reconnection, and request/response handling.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 58000,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 10,
        request_timeout: float = 5.0,
    ):
        """
        Initialize the manager connection.

        Args:
            host: Manager host
            port: Manager port
            reconnect_delay: Delay between reconnection attempts
            max_reconnect_attempts: Maximum reconnection attempts
            request_timeout: Timeout for requests in seconds
        """
        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.request_timeout = request_timeout

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """
        Establish connection to the manager.

        Returns:
            True if connected, False otherwise
        """
        if self._connected:
            return True

        attempts = 0
        while attempts < self.max_reconnect_attempts:
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port
                )
                self._connected = True
                return True
            except (ConnectionError, OSError) as e:
                attempts += 1
                if attempts >= self.max_reconnect_attempts:
                    self._connected = False
                    return False
                await asyncio.sleep(self.reconnect_delay)

        self._connected = False
        return False

    async def disconnect(self) -> None:
        """Close connection to the manager."""
        self._connected = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    async def _ensure_connected(self) -> bool:
        """Ensure connection is established."""
        if not self._connected:
            return await self.connect()
        return True

    async def _send_request(self, request: Request) -> Optional[Response]:
        """Send request and receive response."""
        if not self._writer or not self._reader:
            return None

        try:
            # Send request
            self._writer.write(request.to_bytes())
            await self._writer.drain()

            # Read response
            length_data = await asyncio.wait_for(
                self._reader.readexactly(4),
                timeout=self.request_timeout
            )
            length = int.from_bytes(length_data, 'big')

            data = await asyncio.wait_for(
                self._reader.readexactly(length),
                timeout=self.request_timeout
            )

            return Response.from_bytes(data)

        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            self._connected = False
            return None

    async def request(self, msg_type: str, **data) -> Optional[Dict[str, Any]]:
        """
        Send a request and return response data.

        Args:
            msg_type: Message type
            **data: Request data

        Returns:
            Response data dict or None on error
        """
        async with self._lock:
            if not await self._ensure_connected():
                return None

            request = create_request(msg_type, **data)
            response = await self._send_request(request)

            if response is None:
                # Try reconnect once
                self._connected = False
                if await self._ensure_connected():
                    request = create_request(msg_type, **data)
                    response = await self._send_request(request)

            if response is None:
                return None

            if response.error:
                raise RuntimeError(response.error)

            return response.data

    async def ping(self) -> bool:
        """Check if manager is responsive."""
        try:
            result = await self.request(MSG_PING)
            return result is not None
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        """Check if connected to manager."""
        return self._connected


class SharedCacheBackend:
    """
    Cache backend that uses the shared manager.

    Can be used as a drop-in replacement for InMemoryCache.
    """

    def __init__(self, connection: ManagerConnection):
        """
        Initialize shared cache backend.

        Args:
            connection: Manager connection
        """
        self._connection = connection

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        result = await self._connection.request(MSG_CACHE_GET, key=key)
        if result is None:
            return None
        if result.get("found"):
            value = result.get("value")
            # Decode bytes from base64
            def decode_bytes(obj):
                if isinstance(obj, dict):
                    if "__bytes__" in obj:
                        import base64
                        return base64.b64decode(obj["__bytes__"])
                    return {k: decode_bytes(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [decode_bytes(item) for item in obj]
                return obj
            return decode_bytes(value)
        return None

    async def set(self, key: str, value: Any, expires: Optional[int] = None) -> None:
        """Set value in cache."""
        import base64
        
        # Encode bytes in value to base64 for JSON serialization
        def encode_bytes(obj):
            if isinstance(obj, bytes):
                return {"__bytes__": base64.b64encode(obj).decode('ascii')}
            elif isinstance(obj, dict):
                return {k: encode_bytes(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [encode_bytes(item) for item in obj]
            return obj
        
        encoded_value = encode_bytes(value)

        await self._connection.request(
            MSG_CACHE_SET,
            key=key,
            value=encoded_value,
            expires=expires
        )

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        await self._connection.request(MSG_CACHE_DELETE, key=key)

    async def clear(self) -> None:
        """Clear all cache."""
        await self._connection.request(MSG_CACHE_CLEAR)


class SharedRateLimitStorage:
    """
    Rate limit storage that uses the shared manager.

    Can be used as a drop-in replacement for InMemoryStorage.
    """

    def __init__(self, connection: ManagerConnection):
        """
        Initialize shared rate limit storage.

        Args:
            connection: Manager connection
        """
        self._connection = connection

    async def get_request_count(self, key: str, period: float) -> int:
        """Get request count for key within period."""
        limit = 1000000  # Large number to just get count
        result = await self._connection.request(
            MSG_RATELIMIT_CHECK,
            key=key,
            limit=limit,
            period=period
        )
        if result is None:
            return 0
        # Count = limit - remaining
        return limit - result.get("remaining", 0)

    async def increment(self, key: str, period: float) -> int:
        """Increment request count and return current count."""
        result = await self._connection.request(
            MSG_RATELIMIT_INCREMENT,
            key=key,
            period=period
        )
        if result is None:
            return 0
        return result.get("count", 0)

    async def get_reset_time(self, key: str, period: float) -> float:
        """Get the time when the rate limit resets."""
        result = await self._connection.request(
            MSG_RATELIMIT_CHECK,
            key=key,
            limit=1,
            period=period
        )
        if result is None:
            return time.time() + period
        return result.get("reset", time.time() + period)

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> Tuple[bool, int, float]:
        """
        Check rate limit and return (allowed, remaining, reset_time).

        Args:
            key: Unique identifier
            limit: Maximum requests allowed
            period: Time period in seconds

        Returns:
            Tuple of (allowed, remaining, reset_time)
        """
        result = await self._connection.request(
            MSG_RATELIMIT_CHECK,
            key=key,
            limit=limit,
            period=period
        )
        if result is None:
            # On error, allow request
            return True, limit, time.time() + period

        return (
            result.get("allowed", True),
            result.get("remaining", limit),
            result.get("reset", time.time() + period),
        )
