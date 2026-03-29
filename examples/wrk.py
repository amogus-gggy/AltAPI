from altapi import AltAPI
from altapi.caching import cache, InMemoryCache, CacheManager
from altapi.http import JSONResponse, PlainTextResponse
from altapi.templating import render_template
from pathlib import Path

import os

# Use InMemoryCache for benchmarking (faster than SharedCacheBackend)
BASE_DIR = Path(__file__).resolve().parent
app = AltAPI(
    templates_directory=BASE_DIR / "templates",
    cache_timeout=300,
)

# Set InMemoryCache as default for this benchmark
CacheManager.set_default_backend(InMemoryCache(max_size=10000))

@app.get("/json")
async def bench(request):
    return JSONResponse({"test":"test"})

@app.get("/plaintext")
async def bench2(request):
    return PlainTextResponse("Plain text!")

@app.get("/template")
@cache(expires=300)
async def bench3(request):
    print("test")
    return render_template("test.html", templates_directory=BASE_DIR / "templates")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=8, access_log=False)
