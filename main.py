import asyncio
import os
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

app = FastAPI()

# Variable globale pour stocker la dernière image valide en mémoire (ou sur disque)
# Utiliser un verrou ou une simple variable suffit ici.
latest_image_bytes = None

import time

def get_placeholder_bytes():
    """Charge l'image placeholder ou en crée une grise par défaut."""
    try:
        with open("placeholder.jpg", "rb") as f:
            return f.read()
    except Exception:
        # Création de secours d'une image valide si placeholder.jpg manque
        img = Image.new('RGB', (320, 240), color='gray')
        buf = BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()

# Initialisation propre
latest_image_bytes = get_placeholder_bytes()

def is_valid_image(image_bytes):
    try:
        Image.open(BytesIO(image_bytes))
        return True
    except UnidentifiedImageError:
        print("image invalid")
        return False

# --- 1. ROUTE WEBSOCKET (Remplace receive_stream.py) ---
@app.websocket("/") # ou "/ws" selon ce que vous avez choisi
async def websocket_endpoint(websocket: WebSocket):
    global latest_image_bytes
    await websocket.accept()
    print("ESP32 connected!")
    try:
        while True:
            # On récupère le message sous forme brute (message de type dict ou objet selon FastAPI)
            message = await websocket.receive()
            
            # FastAPI/Starlette renvoie un dict avec 'bytes' ou 'text'
            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
            elif "text" in message and message["text"]:
                # Si l'ESP32 envoie du texte par erreur ou encodé
                data = message["text"].encode('utf-8')
            else:
                continue

            print(f"Received data length: {len(data)}")
            
            if len(data) > 5000 and is_valid_image(data):
                latest_image_bytes = data
                with open("image.jpg", "wb") as f:
                    f.write(data)
                print("image.jpg updated")
                
    except WebSocketDisconnect:
        print("ESP32 disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

# --- 2. ROUTE HTTP STREAMING (Remplace send_image_stream.py) ---
def generate_frames():
    global latest_image_bytes
    while True:
        try:
            # S'assurer qu'on a bien des octets valides
            frame_data = latest_image_bytes if latest_image_bytes else get_placeholder_bytes()
            
            # Valider et réencoder proprement l'image en JPEG via Pillow
            image = Image.open(BytesIO(frame_data))
            img_io = BytesIO()
            image.save(img_io, 'JPEG', quality=80)
            img_bytes = img_io.getvalue()
            
            # Envoi du chunk au format MJPEG standard
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + f"{len(img_bytes)}".encode() + b'\r\n\r\n' + 
                   img_bytes + b'\r\n')
        except Exception as e:
            print(f"Stream error: {e}")
            time.sleep(0.1)
            
        # Contrôle du taux de rafraîchissement (~20-25 images par seconde)
        time.sleep(0.04)

@app.get("/")
def index():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# Pour lancer localement si besoin (sur Render, c'est Uvicorn qui gère)
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
