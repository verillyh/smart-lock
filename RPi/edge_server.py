import asyncio
import socketio
import serial_asyncio
import numpy as np
from scipy.io.wavfile import write
from aiohttp import web
import aiohttp_cors
from datetime import datetime
import os
import pi_recognition

# Constants
SAMPLE_RATE = 8000
DURATION_SECONDS = 10 
# * 2 because sending 2 bytes per sample
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS * 2

# Globals
transport = None
fc = None

# TODO: Do database stuff

# ---------- Serial Protocol ----------
class SerialProtocol(asyncio.Protocol):
    def __init__(self):
        self.buffer = bytearray()
        self.state = "IDLE"
        self.audio_header = b"<SMART_LOCK_AUDIO>"
        self.motion_header = b"<SMART_LOCK_MOTION>"


    def connection_made(self, transport_obj):
        global transport, fc
        transport = transport_obj
        fc = pi_recognition.FaceRecognizer(transport)
        print("Connected to serial port")

    def data_received(self, data):
        # If data is motion detected, handle it here
        self.buffer.extend(data)

        while True:
            # Handle headers
            if self.state == "IDLE":
                # Check if we have a complete header
                if b"<" in self.buffer and b">" in self.buffer:
                    # If it's a motion header
                    if self.motion_header in self.buffer:
                        # Set state to MOTION
                        self.state = "MOTION"
                        # Remove the header from the buffer
                        self.buffer.clear()
                    # If it's an audio header
                    elif self.audio_header in self.buffer:
                        # If we have an audio header, set state to AUDIO
                        self.state = "AUDIO"
                        # Remove the header from the buffer
                        self.buffer.clear()
                    else:
                        # If we have an unknown header, clear the buffer
                        self.buffer.clear()
                        print("Unknown header, clearing buffer")
                # If we don't have a complete header, wait for more data
                else:
                    break

            # If we are in the MOTION state
            elif self.state == "MOTION":
                print("Motion detected")
                fc.recognize_faces()
                # Reset state to IDLE after handling motion
                self.state = "IDLE" 
                break
            
            # If we are in the AUDIO state, handle audio data
            elif self.state == "AUDIO":
                # Extend buffer with the new data
                # self.buffer.extend(data[len(self.audio_header):])
                print(f"Buffer size: {len(self.buffer)}/{TOTAL_SAMPLES}")
                # Process audio data when enough samples are received
                if len(self.buffer) >= TOTAL_SAMPLES:
                    # Send signal to arduino to stop sending audio data
                    transport.write(b"Audio STOP\n")
                    # Preprocess data as audio
                    samples = preprocess_audio(self.buffer[:TOTAL_SAMPLES])
                    # Save audio data to file
                    save_wav(samples)
                    # Reset buffer
                    self.buffer.clear()
                    # Reset state to IDLE after handling audio
                    self.state = "IDLE"
                break

# ---------- General Functions ----------
def preprocess_audio(data):
    print(len(data))
    samples = np.frombuffer(data, dtype="<u2")
    return (samples / 1023) * 2 - 1

def save_wav(samples):
    file_name = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio_array = np.array(samples[:TOTAL_SAMPLES], dtype=np.float32)
    write(file_name, SAMPLE_RATE, audio_array)
    print(f"Saved: {file_name}")


# ---------- Route Functions ----------
async def upload_file(request):
    reader = await request.multipart()
    # Get person name
    person_name_field = await reader.next()
    if (person_name_field.name == "personName"):
        person_name = await person_name_field.text()
    
    # Get image file
    image_field = await reader.next()
    
    # Make new directory for person if it doesn't exist
    # Then, save image to that person's directory
    if (image_field.name == "image"):
        registered_people = os.listdir("uploads")
        if person_name not in registered_people:
            os.mkdir(f"uploads/{person_name}")
            print(f"Created directory for {person_name}")
        
        with open(f"uploads/{person_name}/{image_field.filename}", 'wb') as f:
            while True:
                chunk = await image_field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
    
    # Print logs and train model
    print(f"Saved image for {person_name}: {image_field.filename}")
    print("Training model...")
    fc.train_model("uploads")   
    print("Model trained")
    return web.Response(text="File upload received")


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
# Setup routes
upload_route = app.router.add_post('/upload', upload_file)
cors.add(upload_route)
# Socket.IO server for real-time communication
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


# Setup serial asynchronously
async def setup_serial(app):
    loop = asyncio.get_event_loop()
    await serial_asyncio.create_serial_connection(
        loop, SerialProtocol, '/dev/ttyACM0', baudrate=230400   
    )

# On web server startup, setup serial connection
app.on_startup.append(setup_serial)


# Run the web server
if __name__ == '__main__':
    web.run_app(app, port=3000)