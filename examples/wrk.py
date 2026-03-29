from altapi import AltAPI
from altapi.http import JSONResponse, PlainTextResponse
from altapi.templating import render_template
from pathlib import Path


app = AltAPI(templates_directory=Path(__file__).resolve().parent / "templates")

@app.get("/json")
async def bench(request):
    return JSONResponse({"test":"test"})

@app.get("/plaintext")
async def bench2(request):
    return PlainTextResponse("Plain text!")

@app.get("/template")
async def bench3(request):
    return render_template("test.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=8)