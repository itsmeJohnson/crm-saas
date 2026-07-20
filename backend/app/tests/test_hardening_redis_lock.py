import pytest
import asyncio
import time
from app.core.redis import redis_client

@pytest.mark.asyncio
async def test_redis_distributed_lock_basic():
    # Test that we can acquire the lock
    async with redis_client.lock("test_lock_1", lease_time=10, acquire_timeout=1.0) as locked1:
        assert locked1 is True
        
        # Test that concurrent lock requests on the same key fail/block
        async with redis_client.lock("test_lock_1", lease_time=10, acquire_timeout=0.2) as locked2:
            assert locked2 is False

    # After exiting locked1 block, lock should be released and acquirable again
    async with redis_client.lock("test_lock_1", lease_time=10, acquire_timeout=1.0) as locked3:
        assert locked3 is True


@pytest.mark.asyncio
async def test_redis_distributed_lock_expiration():
    # Test lease time expiration
    async with redis_client.lock("test_lock_expire", lease_time=1, acquire_timeout=1.0) as locked1:
        assert locked1 is True
        # Sleep slightly longer than lease time (1.2 seconds) to let it expire
        await asyncio.sleep(1.2)
        
        # Now we should be able to acquire it since the first one expired
        async with redis_client.lock("test_lock_expire", lease_time=10, acquire_timeout=1.0) as locked2:
            assert locked2 is True
            
        # We manually release locked2 inside its context block, so outside of it, it's released
    
    # Try once more
    async with redis_client.lock("test_lock_expire", lease_time=10, acquire_timeout=1.0) as locked3:
        assert locked3 is True
