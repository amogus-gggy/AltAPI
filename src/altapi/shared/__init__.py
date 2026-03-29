"""
Shared manager module for multi-worker cache and rate limiting.

This module provides a central manager process that handles state
for cache and rate limiting across multiple worker processes.

Usage:
    # Start manager process
    from altapi.shared import start_manager, ManagerConnection

    manager_proc = start_manager()

    # Use in application
    conn = ManagerConnection()
    await conn.connect()

    cache = SharedCacheBackend(conn)
    ratelimit = SharedRateLimitStorage(conn)
"""

import multiprocessing
from typing import Optional

from .manager import SharedManager, run_manager
from .client import ManagerConnection, SharedCacheBackend, SharedRateLimitStorage
from .protocol import (
    MSG_PING, MSG_PONG, MSG_SHUTDOWN,
    MSG_CACHE_GET, MSG_CACHE_SET, MSG_CACHE_DELETE, MSG_CACHE_CLEAR,
    MSG_RATELIMIT_CHECK, MSG_RATELIMIT_INCREMENT,
)


def start_manager(
    host: str = "127.0.0.1",
    port: int = 58000,
    max_cache_size: int = 10000,
    cleanup_interval: int = 60,
    daemon: bool = True,
) -> multiprocessing.Process:
    """
    Start the shared manager as a separate process.

    Args:
        host: Host to bind to
        port: Port to listen on
        max_cache_size: Maximum number of cache entries
        cleanup_interval: Interval for cleanup in seconds
        daemon: Whether to run as daemon process

    Returns:
        Started process instance
    """
    process = multiprocessing.Process(
        target=run_manager,
        kwargs={
            "host": host,
            "port": port,
            "max_cache_size": max_cache_size,
            "cleanup_interval": cleanup_interval,
        },
        name="AltAPI-Shared-Manager",
        daemon=daemon,
    )
    process.start()
    return process


def stop_manager(process: multiprocessing.Process) -> None:
    """
    Stop the shared manager process.

    Args:
        process: Manager process to stop
    """
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()


__all__ = [
    # Manager
    "SharedManager",
    "run_manager",
    "start_manager",
    "stop_manager",
    # Client
    "ManagerConnection",
    "SharedCacheBackend",
    "SharedRateLimitStorage",
    # Protocol constants
    "MSG_PING",
    "MSG_PONG",
    "MSG_SHUTDOWN",
    "MSG_CACHE_GET",
    "MSG_CACHE_SET",
    "MSG_CACHE_DELETE",
    "MSG_CACHE_CLEAR",
    "MSG_RATELIMIT_CHECK",
    "MSG_RATELIMIT_INCREMENT",
]
