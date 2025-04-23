import asyncio
import socketio
import serial_asyncio
import numpy as np
from scipy.io.wavfile import write
from aiohttp import web
import aiohttp_cors
from datetime import datetime

# Constants
SAMPLE_RATE = 8000
DURATION_SECONDS = 20
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS

# Globals
record = False
transport = None

# TODO: Do database stuff

# ---------- Serial Protocol ----------
class SerialProtocol(asyncio.Protocol):
    def connection_made(self, transport_obj):
        global transport
        transport = transport_obj
        print("Connected to serial port")

    def data_received(self, data):
        if len(data) < 2:
            return
        
        # When data is received
        # Assume it is an audio data
        # Preprocess data as audio
        samples = preprocess_audio(data)
        if samples is not None:
            print(f"Buffer size: {len(samples)}/{TOTAL_SAMPLES}")
            if len(samples) >= TOTAL_SAMPLES:
                save_wav(samples)


# ---------- General Functions ----------
async def start_serial():
    loop = asyncio.get_running_loop()
    await serial_asyncio.create_serial_connection(
        loop, lambda: SerialProtocol, 'COM6', baudrate=230400
    )

async def upload_file(request):
    # Handle file upload here
    reader = await request.multipart()
    field = await reader.next()

    if(field.name == "image"):
        filename = field.filename
        print(filename)

    with open(filename, 'wb') as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)
    return web.Response(text="File upload received")

def preprocess_audio(data):
    samples = np.frombuffer(data, dtype="<u2")
    if len(samples) == 0:
        return None
    return (samples / 1023) * 2 - 1

def save_wav(samples):
    file_name = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio_array = np.array(samples[:TOTAL_SAMPLES], dtype=np.float32)
    write(file_name, SAMPLE_RATE, audio_array)
    print(f"Saved: {file_name}")


# ---------- Setup Servers ----------
# Create web server
app = web.Application()
# Setup CORS
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    )
})
upload_route = app.router.add_post('/upload', upload_file)
cors.add(upload_route)
# Socket.IO server (async mode)
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
sio.attach(app)


# ---------- Socket IO ----------
@sio.event
async def connect(sid, environ):
    print(f"Connected: {sid}")

@sio.on("unlock")
async def on_unlock(sid, unlock):
    global transport
    send = "unlock" if unlock else "lock"
    if transport:
        try:
            transport.write(send.encode())
            print(f"Message sent: {send}")
        except Exception as e:
            print(f"Error on write: {e}")
    else:
        print("Transport not initialized")

# Black box
@sio.on("record")
async def on_record(sid, should_record):
    global record
    record = should_record
    # if should_record:
    #     buffer.clear()
    print(f"Recording {'started' if should_record else 'stopped'}")



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_serial())
    web.run_app(app, port=3000)
