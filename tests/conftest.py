"""Shared pytest fixtures."""

import pytest

from altapi.ratelimit.storage import InMemoryRateLimitStorage


@pytest.fixture
def reset_rate_limit_storage():
    """Use in-memory rate limiting and reset global storage between tests."""
    import altapi.ratelimit.limit as limit_mod

    limit_mod.use_shared_memory(False)
    limit_mod.set_storage(InMemoryRateLimitStorage())
    yield
    limit_mod.set_storage(None)
    limit_mod.use_shared_memory(True)
