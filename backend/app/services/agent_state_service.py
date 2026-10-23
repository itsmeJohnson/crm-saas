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
        allowed_states = {"IDLE", "RINGING", "ACTIVE_CALLING", "ON_CALL", "BREAK", "OFFLINE"}
        if state not in allowed_states:
            raise ValueError(f"Invalid state: {state}. Allowed states: {allowed_states}")
        
        key = self._get_key(org_id, user_id)
        payload = {
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        await redis_client.set(key, json.dumps(payload), ex=86400)
        if state == "OFFLINE":
            await redis_client.srem(f"org:{org_id}:active_agents", str(user_id))
        else:
            await redis_client.sadd(f"org:{org_id}:active_agents", str(user_id))

        # Real-time WebSocket state notification
        try:
            from app.api.v1.telephony import ws_manager
            msg = {
                "event": "agent_state_changed",
                "user_id": str(user_id),
                "state": state,
                "timestamp": payload["timestamp"],
                "metadata": payload["metadata"]
            }
            # Notify the agent and active connections
            if str(user_id) in ws_manager.active_connections:
                await ws_manager.send_personal_message(msg, str(user_id))
        except Exception:
            pass

        return payload

    async def list_org_agent_states(self, org_id: str | uuid.UUID) -> dict[str, dict]:
        """Fetch real-time states of all active floor agents for the live War Room monitor."""
        members = await redis_client.smembers(f"org:{org_id}:active_agents")
        results = {}
        for m in members:
            uid = m.decode() if isinstance(m, bytes) else str(m)
            st = await self.get_agent_state(org_id, uid)
            results[uid] = st
        return results
