import json
from collections import defaultdict

from fastapi import WebSocket


class CollaborationHub:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self.presence: dict[str, dict[str, dict]] = defaultdict(dict)

    async def connect(self, project_id: str, websocket: WebSocket, user: dict) -> None:
        await websocket.accept()
        self.rooms[project_id].add(websocket)
        self.presence[project_id][user["id"]] = {
            "user_id": user["id"],
            "display_name": user.get("display_name", user["username"]),
            "role": user["role"],
        }
        await self.broadcast(project_id, {
            "type": "presence.changed",
            "users": list(self.presence[project_id].values()),
        })

    async def disconnect(self, project_id: str, websocket: WebSocket, user: dict) -> None:
        self.rooms[project_id].discard(websocket)
        self.presence[project_id].pop(user["id"], None)
        await self.broadcast(project_id, {
            "type": "presence.changed",
            "users": list(self.presence[project_id].values()),
        })

    async def broadcast(self, project_id: str, message: dict) -> None:
        stale = []
        payload = json.dumps(message, ensure_ascii=False, default=str)
        for websocket in list(self.rooms[project_id]):
            try:
                await websocket.send_text(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.rooms[project_id].discard(websocket)


collaboration_hub = CollaborationHub()
