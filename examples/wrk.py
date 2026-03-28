from altapi import (
    Nebula,
    JSONResponse
)


app = Nebula()

@app.get("/")
async def bench(request):
    return JSONResponse({"test":"test"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)