import time
import logging
from collections import defaultdict
from threading import Lock
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from app.core.config import settings

logger = logging.getLogger("rate_limiter")

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limit_per_minute: int = 120):
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        # Local memory storage as fallback
        self.memory_store = defaultdict(list)
        self.lock = Lock()
        
        # Redis connection setup
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        try:
            import redis
            # Retrieve Redis URL or host details
            redis_url = settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
            self.redis_client = redis.from_url(redis_url, socket_timeout=1.0)
            # Test ping
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Could not initialize Redis connection for Rate Limiter: {e}. Falling back to in-memory tracking.")
            self.redis_client = None

    async def dispatch(self, request: Request, call_next):
        # Allow health checks and docs to bypass rate limiting
        path = request.url.path
        if path.startswith("/health") or path.startswith("/api/v1/health") or path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown-ip"
        current_time = time.time()
        
        is_allowed = True
        
        # Try Redis first if available
        if self.redis_client:
            try:
                key = f"rate_limit:{client_ip}:{int(current_time) // 60}"
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, 60)
                request_count, _ = pipe.execute()
                if request_count > self.limit_per_minute:
                    is_allowed = False
            except Exception as e:
                logger.error(f"Redis rate limiting error: {e}. Falling back to in-memory.")
                is_allowed = self._check_memory_limit(client_ip, current_time)
        else:
            is_allowed = self._check_memory_limit(client_ip, current_time)

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again in a minute."}
            )

        return await call_next(request)

    def _check_memory_limit(self, client_ip: str, current_time: float) -> bool:
        with self.lock:
            # Clean old requests (older than 60s)
            self.memory_store[client_ip] = [t for t in self.memory_store[client_ip] if current_time - t < 60]
            if len(self.memory_store[client_ip]) >= self.limit_per_minute:
                return False
            self.memory_store[client_ip].append(current_time)
            return True
