"""
AltAPI Full Example Application

Demonstrates all major features.
"""
from altapi import AltAPI
from altapi.http import (
    JSONResponse,
    HTMLResponse,
    PlainTextResponse,
    StreamingResponse,
    RedirectResponse,
)
from altapi.websocket import WebSocket
from altapi.templating import Jinja2Templates
from altapi.caching import InMemoryCache, cache
from altapi.ratelimit import rate_limit
import random
import os

# Setup templates and static directories
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Create app with templates, static directories and caching
app = AltAPI(
    templates_directory=templates_dir,
    static_directory=static_dir,
    cache_timeout=300
)

# Setup templates object for TemplateResponse
templates = Jinja2Templates(directory=templates_dir)


@app.get("/")
async def home(request):
    return HTMLResponse("<h1>Welcome to AltAPI!</h1>")


@app.get("/api/hello")
async def hello(request):
    return JSONResponse({"message": "Hello, World!"})


@app.get("/api/cached")
@cache(expires=60)  # Cache for 60 seconds
async def cached_endpoint(request):
    import time
    return JSONResponse({
        "message": "This response is cached for 60 seconds",
        "timestamp": time.time()
    })


@app.post("/api/echo")
async def echo(request):
    data = await request.json()
    return JSONResponse({"echo": data})


# Typed path parameters
@app.get("/api/users/{id:int}")
async def get_user(request):
    user_id = request.path_params["id"]  # int
    return JSONResponse({"id": user_id, "name": f"User {user_id}"})


@app.get("/api/items/{name:str}")
async def get_item(request):
    name = request.path_params["name"]  # str
    return JSONResponse({"name": name, "type": "item"})


@app.get("/api/score/{value:float}")
async def get_score(request):
    value = request.path_params["value"]  # float
    return JSONResponse({"score": value, "doubled": value * 2})


# Sync handler example
@app.get("/api/sync")
def sync_handler(request):
    return JSONResponse({"type": "sync", "message": "I'm synchronous!"})


# Random number endpoints
@app.get("/api/random/async")
async def random_async(request):
    """Async endpoint for generating random number."""
    return JSONResponse({"value": random.randint(1, 100), "type": "async"})


@app.get("/api/random/sync")
def random_sync(request):
    """Sync endpoint for generating random number."""
    return JSONResponse({"value": random.randint(1, 100), "type": "sync"})


# WebSocket echo endpoint
@app.websocket("/ws/echo")
async def websocket_echo(ws: WebSocket):
    await ws.accept()
    while True:
        text = await ws.receive_text()
        print(text)
        await ws.send_text(f"Echo: {text}")


# WebSocket broadcast endpoint with room parameter
@app.websocket("/ws/chat/{room:str}")
async def websocket_chat(ws: WebSocket):
    room = ws.path_params["room"]
    await ws.accept()
    await ws.send_text(f"Welcome to room: {room}!")

    try:
        async for message in ws:
            if "text" in message:
                # Broadcast back with room info
                await ws.send_text(f"[{room}] {message['text']}")
    except Exception:
        await ws.close()


