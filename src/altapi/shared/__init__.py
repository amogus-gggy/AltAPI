"""
Shared memory module - DEPRECATED.

This module has been deprecated. Rate limiting now uses shared memory directly
via altapi.ratelimit.SharedMemoryRateLimitStorage.

For multi-process rate limiting, use:
    from altapi.ratelimit import SharedMemoryRateLimitStorage, rate_limit

    @rate_limit(limit=10, period=60)
    async def handler(request):
        ...

The shared memory backend is automatically used by default.
"""

import warnings

warnings.warn(
    "altapi.shared is deprecated. "
    "Rate limiting now uses shared memory directly. "
    "Use altapi.ratelimit.SharedMemoryRateLimitStorage instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = []
