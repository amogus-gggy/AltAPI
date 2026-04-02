"""
Rate limit storage using multiprocessing.shared_memory.

Provides fast, process-safe rate limiting without network overhead.
"""

import asyncio
import hashlib
import json
import multiprocessing.shared_memory as shm
import struct
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple


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


class InMemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Simple in-memory rate limit storage for single-process use.
    """

    def __init__(self):
        self._limits: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        now = time.time()
        window_start = now - period

        if key not in self._limits:
            self._limits[key] = deque()

        timestamps = self._limits[key]

        # Remove old timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        count = len(timestamps)
        remaining = max(0, limit - count)
        allowed = count < limit

        reset_time = timestamps[0] + period if timestamps else now + period

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            limit=limit,
            reset=reset_time
        )

    async def increment(self, key: str, period: float) -> int:
        now = time.time()
        window_start = now - period

        if key not in self._limits:
            self._limits[key] = deque()

        timestamps = self._limits[key]

        # Remove old timestamps
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        # Add current timestamp
        timestamps.append(now)

        return len(timestamps)


class SharedMemoryRateLimitStorage(BaseRateLimitStorage):
    """
    Rate limit storage using multiprocessing.shared_memory.

    Provides process-safe rate limiting without network overhead.
    Uses a hash-based key indexing system for efficient lookups.

    Args:
        name: Name for the shared memory block (default: "altapi_ratelimit")
        max_keys: Maximum number of unique rate limit keys (default: 10000)
        max_timestamps: Maximum timestamps per key (default: 100)

    Memory layout:
        - Header (64 bytes):
            - magic (4 bytes): b'ALMT'
            - version (4 bytes): version number
            - max_keys (4 bytes): maximum keys
            - max_ts (4 bytes): max timestamps per key
            - initialized (4 bytes): 1 if initialized
            - reserved (44 bytes)

        - Key Index (variable):
            - For each key: hash(32 bytes) + offset(4 bytes) + period(8 bytes) + count(4 bytes) + expires(8 bytes) = 56 bytes

        - Timestamps (variable):
            - For each key: array of timestamps (8 bytes each)
    """

    HEADER_SIZE = 64
    KEY_ENTRY_SIZE = 56  # hash(32) + offset(4) + period(8) + count(4) + expires(8)
    TIMESTAMP_SIZE = 8  # double

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
        self.max_timestamps = max_timestamps

        # Calculate total size
        self._timestamps_size = max_keys * max_timestamps * self.TIMESTAMP_SIZE
        self._key_index_size = max_keys * self.KEY_ENTRY_SIZE
        self._total_size = self.HEADER_SIZE + self._key_index_size + self._timestamps_size

        self._shm: Optional[shm.SharedMemory] = None
        self._lock = threading.Lock()
        self._created = False
        self._empty_slot: int = -1

    def _get_key_hash(self, key: str) -> bytes:
        """Get 32-byte hash of a key."""
        return hashlib.sha256(key.encode('utf-8')).digest()

    def _find_key(self, key_hash: bytes, period: float) -> Tuple[int, bool]:
        """
        Find key in index.

        Returns:
            Tuple of (index, found)
        """
        now = time.time()
        first_empty = -1

        for i in range(self.max_keys):
            offset = self.HEADER_SIZE + i * self.KEY_ENTRY_SIZE
            stored_hash = self._read_bytes(offset, 32)

            # Check if slot matches
            if stored_hash == key_hash:
                # Found - check if expired
                expires = struct.unpack('d', self._read_bytes(offset + 48, 8))[0]
                if expires > now:
                    return i, True
                else:
                    # Expired - return index but mark as not found
                    return i, False

            # Remember first empty slot
            if stored_hash == b'\x00' * 32 and first_empty == -1:
                first_empty = i

        # No match found - return first empty slot or -1
        if first_empty >= 0:
            return first_empty, False

        return -1, False

    def _read_bytes(self, offset: int, size: int) -> bytes:
        """Read bytes from shared memory."""
        return bytes(self._shm.buf[offset:offset + size])

    def _write_bytes(self, offset: int, data: bytes) -> None:
        """Write bytes to shared memory."""
        self._shm.buf[offset:offset + len(data)] = data

    def _initialize(self) -> None:
        """Initialize shared memory structure."""
        # Magic
        self._write_bytes(0, self.MAGIC)
        # Version
        struct.pack_into('I', self._shm.buf, 4, self.VERSION)
        # max_keys
        struct.pack_into('I', self._shm.buf, 8, self.max_keys)
        # max_timestamps
        struct.pack_into('I', self._shm.buf, 12, self.max_timestamps)
        # initialized
        struct.pack_into('I', self._shm.buf, 16, 1)

        self._created = True

    def _ensure_initialized(self) -> None:
        """Ensure shared memory is initialized."""
        if self._shm is not None:
            return

        try:
            # Try attach first
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

        # Try creating
        try:
            self._shm = shm.SharedMemory(
                name=self.name,
                create=True,
                size=self._total_size
            )
            self._initialize()
            self._created = True

        except FileExistsError:
            # Another process created it meanwhile, attach instead
            self._shm = shm.SharedMemory(name=self.name)
            self._created = False

    def _get_or_create_key(self, key: str, period: float) -> int:
        """Get or create key index. Returns index into key array."""
        key_hash = self._get_key_hash(key)
        now = time.time()

        with self._lock:
            idx, found = self._find_key(key_hash, period)

            if found:
                return idx

            # Create new entry
            if idx == -1:
                # Find first empty slot
                for i in range(self.max_keys):
                    offset = self.HEADER_SIZE + i * self.KEY_ENTRY_SIZE
                    stored_hash = self._read_bytes(offset, 32)
                    if stored_hash == b'\x00' * 32:
                        idx = i
                        break

            if idx == -1:
                # No space - use slot 0 as fallback (LRU-like behavior)
                idx = 0

            # Write key hash
            self._write_bytes(self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE, key_hash)
            # Timestamps offset
            ts_offset = self.HEADER_SIZE + self._key_index_size + idx * self.max_timestamps * self.TIMESTAMP_SIZE
            struct.pack_into('I', self._shm.buf, self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE + 32, ts_offset)
            # Period
            struct.pack_into('d', self._shm.buf, self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE + 36, period)
            # Count = 0
            struct.pack_into('I', self._shm.buf, self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE + 44, 0)
            # Expires
            struct.pack_into('d', self._shm.buf, self.HEADER_SIZE + idx * self.KEY_ENTRY_SIZE + 48, now + period)

            return idx

    def _get_timestamps(self, key_idx: int, period: float) -> Tuple[list, int]:
        """Get timestamps for a key after cleanup."""
        now = time.time()
        window_start = now - period

        # Read timestamps offset
        ts_offset = struct.unpack('I', self._read_bytes(
            self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 32, 4
        ))[0]

        # Read count
        count = struct.unpack('I', self._read_bytes(
            self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 44, 4
        ))[0]

        timestamps = []
        for i in range(count):
            ts = struct.unpack('d', self._read_bytes(
                ts_offset + i * self.TIMESTAMP_SIZE, self.TIMESTAMP_SIZE
            ))[0]
            if ts >= window_start:
                timestamps.append(ts)

        return timestamps, ts_offset

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        period: float
    ) -> RateLimitResult:
        """Check rate limit for a key."""
        if self._shm is None:
            self._ensure_initialized()

        key_idx = self._get_or_create_key(key, period)
        now = time.time()

        with self._lock:
            timestamps, ts_offset = self._get_timestamps(key_idx, period)

            count = len(timestamps)
            remaining = max(0, limit - count)
            allowed = count < limit

            reset_time = timestamps[0] + period if timestamps else now + period

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                limit=limit,
                reset=reset_time
            )

    async def increment(self, key: str, period: float) -> int:
        """Increment request count for a key."""
        if self._shm is None:
            self._ensure_initialized()

        key_idx = self._get_or_create_key(key, period)
        now = time.time()
        window_start = now - period

        with self._lock:
            # Read timestamps offset and count
            ts_offset = struct.unpack('I', self._read_bytes(
                self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 32, 4
            ))[0]

            count = struct.unpack('I', self._read_bytes(
                self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 44, 4
            ))[0]

            # Read and filter timestamps
            timestamps = []
            for i in range(count):
                ts = struct.unpack('d', self._read_bytes(
                    ts_offset + i * self.TIMESTAMP_SIZE, self.TIMESTAMP_SIZE
                ))[0]
                if ts >= window_start:
                    timestamps.append(ts)

            # Add current timestamp
            timestamps.append(now)

            # Write back timestamps
            new_count = min(len(timestamps), self.max_timestamps)
            for i, ts in enumerate(timestamps[:self.max_timestamps]):
                struct.pack_into('d', self._shm.buf, ts_offset + i * self.TIMESTAMP_SIZE, ts)

            # Update count
            struct.pack_into('I', self._shm.buf,
                           self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 44, new_count)

            # Update expires
            struct.pack_into('d', self._shm.buf,
                           self.HEADER_SIZE + key_idx * self.KEY_ENTRY_SIZE + 48, now + period)

            return new_count

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
