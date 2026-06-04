import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Also bind path and method
        structlog.contextvars.bind_contextvars(
            method=request.method, path=request.url.path
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
