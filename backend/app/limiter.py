"""
Rate Limiter Configuration for FastAPI using SlowAPI.
Uses an in-memory storage strategy suitable for single-instance / spark deployments.

Architecture Note:
- In-memory rate limiting tracks IP buckets in local process memory.
- Suitable for single-instance student/coursework evaluations.
- For high-availability multi-instance production environments, configure a shared
  Redis backend store via: Limiter(key_func=..., storage_uri="redis://redis-host:6379").
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize in-memory rate limiter keyed by remote client IP address
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
)
