import os
import time
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= {'*'},
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

latest_image_bytes = None


def get_placeholder_bytes():
    """Charge l'image placeholder ou en crée une grise par défaut."""
    try:
        with open("placeholder.jpg", "rb") as f:
            return f.read()
    except Exception:
        img = Image.new('RGB', (320, 240), color='gray')
        buf = BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()


latest_image_bytes = get_placeholder_bytes()


def is_valid_image(image_bytes):
    try:
        Image.open(BytesIO(image_bytes))
        return True
    except UnidentifiedImageError:
        print("image invalid")
        return False


@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    global latest_image_bytes
    await websocket.accept()
    print("ESP32 connected!")
    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
            elif "text" in message and message["text"]:
                data = message["text"].encode('utf-8')
            else:
                continue

            if len(data) > 5000 and is_valid_image(data):
                latest_image_bytes = data

    except WebSocketDisconnect:
        print("ESP32 disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


def generate_frames():
    global latest_image_bytes
    last_sent = None
    while True:
        frame_data = latest_image_bytes if latest_image_bytes else get_placeholder_bytes()

        if frame_data is last_sent:
            time.sleep(0.02)
            continue
        last_sent = frame_data

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + f"{len(frame_data)}".encode() + b'\r\n\r\n' +
               frame_data + b'\r\n')


@app.get("/")
def index():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
