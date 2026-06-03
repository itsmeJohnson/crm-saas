import logging
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = None
        self.url = settings.REDIS_URL

    async def connect(self):
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

# Global instance
redis_client = RedisClient()
