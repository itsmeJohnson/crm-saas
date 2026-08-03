import json
import uuid
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


def _get_cf_key(org_id: uuid.UUID, module: str) -> str:
    return f"tenant_metadata:{org_id}:custom_fields:{module}"


def _get_pipeline_key(org_id: uuid.UUID) -> str:
    return f"tenant_metadata:{org_id}:pipelines"


class MetadataCacheService:
    @staticmethod
    async def get_custom_fields(org_id: uuid.UUID, module: str) -> list[dict[str, Any]] | None:
        key = _get_cf_key(org_id, module)
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.warning(f"Failed to parse cached custom fields for key {key}: {e}")
        return None

    @staticmethod
    async def set_custom_fields(org_id: uuid.UUID, module: str, definitions: list[dict[str, Any]]) -> None:
        key = _get_cf_key(org_id, module)
        try:
            await redis_client.set(key, json.dumps(definitions), ex=CACHE_TTL)
        except Exception as e:
            logger.warning(f"Failed to set cached custom fields for key {key}: {e}")

    @staticmethod
    async def invalidate_custom_fields(org_id: uuid.UUID, module: str) -> None:
        key = _get_cf_key(org_id, module)
        await redis_client.delete(key)

    @staticmethod
    async def get_pipelines(org_id: uuid.UUID) -> list[dict[str, Any]] | None:
        key = _get_pipeline_key(org_id)
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.warning(f"Failed to parse cached pipelines for key {key}: {e}")
        return None

    @staticmethod
    async def set_pipelines(org_id: uuid.UUID, pipelines: list[dict[str, Any]]) -> None:
        key = _get_pipeline_key(org_id)
        try:
            await redis_client.set(key, json.dumps(pipelines), ex=CACHE_TTL)
        except Exception as e:
            logger.warning(f"Failed to set cached pipelines for key {key}: {e}")

    @staticmethod
    async def invalidate_pipelines(org_id: uuid.UUID) -> None:
        key = _get_pipeline_key(org_id)
        await redis_client.delete(key)

    @staticmethod
    async def increment_metadata_version(db: AsyncSession, org_id: uuid.UUID) -> None:
        from sqlalchemy import update
        from app.models.organization import Organization
        await db.execute(
            update(Organization)
            .filter(Organization.id == org_id)
            .values(metadata_version=Organization.metadata_version + 1)
        )

