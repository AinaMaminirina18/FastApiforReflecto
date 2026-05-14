from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from typing import List
import asyncio
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ESP32-CAM WebSocket Stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins= {'*'}, #adresse du frontend
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
# Gestion des connexions
class ConnectionManager:
    def __init__(self):
        # Clients Web qui regardent le stream
        self.active_connections: List[WebSocket] = []
        self.latest_frame = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_frame(self, frame: bytes):
        self.latest_frame = frame
        # Envoie l'image à tous les navigateurs connectés
        for connection in self.active_connections:
            try:
                await connection.send_bytes(frame)
            except Exception:
                # Supprime la connexion si elle est instable
                self.active_connections.remove(connection)

manager = ConnectionManager()

# --- Endpoint pour l'ESP32 ---
@app.websocket("/ws/esp32")
async def websocket_endpoint_esp32(websocket: WebSocket):
    await websocket.accept()
    print("✅ ESP32 Connecté via WebSocket")
    try:
        while True:
            # Reçoit les données binaires directement
            data = await websocket.receive_bytes()
            if len(data) > 1000:
                await manager.broadcast_frame(data)
    except WebSocketDisconnect:
        print("❌ ESP32 Déconnecté")

# --- Endpoint pour l'App Web ---
@app.websocket("/ws/web")
async def websocket_endpoint_web(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # On attend juste pour maintenir la connexion ouverte
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- Conservation du Snapshot (Optionnel) ---
@app.get("/snapshot")
async def snapshot():
    if manager.latest_frame is None:
        return {"message": "Aucune image reçue"}
    return Response(content=manager.latest_frame, media_type="image/jpeg")
