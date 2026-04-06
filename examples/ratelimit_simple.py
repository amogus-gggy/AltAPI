"""
Simple Rate Limiting Example

Usage:
    python examples/ratelimit_simple.py
"""

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.ratelimit import rate_limit, rate_limit_batch

app = AltAPI()


@app.get("/api/data")
@rate_limit(limit=10, period=60)  # 10 requests per minute
async def get_data(request):
    return JSONResponse({"data": "Hello, World!"})


@app.get("/api/premium")
@rate_limit_batch(
    [
        (10, 60),  # 10 per minute
        (100, 3600),  # 100 per hour
        (1000, 86400),  # 1000 per day
    ]
)
async def get_premium(request):
    return JSONResponse({"premium": "data"})


if __name__ == "__main__":
    print("Endpoints:")
    print("  GET /api/data    - 10 req/min")
    print("  GET /api/premium - 10/min, 100/hour, 1000/day")
    print("\nRun: curl -i http://localhost:8000/api/data\n")
    app.run(host="0.0.0.0", port=8000, workers=4)
