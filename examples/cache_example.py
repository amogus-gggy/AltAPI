"""
Пример использования кеширования в AltAPI.
"""
import asyncio

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache, InMemoryCache
import time

# Создаём app с кешем - просто указываем бекенд!
app = AltAPI(
    cache_backend=InMemoryCache(max_size=500),
    cache_timeout=300
)


@app.get("/")
async def home(request):
    return JSONResponse({
        "message": "Welcome to AltAPI Caching Example",
        "endpoints": [
            "/api/expensive - Expensive operation (cached)",
        ]
    })




@app.get("/api/expensive")
@cache(expires=300)  # Кеш на 5 минут
async def expensive_operation(request):
    # Имитация дорогой операции
    await asyncio.sleep(15)
    return JSONResponse({
        "message": "Expensive operation completed",
        "timestamp": time.time(),
        "note": "First call takes 0.5s, subsequent calls are instant (from cache)"
    })





if __name__ == "__main__":
    print("Starting AltAPI with caching example...")
    print("Visit http://localhost:8000 for available endpoints")
    app.run(host="0.0.0.0", port=8000)
