import json
import uuid
from datetime import datetime, timezone
from app.core.redis import redis_client

class AgentStateService:
    @staticmethod
    def _get_key(org_id: str | uuid.UUID, user_id: str | uuid.UUID) -> str:
        return f"org:{org_id}:agent:{user_id}:state"

    async def get_agent_state(self, org_id: str | uuid.UUID, user_id: str | uuid.UUID) -> dict:
        key = self._get_key(org_id, user_id)
        data = await redis_client.get(key)
        if not data:
            return {
                "state": "IDLE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {}
            }
        try:
            return json.loads(data)
        except Exception:
            return {
                "state": "IDLE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {}
            }

    async def set_agent_state(
        self, 
        org_id: str | uuid.UUID, 
        user_id: str | uuid.UUID, 
        state: str, 
        metadata: dict = None
    ) -> dict:
        allowed_states = {"IDLE", "ACTIVE_CALLING", "BREAK"}
        if state not in allowed_states:
            raise ValueError(f"Invalid state: {state}. Allowed states: {allowed_states}")
        
        key = self._get_key(org_id, user_id)
        payload = {
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        await redis_client.set(key, json.dumps(payload), ex=86400)
        return payload
