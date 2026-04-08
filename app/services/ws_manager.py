from typing import Any
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
    
    async def connect(self, event_id: int, websocket: WebSocket):
        await websocket.accept()
        if event_id not in self.active_connections:
            self.active_connections[event_id] = []
        self.active_connections[event_id].append(websocket)
    
    def disconnect(self, event_id: int, websocket: WebSocket):
        if event_id in self.active_connections:
            self.active_connections[event_id].remove(websocket)
            if not self.active_connections[event_id]:
                del self.active_connections[event_id]
    
    async def broadcast(self, event_id: int, message: Any):
        if event_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[event_id]:
                try:
                    if isinstance(message, dict):
                        await connection.send_json(message)
                    else:
                        await connection.send_text(str(message))
                except Exception:
                    disconnected.append(connection)
            
            for ws in disconnected:
                self.disconnect(event_id, ws)


ws_manager = WSManager()