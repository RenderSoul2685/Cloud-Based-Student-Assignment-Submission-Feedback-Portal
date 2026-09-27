"""
Pytest configuration and global fixtures.
Resets the in-memory SlowAPI rate limiter before and after each test function.
"""
import pytest
from backend.app.limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter_for_test():
    """Ensures in-memory rate limit buckets are reset between test runs."""
    limiter.reset()
    yield
    limiter.reset()
