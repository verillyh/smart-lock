import os
import threading
import queue
import time
import numpy as np
import cv2
import face_recognition

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

# TODO: Add access log status. Add new entry regardless if a face was detected or not.

class FaceRecognizer:
    def __init__(self, serial_transport, db, cursor, cv_scaler=5):
        # Database variables
        self.db = db
        self.cursor = cursor

        # Load face data
        self.known_face_encodings = []
        self.known_face_names = []
        self._reload_embeddings()

        self.scaler = cv_scaler
        self.stop_detecting_faces = False
        self.serial_transport = serial_transport
        self.timestamp = None

        # Threading variables
        self.frame_queue = queue.Queue(maxsize=1)
        self.worker_thread = threading.Thread(target=self._process_frames, daemon=True)
        self.worker_thread.start()

        # Initialize camera
        self.picam2 = Picamera2()
        config = self.picam2.create_video_configuration(
            main={"format": "RGB888", "size": (1640, 1232)},
            controls={"FrameRate": 30}
        )
        self.picam2.configure(config)

    def _reload_embeddings(self):
        self.known_face_encodings = []
        self.known_face_names = []
        # SQL Query to get all person names and face embeddings
        self.cursor.execute("""
                            SELECT person.person_name, face_embedding.embedding_vector 
                            FROM person
                            JOIN face_embedding ON person.id = face_embedding.person_id
                            """)
        # Fetch all results
        # Store each person name and embeddings
        for name, blob in self.cursor.fetchall():
            embedding = np.frombuffer(blob, dtype=np.float64)
            self.known_face_encodings.append(embedding)
            self.known_face_names.append(name)

    def _detect_faces_from_frame(self, frame):
        # Check if there are any known faces
        if self.known_face_encodings == []:
            print("[INFO] No known faces found in database.")
            self.stop_detecting_faces = True
            return
        
        # Preprocess frame
        resized = cv2.resize(frame, (0, 0), fx=1/self.scaler, fy=1/self.scaler)

        # Get face encodings from current frame
        locations = face_recognition.face_locations(resized)
        encodings = face_recognition.face_encodings(resized, locations, model='large')
        # Loop over each face's encoding
        for encoding in encodings:
            # Check if the face matches any known faces
            matches = face_recognition.compare_faces(self.known_face_encodings, encoding)
            face_distances = face_recognition.face_distance(self.known_face_encodings, encoding)
            best_match_index = np.argmin(face_distances)

            # If a match is found, get the name of the person
            if matches[best_match_index]:
                name = self.known_face_names[best_match_index]
                print(f"[INFO] Authorized face detected: {name}")
                self.stop_detecting_faces = True
                # Send unlocking signal to arduino
                print("[INFO] Unlocking door...")
                self.serial_transport.write(b"unlock\n") 

                try: 
                    person_id = self.cursor.execute("SELECT id FROM person WHERE person_name = %s",
                                                    (name,)
                                                    )
                    person_id = self.cursor.fetchone()[0]
                    # Log access to the database
                    self.cursor.execute("INSERT INTO access_log (video_file, person_id, access_method) VALUES (%s, %s, 'face')", 
                                        (f"videos/video_{self.timestamp}.mp4", person_id)
                                        )
                    self.db.commit()
                    print("[INFO] Access logged successfully.")
                except Exception as e:
                    print(f"[ERROR] Failed to log access: {e}")
                    self.db.rollback()
                return

    # Process frames in a background thread
    def _process_frames(self):
        while True:
            # Get current frame from the queue
            frame = self.frame_queue.get()
            # If face is already detected, skip additional detection
            if self.stop_detecting_faces:
                continue
            self._detect_faces_from_frame(frame)

    # Callback function for each camera frame before encoding
    def _camera_callback(self, request):    
        # If already detected, skip processing
        if self.stop_detecting_faces:
            return
        # Get frame
        frame = request.make_array("main")
        
        if not self.frame_queue.full():
            self.frame_queue.put(frame)

    def recognize_faces(self, timestamp, duration=10):
        video_out_path = f"record_{timestamp}.mp4"
        self.timestamp = timestamp
        # Reset flags
        self.stop_detecting_faces = False

        # New encoder and output for video recording
        encoder = H264Encoder()
        output = FfmpegOutput(video_out_path)

        # Set callback for each camera frame
        self.picam2.post_callback = self._camera_callback
        
        # Start recording
        print("Starting recording...")
        self.picam2.start_recording(encoder, output)

        # Sleep for the specified duration
        time.sleep(duration)

        # Stop recording
        print("Stopping recording...")
        self.picam2.stop_recording()
        self.picam2.post_callback = None
        return video_out_path
    
    def process_faces(self, imagePath):    
        personName = imagePath.split(os.path.sep)[-2]
        filename = imagePath.split(os.path.sep)[-1]
        print(f"[INFO] start processing image: {filename}...")

        # Load the image and convert it from BGR to RGB
        image = cv2.imread(imagePath)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Get face encoding from the image
        boxes = face_recognition.face_locations(rgb, model="hog")
        encodings = face_recognition.face_encodings(rgb, boxes)
        
        # For each encoding, insert it into the database
        for encoding in encodings:
            try:
                # Check if the person already exists in the database
                self.cursor.execute("SELECT id FROM person WHERE person_name = %s", 
                                    (personName,)
                                    )
                result = self.cursor.fetchone()
                
                if result:
                    result = result[0]
                # If person doesn't exist yet, add new entry
                else:
                    print("[INFO] Person not found in database. Inserting new person...")
                    self.cursor.execute("INSERT INTO person (person_name) VALUES (%s)", 
                                        (personName,)
                                        )
                    print(f"[INFO] Person {personName} inserted.")
                    result = self.cursor.lastrowid    
                
                # Insert face embedding into the database
                print("[INFO] Inserting face embedding into database...")
                self.cursor.execute("INSERT INTO face_embedding (embedding_vector, file_path, person_id) VALUES (%s, %s, %s)",
                                    (encoding.tobytes(), imagePath, result)
                                    )

                self.db.commit()
            except Exception as e:
                print(f"[ERROR] Failed to insert into database: {e}")
                self.db.rollback()
                continue
        
        self._reload_embeddings()

