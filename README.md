# Smart Lock
This project is a web based smart lock with facial recognition, web unlock, and footage recording abilities. The hardware consists of:
-	Arduino Uno R3
-	M-M USB A to USB B
-	Raspberry Pi 4 8Gb
-	Power supply for Raspberry Pi 4
-	IMX219 Camera for Raspberry Pi 4
-	SG90 Servo
-	LM393 Sound sensor module
-	HC-SR501 PIR motion sensor
-	Breadboard
-	LED
-	12 jumper wires
-	1 resistor 10k Ohm
-	1 resistor 220 Ohm

To run the web server, perform the following commands:
1. `cd web-server`
2. `npm install`
3. `npm run dev`

To run the Raspberry Pi server, transfer all the files inside RPi and execute:
`python edge_server.py`

Before running the program, make sure all hardware is connected and the Arduino file is uploaded to the Arduino.

The Arduino code can be found in the arduino_assignment_2 folder.