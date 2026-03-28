from altapi import AltAPI
from altapi.http import JSONResponse


app = AltAPI()

@app.get("/")
async def bench(request):
    return JSONResponse({"test":"test"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=4)