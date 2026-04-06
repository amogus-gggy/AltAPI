"""MyProject - AltAPI Application"""
from altapi import AltAPI
from altapi.http import JSONResponse
from altapi.openapi_decorators import openapi, tag

app = AltAPI(
    title="MyProject API",
    version="0.1.0",
    description="My project API built with AltAPI",
    # For production, disable OpenAPI/SwaggerUI:
    # enable_openapi=False,
    # Custom URLs:
    # openapi_url="/api/openapi.json",
    # docs_url="/api/docs",
)


@app.get("/")
@openapi(summary="Home", description="Welcome endpoint", tags=["general"])
async def home(request):
    return JSONResponse({"message": "Hello, World!"})


@app.get("/api/health")
@openapi(summary="Health Check", description="API health status", tags=["system"])
async def health(request):
    return JSONResponse({"status": "ok"})


@app.get("/api/users/{id:int}")
@openapi(
    summary="Get User",
    description="Returns user information by ID",
    tags=["users"],
    responses={
        "200": {"description": "User found"},
        "404": {"description": "User not found"},
    },
)
async def get_user(request):
    user_id = request.path_params["id"]
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})


@app.post("/api/echo")
@openapi(summary="Echo", description="Returns received JSON", tags=["general"])
async def echo(request):
    data = await request.json()
    return JSONResponse({"echo": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
