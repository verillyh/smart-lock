import os
import pickle
import threading
import queue
import time
import numpy as np
import cv2
import face_recognition
from imutils import paths

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

class FaceRecognizer:
    def __init__(self, serial_transport, cv_scaler=5):
        # Load face data
        with open("encodings.pickle", "rb") as f:
            data = pickle.loads(f.read())
        self.known_face_encodings = data["encodings"]
        self.known_face_names = data["names"]
        self.scaler = cv_scaler

        self.detected = False
        self.serial_transport = serial_transport

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

    def _detect_faces_from_frame(self, frame):
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
                self.detected = True
                # Send unlocking signal to arduino
                print("[INFO] Unlocking door...")
                self.serial_transport.write(b"unlock\n") 
                return

    # Process frames in a background thread
    def _process_frames(self):
        while True:
            frame = self.frame_queue.get()
            if self.detected:
                continue
            self._detect_faces_from_frame(frame)

    # Callback function for each camera frame before encoding
    def _camera_callback(self, request):    
        # If already detected, skip processing
        if self.detected:
            return
        # Get frame
        frame = request.make_array("main")
        
        if not self.frame_queue.full():
            self.frame_queue.put(frame)

    def recognize_faces(self, duration=10, video_out_path="output.mp4"):
        # Reset detected flag
        self.detected = False

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
        return video_out_path

    
    def train_model(self, imagePaths):    
        # Get image folders
        print("[INFO] start processing faces...")
        imagePaths = list(paths.list_images(imagePaths))
        knownEncodings = []
        knownNames = []

        # Loop over the image paths
        for (i, imagePath) in enumerate(imagePaths):
            print(f"[INFO] processing image {i + 1}/{len(imagePaths)}")
            # Get person name from the image folder
            name = imagePath.split(os.path.sep)[-2]
            
            # Load the image and convert it from BGR to RGB
            image = cv2.imread(imagePath)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Get face encoding from the image
            boxes = face_recognition.face_locations(rgb, model="hog")
            encodings = face_recognition.face_encodings(rgb, boxes)
            
            for encoding in encodings:
                knownEncodings.append(encoding)
                knownNames.append(name)


        # Dump to pickle file
        print("[INFO] serializing encodings...")
        data = {"encodings": knownEncodings, "names": knownNames}
        with open("encodings.pickle", "wb") as f:
            f.write(pickle.dumps(data))

        print("[INFO] Training complete. Encodings saved to 'encodings.pickle'")
