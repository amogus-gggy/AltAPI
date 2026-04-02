"""
Rate limiting module for AltAPI.

Provides rate limiting with decorator support using shared memory for multi-process IPC.
No network overhead - uses multiprocessing.shared_memory.

Example usage:
    from altapi import AltAPI
    from altapi.ratelimit import rate_limit

    app = AltAPI()

    @app.get("/api/data")
    @rate_limit(limit=10, period=60)  # 10 requests per minute
    async def get_data(request):
        return JSONResponse({"data": "value"})
"""

from .limit import (
    rate_limit,
    rate_limit_batch,
    set_storage,
    use_shared_memory,
)
from .storage import (
    BaseRateLimitStorage,
    InMemoryRateLimitStorage,
    SharedMemoryRateLimitStorage,
    RateLimitResult,
)

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
