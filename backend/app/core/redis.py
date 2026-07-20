import logging
import uuid
import time
import asyncio
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = None
        self.url = settings.REDIS_URL

    async def connect(self):
        current_loop = asyncio.get_running_loop()
        if getattr(self, "_loop", None) != current_loop:
            if self.client:
                try:
                    await self.client.aclose()
                except Exception:
                    pass
                self.client = None
            self._loop = current_loop

        if not self.client:
            try:
                self.client = aioredis.from_url(self.url, decode_responses=True)
                # Test connection
                await self.client.ping()
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Dashboard caching will be disabled.")
                self.client = None

    async def get(self, key: str) -> str | None:
        await self.connect()
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    async def set(self, key: str, value: str, ex: int = 300) -> bool:
        await self.connect()
        if not self.client:
            return False
        try:
            await self.client.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        await self.connect()
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        await self.connect()
        if not self.client:
            return 0
        try:
            count = 0
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
                count += 1
            return count
        except Exception as e:
            logger.warning(f"Redis delete_pattern failed: {e}")
            return 0
    @asynccontextmanager
    async def lock(self, lock_name: str, lease_time: int = 60, acquire_timeout: float = 10.0):
        """
        Redis-based distributed lock context manager.
        """
        await self.connect()
        if not self.client:
            logger.warning(f"Redis client not connected. Proceeding without lock for '{lock_name}'.")
            yield True
            return

        lock_key = f"lock:{lock_name}"
        token = uuid.uuid4().hex
        end_time = time.time() + acquire_timeout
        acquired = False

        while time.time() < end_time:
            # Try to acquire lock
            res = await self.client.set(lock_key, token, nx=True, ex=lease_time)
            if res:
                acquired = True
                break
            await asyncio.sleep(0.1)

        if not acquired:
            logger.info(f"Could not acquire lock for '{lock_name}'. Skipping execution.")
            yield False
            return

        try:
            logger.info(f"Acquired lock '{lock_key}' with token '{token}'.")
            yield True
        finally:
            # Atomic release using Lua script
            try:
                lua_release = """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                    return redis.call('del', KEYS[1])
                else
                    return 0
                end
                """
                await self.client.eval(lua_release, 1, lock_key, token)
                logger.info(f"Released lock '{lock_key}' for token '{token}'.")
            except Exception as e:
                logger.error(f"Error releasing lock '{lock_key}': {e}")

# Global instance
redis_client = RedisClient()

