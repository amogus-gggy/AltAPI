from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


@app.get("/json")
async def bench():
    return JSONResponse(content={"test": "test"})


@app.get("/plaintext")
async def bench2():
    return PlainTextResponse("Plain text!")


@app.get("/template")
async def bench3(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
