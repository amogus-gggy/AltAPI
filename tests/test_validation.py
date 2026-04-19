"""Tests for request/response validation via request_model and response_model."""

import pytest
import httpx
from pydantic import BaseModel, Field
from typing import Optional

from altapi import AltAPI
from altapi.http import JSONResponse


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: str
    age: Optional[int] = Field(None, ge=0, le=150)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None


class ItemCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    quantity: int = Field(default=0, ge=0)


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    quantity: int


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def validation_app():
    app = AltAPI(enable_openapi=False)

    @app.post("/users", request_model=UserCreate, response_model=UserResponse)
    async def create_user(request):
        data = await request.json()
        return JSONResponse({"id": 1, **data}, status_code=201)

    @app.get("/users/{id:int}", response_model=UserResponse)
    async def get_user(request):
        uid = request.path_params["id"]
        return JSONResponse({"id": uid, "name": "Alice", "email": "alice@example.com"})

    @app.post("/items", request_model=ItemCreate, response_model=ItemResponse)
    async def create_item(request):
        data = await request.json()
        return JSONResponse({"id": 1, **data}, status_code=201)

    @app.post("/no-validation")
    async def no_validation(request):
        data = await request.json()
        return JSONResponse({"received": data})

    return app


# ---------------------------------------------------------------------------
# Request validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_request_passes(validation_app):
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "Alice", "email": "alice@example.com", "age": 30})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Alice"
        assert body["email"] == "alice@example.com"
        assert body["age"] == 30


@pytest.mark.asyncio
async def test_invalid_request_returns_400(validation_app):
    """Missing required 'email' field should trigger 400."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "Alice"})
        assert r.status_code == 400
        body = r.json()
        assert "error" in body


@pytest.mark.asyncio
async def test_invalid_field_value_returns_400(validation_app):
    """Age below 0 violates ge=0 constraint."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "Alice", "email": "a@b.com", "age": -5})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_name_too_short_returns_400(validation_app):
    """Name shorter than min_length=2 should fail."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "A", "email": "a@b.com"})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_optional_field_omitted(validation_app):
    """Optional age field can be omitted."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "Bob", "email": "bob@example.com"})
        assert r.status_code == 201


@pytest.mark.asyncio
async def test_item_valid_request(validation_app):
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/items", json={"name": "Widget", "price": 9.99, "quantity": 5})
        assert r.status_code == 201
        body = r.json()
        assert body["price"] == 9.99


@pytest.mark.asyncio
async def test_item_negative_price_returns_400(validation_app):
    """Price must be > 0."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/items", json={"name": "Widget", "price": -1.0})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Response validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_response_model_applied(validation_app):
    """GET /users/{id} uses response_model — response should match UserResponse shape."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/users/42")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 42
        assert body["name"] == "Alice"
        assert body["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# No-validation endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_validation_accepts_anything(validation_app):
    """Endpoint without request_model accepts arbitrary JSON."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/no-validation", json={"foo": "bar", "baz": 123})
        assert r.status_code == 200
        assert r.json()["received"]["foo"] == "bar"


# ---------------------------------------------------------------------------
# Validation error response shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validation_error_response_shape(validation_app):
    """Validation error response must contain 'error' and 'details' keys."""
    transport = httpx.ASGITransport(app=validation_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/users", json={"name": "Alice"})
        assert r.status_code == 400
        body = r.json()
        assert "error" in body
        assert "details" in body
