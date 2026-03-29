"""
Rate limiting module for AltAPI.

Provides rate limiting with decorator support, similar to SlowAPI.
Uses shared storage by default for multi-worker support.

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
    BaseRateLimitStorage,
    RateLimitResult,
)

__all__ = [
    "rate_limit",
    "rate_limit_batch",
    "BaseRateLimitStorage",
    "RateLimitResult",
]