# WebSocket JSON endpoint
@app.websocket("/ws/json")
async def websocket_json(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_json()
        # Process and echo back with timestamp
        await ws.send_json({"received": data, "status": "processed"})


# Simple WebSocket Chat with broadcast
active_connections: set[WebSocket] = set()


@app.get("/chat")
async def chat_page(request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Chat</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 50px auto; }
            #messages { border: 1px solid #ccc; height: 300px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
            .message { margin: 5px 0; }
            .system { color: #888; font-style: italic; }
            input { width: 70%; padding: 8px; }
            button { padding: 8px 16px; }
        </style>
    </head>
    <body>
        <h1>💬 WebSocket Chat</h1>
        <div id="messages"></div>
        <input type="text" id="messageInput" placeholder="Type a message...">
        <button onclick="sendMessage()">Send</button>
        <script>
            const ws = new WebSocket("ws://" + location.host + "/ws/chat");
            const messages = document.getElementById("messages");
            const input = document.getElementById("messageInput");

            ws.onopen = () => {
                messages.innerHTML += '<div class="system">Connected to chat!</div>';
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                const div = document.createElement("div");
                div.className = "message";
                if (data.type === "system") {
                    div.className += " system";
                }
                div.textContent = data.username + ": " + data.message;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            };

            ws.onclose = () => {
                messages.innerHTML += '<div class="system">Disconnected from chat</div>';
            };

            function sendMessage() {
                const text = input.value.trim();
                if (text) {
                    ws.send(JSON.stringify({ message: text }));
                    input.value = "";
                }
            }

            input.addEventListener("keypress", (e) => {
                if (e.key === "Enter") sendMessage();
            });
        </script>
    </body>
    </html>
    """)


@app.websocket("/ws/chat")
async def websocket_chat_broadcast(ws: WebSocket):
    await ws.accept()
    active_connections.add(ws)
    print(f"[WS] Client connected. Total connections: {len(active_connections)}")

    # Notify everyone about new user
    await broadcast(
        {
            "type": "system",
            "username": "System",
            "message": f"New user connected! Total users: {len(active_connections)}",
        }
    )

    try:
        while True:
            message = await ws.receive_json()
            print(f"[WS] Received message: {message}")
            if isinstance(message, dict) and "message" in message:
                # Broadcast message to all connections (including sender)
                await broadcast(
                    {"type": "chat", "username": "User", "message": message["message"]}
                )
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        active_connections.discard(ws)
        print(f"[WS] Client disconnected. Total connections: {len(active_connections)}")
        # Notify everyone about user disconnect
        if active_connections:
            await broadcast(
                {
                    "type": "system",
                    "username": "System",
                    "message": f"User disconnected. Total users: {len(active_connections)}",
                }
            )


async def broadcast(data: dict):
    """Broadcast message to all connected clients"""
    import json

    message = json.dumps(data)
    disconnected = set()

    print(f"[WS] Broadcasting to {len(active_connections)} connections: {data}")

    for conn in active_connections:
        try:
            await conn.send_text(message)
        except Exception as e:
            print(f"[WS] Failed to send to connection: {e}")
            disconnected.add(conn)

    # Clean up disconnected clients
    for conn in disconnected:
        active_connections.discard(conn)


# New response types examples

@app.get("/api/text")
async def text_response(request):
    """PlainTextResponse example."""
    return PlainTextResponse("This is a plain text response")


@app.get("/api/stream")
async def stream_response(request):
    """StreamingResponse example."""
    async def generate():
        for i in range(10):
            yield f"Line {i}\n"
    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/api/redirect")
async def redirect_response(request):
    """RedirectResponse example."""
    return RedirectResponse("https://example.com")


@app.get("/template")
async def template_response(request):
    """Jinja2 template example."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "AltAPI Templates", "user": "Guest"}
    )


# Additional non-blocking endpoints for benchmark

@app.get("/api/ping")
async def ping(request):
    """Simple ping endpoint."""
    return JSONResponse({"status": "pong"})


@app.get("/api/status")
async def status(request):
    """Status endpoint."""
    return JSONResponse({"healthy": True, "version": "0.1.0"})


@app.post("/api/data")
async def post_data(request):
    """POST data endpoint."""
    data = await request.json()
    return JSONResponse({"received": True, "keys": list(data.keys())})


@app.get("/api/sum/{a:int}/{b:int}")
async def sum_numbers(request):
    """Sum two numbers."""
    a = request.path_params["a"]
    b = request.path_params["b"]
    return JSONResponse({"a": a, "b": b, "sum": a + b})


@app.get("/api/multiply/{x:float}/{y:float}")
async def multiply(request):
    """Multiply two floats."""
    x = request.path_params["x"]
    y = request.path_params["y"]
    return JSONResponse({"x": x, "y": y, "result": x * y})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, workers=2)
