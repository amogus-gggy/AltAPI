"""
Rate limit storage using multiprocessing.shared_memory.

Provides fast, process-safe rate limiting without network overhead.
"""

import multiprocessing.shared_memory as shm
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


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
        pass

    @abstractmethod
    async def increment(self, key: str, period: float) -> int:
        pass

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """
        Atomic check + increment in one operation.
        Override for optimized implementations.
        """
        result = await self.check_rate_limit(key, limit, period)
        if result.allowed:
            await self.increment(key, period)
            # Recalculate remaining after increment
            result = RateLimitResult(
                allowed=result.allowed,
                remaining=max(0, result.remaining - 1),
                limit=result.limit,
                reset=result.reset,
            )
        return result


class InMemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Ultra-fast in-memory rate limiting using sliding window counter.
    O(1) per request - no loops, no arrays, no timestamp storage.
    """

    __slots__ = ('_counters',)

    def __init__(self):
        # key -> [count, window_start]
        self._counters: Dict[str, list] = {}

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        now = time.time()
        counters = self._counters

        entry = counters.get(key)
        if entry is None:
            counters[key] = [0, now]
            return RateLimitResult(allowed=True, remaining=limit, limit=limit, reset=now + period)

        count, window_start = entry
        window_end = window_start + period

        if now >= window_end:
            # Window expired - reset
            entry[0] = 0
            entry[1] = now
            count = 0
            window_start = now

        remaining = max(0, limit - count)
        allowed = count < limit

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            limit=limit,
            reset=window_start + period
        )

    async def increment(self, key: str, period: float) -> int:
        now = time.time()
        counters = self._counters

        entry = counters.get(key)
        if entry is None:
            counters[key] = [1, now]
            return 1

        count, window_start = entry
        if now >= window_start + period:
            # Window expired - reset
            entry[0] = 1
            entry[1] = now
            return 1

        entry[0] = count + 1
        return count + 1

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """Atomic check + increment - single dict lookup, single hash."""
        now = time.time()
        counters = self._counters

        entry = counters.get(key)
        if entry is None:
            counters[key] = [1, now]
            return RateLimitResult(allowed=True, remaining=limit - 1, limit=limit, reset=now + period)

        count, window_start = entry
        if now >= window_start + period:
            # Window expired - reset
            entry[0] = 1
            entry[1] = now
            return RateLimitResult(allowed=True, remaining=limit - 1, limit=limit, reset=now + period)

        remaining = max(0, limit - count)
        allowed = count < limit

        if allowed:
            entry[0] = count + 1
            remaining -= 1

        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, remaining),
            limit=limit,
            reset=window_start + period
        )


class SharedMemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Ultra-fast shared memory rate limiting using sliding window counter.
    O(1) per request - no loops, no timestamp arrays.

    Memory layout:
        - Header (64 bytes): magic, version, max_keys, reserved
        - Key Index: hash(8) + count(4) + window_start(8) + expires(8) = 28 bytes per key
    """

    HEADER_SIZE = 64
    KEY_ENTRY_SIZE = 28  # hash(8) + count(4) + window_start(8) + expires(8)

    MAGIC = b'ALMT'
    VERSION = 1

    def __init__(
        self,
        name: str = "altapi_ratelimit",
        max_keys: int = 10000,
        max_timestamps: int = 100,
    ):
        self.name = name
        self.max_keys = max_keys

        # Calculate total size
        self._key_index_size = max_keys * self.KEY_ENTRY_SIZE
        self._total_size = self.HEADER_SIZE + self._key_index_size

        self._shm: Optional[shm.SharedMemory] = None
        self._created = False

        # Local dict cache: key_hash (int) -> key_idx (int)
        self._key_cache: Dict[int, int] = {}

    def _get_key_hash(self, key: str) -> int:
        """Get fast 64-bit hash of a key."""
        return hash(key) & 0xFFFFFFFFFFFFFFFF

    def _find_key(self, key_hash: int, period: float) -> Tuple[int, bool]:
        """Find key in index using local cache (O(1))."""
        now = time.time()

        # Check local cache first (O(1))
        idx = self._key_cache.get(key_hash)
        if idx is not None:
            offset = self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE
            stored_hash = struct.unpack_from('=Q', self._shm.buf, offset)[0]
            if stored_hash == key_hash:
                expires = struct.unpack_from('=d', self._shm.buf, offset + 20)[0]
                if expires > now:
                    return idx, True
                else:
                    self._key_cache.pop(key_hash, None)
                    return idx, False

        # Cache miss - find first empty slot
        for i in range(self.max_keys):
            offset = self.HEADER_SIZE + i * self.KEY_ENTRY_SIZE
            stored_hash = struct.unpack_from('=Q', self._shm.buf, offset)[0]

            if stored_hash == 0:
                return i, False
            elif stored_hash == key_hash:
                expires = struct.unpack_from('=d', self._shm.buf, offset + 20)[0]
                if expires > now:
                    self._key_cache[key_hash] = i
                    return i, True

        return -1, False

    def _read_bytes(self, offset: int, size: int) -> bytes:
        """Read bytes from shared memory."""
        return bytes(self._shm.buf[offset:offset + size])

    def _write_bytes(self, offset: int, data: bytes) -> None:
        """Write bytes to shared memory."""
        self._shm.buf[offset:offset + len(data)] = data

    def _initialize(self) -> None:
        """Initialize shared memory structure."""
        self._write_bytes(0, self.MAGIC)
        struct.pack_into('I', self._shm.buf, 4, self.VERSION)
        struct.pack_into('I', self._shm.buf, 8, self.max_keys)
        struct.pack_into('I', self._shm.buf, 16, 1)  # initialized
        self._created = True

    def _ensure_initialized(self) -> None:
        """Ensure shared memory is initialized."""
        if self._shm is not None:
            return

        try:
            self._shm = shm.SharedMemory(name=self.name)
            magic = self._read_bytes(0, 4)
            if magic != self.MAGIC:
                self._shm.close()
                self._shm.unlink()
                raise FileNotFoundError
            version = struct.unpack('I', self._read_bytes(4, 4))[0]
            if version != self.VERSION:
                self._shm.close()
                self._shm.unlink()
                raise FileNotFoundError
            self._created = False
            return
        except FileNotFoundError:
            pass

        try:
            self._shm = shm.SharedMemory(name=self.name, create=True, size=self._total_size)
            self._initialize()
            self._created = True
        except FileExistsError:
            self._shm = shm.SharedMemory(name=self.name)
            self._created = False

    def _get_or_create_key(self, key: str, period: float) -> int:
        """Get or create key index."""
        key_hash = self._get_key_hash(key)
        now = time.time()

        idx, found = self._find_key(key_hash, period)

        if found:
            return idx

        # Find first empty slot
        if idx == -1:
            for i in range(self.max_keys):
                offset = self.HEADER_SIZE + i * self.KEY_ENTRY_SIZE
                if struct.unpack_from('=Q', self._shm.buf, offset)[0] == 0:
                    idx = i
                    break

        if idx == -1:
            idx = 0

        # Write key entry: hash(8) + count(4) + window_start(8) + expires(8) = 28 bytes
        offset = self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE
        struct.pack_into('=Q', self._shm.buf, offset, key_hash)
        struct.pack_into('=I', self._shm.buf, offset + 8, 0)  # count
        struct.pack_into('=d', self._shm.buf, offset + 12, now)  # window_start
        struct.pack_into('=d', self._shm.buf, offset + 20, now + period)  # expires

        self._key_cache[key_hash] = idx
        return idx

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """Check rate limit - O(1), no loops."""
        if self._shm is None:
            self._ensure_initialized()

        key_idx = self._get_or_create_key(key, period)
        now = time.time()

        offset = self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE
        count = struct.unpack_from('=I', self._shm.buf, offset + 8)[0]
        window_start = struct.unpack_from('=d', self._shm.buf, offset + 12)[0]

        if now >= window_start + period:
            # Window expired
            return RateLimitResult(allowed=True, remaining=limit, limit=limit, reset=now + period)

        remaining = max(0, limit - count)
        allowed = count < limit

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            limit=limit,
            reset=window_start + period
        )

    async def increment(self, key: str, period: float) -> int:
        """Increment counter - O(1), no loops."""
        if self._shm is None:
            self._ensure_initialized()

        key_idx = self._get_or_create_key(key, period)
        now = time.time()

        offset = self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE
        count = struct.unpack_from('=I', self._shm.buf, offset + 8)[0]
        window_start = struct.unpack_from('=d', self._shm.buf, offset + 12)[0]

        if now >= window_start + period:
            # Window expired - reset
            struct.pack_into('=I', self._shm.buf, offset + 8, 1)
            struct.pack_into('=d', self._shm.buf, offset + 12, now)
            struct.pack_into('=d', self._shm.buf, offset + 20, now + period)
            return 1

        struct.pack_into('=I', self._shm.buf, offset + 8, count + 1)
        return count + 1

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """Atomic check + increment - single hash, single shm lookup."""
        if self._shm is None:
            self._ensure_initialized()

        key_idx = self._get_or_create_key(key, period)
        now = time.time()

        offset = self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE
        count = struct.unpack_from('=I', self._shm.buf, offset + 8)[0]
        window_start = struct.unpack_from('=d', self._shm.buf, offset + 12)[0]

        if now >= window_start + period:
            # Window expired - reset and allow
            struct.pack_into('=I', self._shm.buf, offset + 8, 1)
            struct.pack_into('=d', self._shm.buf, offset + 12, now)
            struct.pack_into('=d', self._shm.buf, offset + 20, now + period)
            return RateLimitResult(allowed=True, remaining=limit - 1, limit=limit, reset=now + period)

        remaining = max(0, limit - count)
        allowed = count < limit

        if allowed:
            struct.pack_into('=I', self._shm.buf, offset + 8, count + 1)
            remaining -= 1

        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, remaining),
            limit=limit,
            reset=window_start + period
        )

    def cleanup(self) -> None:
        """Cleanup shared memory."""
        if self._shm is not None:
            try:
                self._shm.close()
                if self._created:
                    self._shm.unlink()
            except Exception:
                pass

    def __del__(self):
        self.cleanup()


__all__ = [
    "BaseRateLimitStorage",
    "InMemoryRateLimitStorage",
    "SharedMemoryRateLimitStorage",
    "RateLimitResult",
]
