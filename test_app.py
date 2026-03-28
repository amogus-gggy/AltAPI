import requests
import sys
import websockets

from altapi.templating import DEFAULT_404_BODY

import asyncio

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"


def test_home():
    """Test home page (HTML response)."""
    resp = requests.get(f"{BASE_URL}/")
    assert resp.status_code == 200
    assert "Welcome to Nebula!" in resp.text
    assert "text/html" in resp.headers["Content-Type"]
    print("✓ Home page OK")


def test_hello():
    """Test hello endpoint (JSON response)."""
    resp = requests.get(f"{BASE_URL}/api/hello")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"message": "Hello, World!"}
    assert "application/json" in resp.headers["Content-Type"]
    print("✓ Hello endpoint OK")


def test_echo():
    """Test echo endpoint (POST with JSON)."""
    payload = {"name": "Test", "value": 123}
    resp = requests.post(f"{BASE_URL}/api/echo", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"echo": payload}
    print("✓ Echo endpoint OK")


def test_user_by_id():
    """Test user endpoint with typed int path parameter."""
    resp = requests.get(f"{BASE_URL}/api/users/42")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 42  # Now it's an int, not string
    assert data["name"] == "User 42"
    print("✓ User by ID endpoint OK")


def test_item_by_name():
    """Test item endpoint with typed str path parameter."""
    resp = requests.get(f"{BASE_URL}/api/items/widget")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "widget"
    assert data["type"] == "item"
    print("✓ Item by name endpoint OK")


def test_score_by_float():
    """Test score endpoint with typed float path parameter."""
    resp = requests.get(f"{BASE_URL}/api/score/3.14")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 3.14
    assert data["doubled"] == 6.28
    print("✓ Score by float endpoint OK")


