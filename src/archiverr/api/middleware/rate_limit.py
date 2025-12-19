"""
Rate Limiting Middleware for FastAPI

Features:
- In-memory token bucket rate limiting
- Configurable per-endpoint limits
- Bypass for health endpoints
- Rate limit headers in responses

Usage:
    app.add_middleware(RateLimitMiddleware, limiter=RateLimiter())
"""

import asyncio
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    # Default limits (requests per minute)
    default_rpm: int = 60

    # Endpoint-specific limits (requests per minute)
    endpoint_limits: dict[str, int] = field(default_factory=lambda: {
        "/api/v1/run": 10,        # Run execution - expensive
        "/api/v1/run/async": 10,  # Async run
        "/api/v1/run/targets": 10,
        "/api/v1/run/config": 10,
    })

    # Endpoints to bypass rate limiting
    bypass_endpoints: set[str] = field(default_factory=lambda: {
        "/api/v1/system/health",
        "/api/v1/system/info",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    })

    # Window size in seconds
    window_seconds: int = 60

    # Enable/disable rate limiting
    enabled: bool = True


class TokenBucket:
    """Token bucket rate limiter for a single client."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum tokens (burst capacity)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Returns:
            True if tokens consumed, False if rate limited
        """
        async with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    @property
    def remaining(self) -> int:
        """Get remaining tokens."""
        return int(self.tokens)


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.
    
    Thread-safe, per-client rate limiting with configurable limits.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

        # Check environment for enabled flag
        env_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower()
        self.config.enabled = env_enabled in ("true", "1", "yes")

    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier."""
        # Use X-Forwarded-For if behind proxy, otherwise use client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit_for_path(self, path: str) -> int:
        """Get rate limit for specific path."""
        # Check exact match first
        if path in self.config.endpoint_limits:
            return self.config.endpoint_limits[path]

        # Check prefix match (for paths with parameters)
        for prefix, limit in self.config.endpoint_limits.items():
            if path.startswith(prefix):
                return limit

        return self.config.default_rpm

    def _should_bypass(self, path: str) -> bool:
        """Check if path should bypass rate limiting."""
        if not self.config.enabled:
            return True

        # Exact match
        if path in self.config.bypass_endpoints:
            return True

        # Prefix match for docs
        return any(path.startswith(bypass) for bypass in self.config.bypass_endpoints)

    async def is_allowed(self, request: Request) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (allowed, remaining, limit)
        """
        path = request.url.path.rstrip("/") or "/"

        # Check bypass
        if self._should_bypass(path):
            return True, -1, -1

        client_key = self._get_client_key(request)
        limit_rpm = self._get_limit_for_path(path)
        bucket_key = f"{client_key}:{path}"

        async with self._lock:
            if bucket_key not in self._buckets:
                # Create bucket: capacity = limit, refill = limit/60 per second
                self._buckets[bucket_key] = TokenBucket(
                    capacity=limit_rpm,
                    refill_rate=limit_rpm / 60.0
                )

        bucket = self._buckets[bucket_key]
        allowed = await bucket.consume()

        return allowed, bucket.remaining, limit_rpm

    async def cleanup_old_buckets(self):
        """Clean up old unused buckets to prevent memory leak."""
        async with self._lock:
            # Remove buckets that are at full capacity (haven't been used recently)
            now = time.monotonic()
            to_remove = []

            for key, bucket in self._buckets.items():
                # If bucket is full and hasn't been used in 5 minutes
                if bucket.tokens >= bucket.capacity and (now - bucket.last_refill) > 300:
                    to_remove.append(key)

            for key in to_remove:
                del self._buckets[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Adds rate limiting headers to all responses:
    - X-RateLimit-Limit: Maximum requests per window
    - X-RateLimit-Remaining: Remaining requests in window
    - X-RateLimit-Reset: Seconds until window resets
    """

    def __init__(self, app, limiter: RateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiter."""
        allowed, remaining, limit = await self.limiter.is_allowed(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Limit: {limit} requests per minute.",
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "60",
                    "Retry-After": "60"
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers (only if not bypassed)
        if remaining >= 0:
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = "60"

        return response
