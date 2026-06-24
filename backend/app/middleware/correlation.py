import uuid
from contextvars import ContextVar
from fastapi import Request

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
    if not corr_id:
        corr_id = uuid.uuid4().hex

    token = correlation_id_ctx.set(corr_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    finally:
        correlation_id_ctx.reset(token)
