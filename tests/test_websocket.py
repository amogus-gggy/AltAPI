"""Tests for altapi.websocket.ws."""

import pytest

from altapi.websocket.ws import WebSocket, WebSocketState


@pytest.mark.asyncio
async def test_websocket_accept_and_text():
    messages = [
        {"type": "websocket.connect"},
    ]
    sent = []

    async def receive():
        return messages.pop(0)

    async def send(m):
        sent.append(m)

    ws = WebSocket({"type": "websocket", "path": "/ws", "headers": []}, receive, send, {})
    await ws.accept()
    await ws.send_text("hi")
    assert ws.state == WebSocketState.CONNECTED
    assert any(m["type"] == "websocket.accept" for m in sent)
    assert any(m.get("text") == "hi" for m in sent if m["type"] == "websocket.send")


@pytest.mark.asyncio
async def test_receive_text_after_messages():
    seq = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "text": "hello"},
    ]

    async def receive():
        return seq.pop(0) if seq else {"type": "websocket.disconnect", "code": 1000}

    sent = []

    async def send(m):
        sent.append(m)

    ws = WebSocket({"type": "websocket", "path": "/", "headers": []}, receive, send)
    await ws.accept()
    text = await ws.receive_text()
    assert text == "hello"


def test_websocket_state_enum():
    assert WebSocketState.CONNECTING.value == 0
