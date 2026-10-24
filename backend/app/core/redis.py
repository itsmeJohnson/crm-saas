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
        self._memory_store = {}  # key -> (value, expire_timestamp)
        self._memory_sets = {}   # key -> set of values
        self._last_connect_attempt = 0

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
            now = time.time()
            if now - self._last_connect_attempt < 30:
                return  # Skip reconnect spam during cooldown
            self._last_connect_attempt = now
            try:
                self.client = aioredis.from_url(self.url, decode_responses=True)
                # Test connection
                await self.client.ping()
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. In-memory fallback cache enabled.")
                self.client = None

    async def get(self, key: str) -> str | None:
        await self.connect()
        if self.client:
            try:
                val = await self.client.get(key)
                if val is not None:
                    return val
            except Exception as e:
                logger.warning(f"Redis get failed: {e}. Falling back to memory.")
        
        # In-memory fallback
        item = self._memory_store.get(key)
        if item:
            val, expire_at = item
            if expire_at is None or time.time() <= expire_at:
                return val
            else:
                self._memory_store.pop(key, None)
        return None

    async def set(self, key: str, value: str, ex: int = 300) -> bool:
        await self.connect()
        # Always store in memory cache as resilient backup
        expire_at = time.time() + ex if ex else None
        self._memory_store[key] = (value, expire_at)
        
        if not self.client:
            return True
        try:
            await self.client.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed: {e}. Saved in memory fallback.")
            return True

    async def delete(self, key: str) -> bool:
        await self.connect()
        self._memory_store.pop(key, None)
        self._memory_sets.pop(key, None)
        if not self.client:
            return True
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return True

    async def delete_pattern(self, pattern: str) -> int:
        await self.connect()
        import fnmatch
        count = 0
        keys_to_del = [k for k in self._memory_store if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_del:
            self._memory_store.pop(k, None)
            count += 1
            
        if not self.client:
            return count
        try:
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
                count += 1
            return count
        except Exception as e:
            logger.warning(f"Redis delete_pattern failed: {e}")
            return count

    async def sadd(self, key: str, *values) -> int:
        await self.connect()
        if key not in self._memory_sets:
            self._memory_sets[key] = set()
        for v in values:
            self._memory_sets[key].add(str(v))
            
        if not self.client:
            return len(values)
        try:
            return await self.client.sadd(key, *values)
        except Exception as e:
            logger.warning(f"Redis sadd failed: {e}")
            return len(values)

    async def srem(self, key: str, *values) -> int:
        await self.connect()
        if key in self._memory_sets:
            for v in values:
                self._memory_sets[key].discard(str(v))
                
        if not self.client:
            return len(values)
        try:
            return await self.client.srem(key, *values)
        except Exception as e:
            logger.warning(f"Redis srem failed: {e}")
            return len(values)

    async def smembers(self, key: str) -> set:
        await self.connect()
        if self.client:
            try:
                return await self.client.smembers(key)
            except Exception as e:
                logger.warning(f"Redis smembers failed: {e}. Falling back to memory.")
        return set(self._memory_sets.get(key, set()))

    async def ping(self) -> bool:
        await self.connect()
        if not self.client:
            return True  # Memory fallback is alive
        try:
            return await self.client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return True
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

