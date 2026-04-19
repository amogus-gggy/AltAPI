"""
AltAPI Request/Response Validation Example

Demonstrates optional request and response validation using Pydantic models.
"""

from pydantic import BaseModel, Field
from typing import Optional

from altapi import AltAPI
from altapi.http import JSONResponse


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., description="User email")
    age: Optional[int] = Field(None, ge=0, le=150)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    quantity: int = Field(default=0, ge=0)


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    quantity: int


app = AltAPI(
    title="Validation Example",
    version="1.0.0",
    description="Demonstrates request and response validation with Pydantic models",
)


# --- Request + Response validation ---

@app.post(
    "/users",
    request_model=UserCreate,
    response_model=UserResponse,
    summary="Create user",
    tags=["users"],
)
async def create_user(request):
    """
    POST /users with valid body:
        {"name": "Alice", "email": "alice@example.com", "age": 30}

    Invalid body (missing email) returns 400:
        {"name": "Alice"}
    """
    data = await request.json()
    return JSONResponse({"id": 1, **data}, status_code=201)


@app.post(
    "/items",
    request_model=ItemCreate,
    response_model=ItemResponse,
    summary="Create item",
    tags=["items"],
)
async def create_item(request):
    data = await request.json()
    return JSONResponse({"id": 1, **data}, status_code=201)


# --- Response-only validation ---

@app.get(
    "/users/{id:int}",
    response_model=UserResponse,
    summary="Get user",
    tags=["users"],
)
async def get_user(request):
    uid = request.path_params["id"]
    return JSONResponse({"id": uid, "name": "John Doe", "email": "john@example.com", "age": 30})


# --- No validation ---

@app.post("/no-validation")
async def no_validation(request):
    """Accepts any JSON body without validation."""
    data = await request.json()
    return JSONResponse({"received": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
