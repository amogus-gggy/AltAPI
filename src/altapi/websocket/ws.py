import json
from enum import Enum
from typing import Dict, Callable, Any, Optional, Iterable


class WebSocketState(Enum):
    """WebSocket connection state."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class WebSocket:
    """WebSocket connection handler."""

    def __init__(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
        path_params: Optional[Dict[str, Any]] = None,
    ):
        self.scope = scope
        self._receive = receive
        self._send = send
        self.path = scope.get("path", "/")
        self.headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        self.path_params = path_params or {}
        self._state = WebSocketState.CONNECTING

    @property
    def state(self) -> WebSocketState:
        """Get current connection state."""
        return self._state

    async def receive(self) -> Dict[str, Any]:
        """
        Receive ASGI websocket messages, ensuring valid state transitions.
        """
        if self._state == WebSocketState.CONNECTING:
            message = await self._receive()
            message_type = message["type"]
            if message_type != "websocket.connect":
                raise RuntimeError(
                    f'Expected ASGI message "websocket.connect", but got {message_type!r}'
                )
            # Stay in CONNECTING until the application explicitly accepts.
            # This mirrors Starlette/FastAPI semantics: the connect event is received,
            # but the handshake isn't complete until we send "websocket.accept".
            return message
        elif self._state == WebSocketState.CONNECTED:
            message = await self._receive()
            message_type = message["type"]
            if message_type not in {"websocket.receive", "websocket.disconnect"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.receive" or "websocket.disconnect", but got {message_type!r}'
                )
            if message_type == "websocket.disconnect":
                self._state = WebSocketState.DISCONNECTED
            return message
        else:
            raise RuntimeError(
                'Cannot call "receive" once a disconnect message has been received.'
            )

    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send ASGI websocket messages, ensuring valid state transitions.
        """
        if self._state == WebSocketState.CONNECTING:
            message_type = message["type"]
            if message_type not in {"websocket.accept", "websocket.close"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.accept" or "websocket.close", but got {message_type!r}'
                )
            if message_type == "websocket.close":
                self._state = WebSocketState.DISCONNECTED
            else:
                self._state = WebSocketState.CONNECTED
            await self._send(message)
        elif self._state == WebSocketState.CONNECTED:
            message_type = message["type"]
            if message_type not in {"websocket.send", "websocket.close"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.send" or "websocket.close", but got {message_type!r}'
                )
            if message_type == "websocket.close":
                self._state = WebSocketState.DISCONNECTED
            try:
                await self._send(message)
            except OSError:
                self._state = WebSocketState.DISCONNECTED
                raise RuntimeError("WebSocket disconnected")
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol: Optional[str] = None,
        headers: Optional[Iterable[tuple[bytes, bytes]]] = None,
    ) -> None:
        headers = headers or []

        if self._state == WebSocketState.CONNECTING:
            # If we haven't yet seen the 'connect' message, then wait for it first.
            await self.receive()
        await self.send(
            {"type": "websocket.accept", "subprotocol": subprotocol, "headers": headers}
        )

    def _raise_on_disconnect(self, message: Dict[str, Any]) -> None:
        if message["type"] == "websocket.disconnect":
            raise RuntimeError(
                f"WebSocket disconnected with code {message.get('code', 1000)}"
            )

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        await self.send(
            {"type": "websocket.close", "code": code, "reason": reason or ""}
        )

    async def send_text(self, data: str) -> None:
        """Send text data over the WebSocket."""
        if self._state == WebSocketState.CONNECTING:
            await self.accept()
        await self.send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        """Send binary data over the WebSocket."""
        if self._state == WebSocketState.CONNECTING:
            await self.accept()
        await self.send({"type": "websocket.send", "bytes": data})

    async def send_json(self, data: Any) -> None:
        """Send JSON data over the WebSocket."""
        if self._state == WebSocketState.CONNECTING:
            await self.accept()
        await self.send_text(json.dumps(data))

    async def receive_text(self) -> str:
        """Receive text data from the WebSocket."""
        if self._state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )

        while True:
            message = await self._receive()
            if message["type"] == "websocket.disconnect":
                self._state = WebSocketState.DISCONNECTED
                raise RuntimeError(
                    f"WebSocket disconnected with code {message.get('code', 1000)}"
                )
            elif message["type"] == "websocket.receive":
                text = message.get("text")
                if text:
                    return text

                continue

    async def receive_bytes(self) -> bytes:
        if self._state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )

        while True:
            message = await self._receive()
            if message["type"] == "websocket.disconnect":
                self._state = WebSocketState.DISCONNECTED
                raise RuntimeError(
                    f"WebSocket disconnected with code {message.get('code', 1000)}"
                )
            elif message["type"] == "websocket.receive":
                data = message.get("bytes")
                if data:
                    return data
                continue

    async def receive_json(self) -> Any:
        """Receive JSON data from the WebSocket."""
        text = await self.receive_text()
        return json.loads(text)

    async def __aiter__(self):
        """Iterate over incoming messages."""
        while self._state != WebSocketState.DISCONNECTED:
            try:
                message = await self.receive()
                if message["type"] == "websocket.disconnect":
                    self._state = WebSocketState.DISCONNECTED
                    break
                if message["type"] == "websocket.receive":
                    yield message
            except Exception:
                break
