"""MyProject - AltAPI Application"""
from altapi import AltAPI
from altapi.http import JSONResponse

app = AltAPI()


@app.get("/")
async def home(request):
    return JSONResponse({"message": "Hello, World!"})


@app.get("/api/health")
async def health(request):
    return JSONResponse({"status": "ok"})


@app.get("/api/users/{id:int}")
async def get_user(request):
    user_id = request.path_params["id"]
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})


@app.post("/api/echo")
async def echo(request):
    data = await request.json()
    return JSONResponse({"echo": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
