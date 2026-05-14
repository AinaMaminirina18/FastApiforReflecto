
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="ESP32 Cam WebsocketStream")

app.add_middleware(
    CORSMiddleware,
    allow_origins= {'*'}, #adresse du frontend
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
# Liste pour stocker les clients (navigateurs) connectés
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: bytes):
        for connection in self.active_connections:
            await connection.send_bytes(message)

manager = ConnectionManager()

# Endpoint où l'ESP32 envoie ses images
@app.websocket("/ws/esp32")
async def websocket_esp32(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Reçoit l'image brute de l'ESP32
            data = await websocket.receive_bytes()
            # La renvoie à tous les navigateurs ouverts
            await manager.broadcast(data)
    except WebSocketDisconnect:
        print("ESP32 déconnecté")

# Endpoint pour les navigateurs (Visualisation)
@app.websocket("/ws/client")
async def websocket_client(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Maintient la connexion
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Page HTML simple pour voir le stream
@app.get("/")
async def get():
    return HTMLResponse("""
    <html>
        <body>
            <h1>Stream ESP32-CAM</h1>
            <img id="stream" src="" style="width: 100%; max-width: 640px;">
            <script>
                const img = document.getElementById('stream');
                // Remplace par ton URL Render (ex: ws://ton-app.render.com/ws/client)
                const ws = new WebSocket('ws://' + window.location.host + '/ws/client');
                ws.onmessage = function(event) {
                    const url = URL.createObjectURL(event.data);
                    img.src = url;
                    // Libère la mémoire après le chargement de l'image
                    img.onload = () => URL.revokeObjectURL(url);
                };
            </script>
        </body>
    </html>
    """)
