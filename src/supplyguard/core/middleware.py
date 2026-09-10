import time
from uuid import uuid4

import structlog
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from supplyguard.core.logging import log

REQUESTS = Counter("supplyguard_http_requests_total", "Requests", ["method", "path", "status"])
LATENCY = Histogram("supplyguard_http_request_seconds", "Request latency", ["method", "path"])


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add correlation IDs, request logs, and latency metrics around every request."""

    async def dispatch(self, request, call_next):
        """Run the request while guaranteeing metrics and context cleanup on failure."""
        request_id = request.headers.get("x-request-id") or str(uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, method=request.method,
                                               path=request.url.path)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            REQUESTS.labels(request.method, request.url.path, str(status)).inc()
            LATENCY.labels(request.method, request.url.path).observe(elapsed)
            log.info("request_completed", status=status, duration_ms=round(elapsed * 1000, 2))
            structlog.contextvars.clear_contextvars()
