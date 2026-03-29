"""
Пример использования кеширования в AltAPI.

Кеширование работает по умолчанию через shared manager.
Используйте @cache декоратор или app.cache() для кеширования.

Usage:
    python examples/cache_example.py
"""

import asyncio
import time

from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.caching import cache

app = AltAPI(cache_timeout=300)  # 5 минут по умолчанию


@app.get("/")
async def home(request):
    return JSONResponse({
        "message": "Welcome to AltAPI Caching Example",
        "endpoints": [
            "/api/expensive - Дорогая операция (кешируется 5 минут)",
            "/api/data - Данные с разным временем кеширования",
        ]
    })


# Вариант 1: Использование декоратора @cache
@app.get("/api/expensive")
@cache(expires=300)  # Кеш на 5 минут
async def expensive_operation(request):
    """Дорогая операция, результат кешируется."""
    print("called")
    await asyncio.sleep(2)  # Имитация долгой операции
    return JSONResponse({
        "message": "Expensive operation completed",
        "timestamp": time.time(),
        "note": "Первый вызов занимает 2 секунды, последующие - мгновенно (из кеша)"
    })


# Вариант 2: Использование app.cache()
@app.cache("/api/data", expires=60)  # Кеш на 1 минуту
@app.get("/api/data")
async def get_data(request):
    """Данные, которые обновляются раз в минуту."""
    return JSONResponse({
        "data": [1, 2, 3, 4, 5],
        "timestamp": time.time(),
    })


if __name__ == "__main__":
    print("AltAPI с кешированием:")
    print("  GET /api/expensive - 2 сек первый раз, потом из кеша")
    print("  GET /api/data      - Данные с 1 минутой кеширования")
    print("\nRun: curl http://localhost:8000/api/expensive\n")
    app.run(host="0.0.0.0", port=8000, workers=2)
