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
        # Allow health checks, docs, and test environment to bypass rate limiting
        import os
        if os.getenv("TESTING") == "true":
            return await call_next(request)

        path = request.url.path
        if path.startswith("/health") or path.startswith("/api/v1/health") or path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Behind the nginx proxy the real client IP is in X-Forwarded-For (first hop);
        # fall back to the direct peer when there's no proxy.
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            client_ip = fwd.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown-ip"
        current_time = time.time()

        # Sensitive auth endpoints get a much tighter per-IP budget to blunt
        # brute-force / credential-stuffing and signup abuse.
        auth_sensitive = path in (
            "/api/v1/auth/login",
            "/api/v1/auth/public-register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/mfa/verify",
        )
        effective_limit = 10 if auth_sensitive else self.limit_per_minute
        bucket = "auth" if auth_sensitive else "gen"

        # Authenticated traffic is budgeted PER USER, not per IP. Keying on IP
        # alone means every user behind one office NAT / proxy shares a single
        # budget, so a handful of colleagues throttle each other. Auth-sensitive
        # endpoints stay per-IP on purpose — that bucket exists to blunt
        # credential stuffing, where the attacker controls the identity claim.
        identity = client_ip
        if not auth_sensitive:
            user_id = self._user_from_token(request)
            if user_id:
                identity = f"u:{user_id}"
                bucket = "user"

        is_allowed = True

        # Try Redis first if available — fail-closed on outage (prevents per-instance bypass)
        if self.redis_client:
            try:
                key = f"rate_limit:{bucket}:{identity}:{int(current_time) // 60}"
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, 60)
                request_count, _ = pipe.execute()
                if request_count > effective_limit:
                    is_allowed = False
            except Exception as e:
                logger.error(f"Redis rate limiting unavailable: {e}. Returning 503 to prevent bypass.")
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Service temporarily unavailable. Please retry shortly."}
                )
        else:
            # No Redis configured — in-memory fallback (dev/single-instance only)
            is_allowed = self._check_memory_limit(f"{bucket}:{identity}", current_time, effective_limit)

        if not is_allowed:
            # Seconds remaining in the current fixed minute window. Clients (and
            # our own frontend) need Retry-After to back off correctly instead of
            # hammering a throttled endpoint.
            retry_after = max(1, 60 - int(current_time % 60))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again in a minute."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(effective_limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return await call_next(request)

    @staticmethod
    def _user_from_token(request) -> str | None:
        """Resolve the caller's user id from a VERIFIED bearer token.

        Verification matters: an unverified `sub` claim would let anyone mint
        arbitrary identities and sidestep the limit entirely. On any failure we
        return None and the caller falls back to the per-IP budget.
        """
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return None
        try:
            import jwt as _jwt
            from app.core.config import settings as _s
            payload = _jwt.decode(auth[7:].strip(), _s.JWT_SECRET_KEY,
                                  algorithms=[_s.JWT_ALGORITHM])
            sub = payload.get("sub")
            return str(sub) if sub else None
        except Exception:
            return None

    def _check_memory_limit(self, client_ip: str, current_time: float, limit: int | None = None) -> bool:
        limit = limit if limit is not None else self.limit_per_minute
        with self.lock:
            # Clean old requests (older than 60s)
            self.memory_store[client_ip] = [t for t in self.memory_store[client_ip] if current_time - t < 60]
            if len(self.memory_store[client_ip]) >= limit:
                return False
            self.memory_store[client_ip].append(current_time)
            return True
