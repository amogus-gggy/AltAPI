"""
Protocol definitions for shared manager communication.

Defines message types and serialization for IPC between workers and manager.
"""

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Union


# Message types
MSG_PING = "ping"
MSG_PONG = "pong"
MSG_SHUTDOWN = "shutdown"

# Cache operations
MSG_CACHE_GET = "cache_get"
MSG_CACHE_SET = "cache_set"
MSG_CACHE_DELETE = "cache_delete"
MSG_CACHE_CLEAR = "cache_clear"

# Rate limit operations
MSG_RATELIMIT_CHECK = "ratelimit_check"
MSG_RATELIMIT_INCREMENT = "ratelimit_increment"

# Error handling
MSG_ERROR = "error"


@dataclass
class Request:
    """Request message sent to manager."""
    type: str
    data: Dict[str, Any]
    request_id: Optional[str] = None

    def to_bytes(self) -> bytes:
        """Serialize request to bytes with length prefix."""
        data = json.dumps(asdict(self)).encode('utf-8')
        # 4-byte length prefix (big-endian)
        length = len(data)
        return length.to_bytes(4, 'big') + data

    @classmethod
    def from_bytes(cls, data: bytes) -> 'Request':
        """Deserialize request from bytes."""
        obj = json.loads(data.decode('utf-8'))
        return cls(**obj)


@dataclass
class Response:
    """Response message from manager."""
    type: str
    data: Dict[str, Any]
    request_id: Optional[str] = None
    error: Optional[str] = None

    def to_bytes(self) -> bytes:
        """Serialize response to bytes with length prefix."""
        data = json.dumps(asdict(self)).encode('utf-8')
        length = len(data)
        return length.to_bytes(4, 'big') + data

    @classmethod
    def from_bytes(cls, data: bytes) -> 'Response':
        """Deserialize response from bytes."""
        obj = json.loads(data.decode('utf-8'))
        return cls(**obj)


def create_request(msg_type: str, **data) -> Request:
    """Create a request with auto-generated request_id."""
    import uuid
    return Request(
        type=msg_type,
        data=data,
        request_id=str(uuid.uuid4())
    )


def create_response(req: Request, data: Dict[str, Any], error: Optional[str] = None) -> Response:
    """Create a response for a request."""
    return Response(
        type=req.type,
        data=data,
        request_id=req.request_id,
        error=error
    )
