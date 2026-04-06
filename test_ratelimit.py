"""
Rate Limit Test Script using aiohttp

Sends multiple concurrent requests to test rate limiting.

Usage:
    python test_ratelimit.py
"""

import asyncio
import aiohttp
import time


async def test_rate_limit(
    url: str = "http://localhost:8000/api/data",
    num_requests: int = 15,
    concurrent: int = 1,
):
    """
    Test rate limiting by sending multiple requests.

    Args:
        url: Endpoint URL
        num_requests: Total number of requests to send
        concurrent: Number of concurrent requests
    """
    print(f"Testing rate limit: {num_requests} requests, {concurrent} concurrent")
    print(f"URL: {url}")
    print("-" * 60)

    results = {
        "200": 0,
        "429": 0,
        "other": 0,
    }

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(concurrent)

        async def make_request(session: aiohttp.ClientSession, req_id: int):
            async with semaphore:
                start = time.time()
                try:
                    async with session.get(url) as response:
                        elapsed = time.time() - start
                        status = response.status
                        body = await response.text()

                        if status == 200:
                            results["200"] += 1
                        elif status == 429:
                            results["429"] += 1
                        else:
                            results["other"] += 1

                        # Get rate limit headers
                        limit = response.headers.get("X-RateLimit-Limit", "N/A")
                        remaining = response.headers.get("X-RateLimit-Remaining", "N/A")
                        reset = response.headers.get("X-RateLimit-Reset", "N/A")
                        retry_after = response.headers.get("Retry-After", "N/A")

                        print(
                            f"[{req_id:02d}] Status: {status:3d} | "
                            f"Limit: {limit:>3} | Remaining: {remaining:>3} | "
                            f"Retry-After: {retry_after:>3} | "
                            f"Time: {elapsed:.3f}s"
                        )
                        return status

                except Exception as e:
                    elapsed = time.time() - start
                    results["other"] += 1
                    print(f"[{req_id:02d}] ERROR: {e} ({elapsed:.3f}s)")
                    return None

        # Send all requests
        tasks = [make_request(session, i) for i in range(num_requests)]
        await asyncio.gather(*tasks)

    print("-" * 60)
    print("Results:")
    print(f"  200 OK:           {results['200']}")
    print(f"  429 Rate Limited: {results['429']}")
    print(f"  Other:            {results['other']}")

    if results["429"] > 0:
        print("\n✅ Rate limiting is WORKING!")
    else:
        print("\n❌ Rate limiting is NOT working!")


async def test_batch():
    """Test rate limiting with batch of requests."""
    print("=" * 60)
    print("TEST 1: Sequential requests (should hit limit after 10)")
    print("=" * 60)
    await test_rate_limit(num_requests=15, concurrent=1)

    print("\n\n")
    print("=" * 60)
    print("TEST 2: Concurrent requests (should hit limit quickly)")
    print("=" * 60)
    await test_rate_limit(num_requests=15, concurrent=10)


if __name__ == "__main__":
    asyncio.run(test_batch())
