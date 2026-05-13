from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time

app = FastAPI(title="ESP32-CAM Stream")

latest_frame = None
frame_lock = asyncio.Lock()
frame_count = 0

app.add_middleware(
    CORSMiddleware,
    allow_origins= {'*'}, #adresse du frontend
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

@app.post("/upload_frame")
async def upload_frame(request: Request):
    global latest_frame, frame_count
   
    content = await request.body()
   
    if len(content) < 1000:
        return {"status": "error", "message": "Image trop petite"}
   
    async with frame_lock:
        latest_frame = content
        frame_count += 1
   
    print(f"✅ Frame reçu | Taille: {len(content)} octets | Total: {frame_count}")
    return {"status": "success", "size": len(content), "count": frame_count}


async def mjpeg_generator():
    global latest_frame
    while True:
        async with frame_lock:
            if latest_frame is None:
                await asyncio.sleep(0.1)
                continue
            frame = latest_frame
       
        yield b"--frame\r\n"
        yield b"Content-Type: image/jpeg\r\n"
        yield f"Content-Length: {len(frame)}\r\n\r\n".encode()
        yield frame
        yield b"\r\n"
       
        await asyncio.sleep(0.05)


@app.get("/stream")
async def video_stream():
    return StreamingResponse(mjpeg_generator(),
                           media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/snapshot")
async def snapshot():
    async with frame_lock:
        if latest_frame is None:
            return {"message": "Aucune image reçue"}
        return Response(content=latest_frame, media_type="image/jpeg")


@app.get("/status")
async def status():
    async with frame_lock:
        return {
            "frames_received": frame_count,
            "has_image": latest_frame is not None,
            "image_size": len(latest_frame) if latest_frame else 0
        }


@app.get("/")
async def home():
    return """
    <h1>ESP32-CAM Stream</h1>
    <p><a href="/status" target="_blank">Status</a></p>
    <p><a href="/snapshot" target="_blank">Snapshot</a></p>
    <img src="/stream" style="max-width: 100%; border: 2px solid #333;"/>
    """