def test_sync_handler():
    """Test synchronous handler."""
    resp = requests.get(f"{BASE_URL}/api/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "sync"
    assert "I'm synchronous!" in data["message"]
    print("✓ Sync handler OK")


def test_random_async():
    """Test async random number endpoint (2 requests)."""
    results = []
    for i in range(2):
        resp = requests.get(f"{BASE_URL}/api/random/async")
        assert resp.status_code == 200
        data = resp.json()
        assert "value" in data
        assert data["type"] == "async"
        assert 1 <= data["value"] <= 100
        results.append(data["value"])
        print(f"✓ Async random request {i+1}: {data['value']}")
    print(f"  Results: {results}")


def test_random_sync():
    """Test sync random number endpoint (2 requests)."""
    results = []
    for i in range(2):
        resp = requests.get(f"{BASE_URL}/api/random/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert "value" in data
        assert data["type"] == "sync"
        assert 1 <= data["value"] <= 100
        results.append(data["value"])
        print(f"✓ Sync random request {i+1}: {data['value']}")
    print(f"  Results: {results}")


def test_plain_text_response():
    """Test PlainTextResponse endpoint."""
    resp = requests.get(f"{BASE_URL}/api/text")
    assert resp.status_code == 200
    assert resp.text == "This is a plain text response"
    assert "text/plain" in resp.headers["Content-Type"]
    print("✓ PlainTextResponse OK")


def test_streaming_response():
    """Test StreamingResponse endpoint."""
    resp = requests.get(f"{BASE_URL}/api/stream")
    assert resp.status_code == 200
    expected = "".join([f"Line {i}\n" for i in range(10)])
    assert resp.text == expected
    print("✓ StreamingResponse OK")


def test_redirect_response():
    """Test RedirectResponse endpoint."""
    resp = requests.get(f"{BASE_URL}/api/redirect", allow_redirects=False)
    assert resp.status_code in [307, 301, 302]
    assert resp.headers["Location"] == "https://example.com"
    print("✓ RedirectResponse OK")


def test_static_file():
    """Test static file serving."""
    resp = requests.get(f"{BASE_URL}/static/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["Content-Type"] or "text/plain" in resp.headers["Content-Type"]
    assert "Nebula Static" in resp.text or "body" in resp.text
    print("✓ Static file OK")


def test_static_file_not_found():
    """Test static file 404."""
    resp = requests.get(f"{BASE_URL}/static/nonexistent.css")
    assert resp.status_code == 404
    print("✓ Static file 404 OK")


def test_template_response():
    """Test Jinja2 template response."""
    resp = requests.get(f"{BASE_URL}/template")
    assert resp.status_code == 200
    assert "Nebula Templates" in resp.text
    assert "text/html" in resp.headers["Content-Type"]
    assert "Logged in as: Guest" in resp.text
    print("✓ TemplateResponse OK")


def test_ping():
    """Test ping endpoint."""
    resp = requests.get(f"{BASE_URL}/api/ping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pong"
    print("✓ Ping endpoint OK")


def test_status():
    """Test status endpoint."""
    resp = requests.get(f"{BASE_URL}/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["healthy"] is True
    assert "version" in data
    print("✓ Status endpoint OK")


def test_post_data():
    """Test POST data endpoint."""
    payload = {"key1": "value1", "key2": 123}
    resp = requests.post(f"{BASE_URL}/api/data", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert set(data["keys"]) == {"key1", "key2"}
    print("✓ POST data endpoint OK")


def test_sum():
    """Test sum endpoint."""
    resp = requests.get(f"{BASE_URL}/api/sum/10/20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["a"] == 10
    assert data["b"] == 20
    assert data["sum"] == 30
    print("✓ Sum endpoint OK")


def test_multiply():
    """Test multiply endpoint."""
    resp = requests.get(f"{BASE_URL}/api/multiply/2.5/4")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["x"] - 2.5) < 0.01
    assert abs(data["y"] - 4.0) < 0.01
    assert abs(data["result"] - 10.0) < 0.01
    print("✓ Multiply endpoint OK")


def test_not_found():
    """Test 404 response."""
    resp = requests.get(f"{BASE_URL}/nonexistent")
    assert resp.status_code == 404
    assert resp.content == bytes(DEFAULT_404_BODY.encode())
    print("✓ 404 response OK")


async def test_websocket_echo():
    """Test WebSocket echo endpoint."""
    ws = await websockets.connect(f"{WS_URL}/ws/echo")

    try:
        await ws.send("Hello")
        result = await ws.recv()
        assert result == "Echo: Hello"

        await ws.send("World")
        result = await ws.recv()
        assert result == "Echo: World"

        print("✓ WebSocket echo OK")
    finally:
        await ws.close()


async def test_websocket_chat_with_room():
    """Test WebSocket chat endpoint with room parameter."""
    ws = await websockets.connect(f"{WS_URL}/ws/chat/general")
    try:
        # First message should be welcome (received immediately after accept)
        result = await ws.recv()
        assert result == "Welcome to room: general!"

        # Send a message
        await ws.send("Hi everyone!")
        result = await ws.recv()
        assert result == "[general] Hi everyone!"

        print("✓ WebSocket chat with room OK")
    finally:
        await ws.close()


async def test_websocket_json():
    """Test WebSocket JSON endpoint."""
    ws = await websockets.connect(f"{WS_URL}/ws/json")
    try:
        await ws.send('{"name": "test", "value": 42}')
        result = await ws.recv()
        import json

        data = json.loads(result)
        assert data["received"] == {"name": "test", "value": 42}
        assert data["status"] == "processed"

        print("✓ WebSocket JSON OK")
    finally:
        await ws.close()


async def main():
    try:
        print("Running tests...\n")

        # HTTP tests
        test_home()
        test_hello()
        test_echo()
        test_user_by_id()
        test_item_by_name()
        test_score_by_float()
        test_sync_handler()
        test_random_async()
        test_random_sync()
        
        # New response types tests
        test_plain_text_response()
        test_streaming_response()
        test_redirect_response()
        
        # Static files and templates
        test_static_file()
        test_static_file_not_found()
        test_template_response()
        
        # New benchmark endpoints
        test_ping()
        test_status()
        test_post_data()
        test_sum()
        test_multiply()
        
        # Error handling
        test_not_found()
        
        # WebSocket tests
        await test_websocket_echo()
        await test_websocket_chat_with_room()
        await test_websocket_json()

        print("\n✅ All tests passed!")
        return

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to server")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
