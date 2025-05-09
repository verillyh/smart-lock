import socketio
import serial
import threading
import numpy as np
from scipy.io.wavfile import write
from aiohttp import web
import aiohttp_cors
from datetime import datetime
import os
import subprocess
import pi_recognition
import database 

# Constants
SAMPLE_RATE = 8000
DURATION_SECONDS = 10
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS * 2

# Globals
fc = None
serial_writer = None
db, cursor = database.setup()

# ---------- Serial Thread ----------
class SerialReaderThread(threading.Thread):
    def __init__(self, port="/dev/ttyACM0", baudrate=230400):
        super().__init__(daemon=True)
        self.ser = serial.Serial(port, baudrate, timeout=0)
        # State variables
        self.state = "IDLE"
        self.buffer = bytearray()
        self.running = True
        self.timestamp = None
        # Data headers
        self.audio_header = b"<SMART_LOCK_AUDIO>"
        self.motion_header = b"<SMART_LOCK_MOTION>"

    def run(self):
        global serial_writer, fc
        # Save for socket.io access
        serial_writer = self.ser  
        fc = pi_recognition.FaceRecognizer(serial_writer, db, cursor)

        # While serial is alive...
        while self.running:
            try:
                # If there's data coming in, read, buffer, and handle it
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting)
                    self.buffer.extend(data)
                    self._handle_data()
            except Exception as e:
                print(f"[Serial Error] {e}")

    def _handle_data(self):
        # If current state is IDLE, check for data headers in incoming data
        if self.state == "IDLE":
            # Handle motion header
            if self.motion_header in self.buffer:
                print("[INFO] Motion detected")
                self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Start video recording and face recognition
                threading.Thread(target=fc.recognize_faces, kwargs={"timestamp": self.timestamp}, daemon=True).start()
                # Start audio recording
                self.ser.write(b"Audio START\n")
                # Clear buffer and set state to AUDIO
                self.buffer.clear()
                self.state = "AUDIO"

            # Handle audio header
            elif self.audio_header in self.buffer:
                print("[INFO] Audio header received")
                self.buffer.clear()
                self.state = "AUDIO"

        # If state is AUDIO, check for handle audio data
        elif self.state == "AUDIO":
            # If enough data is received, process it
            if len(self.buffer) >= TOTAL_SAMPLES:
                print("[INFO] Audio samples complete. Saving...")
                # Signal arduino to stop recording
                self.ser.write(b"Audio STOP\n")
                # Preprocess samples
                samples = preprocess_audio(self.buffer[:TOTAL_SAMPLES])
                # Save audio to WAV file
                save_wav(samples, self.timestamp)
                # Stitch audio and video together
                stitch_audio_video(self.timestamp)
                # Reset
                self.buffer.clear()
                self.state = "IDLE"

    def stop(self):
        self.running = False
        self.ser.close()


# ---------- General Functions ----------
def preprocess_audio(data):
    # Convert byte data to numpy array and normalize to [-1, 1]
    samples = np.frombuffer(data, dtype="<u2")
    return (samples / 1023) * 2 - 1

def save_wav(samples, timestamp):
    file_name = f"audio_{timestamp}.wav"
    audio_array = np.array(samples[:TOTAL_SAMPLES], dtype=np.float32)
    write(file_name, SAMPLE_RATE, audio_array)

def stitch_audio_video(timestamp):
    video = f"record_{timestamp}.mp4"
    audio = f"audio_{timestamp}.wav"
    output = f"videos/video_{timestamp}.mp4"

    command = [
        "ffmpeg",
        "-y",
        "-i", video,
        "-i", audio,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-hide_banner",
        "-loglevel", "panic",
        output,
        ]

    try:
        print("[INFO] Stitching audio and video...")
        # Produce video with audio
        subprocess.run(command, check=True)
        # Remove video file
        subprocess.run(["rm", f"record_{timestamp}.mp4"])
        # Remove audio file
        subprocess.run(["rm", f"audio_{timestamp}.wav"])
        print(f"[INFO] Stitching complete. Saved to {output}")
    except Exception as e:
        print(e) 

def get_access_logs():
    try:
        cursor.execute("""
                    SELECT 
                        DATE(access_time) AS access_date,
                        SUM(access_method = 'face') AS face_count,
                        SUM(access_method = 'remote') AS remote_count
                    FROM access_log
                    GROUP BY access_date
                    ORDER BY access_date;                       
                """)
        results = cursor.fetchall()
        logs = []
        for result in results:
            access_date = result[0].strftime('%d/%m/%Y')
            
            logs.append({
                "date": access_date,
                "face_count": int(result[1]),
                "web_count": int(result[2])
            })
        
        return logs
    except Exception as e:
        print(f"[ERROR] Failed to fetch access logs: {e}")
        return []        

# ---------- Route Functions ----------
async def upload_file(request):
    # Get reader
    reader = await request.multipart()

    # Get person name
    person_name_field = await reader.next()
    if (person_name_field.name == "personName"):
        person_name = await person_name_field.text()
    
    # Get image field
    image_field = await reader.next()
    
    if (image_field.name == "image"):
        # If a directory has not been made for the person, create one
        registered_people = os.listdir("uploads")
        if person_name not in registered_people:
            os.mkdir(f"uploads/{person_name}")
            print(f"Created directory for {person_name}")
        
        # Save the image to the person's directory
        with open(f"uploads/{person_name}/{image_field.filename}", 'wb') as f:
            while True:
                chunk = await image_field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
    
    print(f"Saved image for {person_name}: {image_field.filename}")
    print("Training model...")
    # Train model with the whole uploads directory
    fc.process_faces(f"uploads/{person_name}/{image_field.filename}")   
    print("Model trained")
    return web.Response(text="File upload received")


# ---------- Web Server Setup ----------
app = web.Application()
# Setup CORS
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    )
})
# Routes
upload_route = app.router.add_post('/upload', upload_file)
cors.add(upload_route)
# Socket.IO for real-time communication
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
sio.attach(app)


# ---------- Socket.IO ----------
@sio.event
async def connect(sid, environ):
    print(f"Socket connected: {sid}")

@sio.on("unlock")
async def on_unlock(sid, unlock):
    global serial_writer
    if serial_writer:
        command = b"unlock\n" if unlock else b"lock\n"
        try:
            serial_writer.write(command)
            print(f"[INFO] Unlock command sent: {command.decode()}")
        except Exception as e:
            print(f"[Serial Write Error] {e}")

        try: 
            print("[INFO] Inserting access log into database...")
            cursor.execute("INSERT INTO access_log (access_method) VALUES ('remote')")
            db.commit()
        except Exception as e:
            print(f"[ERROR] Failed to log access: {e}")
            db.rollback()
    else:
        print("Serial not ready")

@sio.on("refresh")
async def refresh(sid):
    logs = get_access_logs()
    await sio.emit("access_logs", logs)
    print(f"[INFO] Access logs sent to {sid}")


# ---------- Startup Serial Thread ----------
def start_serial_thread():
    serial_thread = SerialReaderThread("/dev/ttyACM0", 230400)
    serial_thread.start()
    return serial_thread


# ---------- Run App ----------
if __name__ == '__main__':
    serial_thread = start_serial_thread()
    try:
        web.run_app(app, port=3000)
    finally:
        serial_thread.stop()